<script setup lang="ts">
/**
 * Hover roster under header faces: members, roles, online, leader controls.
 */
import { computed, ref, watch } from 'vue'

import { Plus, Trash2 } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import MindmateMentionMenu from '@/components/mindmate/MindmateMentionMenu.vue'
import MindmateSeminarRoleSelect from '@/components/mindmate/MindmateSeminarRoleSelect.vue'
import { swissGlassConfirm, useLanguage } from '@/composables'
import {
  requestSeminarMention,
  seminarSpectator,
} from '@/composables/mindmate/mindmateSeminarChrome'
import { seminarShowsMemberOrg } from '@/composables/mindmate/seminarGroupRoster'
import { useSeminarMemberPresence } from '@/composables/mindmate/useSeminarMemberPresence'
import {
  type SeminarBriefRole,
  isSeminarBuiltinRole,
} from '@/utils/mindmateSeminarBrief'
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
const { isOnline, presenceRank } = useSeminarMemberPresence()
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
  if (isSeminarBuiltinRole(role) || role === 'none') {
    return t(`mindmate.home.brief.role.${role === 'none' ? 'observer' : role}`)
  }
  return role
}

function memberRoleValue(member: SeminarGroupMember): SeminarBriefRole {
  return member.role === 'none' ? 'observer' : member.role
}

async function onRoleUpdate(member: SeminarGroupMember, role: SeminarBriefRole): Promise<void> {
  if (role === memberRoleValue(member)) {
    return
  }
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
            v-if="isOnline(member.userId, member.online)"
            class="mm-members-pop__dot is-on"
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
          <span
            v-if="member.pending"
            class="mm-members-pop__pending"
          >
            <I18nText k="mindmate.home.brief.pendingConsent" />
          </span>
          <span
            v-if="seminarShowsMemberOrg && member.organizationName"
            class="mm-members-pop__org"
            >{{ member.organizationName }}</span
          >
        </div>
        <span class="mm-members-pop__role-wrap">
          <MindmateSeminarRoleSelect
            v-if="isLeader && !member.isLeader && member.userId !== selfUserId"
            :model-value="memberRoleValue(member)"
            :disabled="busy"
            @update:model-value="onRoleUpdate(member, $event)"
          />
          <span
            v-else
            class="mm-members-pop__role-text"
            :class="{ 'is-custom': !isSeminarBuiltinRole(memberRoleValue(member)) }"
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
        <p
          v-if="
            isLeader &&
            !member.isLeader &&
            member.userId !== selfUserId &&
            memberRoleValue(member) === 'observer'
          "
          class="mm-members-pop__role-note"
        >
          <I18nText k="mindmate.home.brief.role.observerHint" />
        </p>
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

    <MindmateMentionMenu
      v-if="mentionMenu"
      :x="mentionMenu.x"
      :y="mentionMenu.y"
      :name="mentionMenu.name"
      @choose="chooseMention"
      @close="mentionMenu = null"
    />
  </div>
</template>

<style scoped>
.mm-members-pop {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 40;
  width: min(360px, calc(100vw - 24px));
  padding: 10px;
  border: 1px solid #e9e5ff;
  border-radius: 14px;
  background: #fff;
  box-shadow:
    0 10px 30px rgba(28, 25, 23, 0.12),
    0 2px 8px rgba(28, 25, 23, 0.06);
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
  font-size: 12px;
  font-weight: 500;
  color: #a8a29e;
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
  grid-template-columns: 34px minmax(0, 1fr) auto auto;
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
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 650;
  flex-shrink: 0;
}

.mm-members-pop__avatar.is-offline {
  opacity: 0.55;
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
  font-size: 13px;
  font-weight: 600;
  color: #1c1917;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-members-pop__tag {
  margin-left: 4px;
  font-size: 11px;
  font-weight: 500;
  color: #7c3aed;
}

.mm-members-pop__pending,
.mm-members-pop__org {
  font-size: 11px;
  color: #a8a29e;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-members-pop__role-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  min-width: 0;
}

.mm-members-pop__role-note {
  grid-column: 1 / -1;
  margin: 0;
  font-size: 11px;
  line-height: 1.45;
  color: #a8a29e;
}

.mm-members-pop__role-text {
  max-width: 108px;
  font-size: 11px;
  color: #57534e;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-members-pop__role-text.is-custom {
  color: #5b21b6;
  font-weight: 600;
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
  color: #1c1917;
  background: #f5f5f4;
}

.mm-members-pop__remove:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.mm-members-pop__add {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  margin-top: 8px;
  min-height: 34px;
  border: 1px dashed #ddd6fe;
  border-radius: 10px;
  background: #faf8ff;
  color: #5b21b6;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.mm-members-pop__add:hover:not(:disabled) {
  background: #f5f3ff;
}

.mm-members-pop__add:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
