<template>
  <!-- One line. The name was on its own row under a 2xl avatar, which cost about
       56px to restate something the email header shows a few inches to the left.
       The avatar still binds Contact.image, so a synced profile photo appears
       here with no further change. -->
  <div class="mt-3 flex items-center gap-2">
    <Avatar :label="contact.data?.name" :image="contactImage" size="lg" />
    <Tooltip :text="contact.data?.name || contact.data?.email_id">
      <div class="flex gap-1.5 items-center min-w-0">
        <p class="text-base font-medium text-ink-gray-8 max-w-[180px] truncate">
          {{ contact.data?.name || contact.data?.email_id }}
        </p>
        <ExternalLinkIcon
          v-if="!contact.loading"
          class="size-3.5 shrink-0 text-ink-gray-5 cursor-pointer hover:text-ink-gray-8"
          @click="openContact(contact.data.name)"
        />
      </div>
    </Tooltip>
    <div class="flex gap-1.5 ml-auto" v-if="isCallingEnabled">
      <Tooltip :text="contact.data?.email_id">
        <!-- Email Button -->
        <Button size="sm" @click="toggleEmailBox()">
          <template #icon>
            <EmailIcon class="size-4" />
          </template>
        </Button>
        <!-- Call Button -->
        <Button size="sm" v-if="isCallingEnabled" @click="callContact">
          <template #icon>
            <PhoneIcon class="size-4" />
          </template>
        </Button>
      </Tooltip>
    </div>
    <SetContactPhoneModal
      v-model="showPhoneModal"
      :name="contact.data?.name ?? ''"
      @onUpdate="contact.reload"
    />
  </div>
</template>

<script setup lang="ts">
import { toggleEmailBox } from "@/pages/ticket/modalStates";
import { useTelephonyStore } from "@/stores/telephony";
import { useUserStore } from "@/stores/user";
import { TicketContactSymbol, TicketSymbol } from "@/types";
import { openContact } from "@/utils";
import { Avatar, Button, Tooltip } from "frappe-ui";
import { storeToRefs } from "pinia";
import { computed, inject, ref } from "vue";
import { ExternalLinkIcon } from "../icons";
import EmailIcon from "../icons/EmailIcon.vue";
import PhoneIcon from "../icons/PhoneIcon.vue";
import SetContactPhoneModal from "../ticket/SetContactPhoneModal.vue";
const telephonyStore = useTelephonyStore();
const { getUser } = useUserStore();
const { isCallingEnabled } = storeToRefs(telephonyStore);
const showPhoneModal = ref(false);

const ticket = inject(TicketSymbol)!;

const contact = inject(TicketContactSymbol)!;
const contactImage = computed(() => {
  if (!contact.value?.data) return "";
  const email = contact.value?.data?.email_id ?? "";
  return (
    contact.value?.data?.image || (email && getUser(email)?.user_image) || ""
  );
});

const callContact = () => {
  if (!contact.value.data.mobile_no && !contact.value.data.phone) {
    showPhoneModal.value = true;
    return;
  }
  telephonyStore.makeCall({
    number: contact.value.data.mobile_no || contact.value.data.phone,
    doctype: "HD Ticket",
    docname: ticket.value.name,
  });
};
</script>

<style scoped></style>
