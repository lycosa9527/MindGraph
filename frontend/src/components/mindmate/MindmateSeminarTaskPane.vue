<script setup lang="ts">
/**
 * PowerPoint-style right task pane: vertical icon rail + content drawer.
 */
import { computed, ref, watch } from 'vue'

import { Archive, Folder, Plus, Search, Trash2, Users, X } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import MindmateMentionMenu from '@/components/mindmate/MindmateMentionMenu.vue'
import MindmateSeminarArtifactsDrawer from '@/components/mindmate/MindmateSeminarArtifactsDrawer.vue'
import MindmateSeminarFolderDrawer from '@/components/mindmate/MindmateSeminarFolderDrawer.vue'
import MindmateSeminarHighlightsDrawer from '@/components/mindmate/MindmateSeminarHighlightsDrawer.vue'
import MindmateSoftIcon from '@/components/mindmate/MindmateSoftIcon.vue'
import { swissGlassConfirm, useLanguage } from '@/composables'
import {
  type SeminarTaskPaneTab,
  closeSeminarTaskDrawer,
  loadSeminarHighlights,
  requestSeminarMention,
  seminarLiveMessages,
  seminarSpectator,
  seminarTaskPaneTab,
  toggleSeminarTaskPane,
} from '@/composables/mindmate/mindmateSeminarChrome'
import { SEMINAR_BRIEF_ROLE_OPTIONS, type SeminarBriefRole } from '@/utils/mindmateSeminarBrief'
import type { SeminarGroupMember } from '@/utils/mindmateSeminarGroup'
import { seminarAvatarSurname, seminarAvatarTone } from '@/utils/seminarAvatarSurname'

const props = defineProps<{
  sessionId: string
  members: SeminarGroupMember[]
  isLeader?: boolean
  selfUserId?: number
  busy?: boolean
}>()

const emit = defineEmits<{
  (e: 'addMembers'): void
  (e: 'changeRole', userId: number, role: SeminarBriefRole): void
  (e: 'removeMember', userId: number): void
}>()

const { t } = useLanguage()
const memberQuery = ref('')
const mentionMenu = ref<{ x: number; y: number; name: string } | null>(null)

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

const activeTab = computed(() => seminarTaskPaneTab.value)
const paneOpen = computed(() => activeTab.value != null)

const navItems: {
  id: SeminarTaskPaneTab
  icon: typeof Users | 'highlights'
  labelKey: string
}[] = [
  { id: 'members', icon: Users, labelKey: 'mindmate.taskPane.members' },
  { id: 'files', icon: Folder, labelKey: 'mindmate.taskPane.files' },
  { id: 'artifacts', icon: Archive, labelKey: 'mindmate.taskPane.artifacts' },
  { id: 'highlights', icon: 'highlights', labelKey: 'mindmate.taskPane.highlights' },
]

const paneTitleKey = computed(() => {
  if (activeTab.value === 'members') {
    return 'mindmate.taskPane.membersHeading'
  }
  if (activeTab.value === 'files') {
    return 'mindmate.folder.title'
  }
  if (activeTab.value === 'artifacts') {
    return 'mindmate.artifacts.title'
  }
  if (activeTab.value === 'highlights') {
    return 'mindmate.highlights.title'
  }
  return 'mindmate.home.groupInfo'
})

watch(
  () => props.sessionId,
  (sessionId) => {
    loadSeminarHighlights(sessionId)
  },
  { immediate: true }
)

const sortedMembers = computed(() =>
  [...props.members].sort((left, right) => {
    if (left.isLeader !== right.isLeader) {
      return left.isLeader ? -1 : 1
    }
    if (left.online !== right.online) {
      return left.online ? -1 : 1
    }
    return left.name.localeCompare(right.name, 'zh-Hans-CN')
  })
)

const visibleMembers = computed(() => {
  const query = memberQuery.value.trim().toLowerCase()
  if (!query) {
    return sortedMembers.value
  }
  return sortedMembers.value.filter((member) => member.name.toLowerCase().includes(query))
})

function onNavClick(tab: SeminarTaskPaneTab): void {
  toggleSeminarTaskPane(tab)
}

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
</script>

<template>
  <div
    class="mm-task-pane"
    :class="{ 'is-open': paneOpen }"
  >
    <section
      v-if="paneOpen && activeTab"
      class="mm-task-pane__drawer"
      :aria-label="t(paneTitleKey)"
    >
      <header class="mm-task-pane__head">
        <h2 class="mm-task-pane__title">
          <I18nText :k="paneTitleKey" />
          <span
            v-if="activeTab === 'members'"
            class="mm-task-pane__count"
          >
            <I18nText
              k="mindmate.taskPane.memberCount"
              :params="{ n: members.length }"
            />
          </span>
        </h2>
        <button
          type="button"
          class="mm-task-pane__close"
          :aria-label="t('common.close')"
          @click="closeSeminarTaskDrawer()"
        >
          <X
            :size="16"
            aria-hidden="true"
          />
        </button>
      </header>

      <div class="mm-task-pane__body">
        <div
          v-if="activeTab === 'members'"
          class="mm-task-pane__members"
        >
          <label class="mm-task-pane__search">
            <Search
              :size="14"
              aria-hidden="true"
            />
            <input
              v-model="memberQuery"
              type="search"
              :placeholder="t('mindmate.taskPane.memberSearch')"
              :aria-label="t('mindmate.taskPane.memberSearch')"
            />
          </label>
          <ul class="mm-task-pane__member-list">
            <li
              v-for="member in visibleMembers"
              :key="member.userId"
              class="mm-task-pane__member-row"
            >
              <span
                class="mm-task-pane__avatar"
                :class="{ 'is-mentionable': canMentionMember(member) }"
                :style="{
                  background: seminarAvatarTone(member.userId).background,
                  color: seminarAvatarTone(member.userId).color,
                }"
                @contextmenu="onMemberAvatarMenu($event, member)"
              >
                {{ seminarAvatarSurname(member.name) }}
                <span
                  class="mm-task-pane__dot"
                  :class="{ 'is-on': member.online && !member.pending }"
                  aria-hidden="true"
                />
              </span>
              <div class="mm-task-pane__member-meta">
                <span class="mm-task-pane__member-name">
                  {{ member.name }}
                  <span
                    v-if="member.isLeader"
                    class="mm-task-pane__tag"
                    ><I18nText k="mindmate.home.brief.role.leader"
                  /></span>
                </span>
                <span
                  class="mm-task-pane__member-status"
                  :class="{ 'is-on': member.online && !member.pending }"
                >
                  <span
                    class="mm-task-pane__status-dot"
                    aria-hidden="true"
                  />
                  <I18nText
                    v-if="member.pending"
                    k="mindmate.home.brief.pendingConsent"
                  /><template v-else
                    ><I18nText
                      v-if="member.online"
                      k="mindmate.home.memberOnline" /><I18nText
                      v-else
                      k="mindmate.home.memberOffline"
                  /></template>
                </span>
              </div>
              <span class="mm-task-pane__role-wrap">
                <select
                  v-if="isLeader && !member.isLeader && member.userId !== selfUserId"
                  class="mm-task-pane__role"
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
                  class="mm-task-pane__role-text"
                  >{{ roleLabel(memberRoleValue(member)) }}</span
                >
              </span>
              <button
                v-if="isLeader && !member.isLeader && member.userId !== selfUserId"
                type="button"
                class="mm-task-pane__remove"
                :disabled="busy"
                :aria-label="t('mindmate.home.brief.remove')"
                @click="emit('removeMember', member.userId)"
              >
                <Trash2 :size="14" />
              </button>
            </li>
          </ul>
          <button
            v-if="!seminarSpectator"
            type="button"
            class="mm-task-pane__add"
            :disabled="busy"
            @click="emit('addMembers')"
          >
            <Plus :size="14" />
            <I18nText k="mindmate.home.addMembers" />
          </button>
        </div>

        <MindmateSeminarFolderDrawer
          v-else-if="activeTab === 'files' && sessionId"
          :session-id="sessionId"
          embedded
          @close="closeSeminarTaskDrawer()"
        />

        <MindmateSeminarArtifactsDrawer
          v-else-if="activeTab === 'artifacts' && sessionId"
          :session-id="sessionId"
          :messages="seminarLiveMessages"
          embedded
          @close="closeSeminarTaskDrawer()"
        />

        <MindmateSeminarHighlightsDrawer
          v-else-if="activeTab === 'highlights' && sessionId"
          :session-id="sessionId"
          :members="members"
          :is-leader="isLeader"
          :self-user-id="selfUserId"
          embedded
          @close="closeSeminarTaskDrawer()"
        />
      </div>
    </section>

    <nav
      class="mm-task-pane__rail"
      :aria-label="t('mindmate.home.groupInfo')"
    >
      <button
        v-for="item in navItems"
        :key="item.id"
        type="button"
        class="mm-task-pane__nav"
        :class="{ 'is-active': activeTab === item.id }"
        :aria-pressed="activeTab === item.id"
        :title="t(item.labelKey)"
        @click="onNavClick(item.id)"
      >
        <MindmateSoftIcon
          v-if="item.icon === 'highlights'"
          name="highlights"
          :size="18"
        />
        <component
          :is="item.icon"
          v-else
          :size="18"
          aria-hidden="true"
        />
        <span><I18nText :k="item.labelKey" /></span>
      </button>
    </nav>
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
.mm-task-pane {
  display: flex;
  flex-direction: row;
  flex: 0 0 auto;
  flex-shrink: 0;
  min-height: 0;
  height: 100%;
  background: #fff;
  border-left: 1px solid #eceef3;
}

.mm-task-pane__drawer {
  display: flex;
  flex-direction: column;
  flex: 0 0 20rem;
  width: 20rem;
  max-width: min(20rem, 42vw);
  min-width: 0;
  min-height: 0;
  height: 100%;
  background: #f7f8fa;
  border-right: 1px solid #eceef3;
}

.mm-task-pane__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 14px 10px;
  background: #fff;
  flex-shrink: 0;
}

.mm-task-pane__title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #18191c;
}

.mm-task-pane__count {
  padding: 1px 8px;
  border-radius: 999px;
  background: #efeafe;
  color: #7c6fe8;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
}

.mm-task-pane__close {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #78716c;
  cursor: pointer;
}

.mm-task-pane__close:hover {
  background: #f5f5f4;
  color: #1c1917;
}

.mm-task-pane__body {
  flex: 1 1 0;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.mm-task-pane__members {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 12px 12px;
  min-height: 0;
}

.mm-task-pane__search {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 10px;
  border: 1px solid #ececf1;
  border-radius: 10px;
  background: #fff;
  color: #9c9aa8;
}

.mm-task-pane__search input {
  flex: 1 1 auto;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: #18191c;
  font: inherit;
  font-size: 13px;
}

.mm-task-pane__search input::placeholder {
  color: #9c9aa8;
}

.mm-task-pane__member-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mm-task-pane__member-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 8px 8px 8px 10px;
  border: 1px solid #ececf1;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(24, 25, 28, 0.04);
}

.mm-task-pane__avatar {
  position: relative;
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
}

.mm-task-pane__avatar.is-mentionable {
  cursor: context-menu;
}

.mm-task-pane__dot {
  position: absolute;
  right: -1px;
  bottom: -1px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  border: 2px solid #fff;
  background: #d6d3d1;
}

.mm-task-pane__dot.is-on {
  background: #22c55e;
}

.mm-task-pane__member-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mm-task-pane__member-name {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-size: 13px;
  font-weight: 700;
  color: #18191c;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-task-pane__tag {
  flex-shrink: 0;
  padding: 0 6px;
  border-radius: 999px;
  background: #efeafe;
  color: #7c6fe8;
  font-size: 11px;
  font-weight: 600;
}

.mm-task-pane__member-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #9c9aa8;
}

.mm-task-pane__member-status.is-on {
  color: #22a06b;
}

.mm-task-pane__status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #c4c4cc;
}

.mm-task-pane__member-status.is-on .mm-task-pane__status-dot {
  background: #22c55e;
}

.mm-task-pane__role-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  flex: 0 0 auto;
  margin-left: auto;
  min-width: 0;
}

.mm-task-pane__role,
.mm-task-pane__role-text {
  max-width: 96px;
  font-size: 12px;
  color: #6b6b76;
}

.mm-task-pane__role {
  height: 28px;
  padding: 0 22px 0 10px;
  border: 1px solid #ececf1;
  border-radius: 999px;
  background-color: #f7f7f8;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239c9aa8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 6px center;
  appearance: none;
  cursor: pointer;
}

.mm-task-pane__role-text {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: #f7f7f8;
  white-space: nowrap;
}

.mm-task-pane__remove {
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

.mm-task-pane__remove:hover:not(:disabled) {
  background: #fef2f2;
  color: #ef4444;
}

.mm-task-pane__add {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  height: 40px;
  margin-top: 2px;
  border: 1px dashed #c4b5fd;
  border-radius: 12px;
  background: #fff;
  color: #6d5efc;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.mm-task-pane__add:hover:not(:disabled) {
  background: #f5f3ff;
}

.mm-task-pane__rail {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
  flex: 0 0 58px;
  width: 58px;
  min-width: 58px;
  max-width: 58px;
  padding: 10px 6px;
  background: #fff;
  box-sizing: border-box;
}

.mm-task-pane__nav {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  min-height: 54px;
  padding: 8px 2px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: #57534e;
  font: inherit;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.2;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.mm-task-pane__nav:hover {
  background: #f5f3ff;
  color: #6d5efc;
}

.mm-task-pane__nav.is-active {
  background: #ede9fe;
  color: #6d5efc;
}

@media (max-width: 768px) {
  .mm-task-pane {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    z-index: 30;
    box-shadow: -8px 0 24px rgba(15, 23, 42, 0.12);
  }

  .mm-task-pane:not(.is-open) {
    box-shadow: none;
  }

  .mm-task-pane__drawer {
    width: min(20rem, calc(100vw - 58px));
  }
}
</style>
