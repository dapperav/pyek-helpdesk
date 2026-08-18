<template>
  <!-- View Controls -->
  <div
    :class="[
      'flex items-center justify-between gap-2 px-5 pb-4 pt-3 ',
      list?.data?.data?.length > 0 ? 'relative' : 'absolute w-[stretch]',
    ]"
    v-if="showViewControls"
  >
    <!-- Universal search (PYEK, desktop tickets): the always-visible door to
         the same overlay the rail's Search opens — every ticket, every
         status. -->
    <button
      v-if="boardAvailable"
      type="button"
      class="pyek-searchbox"
      :aria-label="__('Search all tickets')"
      @click="openUniversalSearch()"
    >
      <LucideSearch class="size-3.5 shrink-0" />
      <span class="truncate">{{ __("Search any ticket — name, keyword, or number…") }}</span>
      <kbd>/</kbd>
    </button>
    <QuickFilters v-if="!isMobileView" />
    <div v-if="!isMobileView" class="-ml-2 h-5 border-l"></div>
    <div
      class="flex items-start gap-2 justify-end h-full py-1 pl-0.5"
      v-if="!isMobileView"
    >
      <!-- Board ⇄ List (PYEK, desktop tickets — Mark 2026-08-18): board is
           the default, the familiar table is one click back, remembered per
           user. -->
      <div
        v-if="boardAvailable"
        class="flex rounded-lg bg-surface-gray-2 p-0.5"
        role="tablist"
        :aria-label="__('View mode')"
      >
        <button
          type="button"
          role="tab"
          class="pyek-vmode"
          :class="{ on: viewMode === 'board' }"
          :aria-pressed="viewMode === 'board'"
          @click="viewMode = 'board'"
        >
          <LucideColumns3 class="size-3.5" />{{ __("Board") }}
        </button>
        <button
          type="button"
          role="tab"
          class="pyek-vmode"
          :class="{ on: viewMode === 'list' }"
          :aria-pressed="viewMode === 'list'"
          @click="viewMode = 'list'"
        >
          <LucideList class="size-3.5" />{{ __("List") }}
        </button>
      </div>
      <Button
        :label="__('Save Changes')"
        v-if="isViewUpdated && canSaveView"
        @click="handleViewUpdate"
      />
      <Reload @click="handleReload" :loading="list.loading" />
      <Filter />
      <SortBy :hide-label="isMobileView" />
      <ColumnSettings
        :hide-label="isMobileView"
        v-if="!options.hideColumnSetting"
      />
    </div>
    <div v-else class="flex justify-between items-center w-full">
      <Filter />
      <div class="flex items-center gap-2">
        <Reload @click="handleReload" :loading="list.loading" />
        <SortBy :hide-label="isMobileView" />
      </div>
    </div>
  </div>

  <!-- Loading State -->
  <div
    v-if="list.loading && !list.data?.data?.length"
    class="flex items-center justify-center h-full w-full absolute top-0 z-100"
  >
    <LoadingIndicator :scale="8" />
  </div>
  <!-- The tickets BOARD (PYEK, desktop — Mark 2026-08-18): same fetched rows,
       same chrome above and footer below; only the middle swaps. Lanes and
       card language live in PyekTicketBoard. -->
  <div
    v-else-if="showBoard && list.data?.data.length > 0"
    class="flex-1 overflow-y-auto pt-1"
  >
    <PyekTicketBoard
      :rows="list.data.data"
      :mine-view="isMineBoard"
      @row-click="openOutlookRow"
    />
  </div>
  <!-- Outlook-inbox rows (PYEK): custom row rendering, all list chrome above
       and the footer below stay intact. -->
  <div
    v-else-if="options.outlookRows && list.data?.data.length > 0"
    class="flex-1 overflow-y-auto"
    :class="isMobileView ? 'flex flex-col gap-[9px] bg-[#fbfdff] px-3 pt-2 pb-3' : ''"
  >
    <OutlookTicketRow
      v-for="row in list.data.data"
      :key="row.name"
      :row="row"
      :selected="outlookSelected.has(row.name)"
      :selecting="outlookSelected.size > 0"
      @click="openOutlookRow(row)"
      @toggle="toggleOutlookSelect(row.name)"
      @actions="actionTicket = row"
    />
    <!-- Bulk action bar (PYEK): sticky at the bottom of the list whenever rows
         are selected, so the status control is always visible. -->
    <!-- On the phone the list's scroll happens on a MobileLayout ancestor
         (the PR 125 fixed shell), so `sticky` inside this grown container
         never engages — pin the bar to the viewport above the glass nav
         instead. Desktop keeps sticky (its container is the scroller). -->
    <div
      v-if="outlookSelected.size"
      class="flex items-center justify-between gap-3 border-t bg-surface-base px-4 py-3 shadow-lg"
      :class="isMobileView ? 'fixed inset-x-0 z-30' : 'sticky z-10'"
      style="bottom: var(--pyek-nav-h, 0px)"
    >
      <span class="text-sm font-medium text-ink-gray-7">
        {{ outlookSelected.size }} {{ __("selected") }}
      </span>
      <div class="flex items-center gap-2">
        <Dropdown :options="bulkStatusOptions" placement="top">
          <Button variant="solid" :label="__('Set status')" :loading="bulkUpdating">
            <template #suffix>
              <FeatherIcon name="chevron-down" class="h-4 w-4" />
            </template>
          </Button>
        </Dropdown>
        <Button
          variant="ghost"
          :label="__('Clear')"
          @click="clearOutlookSelection"
        />
      </div>
    </div>
    <!-- Swipe-left action sheet (PYEK): opened from a row's swipe. -->
    <TicketActionSheet
      v-if="actionTicket"
      :ticket="actionTicket.name"
      :subject="actionTicket.subject"
      :assign="actionTicket._assign"
      @done="
        actionTicket = null;
        handleReload();
      "
      @close="actionTicket = null"
    />
  </div>

  <!-- List View -->
  <ListView
    v-else-if="list.data?.data.length > 0"
    class="flex-1"
    :columns="columns"
    :rows="rows"
    row-key="name"
    :options="{
      selectable: options.selectable,
      showTooltip: false,
      resizeColumn: true,
      getRowRoute: (row) => ({
        name: options.rowRoute?.name,
        params: { [options.rowRoute?.prop]: row.name },
        query: { view: route.query?.view },
      }),
      emptyState,
    }"
  >
    <ListHeader class="sm:mx-5 mx-3">
      <ListHeaderItem
        v-for="column in columns"
        :key="column.key"
        :item="column"
        @columnWidthUpdated="handleColumnResize"
      />
    </ListHeader>
    <ListRows
      :rows="rows"
      v-slot="{ idx, column, item, row }"
      :group-by-actions="options.groupByActions"
      @scrollend="handleListScroll"
      class="list-rows"
    >
      <ListRowItem :item="item" :column="column" :row="row">
        <component
          :is="listCell(column, row, item, idx)"
          :key="column.key"
          @click="(e) => handleFieldClick(e, column, row, item)"
        />
      </ListRowItem>
    </ListRows>
    <ListSelectBanner v-if="options.showSelectBanner">
      <template #actions="{ selections, unselectAll }">
        <Dropdown :options="selectBannerOptions(selections, unselectAll)">
          <Button icon="lucide-more-horizontal" variant="ghost" />
        </Dropdown>
      </template>
    </ListSelectBanner>
  </ListView>

  <!-- List Footer -->
  <div
    class="p-20 border-t sm:px-5 px-3 py-2"
    v-if="list.data?.data.length > 0"
  >
    <ListFooter
      :options="{
        rowCount: list?.data?.row_count,
        totalCount: list?.data?.total_count,
      }"
      :pageLengthCount="defaultParams.page_length_count"
      @loadMore="handlePageLength(defaultParams.page_length_count, true)"
      v-model="defaultParams.page_length_count"
      @update:modelValue="
        (count) => {
          handlePageLength(count);
        }
      "
    />
  </div>
  <!-- Empty State -->
  <EmptyState
    v-else-if="!list.loading"
    :title="emptyState.title"
    :icon="emptyState.icon"
    :description="emptyState.description"
  />
</template>

<script setup lang="ts">
import { MultipleAvatar, StarRating } from "@/components";
import {
  ColumnSettings,
  QuickFilters,
  Reload,
  SortBy,
} from "@/components/view-controls";
import { Filter, normalizeFilters } from "@/components/view-controls/filter";
import { useScreenSize } from "@/composables/screen";
import {
  currentView as headerView,
  useView,
  views,
} from "@/composables/useView";
import { useAuthStore } from "@/stores/auth";
import { globalStore } from "@/stores/globalStore";
import { capture } from "@/telemetry";
import { View, ViewType } from "@/types";
import { formatTimeShort, getIcon } from "@/utils";
import { useStorage } from "@vueuse/core";
import { useTicketStatusStore } from "@/stores/ticketStatus";
import { __ } from "@/translation";
import {
  call,
  createResource,
  Dropdown,
  FeatherIcon,
  frappeRequest,
  ListFooter,
  ListHeader,
  ListHeaderItem,
  ListRowItem,
  ListSelectBanner,
  ListView,
  LoadingIndicator,
  dayjs,
  toast,
} from "frappe-ui";
import {
  computed,
  h,
  onMounted,
  provide,
  reactive,
  ref,
  VNode,
  watch,
  watchEffect,
} from "vue";
import { useRoute, useRouter } from "vue-router";

import EmptyState from "./EmptyState.vue";
import ListRows from "./ListRows.vue";
import OutlookTicketRow from "./ticket/OutlookTicketRow.vue";
import PyekTicketBoard from "./ticket/PyekTicketBoard.vue";
import TicketActionSheet from "./ticket/TicketActionSheet.vue";
import { openUniversalSearch } from "@/composables/universalSearch";
import LucideColumns3 from "~icons/lucide/columns-3";
import LucideList from "~icons/lucide/list";
import LucideSearch from "~icons/lucide/search";

interface P {
  options: {
    doctype: string;
    defaultFilters?: Record<string, any>;
    columnConfig?: Record<string, any>;
    emptyState?: {
      // type of a h componnt
      icon?: string | VNode;
      title: string;
      description?: string;
    };
    hideViewControls?: boolean;
    hideColumnSetting?: boolean;
    selectable?: boolean;
    view?: ViewType;
    groupByActions?: Array<any>;
    showSelectBanner?: boolean;
    selectBannerActions?: Record<string, any>;
    default_page_length?: number;
    isCustomerPortal?: boolean;
    rowRoute?: Record<string, string>;
    // PYEK: render the list as Outlook-inbox style rows instead of the column
    // table. Keeps all view/filter/sort/pagination chrome intact.
    outlookRows?: boolean;
    // PYEK: offer the desktop tickets BOARD (three ownership lanes) with a
    // Board ⇄ List toggle in the view controls. Desktop only.
    board?: boolean;
  };
}

interface E {
  (event: "rowClick", row: any): void;
}
const props = defineProps<P>();
const emit = defineEmits<E>();
const route = useRoute();
const router = useRouter();
const { isManager } = useAuthStore();
const { $dialog, $socket } = globalStore();
const { getStatus, statuses } = useTicketStatusStore();

const listSelections = ref(new Set());
const defaultOptions = reactive({
  doctype: "",
  hideViewControls: false,
  selectable: false,
  view: {
    view_type: "list",
    group_by_field: "owner",
    name: route.query.view,
  },
  groupByActions: [],
  default_page_length: 20,
  isCustomerPortal: false,
  hideColumnSetting: true,
  rowRoute: {
    name: "",
    prop: "",
  },
  selectBannerActions: [
    {
      label: __("Delete"),
      icon: "lucide-trash-2",
      onClick: (selections: Set<string>) => {
        $dialog({
          title: __("Delete"),
          message: __("Are you sure you want to delete {0} item(s)?", [
            selections.size,
          ]),
          actions: [
            {
              label: __("Delete"),
              variant: "solid",
              theme: "red",
              iconLeft: "trash-2",
              onClick({ close }) {
                handleBulkDelete(close, selections);
              },
            },
          ],
        });
      },
      condition: () => !options.value.isCustomerPortal && isManager,
    },
  ],
});

function handleBulkDelete(hide: Function, selections: Set<string>) {
  capture("bulk_delete" + props.options.doctype);
  const requested = Array.from(selections);
  const requestedCount = requested.length;

  const failureMessages: string[] = [];
  let successMessage = "";
  let failedCount = 0;

  const onBulkResult = (data: { message: string; title: string }) => {
    const isFailure =
      data.title === __("Bulk Operation Failed") ||
      data.title === "Bulk Operation Failed";
    const isSuccess =
      data.title === __("Bulk Operation Successful") ||
      data.title === "Bulk Operation Successful";
    if (!isFailure && !isSuccess) return;

    if (isFailure) {
      // Parse how many items failed from the message (Frappe includes the count)
      const match = data.message.match(/Failed to delete (\d+) documents?/);
      if (match) {
        failedCount = parseInt(match[1], 10);
      }
      failureMessages.push(data.message);
    } else {
      successMessage = data.message;
    }
  };

  $socket.on("msgprint", onBulkResult);

  // Use frappeRequest (not `call`) so per-item delete errors surfaced in
  // `_server_messages` get routed through the app's serverMessagesHandler.
  // `call` silently drops them on 200 responses.
  frappeRequest({
    url: "frappe.desk.reportview.delete_items",
    params: {
      items: JSON.stringify(requested),
      doctype: props.options.doctype,
    },
  }).finally(() => {
    $socket.off("msgprint", onBulkResult);

    const deletedCount = requestedCount - failedCount;

    if (failureMessages.length > 0 && deletedCount > 0) {
      // Partial success: some deleted, some failed — show both toasts
      toast.success(__("{0} item(s) deleted successfully", [deletedCount]));
      for (const msg of failureMessages) {
        toast.error(msg);
      }
    } else if (failureMessages.length > 0) {
      // All failed
      for (const msg of failureMessages) {
        toast.error(msg);
      }
    } else if (successMessage) {
      // All succeeded
      toast.success(successMessage);
    } else {
      // Fallback: no socket messages received (e.g. enqueued for >10 items)
      toast.success(__("{0} item(s) queued for deletion", [requestedCount]));
    }

    hide();
    reset();
  });
}

function reset() {
  exposeFunctions.reload();
  exposeFunctions.unselectAll();
}

const options = computed(() => {
  return {
    ...defaultOptions,
    ...props.options,
  };
});

// PYEK: navigate on Outlook-row click (mirrors ListView's getRowRoute).
function openOutlookRow(row: any) {
  router.push({
    name: options.value.rowRoute?.name,
    params: { [options.value.rowRoute?.prop as string]: row.name },
    query: { view: route.query?.view },
  });
}

// PYEK: multi-select + bulk status change for the Outlook list (e.g. bulk-close
// notification alerts without opening each one).
const outlookSelected = ref<Set<string>>(new Set());
// PYEK: the ticket whose swipe-left action sheet is open (null = closed).
const actionTicket = ref<Record<string, any> | null>(null);
function toggleOutlookSelect(name: string) {
  const s = new Set(outlookSelected.value);
  s.has(name) ? s.delete(name) : s.add(name);
  outlookSelected.value = s;
}
function clearOutlookSelection() {
  outlookSelected.value = new Set();
}
const bulkUpdating = ref(false);
const bulkStatusOptions = computed(() =>
  (statuses.data || [])
    .filter((s: any) => s.enabled)
    .map((s: any) => ({
      label: s.label_agent,
      onClick: () => applyBulkStatus(s.label_agent),
    }))
);
async function applyBulkStatus(status: string) {
  const ids = Array.from(outlookSelected.value);
  if (!ids.length) return;
  bulkUpdating.value = true;
  try {
    const res = await call("helpdesk.api.ticket.bulk_set_status", {
      ticket_ids: ids,
      status,
    });
    toast.success(__("Updated {0} ticket(s)", [res?.updated ?? ids.length]));
    clearOutlookSelection();
    list.reload();
  } catch (e) {
    toast.error(__("Failed to update tickets"));
  } finally {
    bulkUpdating.value = false;
  }
}

const { isMobileView } = useScreenSize();

// --- Board ⇄ List (PYEK, desktop tickets — Mark 2026-08-18) -----------------
// Board is the default; the toggle is remembered per user. One key, one
// mounted ListViewBuilder per screen (the useStorage sharing trap needs two
// simultaneous consumers to bite).
const viewMode = useStorage("pyek_tickets_view_mode", "board");
const boardAvailable = computed(
  () => !!options.value.board && !isMobileView.value
);
const showBoard = computed(
  () => boardAvailable.value && viewMode.value === "board"
);

// Mine-style views (filters pin _assign to the viewer) get the two-lane
// board — everything in them is already owned by you.
const isMineBoard = computed(() => {
  const name = route.query.view as string;
  if (!name) return false;
  const v = (views.data || []).find((x: any) => x.name === name);
  if (!v) return false;
  const filters =
    typeof v.filters === "string" ? v.filters : JSON.stringify(v.filters || {});
  return filters.includes("_assign");
});

const defaultEmptyState = {
  icon: "",
  title: __("No Data Found"),
};

const pageLengthCount = useStorage(
  `list_page_length_count+${props.options.doctype}`,
  options.value.default_page_length
);

const defaultParams = reactive({
  doctype: options.value.doctype,
  filters: {},
  default_filters: options.value.defaultFilters,
  order_by: "modified desc",
  page_length: pageLengthCount.value,
  page_length_count: pageLengthCount.value,
  view: options.value.view,
  columns: [],
  rows: [],
  show_customer_portal_fields: options.value.isCustomerPortal,
  is_default: false,
});

const emptyState = computed(() => {
  return options.value?.emptyState || defaultEmptyState;
});

const isViewUpdated = ref(false);

const list = createResource({
  url: "helpdesk.api.doc.get_list_data",
  params: defaultParams,
  transform: (data) => {
    data.columns.forEach((column) => {
      handleFetchFromField(column);
      handleColumnConfig(column);
    });
    return data;
  },
  onSuccess: (data) => {
    list.params = defaultParams;
    columns.value = data.columns;
  },
});

// The board wants the whole live picture, not the first page: widen the
// fetch window once per view (the user's stored List page-length preference
// stays untouched; the footer's Load more still works past 100). Lives below
// the resource on purpose — watchEffect runs synchronously at setup.
watchEffect(() => {
  if (!showBoard.value) return;
  const total = list.data?.total_count ?? 0;
  if (defaultParams.page_length < 100 && total > defaultParams.page_length) {
    defaultParams.page_length = 100;
    list.reload();
  }
});

const exposeFunctions = {
  list,
  reload,
  unselectAll: () => {},
};

function selectBannerOptions(selections: Set<string>, unselectAll = () => {}) {
  exposeFunctions["unselectAll"] = unselectAll;

  // Get the user-provided actions
  const userActions = options.value.selectBannerActions.map((action) => ({
    ...action,
    onClick: () => action.onClick?.(selections),
  }));

  // Get the default actions
  // overwrite the default actions if user provided actions with same label
  const defaultActions = defaultOptions.selectBannerActions
    .filter(
      (action) =>
        !userActions.some(
          (defaultAction) => defaultAction.label === action.label
        )
    )
    .map((action) => ({
      ...action,
      onClick: () => action.onClick?.(selections),
    }));

  // Return combined actions
  return [...userActions, ...defaultActions];
}

const rows = computed(() => {
  if (!list.data?.data) return [];
  if (list.data.view_type === "group_by") {
    if (!list.data?.group_by_field?.name) return [];
    return getGroupedByRows(list.data.data, list.data.group_by_field);
  }
  return list.data?.data;
});
const columns = ref([]);

function getGroupedByRows(listRows, groupByField) {
  let groupedRows = [];
  groupByField.options?.forEach((option) => {
    let filteredRows = [];

    if (!option.value) {
      filteredRows = listRows.filter((row) => !row[groupByField.name]);
    } else {
      filteredRows = listRows.filter(
        (row) => row[groupByField.name] == option.value
      );
    }

    let groupDetail = {
      group: option || " ",
      collapsed: false,
      rows: filteredRows,
      icon: h(FeatherIcon, {
        name: "folder",
        class: "h-4 w-4 flex-shrink-0 text-ink-gray-6",
      }),
    };
    groupedRows.push(groupDetail);
  });
  return groupedRows || listRows;
}

function handleFetchFromField(column) {
  if (!column.hasOwnProperty("key")) return column;
  const regex = /([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)/;
  const isFetchFromField = column.key.match(regex);
  column.key = isFetchFromField ? isFetchFromField[2] : column.key;
}

function handleColumnConfig(column) {
  if (!options.value?.columnConfig) return column;
  const columnConfig = options.value.columnConfig;
  if (!columnConfig.hasOwnProperty(column.key)) return column;
  column.prefix = columnConfig[column.key]?.prefix;

  return column;
}

const filterableFields = createResource({
  url: "helpdesk.api.doc.get_filterable_fields",
  cache: ["DocField", options.value.doctype],
  auto: !options.value.hideViewControls,
  params: {
    doctype: options.value.doctype,
    append_assign: true,
    show_customer_portal_fields: defaultParams.show_customer_portal_fields,
  },
  transform: (data) => {
    data = data.map((field) => {
      return {
        label: field.label,
        value: field.fieldname,
        ...field,
      };
    });
    return data;
  },
});

const sortableFields = createResource({
  url: "helpdesk.api.doc.sort_options",
  auto: !options.value.hideViewControls,
  params: {
    doctype: options.value.doctype,
    show_customer_portal_fields: defaultParams.show_customer_portal_fields,
  },
});

const quickFilters = createResource({
  url: "helpdesk.api.doc.get_quick_filters",
  auto: !options.value.hideViewControls,
  params: {
    doctype: options.value.doctype,
    show_customer_portal_fields: defaultParams.show_customer_portal_fields,
  },
  transform: (data) => {
    if (Boolean(data.length)) return;
    data = [{ name: "name", label: "Name", fieldtype: "Data" }];
    return data;
  },
});

function listCell(column: any, row: any, item: any, idx: number) {
  const columnConfig = options.value.columnConfig;
  if (columnConfig && columnConfig[column.key]?.custom) {
    return columnConfig[column.key]?.custom({ column, row, item, idx });
  }
  if (idx === 0) {
    return h("span", {
      class: "truncate text-base text-ink-gray-6",
      textContent: item,
    });
  }
  if (column.type === "Datetime") {
    return h("span", {
      class: "text-p-xs",
      textContent: formatTimeShort(item),
    });
  }
  if (column.type === "MultipleAvatar") {
    return h(MultipleAvatar, {
      avatars: item,
      hideName: false,
      class: "flex items-center flex-1 min-w-0",
    });
  }
  if (column.type === "Rating") {
    return h(StarRating, {
      rating: item || 0,
      class: "truncate",
    });
  }
  return h("span", {
    class: "truncate flex-1",
    textContent: item,
  });
}

function handleFieldClick(e: MouseEvent, column, row, item) {
  const noFilterFields = ["Data", "Datetime", "Rating", "Int", "Float"];
  if (noFilterFields.includes(column.type)) {
    if (options.value.rowRoute?.name !== "") {
      return;
    }
    emit("rowClick", row.name);
    return;
  }
  e.stopPropagation();
  e.preventDefault();

  if (column.label == "Status" && options.value.doctype === "HD Ticket") {
    item = getStatus(item)?.label_agent;
  }

  if (column.type === "MultipleAvatar") {
    if (item.length > 1) {
      let target = e.target as HTMLElement;
      target = target.closest(".user-avatar");
      if (target) {
        item = target.getAttribute("data-name");
      }
    } else {
      item = item[0].name;
    }
    applyColumnFilter(column.key, "LIKE", `%${item}%`);
    return;
  }
  applyColumnFilter(column.key, "=", item);
}

function applyColumnFilter(key: string, operator: string, value: any) {
  const conditions = normalizeFilters(defaultParams.filters).filter(
    (condition) => condition[0] !== key
  );
  conditions.push([key, operator, value]);
  applyFilters(conditions);
}

const showViewControls = computed(() => {
  return (
    !options.value.hideViewControls &&
    filterableFields.data &&
    sortableFields.data &&
    quickFilters.data
  );
});

const listViewData = reactive({
  list,
  filterableFields,
  quickFilters,
  sortableFields,
});

provide("listViewData", listViewData);

provide("listViewActions", {
  applyFilters,
  applySort,
  updateColumns,
  reload,
});

function applyFilters(filters) {
  isViewUpdated.value = true;
  defaultParams.filters = normalizeFilters(filters);
  list.submit({ ...defaultParams });

  // automatically update filters for default view
  if (!defaultParams.is_default) return;
  handleViewUpdate();
  isViewUpdated.value = false;
}

function applySort(order_by: string) {
  isViewUpdated.value = true;
  defaultParams.order_by = order_by;
  list.submit({ ...defaultParams, order_by });
  if (!defaultParams.is_default) return;
  handleViewUpdate();
  isViewUpdated.value = false;
}

function updateColumns(obj) {
  isViewUpdated.value = true;
  const { columns: _columns, isDefault, rows } = obj;
  _columns?.forEach((column) => {
    handleFetchFromField(column);
    handleColumnConfig(column);
  });
  columns.value = defaultParams.columns = isDefault ? "" : _columns;
  defaultParams.rows = isDefault ? "" : rows;
  list.reload({ ...defaultParams });
}

function reload(reset: boolean = false) {
  if (reset) {
    defaultParams.filters = normalizeFilters(options.value.defaultFilters);
    defaultParams.order_by = "modified desc";
    defaultParams.page_length = options.value.default_page_length;
    pageLengthCount.value = options.value.default_page_length;
    defaultParams.page_length_count = pageLengthCount.value;
    defaultParams.columns = [];
    defaultParams.rows = [];
    defaultParams.is_default = true;
  }
  list.reload({ ...defaultParams });
}

function handlePageLength(count: number, loadMore: boolean = false) {
  pageLengthCount.value = count;
  defaultParams.page_length_count = pageLengthCount.value;
  if (loadMore) {
    defaultParams.page_length += count;
  } else {
    if (
      count === defaultParams.page_length &&
      count === defaultParams.page_length_count
    ) {
      return;
    }
    defaultParams.page_length = count;
    defaultParams.page_length_count = count;
  }
  list.reload();
}

function handleViewUpdate() {
  const view = {
    filters: JSON.stringify(defaultParams.filters),
    columns: JSON.stringify(defaultParams.columns),
    rows: JSON.stringify(defaultParams.rows),
    order_by: defaultParams.order_by,
    name: (route.query.view as string) || "default",
    dt: options.value.doctype,
    route_name: route.name,
    is_customer_portal: options.value.isCustomerPortal,
  };
  const currentView = findView(route.query.view as string).value;
  if (currentView && currentView.public) {
    $dialog({
      title: __("Confirm Changes"),
      message: __(
        "This view is public. Changes made will be visible to everyone."
      ),
      actions: [
        {
          label: __("Save"),
          variant: "solid",
          onClick({ close }) {
            updateView(view, () => {
              isViewUpdated.value = false;
            });
            close();
          },
        },
        {
          label: __("Cancel"),
          variant: "outline",
          onClick({ close }) {
            close();
          },
        },
      ],
    });
  } else {
    updateView(view, () => {
      isViewUpdated.value = false;
    });
  }
}

const { findView, updateView, defaultView } = useView(options.value.doctype);

const canSaveView = computed(() => {
  let currentView: View = findView(route.query.view as string).value;
  if (currentView?.is_standard) return false;
  if (!currentView || !currentView.public) return true;
  if (currentView.public && isManager) {
    return true;
  }
  return false;
});

function handleReload() {
  handleViewChanges();
  isViewUpdated.value = false;
}

function handleViewChanges() {
  let currentView: View = findCurrentView();
  if (!currentView) {
    router.push({ name: route.name });
    reload(true);
    return;
  }
  // normalize so legacy dict-format saved views become list conditions
  defaultParams.filters = normalizeFilters(currentView.filters);
  defaultParams.order_by = currentView.order_by || "modified desc";
  defaultParams.columns = currentView.columns;
  defaultParams.rows = currentView.rows;

  if (route.query.filters) {
    try {
      const parsedFilters = normalizeFilters(
        JSON.parse(route.query.filters as string)
      );
      if (parsedFilters.length > 0) {
        const overriddenFields = new Set(parsedFilters.map((c) => c[0]));
        defaultParams.filters = [
          ...normalizeFilters(defaultParams.filters).filter(
            (c) => !overriddenFields.has(c[0])
          ),
          ...parsedFilters,
        ];
      }
    } catch (e) {
      console.error("Failed to parse filters from URL", e);
    }
  }

  list.submit({ ...defaultParams });
}

function findCurrentView() {
  let currentView: View;
  if (route.query.view) {
    currentView = findView(route.query.view as string).value;
    defaultParams.is_default = false;
  } else if (defaultView.value) {
    currentView = defaultView.value;
    defaultParams.is_default = true;
  }
  return currentView;
}

watch(
  () => route.query.view,
  (val: string) => {
    defaultParams.view.name = val;
    handleViewChanges();
    if (!val) {
      headerView.value.label = __("List");
      headerView.value.icon = LucideAlignJustify;
    }
  }
);

const listScrollPosition = useStorage(
  `list_position+${props.options.doctype}`,
  0
);
function handleListScroll(e) {
  listScrollPosition.value = e.target.scrollTop;
}
function handleScrollPosition() {
  setTimeout(() => {
    const listContainer = document.querySelector(".list-rows");
    if (!listContainer) return;
    listContainer.scrollTop = listScrollPosition.value;
  }, 200);
}

function handleColumnResize({ key, width, save } = {}) {
  const column = columns.value.find((c) => c.key === key);
  if (column) column.width = width;
  if (!save) return;
  isViewUpdated.value = true;
  defaultParams.columns = columns.value;
  if (!defaultParams.is_default) return;
  handleViewUpdate();
  isViewUpdated.value = false;
}

onMounted(async () => {
  handleScrollPosition();

  if (views.data?.length > 0 && views.filters?.dt === options.value.doctype) {
    handleViewChanges();
  } else {
    await views.list.promise;
    handleViewChanges();
  }
  if (route.query.view || defaultView.value) {
    if (route.query.view) {
      const currentView = findCurrentView();
      if (!currentView) return;
      headerView.value.label = currentView.label || __("List");
      headerView.value.icon = getIcon(currentView.icon);
    }
    return;
  }
});

defineExpose(exposeFunctions);
</script>

<style scoped>
/* Universal-search door (PYEK): looks like an input, opens the overlay. */
.pyek-searchbox {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 1 400px;
  min-width: 0;
  border: 1px solid var(--outline-gray-1);
  border-radius: 9px;
  background: var(--surface-white, #fff);
  padding: 6px 11px;
  font-size: 13px;
  color: var(--ink-gray-5);
  cursor: text;
  text-align: left;
  transition: border-color 0.15s;
}
.pyek-searchbox:hover {
  border-color: var(--outline-gray-2);
}
.pyek-searchbox kbd {
  margin-left: auto;
  font: inherit;
  font-size: 11px;
  color: var(--ink-gray-4);
  border: 1px solid var(--outline-gray-1);
  border-radius: 5px;
  padding: 0 6px;
  background: var(--surface-gray-1, #f7fafd);
}

/* Board ⇄ List segmented toggle (PYEK). */
.pyek-vmode {
  display: flex;
  align-items: center;
  gap: 5px;
  border: 0;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink-gray-6);
  background: transparent;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.pyek-vmode:hover {
  color: var(--ink-gray-8);
}
.pyek-vmode.on {
  background: var(--surface-white, #fff);
  color: var(--ink-gray-9);
  box-shadow: 0 1px 3px rgba(27, 42, 74, 0.12);
}
</style>
