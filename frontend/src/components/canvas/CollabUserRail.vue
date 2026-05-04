<script setup lang="ts">
/**
 * CollabUserRail - Fixed left-side participant rail for active collab sessions.
 * Shows a stacked list of avatar circles (first char of username) for every
 * participant. Visible only when a workshop session is active.
 */
import { computed } from 'vue'

import { ElTooltip } from 'element-plus'

import { useLanguage } from '@/composables'
import type { ParticipantInfo } from '@/composables/workshop/useWorkshop'
import { colorForUser } from '@/shared/collabPalette'

const { t } = useLanguage()

const props = defineProps<{
  workshopCode: string | null
  participants: ParticipantInfo[] | undefined
}>()

function getUserColor(userId: number): string {
  return colorForUser(userId)
}

/** First character suitable for an avatar (handles CJK, Latin, emoji). */
function avatarChar(username: string): string {
  return username.trim().charAt(0).toUpperCase() || '?'
}

/** Short display label: first word / segment of username, capped at 6 chars. */
function shortName(username: string): string {
  const first = username.trim().split(/[\s_-]+/)[0]
  return first.length > 6 ? first.slice(0, 6) : first
}

/**
 * Windowed rendering budget. Rooms with more than MAX_VISIBLE_PARTICIPANTS
 * participants collapse the tail into a "+N more" pill so the DOM cost of the
 * rail stays bounded even for a 500-user webinar-style workshop. The full
 * list is still available via the participants tooltip on the overflow pill.
 */
const MAX_VISIBLE_PARTICIPANTS = 30

const visibleParticipants = computed(() => {
  const list = props.participants ?? []
  return list.length > MAX_VISIBLE_PARTICIPANTS ? list.slice(0, MAX_VISIBLE_PARTICIPANTS) : list
})

const overflowCount = computed(() => {
  const total = props.participants?.length ?? 0
  return total > MAX_VISIBLE_PARTICIPANTS ? total - MAX_VISIBLE_PARTICIPANTS : 0
})

const overflowTooltip = computed(() => {
  const list = props.participants ?? []
  if (list.length <= MAX_VISIBLE_PARTICIPANTS) return ''
  const hiddenNames = list
    .slice(MAX_VISIBLE_PARTICIPANTS)
    .map((p) => p.username)
    .slice(0, 50)
  return hiddenNames.join(', ')
})

const visible = computed(() => !!props.workshopCode && (props.participants?.length ?? 0) > 0)
</script>

<template>
  <Transition name="rail-fade">
    <div
      v-if="visible"
      class="collab-user-rail"
      role="list"
      :aria-label="t('canvasPage.collabParticipantsAria')"
    >
      <ElTooltip
        v-for="participant in visibleParticipants"
        :key="participant.user_id"
        :content="participant.username"
        placement="right"
        :show-after="300"
      >
        <div
          class="rail-entry"
          role="listitem"
        >
          <div
            class="rail-avatar"
            :style="{ backgroundColor: getUserColor(participant.user_id) }"
          >
            {{ avatarChar(participant.username) }}
          </div>
          <span class="rail-label">{{ shortName(participant.username) }}</span>
        </div>
      </ElTooltip>
      <ElTooltip
        v-if="overflowCount > 0"
        :content="overflowTooltip"
        placement="right"
        :show-after="300"
      >
        <div
          class="rail-entry"
          role="listitem"
        >
          <div class="rail-avatar rail-avatar--overflow">+{{ overflowCount }}</div>
          <span class="rail-label">{{ t('canvasPage.collabParticipantsMore') }}</span>
        </div>
      </ElTooltip>
    </div>
  </Transition>
</template>

<style scoped>
.collab-user-rail {
  position: fixed;
  left: 0;
  top: 56px; /* below topbar (~48px) + small gap */
  z-index: 30;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 8px 6px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
  border-right: 1px solid rgba(0, 0, 0, 0.07);
  border-radius: 0 10px 10px 0;
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.06);
  max-height: calc(100vh - 72px);
  overflow-y: auto;
  scrollbar-width: none;
  pointer-events: auto;
}

.collab-user-rail::-webkit-scrollbar {
  display: none;
}

.rail-entry {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  cursor: default;
}

.rail-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  border: 2px solid rgba(255, 255, 255, 0.6);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
  transition: transform 0.15s ease;
  user-select: none;
}

.rail-avatar--overflow {
  background: #64748b;
  font-size: 11px;
}

.rail-entry:hover .rail-avatar {
  transform: scale(1.08);
}

.rail-label {
  font-size: 9px;
  font-weight: 500;
  color: #555;
  max-width: 40px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: center;
  line-height: 1.2;
}

/* Entry / exit animation */
.rail-fade-enter-active,
.rail-fade-leave-active {
  transition:
    opacity 0.25s ease,
    transform 0.25s ease;
}

.rail-fade-enter-from,
.rail-fade-leave-to {
  opacity: 0;
  transform: translateX(-8px);
}

/* Dark mode */
:global(.dark) .collab-user-rail {
  background: rgba(30, 30, 40, 0.92);
  border-right-color: rgba(255, 255, 255, 0.07);
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.3);
}

:global(.dark) .rail-label {
  color: #aaa;
}
</style>
