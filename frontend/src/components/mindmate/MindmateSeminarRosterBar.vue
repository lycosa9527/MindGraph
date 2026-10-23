<script setup lang="ts">
/**
 * Seminar roster chrome: faces with hover panel; opens members task pane on click.
 */
import { ref } from 'vue'

import MindmateSeminarFaces from '@/components/mindmate/MindmateSeminarFaces.vue'
import MindmateSeminarMembersPopover from '@/components/mindmate/MindmateSeminarMembersPopover.vue'
import { useLanguage } from '@/composables'
import type { SeminarBriefRole } from '@/utils/mindmateSeminarBrief'
import type { SeminarGroupMember } from '@/utils/mindmateSeminarGroup'

defineProps<{
  membersOpen?: boolean
  members?: SeminarGroupMember[]
  isLeader?: boolean
  /** @deprecated use isLeader */
  isHost?: boolean
  selfUserId?: number
  busy?: boolean
}>()

const emit = defineEmits<{
  (e: 'toggleMembers'): void
  (e: 'addMembers'): void
  (e: 'changeRole', userId: number, role: SeminarBriefRole): void
  (e: 'removeMember', userId: number): void
}>()

const { t } = useLanguage()
const popoverOpen = ref(false)
const popover = ref<{ keepOpen: () => void; scheduleClose: () => void } | null>(null)

function openPopover(): void {
  popoverOpen.value = true
  popover.value?.keepOpen()
}

function scheduleClosePopover(): void {
  popover.value?.scheduleClose()
}
</script>

<template>
  <div class="seminar-roster-bar">
    <div
      class="seminar-roster-bar__faces-wrap"
      @mouseenter="openPopover"
      @mouseleave="scheduleClosePopover"
      @focusin="openPopover"
    >
      <button
        type="button"
        class="seminar-roster-bar__faces"
        :aria-expanded="popoverOpen || membersOpen"
        :aria-label="t('mindmate.collabSessionMembersTitle')"
        @click="emit('toggleMembers')"
      >
        <MindmateSeminarFaces />
      </button>
      <MindmateSeminarMembersPopover
        ref="popover"
        :open="popoverOpen"
        :members="members || []"
        :is-leader="Boolean(isLeader ?? isHost)"
        :self-user-id="selfUserId"
        :busy="busy"
        @close="popoverOpen = false"
        @add="emit('addMembers')"
        @change-role="(userId, role) => emit('changeRole', userId, role)"
        @remove="(userId) => emit('removeMember', userId)"
      />
    </div>
  </div>
</template>

<style scoped>
.seminar-roster-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.seminar-roster-bar__faces-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.seminar-roster-bar__faces {
  display: inline-flex;
  align-items: center;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
}
</style>
