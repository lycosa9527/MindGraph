<script setup lang="ts">
/**
 * Hover roster under header faces: members, roles, online, leader controls.
 */
import { computed, ref, watch } from 'vue'

import { Plus, Trash2 } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import MindmateMentionMenu from '@/components/mindmate/MindmateMentionMenu.vue'
import MindmateSeminarRoleIcon from '@/components/mindmate/MindmateSeminarRoleIcon.vue'
import { swissGlassConfirm, useLanguage } from '@/composables'
import {
  requestSeminarMention,
  seminarSpectator,
} from '@/composables/mindmate/mindmateSeminarChrome'
import { useSeminarMemberPresence } from '@/composables/mindmate/useSeminarMemberPresence'
import { SEMINAR_BRIEF_ROLE_OPTIONS, type SeminarBriefRole } from '@/utils/mindmateSeminarBrief'
import type { SeminarGroupMember } from '@/utils/mindmateSeminarGroup'
import { seminarAvatarSurname, seminarAvatarTone } from '@/utils/seminarAvatarSurname'

const props = defineProps<{
  open: boolean
  members: SeminarGroupMember[]
  /** Current user is the seminar leader (role), not merely the room creator. */
  isLeader: boolean
  selfUserId?: number
  busy?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'add'): void
  (e: 'changeRole', userId: number, role: SeminarBriefRole): void
  (e: 'remove', userId: number): void
}>()

const { t } = useLanguage()
const { isOnline, presenceRank, statusText } = useSeminarMemberPresence()
const root = ref<HTMLElement | null>(null)
const mentionMenu = ref<{ x: number; y: number; name: string } | null>(null)
let hideTimer: ReturnType<typeof setTimeout> | null = null

function canMentionMember(member: SeminarGroupMember): boolean {
  const name = member.name.trim()
  if (!name || seminarSpectator.value) {
    return false
  }
  return props.selfUserId == null || member.userId !== props.selfUserId
}

function onMemberAvatarMenu(event: MouseEvent, member: SeminarGroupMember): void {
  if (!canMentionMember(member)) {
    return
  }
  event.preventDefault()
  event.stopPropagation()
  keepOpen()
  mentionMenu.value = {
    x: event.clientX,
    y: event.clientY,
    name: member.name.trim(),
  }
}

function chooseMention(): void {
  const name = mentionMenu.value?.name || ''
  mentionMenu.value = null
  if (name) {
    requestSeminarMention(name)
  }
}

const sorted = computed(() =>
  [...props.members].sort((left, right) => {
    if (left.isLeader !== right.isLeader) {
      return left.isLeader ? -1 : 1
    }
    const presenceDiff =
      presenceRank(left.userId, left.online, left.lastSeenAt) -
      presenceRank(right.userId, right.online, right.lastSeenAt)
    if (presenceDiff !== 0) {
      return presenceDiff
    }
    return left.name.localeCompare(right.name, 'zh-Hans-CN')
  })
)

function roleLabel(role: SeminarBriefRole): string {
  return t(`mindmate.home.brief.role.${role}`)
}

function memberRoleValue(member: SeminarGroupMember): SeminarBriefRole {
  return member.role === 'none' ? 'observer' : member.role
}

async function onRoleSelect(member: SeminarGroupMember, event: Event): Promise<void> {
  const select = event.target as HTMLSelectElement
  const role = select.value as SeminarBriefRole
  const previous = memberRoleValue(member)
  if (role === 'leader') {
    try {
      await swissGlassConfirm(
        t('mindmate.home.brief.transferLeaderConfirm', { name: member.name }),
        t('mindmate.home.brief.transferLeaderTitle'),
        {
          confirmButtonText: t('common.confirm'),
          cancelButtonText: t('common.cancel'),
          type: 'warning',
        }
      )
    } catch {
      select.value = previous
      return
    }
  }
  emit('changeRole', member.userId, role)
}

function keepOpen(): void {
  if (hideTimer != null) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
}

function scheduleClose(): void {
  keepOpen()
  hideTimer = setTimeout(() => {
    hideTimer = null
    if (mentionMenu.value) {
      return
    }
    emit('close')
  }, 180)
}

watch(
  () => props.open,
  (open) => {
    if (!open) {
      keepOpen()
    }
  }
)

defineExpose({ keepOpen, scheduleClose })
</script>

<template>
  <div
    v-if="open"
    ref="root"
    class="mm-members-pop"
    @mouseenter="keepOpen"
    @mouseleave="scheduleClose"
  >
    <header class="mm-members-pop__head">
      <span><I18nText k="mindmate.collabSessionMembersTitle" /></span>
      <span class="mm-members-pop__count">{{ members.length }}</span>
    </header>

    <ul class="mm-members-pop__list">
      <li
        v-for="member in sorted"
        :key="member.userId"
        class="mm-members-pop__row"
      >
        <span
          class="mm-members-pop__avatar"
          :class="{
            'is-offline': !isOnline(member.userId, member.online),
            'is-mentionable': canMentionMember(member),
          }"
          :style="{
            background: seminarAvatarTone(member.userId).background,
            color: seminarAvatarTone(member.userId).color,
          }"
          @contextmenu="onMemberAvatarMenu($event, member)"
        >
          {{ seminarAvatarSurname(member.name) }}
          <span
            class="mm-members-pop__dot"
            :class="{ 'is-on': isOnline(member.userId, member.online) }"
            aria-hidden="true"
          />
        </span>
        <div class="mm-members-pop__meta">
          <span class="mm-members-pop__name">
            {{ member.name }}
            <span
              v-if="member.isLeader"
              class="mm-members-pop__tag"
              ><I18nText k="mindmate.home.brief.role.leader"
            /></span>
          </span>
          <span class="mm-members-pop__status">
            <I18nText
              v-if="member.pending"
              k="mindmate.home.brief.pendingConsent"
            /><template v-else>{{
              statusText(member.userId, member.online, member.lastSeenAt)
            }}</template>
          </span>
        </div>
        <span class="mm-members-pop__role-wrap">
          <MindmateSeminarRoleIcon
            :role="member.isLeader ? 'leader' : memberRoleValue(member)"
            :size="22"
          />
          <select
            v-if="isLeader && !member.isLeader && member.userId !== selfUserId"
            class="mm-members-pop__role"
            :disabled="busy"
            :value="memberRoleValue(member)"
            @change="onRoleSelect(member, $event)"
          >
            <option
              v-for="role in SEMINAR_BRIEF_ROLE_OPTIONS"
              :key="role"
              :value="role"
            >
              {{ roleLabel(role) }}
            </option>
          </select>
          <span
            v-else
            class="mm-members-pop__role-text"
            >{{ roleLabel(member.role === 'none' ? 'observer' : member.role) }}</span
          >
        </span>
        <button
          v-if="isLeader && !member.isLeader && member.userId !== selfUserId"
          type="button"
          class="mm-members-pop__remove"
          :disabled="busy"
          :aria-label="t('mindmate.home.brief.remove')"
          @click="emit('remove', member.userId)"
        >
          <Trash2 :size="14" />
        </button>
      </li>
    </ul>

    <button
      v-if="!seminarSpectator"
      type="button"
      class="mm-members-pop__add"
      :disabled="busy"
      @click="emit('add')"
    >
      <Plus :size="14" />
      <I18nText k="mindmate.home.addMembers" />
    </button>
  </div>
  <MindmateMentionMenu
    v-if="mentionMenu"
    :x="mentionMenu.x"
    :y="mentionMenu.y"
    :name="mentionMenu.name"
    @choose="chooseMention"
    @close="mentionMenu = null"
  />
</template>

<style scoped>
.mm-members-pop {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 40;
  width: min(360px, 82vw);
  padding: 10px;
  border: 1px solid #e9e5ff;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 14px 36px rgba(76, 61, 180, 0.14);
}

.mm-members-pop__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 2px 4px 8px;
  font-size: 13px;
  font-weight: 650;
  color: #1c1917;
}

.mm-members-pop__count {
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: #f5f3ff;
  color: #6d5efc;
  font-size: 11px;
  font-weight: 650;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.mm-members-pop__list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 280px;
  overflow: auto;
}

.mm-members-pop__row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto 28px;
  align-items: center;
  gap: 8px;
  padding: 8px 4px;
  border-radius: 10px;
}

.mm-members-pop__row:hover {
  background: #faf8ff;
}

.mm-members-pop__avatar {
  position: relative;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 650;
}

.mm-members-pop__avatar.is-offline {
  filter: grayscale(0.35);
  opacity: 0.78;
}

.mm-members-pop__avatar.is-mentionable {
  cursor: context-menu;
}

.mm-members-pop__dot {
  position: absolute;
  right: -1px;
  bottom: -1px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  border: 2px solid #fff;
  background: #d6d3d1;
}

.mm-members-pop__dot.is-on {
  background: #22c55e;
}

.mm-members-pop__meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mm-members-pop__name {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-size: 13px;
  font-weight: 600;
  color: #1c1917;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-members-pop__tag {
  flex-shrink: 0;
  padding: 1px 6px;
  border-radius: 999px;
  background: #ede9fe;
  color: #6d28d9;
  font-size: 10px;
  font-weight: 650;
}

.mm-members-pop__status {
  font-size: 11px;
  color: #a8a29e;
}

.mm-members-pop__role-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  min-width: 0;
}

.mm-members-pop__role,
.mm-members-pop__role-text {
  width: 96px;
  font-size: 11px;
  color: #57534e;
}

.mm-members-pop__role {
  height: 28px;
  padding: 0 6px;
  border: 1px solid #e9e5ff;
  border-radius: 8px;
  background: #fff;
}

.mm-members-pop__role-text {
  text-align: right;
}

.mm-members-pop__remove {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #a8a29e;
  cursor: pointer;
}

.mm-members-pop__remove:hover:not(:disabled) {
  background: #fef2f2;
  color: #ef4444;
}

.mm-members-pop__add {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  margin-top: 8px;
  height: 34px;
  border: 1px dashed #c4b5fd;
  border-radius: 10px;
  background: #faf8ff;
  color: #6d5efc;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.mm-members-pop__add:hover:not(:disabled) {
  background: #f5f3ff;
}
</style>
