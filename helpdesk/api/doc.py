import frappe
from frappe import _
from frappe.desk.form.assign_to import set_status
from frappe.model import no_value_fields
from frappe.model.document import get_controller
from frappe.utils.caching import redis_cache
from pypika import Criterion

from helpdesk.api.dashboard import COUNT_NAME
from helpdesk.utils import (
    call_log_default_columns,
    check_permissions,
    contact_default_columns,
    contact_default_rows,
    parse_call_logs,
)


@frappe.whitelist()
def get_list_data(
    doctype: str,
    # flake8: noqa
    filters: dict | list = {},
    default_filters: dict = {},
    order_by: str = "modified desc",
    page_length: int = 20,
    columns: list = [],
    rows: list = [],
    show_customer_portal_fields: bool = False,
    view: dict | None = None,
    is_default: bool = False,
) -> dict:
    is_custom = False

    rows = frappe.parse_json(rows or "[]")
    columns = frappe.parse_json(columns or "[]")
    filters = frappe.parse_json(filters or "[]")

    view_type = view.get("view_type") if view else None
    view_name = view.get("name") if view else None

    group_by_field = view.get("group_by_field") if view else None
    label_doc = view.get("label_doc") if view else None
    label_field = view.get("label_field") if view else None

    handle_at_me_support(filters)
    handle_assigned_on_filter(filters, doctype)

    _list = get_controller(doctype)
    default_rows = []
    if hasattr(_list, "default_list_data"):
        default_rows = _list.default_list_data().get("rows")

    if columns or rows:
        is_default = False
        is_custom = True
        columns = frappe.parse_json(columns)
        rows = frappe.parse_json(rows)

    if not columns:
        columns = [
            {"label": "Name", "type": "Data", "key": "name", "width": "16rem"},
            {
                "label": "Last Modified",
                "type": "Datetime",
                "key": "modified",
                "width": "8rem",
            },
        ]

    if not rows:
        rows = ["name"]

    # flake8: noqa
    if is_default:
        default_view = default_view_exists(doctype)
        if not default_view:
            if doctype == "Contact":
                columns = contact_default_columns
                rows = contact_default_rows
            elif doctype == "TP Call Log":
                columns = call_log_default_columns
            elif hasattr(_list, "default_list_data"):
                columns = (
                    _list.default_list_data(show_customer_portal_fields).get("columns")
                    if doctype == "HD Ticket"
                    else _list.default_list_data().get("columns")
                )
                rows = default_rows
        else:
            [columns, rows] = handle_default_view(
                doctype, _list, show_customer_portal_fields
            )
            if default_filters and not filters:
                default_filters = frappe.parse_json(default_filters)
                for key, value in (default_filters or {}).items():
                    if isinstance(value, list):
                        filters.append([key, value[0], value[1]])
                    else:
                        filters.append([key, "=", value])

    if rows is None:
        rows = []

    # check if rows has all keys from columns if not add them
    for column in columns:
        if column.get("key") not in rows:
            rows.append(column.get("key"))

    if group_by_field and group_by_field not in rows:
        rows.append(group_by_field)

    rows.append("name") if "name" not in rows else rows
    if doctype == "HD Ticket":
        rows.append("_seen") if "_seen" not in rows else rows
        # PYEK: fields the Outlook-style agent list row renders (requester, park
        # strip, SLA, preview snippet, date). Force-appended so they're present
        # under any saved view, mirroring the _seen append above. Agent portal
        # only — don't push internal fields into the customer portal payload.
        if not show_customer_portal_fields:
            for _pyek_field in (
                "raised_by",
                "contact",
                "subject",
                "status",
                "priority",
                "agent_group",
                "agreement_status",
                "status_category",
                "pyek_property",
                "pyek_requested_due_date",
                "description",
                "modified",
                "creation",
            ):
                if _pyek_field not in rows:
                    rows.append(_pyek_field)
            # PYEK-AP: invoice fields the AP-instance list row renders (vendor,
            # amount, doc-type, invoice #, and the missing/duplicate flags). Guarded
            # by has_field so the IT/HR sites — which don't have these columns —
            # never query them (an unknown column would 500 the whole list). The
            # frontend keys the AP row layout off the presence of these keys.
            if frappe.get_meta("HD Ticket").has_field("ap_vendor"):
                for _ap_field in (
                    "ap_vendor",
                    "ap_amount",
                    "ap_doc_type",
                    "ap_invoice_number",
                    "ap_missing_invoice",
                    "ap_duplicate",
                ):
                    if _ap_field not in rows:
                        rows.append(_ap_field)
    # PYEK: two-tier ordering for the agent ticket list — float tickets that are
    # due soon (overdue / today / within the next 7 days, by pyek_requested_due_date)
    # to the TOP so agents can prioritise by due date, then fall back to the
    # requested order for everything else. Agent portal, non-group-by only. The
    # frontend paginates by growing page_length from the top (no offset), so a
    # top-down order is sufficient. A `<=` date filter excludes NULLs, so the two
    # buckets are disjoint (no dedup needed).
    _pyek_due_sort = (
        doctype == "HD Ticket"
        and not show_customer_portal_fields
        and view_type != "group_by"
    )
    if _pyek_due_sort:
        from frappe.utils import add_days, today

        _cutoff = add_days(today(), 7)

        # Normalise incoming filters to a list of [field, op, value] conditions
        # so we can safely append the due-date bounds (a dict can't hold two
        # conditions on the same field).
        if isinstance(filters, dict):
            _base = []
            for _k, _v in filters.items():
                if isinstance(_v, (list, tuple)) and len(_v) == 2:
                    _base.append([_k, _v[0], _v[1]])
                else:
                    _base.append([_k, "=", _v])
        else:
            _base = list(filters)

        # IMPORTANT: frappe's `<=` on a nullable Date INCLUDES NULL rows, so the
        # due-soon bucket MUST also require the field is set — otherwise every
        # no-due ticket falls into it and (since NULLs sort first on `asc`)
        # buries the real due dates at the top. Verified against the live data.
        _due_soon = (
            frappe.get_list(
                doctype,
                fields=rows,
                filters=_base
                + [
                    ["pyek_requested_due_date", "is", "set"],
                    ["pyek_requested_due_date", "<=", _cutoff],
                ],
                order_by="pyek_requested_due_date asc",
                page_length=page_length,
            )
            or []
        )
        # Everything else (no due date, or due beyond the cutoff), in the
        # requested order. Disjoint from the due-soon bucket.
        _rest = (
            frappe.get_list(
                doctype,
                fields=rows,
                filters=_base,
                or_filters=[
                    ["pyek_requested_due_date", "is", "not set"],
                    ["pyek_requested_due_date", ">", _cutoff],
                ],
                order_by=order_by,
                page_length=page_length,
            )
            or []
        )
        data = (_due_soon + _rest)[:page_length]
    else:
        data = (
            frappe.get_list(
                doctype,
                fields=rows,
                filters=filters,
                order_by=order_by,
                page_length=page_length,
            )
            or []
        )

    if doctype == "TP Call Log":
        data = parse_call_logs(data)

    # PYEK: attach the latest email in each ticket's thread as `_last_message`
    # so the agent list preview shows the most recent reply (Outlook-style), not
    # the original description. Falls back to the description when a ticket has
    # no email communications yet (e.g. portal/Wrike-created). Agent portal only.
    if doctype == "HD Ticket" and not show_customer_portal_fields and data:
        import re

        from frappe.utils import strip_html_tags

        # Outlook / HTML emails embed <style>/<script>/<head> blocks (and MSO
        # conditional comments) whose TEXT survives strip_html_tags — that's the
        # "v\:* {behavior:url(#default#VML)} …" junk that was leaking into the
        # preview. Drop those blocks + comments before stripping the tags.
        _noise_re = re.compile(
            r"<(style|script|head)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL
        )

        def _preview(_html):
            _html = _noise_re.sub(" ", _html or "")
            _html = re.sub(r"<!--.*?-->", " ", _html, flags=re.DOTALL)
            return " ".join(strip_html_tags(_html).split())[:200]

        _names = [d.get("name") for d in data if d.get("name")]
        if _names:
            _comms = frappe.get_all(
                "Communication",
                filters={
                    "reference_doctype": "HD Ticket",
                    "reference_name": ["in", _names],
                    "communication_type": "Communication",
                },
                fields=["reference_name", "content"],
                order_by="creation desc",
            )
            _latest = {}
            for _c in _comms:
                _rn = _c.get("reference_name")
                if _rn and _rn not in _latest:
                    _latest[_rn] = _c.get("content")
            for _d in data:
                _html = _latest.get(_d.get("name")) or _d.get("description") or ""
                _d["_last_message"] = _preview(_html)

    fields = frappe.get_meta(doctype).fields
    fields = [field for field in fields if field.fieldtype not in no_value_fields]
    fields = [
        {
            "label": field.label,
            "type": field.fieldtype,
            "value": field.fieldname,
            "options": field.options,
        }
        for field in fields
        if field.label and field.fieldname
    ]

    std_fields = [
        {"label": "Name", "type": "Data", "value": "name"},
        {"label": "Created On", "type": "Datetime", "value": "creation"},
        {"label": "Last Modified", "type": "Datetime", "value": "modified"},
        {
            "label": "Modified By",
            "type": "Link",
            "value": "modified_by",
            "options": "User",
        },
        {"label": "Assigned To", "type": "Text", "value": "_assign"},
        {"label": "Owner", "type": "Link", "value": "owner", "options": "User"},
    ]

    for field in std_fields:
        if field.get("value") not in rows:
            rows.append(field.get("value"))
        if field not in fields:
            fields.append(field)

    if show_customer_portal_fields:
        fields = get_customer_portal_fields(doctype, fields)

    if group_by_field and view_type == "group_by":

        def get_options(fieldtype, options):
            if fieldtype == "Select":
                return [option for option in options.split("\n")]
            else:
                has_empty_values = any([not d.get(group_by_field) for d in data])
                options = list(set([d.get(group_by_field) for d in data]))
                options = [u for u in options if u]
                options = [category_name for category_name in options if category_name]
                options = [
                    {
                        "label": frappe.db.get_value(
                            label_doc if label_doc else doctype,
                            option,
                            label_field if label_field else group_by_field,
                        ),
                        "value": option,
                    }
                    for option in options
                    if option
                ]
                if has_empty_values:
                    options.append({"label": "", "value": ""})

                if order_by and group_by_field in order_by:
                    order_by_fields = order_by.split(",")
                    order_by_fields = [
                        (field.split(" ")[0], field.split(" ")[1])
                        for field in order_by_fields
                    ]
                    if (group_by_field, "asc") in order_by_fields:
                        options.sort(key=lambda x: x.get("label"))
                    elif (group_by_field, "desc") in order_by_fields:
                        options.sort(reverse=True, key=lambda x: x.get("label"))
                else:
                    options.sort(key=lambda x: x.get("label"))

                # general category at first position
                idx = [
                    idx for idx, o in enumerate(options) if o.get("label") == "General"
                ]
                if len(idx) == 0:
                    return options

                idx = idx[0]
                default_category = options[idx]
                options.pop(idx)
                options.insert(0, default_category)
                return options

        for field in fields:
            if field.get("value") == group_by_field:
                options = get_options(field.get("type"), field.get("options"))
                group_by_field = {
                    "label": field.get("label"),
                    "name": field.get("value"),
                    "type": field.get("type"),
                    "options": options,
                }

    return {
        "data": data,
        "columns": columns,
        "rows": rows,
        "fields": fields if doctype == "HD Ticket" else [],
        "total_count": frappe.get_list(doctype, fields=[COUNT_NAME], filters=filters)[
            0
        ].get("count", 0),
        "row_count": len(data),
        "group_by_field": group_by_field,
        "view_type": view_type,
    }


@frappe.whitelist()
@redis_cache()
def get_filterable_fields(
    doctype: str,
    show_customer_portal_fields: bool = False,
    ignore_team_restrictions: bool = False,
):
    check_permissions(doctype, None)
    QBDocField = frappe.qb.DocType("DocField")
    QBCustomField = frappe.qb.DocType("Custom Field")
    allowed_fieldtypes = [
        "Check",
        "Data",
        "Float",
        "Int",
        "Link",
        "Long Text",
        "Select",
        "Small Text",
        "Text Editor",
        "Text",
        "Rating",
        "Duration",
        "Date",
        "Datetime",
    ]

    visible_custom_fields = get_visible_custom_fields()
    customer_portal_fields = [
        "name",
        "subject",
        "status",
        "priority",
        "response_by",
        "resolution_by",
        "creation",
        "customer",
    ]

    from_doc_fields = (
        frappe.qb.from_(QBDocField)
        .select(
            QBDocField.fieldname,
            QBDocField.fieldtype,
            QBDocField.label,
            QBDocField.name,
            QBDocField.options,
        )
        .where(QBDocField.parent == doctype)
        .where(QBDocField.hidden == False)
        .where(Criterion.any([QBDocField.fieldtype == i for i in allowed_fieldtypes]))
    )

    from_custom_fields = (
        frappe.qb.from_(QBCustomField)
        .select(
            QBCustomField.fieldname,
            QBCustomField.fieldtype,
            QBCustomField.label,
            QBCustomField.name,
            QBCustomField.options,
        )
        .where(QBCustomField.dt == doctype)
        .where(QBCustomField.hidden == False)
        .where(
            Criterion.any([QBCustomField.fieldtype == i for i in allowed_fieldtypes])
        )
    )

    # for customer portal show only fields present in customer_portal_fields
    if show_customer_portal_fields:
        from_doc_fields = from_doc_fields.where(
            QBDocField.fieldname.isin(customer_portal_fields)
        )
        if len(visible_custom_fields) > 0:
            from_custom_fields = from_custom_fields.where(
                QBCustomField.fieldname.isin(visible_custom_fields)
            )
            from_custom_fields = from_custom_fields.run(as_dict=True)
        else:
            from_custom_fields = []

    if not show_customer_portal_fields:
        from_custom_fields = from_custom_fields.run(as_dict=True)

    from_doc_fields = from_doc_fields.run(as_dict=True)
    # from hd ticket template get children with fieldname and hidden_from_customer

    res = []
    res.extend(from_doc_fields)
    # TODO: Ritvik => till a better way we have for custom fields, just show custom fields

    res.extend(from_custom_fields)
    if not show_customer_portal_fields and doctype == "HD Ticket":
        res.append(
            {
                "fieldname": "_assign",
                "fieldtype": "Link",
                "label": "Assigned to",
                "name": "_assign",
                "options": "HD Agent",
            }
        )

    if not ignore_team_restrictions:
        enable_restrictions = frappe.db.get_single_value(
            "HD Settings", "restrict_tickets_by_agent_group"
        )
        if enable_restrictions and doctype == "HD Ticket":
            res = [r for r in res if r.get("fieldname") != "agent_group"]

    standard_fields = [
        {"fieldname": "name", "fieldtype": "Link", "label": "ID", "options": doctype},
        {
            "fieldname": "owner",
            "fieldtype": "Link",
            "label": "Created By",
            "options": "User",
        },
        {
            "fieldname": "modified_by",
            "fieldtype": "Link",
            "label": "Last Updated By",
            "options": "User",
        },
        {"fieldname": "creation", "fieldtype": "Datetime", "label": "Created On"},
        {"fieldname": "modified", "fieldtype": "Datetime", "label": "Last Updated On"},
        {
            "fieldname": "__assigned_on",
            "fieldtype": "Date",
            "label": "Assigned on",
            "name": "__assigned_on",
        },
    ]
    for field in standard_fields:
        if field.get("fieldname") not in [r.get("fieldname") for r in res]:
            res.append(field)
    return res


@frappe.whitelist()
def sort_options(doctype: str, show_customer_portal_fields: bool = False):
    fields = frappe.get_meta(doctype).fields
    fields = [field for field in fields if field.fieldtype not in no_value_fields]
    fields = [
        {
            "label": field.label,
            "value": field.fieldname,
        }
        for field in fields
        if field.label and field.fieldname
    ]

    if show_customer_portal_fields:
        fields = get_customer_portal_fields(doctype, fields)

    standard_fields = [
        {"label": "Name", "value": "name"},
        {"label": "Created On", "value": "creation"},
        {"label": "Last Modified", "value": "modified"},
        {"label": "Modified By", "value": "modified_by"},
        {"label": "Owner", "value": "owner"},
    ]

    fields.extend(standard_fields)

    return fields


@frappe.whitelist()
def get_quick_filters(doctype: str, show_customer_portal_fields: bool = False):
    meta = frappe.get_meta(doctype)
    fields = [field for field in meta.fields if field.in_standard_filter]
    quick_filters = []
    name_filter = {"label": "ID", "name": "name", "type": "Data"}
    if doctype == "Contact":
        quick_filters.append(name_filter)
        return quick_filters
    elif doctype == "TP Call Log":
        quick_filters.append(name_filter)
        return quick_filters
    name_filter_doctypes = ["HD Agent", "HD Customer", "HD Ticket"]
    if doctype in name_filter_doctypes:
        quick_filters.append(name_filter)

    for field in fields:
        options = []
        if field.fieldtype == "Select":
            options = field.options.split("\n")
            options = [{"label": option, "value": option} for option in options]
            options.insert(0, {"label": "", "value": ""})

        if field.fieldtype == "Link":
            options = field.options

        quick_filters.append(
            {
                "label": _(field.label),
                "name": field.fieldname,
                "type": field.fieldtype,
                "options": options,
            }
        )

    if doctype != "HD Ticket":
        return quick_filters

    _list = get_controller(doctype)
    if hasattr(_list, "filter_standard_fields") and show_customer_portal_fields:
        # to filter out more fields from customer remember to update customer_not_allowed_fields in hd_ticket.py
        quick_filters = _list.filter_standard_fields(quick_filters)

    return quick_filters


def get_customer_portal_fields(doctype, fields):
    visible_custom_fields = get_visible_custom_fields()
    customer_portal_fields = [
        "name",
        "subject",
        "status",
        "priority",
        "response_by",
        "resolution_by",
        "creation",
        *visible_custom_fields,
    ]
    fields = [field for field in fields if field.get("value") in customer_portal_fields]
    return fields


def get_visible_custom_fields():
    return frappe.db.get_all(
        "HD Ticket Template Field",
        {"parent": "Default", "hide_from_customer": 0},
        pluck="fieldname",
    )


def default_view_exists(doctype):
    return frappe.db.exists(
        "HD View",
        {
            "is_default": 1,
            "user": frappe.session.user,
            "dt": doctype,
        },
    )


def handle_default_view(doctype, _list, show_customer_portal_fields):
    [columns, rows] = frappe.get_value(
        "HD View",
        {
            "is_default": 1,
            "user": frappe.session.user,
            "dt": doctype,
        },
        ["columns", "rows"],
    )
    columns = frappe.parse_json(columns)
    rows = frappe.parse_json(rows)

    if not columns:
        if doctype == "Contact":
            columns = contact_default_columns
            rows = ["name", "email_id", "mobile_no", "image", "creation"]
        elif doctype == "TP Call Log":
            columns = call_log_default_columns
            rows = ["name", "caller", "receiver", "creation"]
        else:
            columns = (
                _list.default_list_data(show_customer_portal_fields).get("columns")
                if doctype == "HD Ticket"
                else _list.default_list_data().get("columns")
            )
    if not rows:
        rows = _list.default_list_data().get("rows")

    return [columns, rows]


def handle_at_me_support(filters):
    # Converts @me in filters to current user
    if isinstance(filters, dict):
        for key in filters:
            _replace_at_me(filters, key)
        return filters
    for condition in filters:
        if isinstance(condition, list) and condition:
            _replace_at_me(condition, len(condition) - 1)
    return filters


def _replace_at_me(container, key):
    value = container[key]
    if isinstance(value, list):
        if "@me" in value:
            value[value.index("@me")] = frappe.session.user
        elif "%@me%" in value:
            index = [i for i, v in enumerate(value) if v == "%@me%"]
            for i in index:
                value[i] = "%" + frappe.session.user + "%"
    elif value == "@me":
        container[key] = frappe.session.user
    elif value == "%@me%":
        container[key] = "%" + frappe.session.user + "%"


def handle_assigned_on_filter(filters, doctype):
    """
    Handle the custom __assigned_on filter by querying ToDo table
    and merging the matching ticket names into the filters in place.
    """
    assigned_on_filter = _pop_assigned_on_filter(filters)
    if assigned_on_filter is None:
        return

    # Build ToDo query based on the operator and value
    ToDo = frappe.qb.DocType("ToDo")
    query = (
        frappe.qb.from_(ToDo)
        .select(ToDo.reference_name)
        .distinct()
        .where(ToDo.reference_type == doctype)
        .where(ToDo.allocated_to == frappe.session.user)
        .where(ToDo.status == "Open")
    )

    # Apply date filter based on operator
    query = apply_datetime_filter(query, ToDo.creation, assigned_on_filter)

    ticket_names = [row[0] for row in query.run()]
    # No matching tickets results in an impossible filter
    _merge_name_filter(filters, ticket_names)


def _pop_assigned_on_filter(filters):
    if isinstance(filters, dict):
        if "__assigned_on" not in filters:
            return None
        return filters.pop("__assigned_on")
    condition = next(
        (
            condition
            for condition in filters
            if isinstance(condition, list)
            and condition
            and condition[0] == "__assigned_on"
        ),
        None,
    )
    if condition is None:
        return None
    filters.remove(condition)
    return [condition[1], condition[2]] if len(condition) >= 3 else None


def _merge_name_filter(filters, ticket_names):
    if isinstance(filters, dict):
        if ticket_names and "name" in filters:
            existing_filter = filters["name"]
            if isinstance(existing_filter, list) and existing_filter[0] == "in":
                # Intersection of both filters
                ticket_names = list(set(ticket_names) & set(existing_filter[1]))
        filters["name"] = ["in", ticket_names]
        return
    existing = next(
        (
            condition
            for condition in filters
            if isinstance(condition, list)
            and len(condition) >= 3
            and condition[0] == "name"
            and str(condition[1]).lower() == "in"
        ),
        None,
    )
    if existing:
        existing[2] = list(set(ticket_names) & set(existing[2]))
    else:
        filters.append(["name", "in", ticket_names])


def apply_datetime_filter(query, field, filter_value):
    """Apply datetime filter to query based on operator."""
    if isinstance(filter_value, list):
        operator, value = filter_value[0], filter_value[1]
    else:
        operator, value = "=", filter_value

    if operator == "=":
        query = query.where(field == value)
    elif operator == "!=":
        query = query.where(field != value)
    elif operator == ">":
        query = query.where(field > value)
    elif operator == "<":
        query = query.where(field < value)
    elif operator == ">=":
        query = query.where(field >= value)
    elif operator == "<=":
        query = query.where(field <= value)
    elif operator == "between":
        if isinstance(value, list) and len(value) == 2:
            query = query.where(field >= value[0]).where(field <= value[1])
    elif operator == "timespan":
        from frappe.utils import get_datetime, get_timespan_date_range

        start, end = get_timespan_date_range(value)
        # convert to datetime to include full start and end day
        start_dt = get_datetime(str(start)).replace(hour=0, minute=0, second=0)
        end_dt = get_datetime(str(end)).replace(hour=23, minute=59, second=59)
        query = query.where(field >= start_dt).where(field <= end_dt)
    elif operator == "is":
        if value == "set":
            query = query.where(field.isnotnull())
        else:
            query = query.where(field.isnull())

    return query


@frappe.whitelist()
def remove_assignments(doctype: str, name: str, assignees: list[str]):
    assignees = frappe.parse_json(assignees)

    if not assignees:
        return

    for assign_to in assignees:
        set_status(
            doctype,
            name,
            todo=None,
            assign_to=assign_to,
            status="Cancelled",
        )
