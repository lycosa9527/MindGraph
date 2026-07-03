<script setup lang="ts">
/**
 * Org contacts sidebar — shared between Workshop Chat and MindMate collab.
 */
import { computed, onMounted, ref } from 'vue'

import { ElButton, ElInput } from 'element-plus'

import { useLanguage } from '@/composables'
import { useOrgContacts } from '@/composables/social/useOrgContacts'
import UserCardPopover from '@/components/workshop-chat/UserCardPopover.vue'

const props = withDefaults(
  defineProps<{
    /** Zulip-style green/grey dots only (online vs everyone else). */
    zulipPresence?: boolean
  }>(),
  { zulipPresence: false },
)

const emit = defineEmits<{
  (e: 'message', partnerId: number): void
  (e: 'start-dm', partnerId: number): void
  (e: 'view-profile', userId: number): void
  (e: 'manage-user', userId: number): void
}>()

const { t } = useLanguage()
const { store, presence, contactsSearchInput, loadingMoreContacts, contactSections, loadMoreContacts, refreshContacts } =
  useOrgContacts()

const contactPopoverUserId = ref<number | null>(null)

const displaySections = computed(() => {
  if (!props.zulipPresence) {
    return contactSections.value
  }
  const online = presence.contactsOnline.value
  const offline = [
    ...presence.contactsRecentlyOnline.value,
    ...presence.contactsOffline.value,
  ]
  const sections: typeof contactSections.value = []
  if (online.length > 0) {
    sections.push({
      key: 'online',
      labelKey: 'workshop.contactsOnlineNow',
      members: online,
    })
  }
  if (offline.length > 0) {
    sections.push({
      key: 'offline',
      labelKey: 'workshop.contactsOffline',
      members: offline,
    })
  }
  return sections
})

function presenceDotClass(sectionKey: string): string {
  if (props.zulipPresence) {
    return sectionKey === 'online' ? 'bg-green-500' : 'bg-stone-300'
  }
  if (sectionKey === 'online') {
    return 'bg-green-500'
  }
  if (sectionKey === 'recently_online') {
    return 'bg-amber-400'
  }
  return 'bg-stone-300'
}

onMounted(() => {
  void refreshContacts()
})

function handleStartDm(partnerId: number): void {
  emit('start-dm', partnerId)
  emit('message', partnerId)
}
</script>

<template>
  <div class="org-contacts-panel flex flex-col h-full min-h-0">
    <div class="org-contacts-panel__header px-3 py-3 border-b border-stone-200">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs font-medium text-stone-500 uppercase tracking-wide">
          {{ t('workshop.contacts') }}
        </span>
        <span class="text-xs text-stone-400">
          {{ presence.contactsOnlineCount }} {{ t('workshop.online') }}
        </span>
      </div>
      <ElInput
        v-model="contactsSearchInput"
        type="search"
        clearable
        size="small"
        :placeholder="t('workshop.searchMembers')"
      />
    </div>

    <div class="flex-1 overflow-y-auto px-2 py-2">
      <template
        v-for="section in displaySections"
        :key="section.key"
      >
        <div
          v-if="section.labelKey"
          class="text-[10px] font-medium text-stone-400 uppercase tracking-wide px-1 py-2"
        >
          {{ t(section.labelKey) }}
        </div>
        <div
          v-for="member in section.members"
          :key="`${section.key}-${member.id}`"
        >
          <UserCardPopover
            :user="{ id: member.id, name: member.name, avatar: member.avatar }"
            :visible="contactPopoverUserId === member.id"
            :channel-context="false"
            @update:visible="contactPopoverUserId = $event ? member.id : null"
            @start-dm="handleStartDm"
            @view-profile="emit('view-profile', $event)"
            @manage-user="emit('manage-user', $event)"
          >
            <div class="org-contacts-panel__row flex items-start gap-2 px-2 py-1.5 rounded-lg hover:bg-stone-100 cursor-pointer">
              <span
                class="org-contacts-panel__presence mt-1.5 shrink-0 w-2 h-2 rounded-full"
                :class="presenceDotClass(section.key)"
              />
              <div class="min-w-0 flex-1">
                <div
                  class="text-sm truncate"
                  :class="section.key === 'online' ? 'text-stone-800 font-medium' : 'text-stone-600'"
                >
                  {{ member.name
                  }}<span
                    v-if="presence.isContactSelf(member.id)"
                    class="text-stone-400 text-xs ml-1"
                    >{{ t('workshop.you') }}</span
                  >
                </div>
                <div
                  v-if="!zulipPresence && section.key === 'recently_online'"
                  class="text-[11px] text-stone-400 truncate"
                >
                  {{ presence.contactLastOnlineSubtitle(member.id) }}
                </div>
              </div>
            </div>
          </UserCardPopover>
        </div>
      </template>
      <div
        v-if="store.orgMembers.length === 0"
        class="text-xs text-stone-400 text-center py-6"
      >
        {{ t('workshop.noMembersFound') }}
      </div>
    </div>

    <div
      v-if="store.orgMembersTotal > 0"
      class="px-3 py-2 border-t border-stone-200 text-xs text-stone-400 flex items-center justify-between gap-2"
    >
      <span>
        {{
          t('workshop.contactsLoadedCount')
            .replace('{0}', String(store.orgMembers.length))
            .replace('{1}', String(store.orgMembersTotal))
        }}
      </span>
      <ElButton
        v-if="store.orgMembersHasMore"
        text
        size="small"
        type="primary"
        :loading="loadingMoreContacts"
        @click="loadMoreContacts"
      >
        {{ t('workshop.loadMore') }}
      </ElButton>
    </div>
  </div>
</template>
