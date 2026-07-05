<script setup lang="ts">
/**
 * Org contacts roster panel — shared IM contact list for Workshop Chat,
 * MindMate collab, and future global IM widget.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { ElButton, ElInput } from 'element-plus'

import { Search } from '@lucide/vue'

import UserCardPopover from '@/components/workshop-chat/UserCardPopover.vue'
import { useLanguage, useNotifications } from '@/composables'
import { type OrgRosterSource, useOrgRosterPanel } from '@/composables/social'
import { authFetch } from '@/utils/api'

const props = withDefaults(
  defineProps<{
    source?: OrgRosterSource
    /** Zulip-style green/grey dots only (online vs everyone else). */
    zulipPresence?: boolean
    /** Compact search row (MindMate collab sidebar). */
    variant?: 'default' | 'compact'
    /** When set, user card shows collab poke action. */
    sessionId?: string
    /** MindMate collab room code (public seminar session roster). */
    collabRoomCode?: string
    /** MindMate collab visibility — network uses session participant roster. */
    collabVisibility?: string
  }>(),
  {
    source: 'workshop',
    zulipPresence: false,
    variant: 'default',
    sessionId: '',
    collabRoomCode: '',
    collabVisibility: 'organization',
  }
)

const emit = defineEmits<{
  (e: 'message', partnerId: number): void
  (e: 'startDm', partnerId: number): void
  (e: 'viewProfile', userId: number): void
  (e: 'manageUser', userId: number): void
}>()

const { t } = useLanguage()
const notify = useNotifications()

const effectiveZulipPresence = computed(
  () => props.zulipPresence || props.source === 'mindmate-collab'
)

const rosterPanel = useOrgRosterPanel({
  source: props.source,
  zulipPresence: effectiveZulipPresence.value,
  collabRoomCode: () => props.collabRoomCode ?? '',
  collabVisibility: () => props.collabVisibility ?? 'organization',
})

const {
  members,
  membersTotal,
  membersHasMore,
  contactsSearchInput,
  loading,
  loadingMore,
  presence,
  contactSections,
  loadMoreContacts,
  refreshContacts,
} = rosterPanel

const contactPopoverUserId = ref<number | null>(null)
const pokingUserId = ref<number | null>(null)

const isCompact = computed(() => props.variant === 'compact')
const collabContext = computed(() => props.source === 'mindmate-collab')
const isPublicCollabSeminar = computed(
  () => collabContext.value && props.collabVisibility === 'network',
)

const displaySections = contactSections

function presenceDotClass(sectionKey: string): string {
  if (effectiveZulipPresence.value) {
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

let sessionRosterTimer: ReturnType<typeof setInterval> | null = null

watch(
  isPublicCollabSeminar,
  (active) => {
    if (sessionRosterTimer != null) {
      clearInterval(sessionRosterTimer)
      sessionRosterTimer = null
    }
    if (active) {
      sessionRosterTimer = setInterval(() => {
        if (props.sessionId) {
          void refreshContacts()
        }
      }, 20_000)
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  if (sessionRosterTimer != null) {
    clearInterval(sessionRosterTimer)
  }
})

watch(
  () => [props.sessionId, props.collabRoomCode, props.collabVisibility] as const,
  () => {
    void refreshContacts()
  },
)

function handleStartDm(partnerId: number): void {
  emit('startDm', partnerId)
  emit('message', partnerId)
}

async function handlePoke(targetUserId: number): Promise<void> {
  if (!props.sessionId || pokingUserId.value != null) {
    return
  }
  pokingUserId.value = targetUserId
  try {
    const response = await authFetch('/api/mindmate/collab/poke', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: props.sessionId,
        target_user_id: targetUserId,
      }),
    })
    if (response.ok) {
      const data = (await response.json()) as { delivered?: boolean }
      if (data.delivered) {
        notify.success(t('mindmate.collabPokeSent'))
      } else {
        notify.info(t('mindmate.collabPokeOffline'))
      }
    } else {
      notify.error(t('mindmate.collabPokeFailed'))
    }
  } catch {
    notify.error(t('mindmate.collabPokeFailed'))
  } finally {
    pokingUserId.value = null
    contactPopoverUserId.value = null
  }
}
</script>

<template>
  <div
    class="org-contacts-panel flex flex-col h-full min-h-0"
    :class="{ 'org-contacts-panel--compact bg-stone-50': isCompact }"
  >
    <div
      class="org-contacts-panel__header shrink-0 border-b border-stone-200"
      :class="isCompact ? 'px-3 py-2.5 bg-white border-stone-200/90' : 'px-3 py-3'"
    >
      <div
        v-if="!isCompact"
        class="flex items-center justify-between mb-2"
      >
        <span class="text-xs font-medium text-stone-500 uppercase tracking-wide">
          {{ t('workshop.contacts') }}
        </span>
        <span class="text-xs text-stone-400">
          {{ presence.contactsOnlineCount }} {{ t('workshop.online') }}
        </span>
      </div>

      <div
        v-if="isCompact && isPublicCollabSeminar"
        class="mb-2 text-[11px] font-medium text-stone-500"
      >
        {{ t('mindmate.collabSessionMembersTitle') }}
      </div>
      <div
        v-if="isCompact"
        class="org-contacts-panel__search-wrap relative"
      >
        <Search
          class="org-contacts-panel__search-icon"
          :size="14"
          aria-hidden="true"
        />
        <input
          v-model="contactsSearchInput"
          type="search"
          class="org-contacts-panel__search"
          :placeholder="t('workshop.searchMembers')"
          :aria-label="t('workshop.searchMembers')"
        />
      </div>
      <ElInput
        v-else
        v-model="contactsSearchInput"
        type="search"
        clearable
        size="small"
        :placeholder="t('workshop.searchMembers')"
      />
    </div>

    <div
      class="org-contacts-panel__scroll flex-1 min-h-0 overflow-y-auto"
      :class="isCompact ? 'py-1' : 'px-2 py-2'"
    >
      <div
        v-if="loading && members.length === 0"
        class="px-3 py-8 text-center text-xs text-stone-400"
      >
        {{ t('common.loading') }}
      </div>

      <template v-else>
        <template
          v-for="section in displaySections"
          :key="section.key"
        >
          <div
            v-if="section.labelKey && !isCompact"
            class="text-[10px] font-medium text-stone-400 uppercase tracking-wide px-1 py-2"
          >
            {{ t(section.labelKey) }}
          </div>
          <ul
            class="org-contacts-panel__list"
            :class="{ 'org-contacts-panel__list--compact': isCompact }"
          >
            <li
              v-for="member in section.members"
              :key="`${section.key}-${member.id}`"
            >
              <UserCardPopover
                :user="{ id: member.id, name: member.name, avatar: member.avatar }"
                :visible="contactPopoverUserId === member.id"
                :channel-context="false"
                :collab-context="collabContext"
                :member-online="presence.isUserOnline(member.id)"
                @update:visible="contactPopoverUserId = $event ? member.id : null"
                @start-dm="handleStartDm"
                @view-profile="emit('viewProfile', $event)"
                @manage-user="emit('manageUser', $event)"
                @poke="handlePoke"
              >
                <component
                  :is="isCompact ? 'button' : 'div'"
                  :type="isCompact ? 'button' : undefined"
                  class="org-contacts-panel__row"
                  :class="{
                    'org-contacts-panel__row--compact': isCompact,
                    'flex items-start gap-2 px-2 py-1.5 rounded-lg hover:bg-stone-100 cursor-pointer':
                      !isCompact,
                  }"
                >
                  <span
                    class="org-contacts-panel__presence shrink-0 rounded-full"
                    :class="[
                      isCompact ? 'org-contacts-panel__presence--compact' : 'mt-1.5 w-2 h-2',
                      presenceDotClass(section.key),
                    ]"
                    aria-hidden="true"
                  />
                  <div
                    class="min-w-0 flex-1 text-left"
                    :class="isCompact ? '' : ''"
                  >
                    <div
                      class="truncate"
                      :class="
                        isCompact
                          ? 'org-contacts-panel__name text-[13px] font-medium text-stone-700'
                          : [
                              'text-sm',
                              section.key === 'online'
                                ? 'text-stone-800 font-medium'
                                : 'text-stone-600',
                            ]
                      "
                    >
                      {{ member.name
                      }}<span
                        v-if="presence.isContactSelf(member.id)"
                        class="text-stone-400 text-xs ml-1"
                        >{{ t('workshop.you') }}</span
                      >
                    </div>
                    <div
                      v-if="!effectiveZulipPresence && section.key === 'recently_online'"
                      class="text-[11px] text-stone-400 truncate"
                    >
                      {{ presence.contactLastOnlineSubtitle(member.id) }}
                    </div>
                  </div>
                </component>
              </UserCardPopover>
            </li>
          </ul>
        </template>

        <div
          v-if="members.length === 0 && !loading"
          class="text-xs text-stone-400 text-center py-6"
          :class="{ 'py-10 leading-relaxed': isCompact }"
        >
          {{ t('workshop.noMembersFound') }}
        </div>
      </template>
    </div>

    <div
      v-if="membersTotal > 0"
      class="org-contacts-panel__footer shrink-0 border-t border-stone-200 text-xs text-stone-400 flex items-center justify-between gap-2"
      :class="isCompact ? 'px-3 py-2 bg-white border-stone-200/90' : 'px-3 py-2'"
    >
      <span :class="{ 'text-[11px] tabular-nums': isCompact }">
        {{
          t('workshop.contactsLoadedCount')
            .replace('{0}', String(members.length))
            .replace('{1}', String(membersTotal))
        }}
      </span>
      <ElButton
        v-if="membersHasMore && !isCompact"
        text
        size="small"
        type="primary"
        :loading="loadingMore"
        @click="loadMoreContacts"
      >
        {{ t('workshop.loadMore') }}
      </ElButton>
      <button
        v-else-if="membersHasMore && isCompact"
        type="button"
        class="org-contacts-panel__load-more"
        :disabled="loadingMore"
        @click="loadMoreContacts"
      >
        {{ t('workshop.loadMore') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.org-contacts-panel__search-wrap {
  position: relative;
}

.org-contacts-panel__search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: #a8a29e;
  pointer-events: none;
}

.org-contacts-panel__search {
  width: 100%;
  box-sizing: border-box;
  padding: 7px 10px 7px 32px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.35;
  color: #1c1917;
  background: #fafaf9;
  border: 1px solid #e7e5e4;
  border-radius: 8px;
  outline: none;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    background 0.15s ease;
}

.org-contacts-panel__search::placeholder {
  color: #a8a29e;
  font-weight: 400;
}

.org-contacts-panel__search:focus {
  background: #fff;
  border-color: #d6d3d1;
  box-shadow: 0 0 0 3px rgba(231, 229, 228, 0.55);
}

.org-contacts-panel__scroll::-webkit-scrollbar {
  width: 4px;
}

.org-contacts-panel__scroll::-webkit-scrollbar-thumb {
  background: #e7e5e4;
  border-radius: 2px;
}

.org-contacts-panel__list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.org-contacts-panel__list--compact {
  padding: 0 6px 4px;
}

.org-contacts-panel__row--compact {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 7px 8px;
  margin: 1px 0;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 0.12s ease;
}

.org-contacts-panel__row--compact:hover {
  background: #f5f5f4;
}

.org-contacts-panel__presence--compact {
  width: 8px;
  height: 8px;
  margin-top: 1px;
}

.org-contacts-panel__presence--compact.bg-green-500 {
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.18);
}

.org-contacts-panel__load-more {
  font-size: 11px;
  font-weight: 500;
  color: #57534e;
  background: #f5f5f4;
  border: 1px solid #e7e5e4;
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
  transition:
    background 0.12s ease,
    border-color 0.12s ease;
}

.org-contacts-panel__load-more:hover:not(:disabled) {
  background: #e7e5e4;
  border-color: #d6d3d1;
}

.org-contacts-panel__load-more:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
