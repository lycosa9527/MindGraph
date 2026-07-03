<script setup lang="ts">
/**
 * MindMate collab — school member list (right column, Swiss / Zulip-style).
 */
import { computed, onMounted, ref } from 'vue'

import { Search } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { useMindmateCollabOrgMembers } from '@/composables/mindmate/useMindmateCollabOrgMembers'
import UserCardPopover from '@/components/workshop-chat/UserCardPopover.vue'
import { authFetch } from '@/utils/api'

const props = defineProps<{
  sessionId: string
  roomCode: string
  roomTitle: string
}>()

const emit = defineEmits<{
  (e: 'message', partnerId: number): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const {
  members,
  membersTotal,
  membersHasMore,
  loading,
  loadingMore,
  contactsSearchInput,
  displaySections,
  isContactSelf,
  refreshContacts,
  loadMoreContacts,
} = useMindmateCollabOrgMembers()

const contactPopoverUserId = ref<number | null>(null)
const pokingUserId = ref<number | null>(null)

const sortedMembers = computed(() =>
  displaySections.value.flatMap((section) =>
    section.members.map((member) => ({
      member,
      online: section.key === 'online',
    })),
  ),
)

onMounted(() => {
  void refreshContacts()
})

function handleStartDm(partnerId: number): void {
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
  <div class="mmc-members flex flex-col h-full min-h-0 bg-stone-50">
    <header class="mmc-members__header shrink-0 px-3 py-2.5 border-b border-stone-200/90 bg-white">
      <div class="mmc-members__search-wrap relative">
        <Search
          class="mmc-members__search-icon"
          :size="14"
          aria-hidden="true"
        />
        <input
          v-model="contactsSearchInput"
          type="search"
          class="mmc-members__search"
          :placeholder="t('workshop.searchMembers')"
          :aria-label="t('workshop.searchMembers')"
        />
      </div>
    </header>

    <div class="mmc-members__scroll flex-1 min-h-0 overflow-y-auto py-1">
      <div
        v-if="loading && members.length === 0"
        class="px-3 py-8 text-center text-xs text-stone-400"
      >
        {{ t('common.loading') }}
      </div>

      <ul
        v-else-if="sortedMembers.length > 0"
        class="mmc-members__list"
      >
        <li
          v-for="{ member, online } in sortedMembers"
          :key="member.id"
        >
          <UserCardPopover
            :user="{ id: member.id, name: member.name, avatar: member.avatar }"
            :visible="contactPopoverUserId === member.id"
            :channel-context="false"
            collab-context
            @update:visible="contactPopoverUserId = $event ? member.id : null"
            @start-dm="handleStartDm"
            @poke="handlePoke"
          >
            <button
              type="button"
              class="mmc-members__row"
            >
              <span
                class="mmc-members__dot shrink-0"
                :class="online ? 'mmc-members__dot--online' : 'mmc-members__dot--offline'"
                aria-hidden="true"
              />
              <span class="mmc-members__name truncate">
                {{ member.name }}
                <span
                  v-if="isContactSelf(member.id)"
                  class="mmc-members__you"
                >
                  {{ t('workshop.you') }}
                </span>
              </span>
            </button>
          </UserCardPopover>
        </li>
      </ul>

      <div
        v-else-if="!loading"
        class="px-3 py-10 text-center text-xs text-stone-400 leading-relaxed"
      >
        {{ t('workshop.noMembersFound') }}
      </div>
    </div>

    <footer
      v-if="membersTotal > 0"
      class="mmc-members__footer shrink-0 px-3 py-2 border-t border-stone-200/90 bg-white flex items-center justify-between gap-2"
    >
      <span class="text-[11px] text-stone-400 tabular-nums">
        {{
          t('workshop.contactsLoadedCount')
            .replace('{0}', String(members.length))
            .replace('{1}', String(membersTotal))
        }}
      </span>
      <button
        v-if="membersHasMore"
        type="button"
        class="mmc-members__load-more"
        :disabled="loadingMore"
        @click="loadMoreContacts"
      >
        {{ t('workshop.loadMore') }}
      </button>
    </footer>
  </div>
</template>

<style scoped>
.mmc-members__search-wrap {
  position: relative;
}

.mmc-members__search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: #a8a29e;
  pointer-events: none;
}

.mmc-members__search {
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
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

.mmc-members__search::placeholder {
  color: #a8a29e;
  font-weight: 400;
}

.mmc-members__search:focus {
  background: #fff;
  border-color: #d6d3d1;
  box-shadow: 0 0 0 3px rgba(231, 229, 228, 0.55);
}

.mmc-members__scroll::-webkit-scrollbar {
  width: 4px;
}

.mmc-members__scroll::-webkit-scrollbar-thumb {
  background: #e7e5e4;
  border-radius: 2px;
}

.mmc-members__list {
  list-style: none;
  margin: 0;
  padding: 0 6px 4px;
}

.mmc-members__row {
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

.mmc-members__row:hover {
  background: #f5f5f4;
}

.mmc-members__dot {
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  margin-top: 1px;
}

.mmc-members__dot--online {
  background: #22c55e;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.18);
}

.mmc-members__dot--offline {
  background: #d6d3d1;
}

.mmc-members__name {
  font-size: 13px;
  font-weight: 500;
  color: #44403c;
  line-height: 1.35;
  min-width: 0;
}

.mmc-members__you {
  margin-left: 4px;
  font-size: 11px;
  font-weight: 400;
  color: #a8a29e;
}

.mmc-members__load-more {
  font-size: 11px;
  font-weight: 500;
  color: #57534e;
  background: #f5f5f4;
  border: 1px solid #e7e5e4;
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
  transition: background 0.12s ease, border-color 0.12s ease;
}

.mmc-members__load-more:hover:not(:disabled) {
  background: #e7e5e4;
  border-color: #d6d3d1;
}

.mmc-members__load-more:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
