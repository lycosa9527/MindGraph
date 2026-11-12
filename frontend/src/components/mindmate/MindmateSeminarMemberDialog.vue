<script setup lang="ts">
/**
 * Add seminar members — invite-code share and platform-tier org filter.
 * Layout mirrors the seminar brief participant picker.
 */
import { computed, nextTick, ref, watch } from 'vue'

import { ElButton, ElDialog, ElOption, ElSelect } from 'element-plus'

import { ChevronDown, Link2, School, Search, X } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { type OrgMember, useWorkshopChatStore } from '@/stores/workshopChat'
import { authFetch } from '@/utils/api'
import {
  type SeminarInviteOrgOption,
  loadSeminarInviteOrganizations,
} from '@/utils/mindmateSeminarInviteOrgs'
import { seminarAvatarSurname, seminarAvatarTone } from '@/utils/seminarAvatarSurname'

const visible = defineModel<boolean>({ required: true })

const props = withDefaults(
  defineProps<{
    busy?: boolean
    excludeIds?: number[]
    /** Live room code — enables invite-code fold for any member who can invite. */
    inviteCode?: string
    titleKey?: string
    hintKey?: string
    confirmKey?: string
  }>(),
  {
    busy: false,
    excludeIds: () => [],
    inviteCode: '',
    titleKey: 'mindmate.home.memberDialogTitle',
    hintKey: 'mindmate.home.memberDialogHint',
    confirmKey: 'mindmate.home.memberDialogConfirm',
  }
)

const emit = defineEmits<{
  (e: 'confirm', userIds: number[]): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const workshopChat = useWorkshopChatStore()
const loading = ref(false)
const loadFailed = ref(false)
const members = ref<OrgMember[]>([])
const selected = ref<number[]>([])
const memberById = ref<Map<number, OrgMember>>(new Map())
const fold = ref<'school' | 'invite' | null>('school')
const memberQuery = ref('')
const orgSearchOpen = ref(false)
const orgSearchInput = ref<HTMLInputElement | null>(null)
const canBrowseOrgs = ref(false)
const inviteOrgs = ref<SeminarInviteOrgOption[]>([])
const selectedOrgId = ref<number | null>(null)

const selfId = computed(() => {
  const id = Number(authStore.user?.id)
  return Number.isFinite(id) && id > 0 ? id : 0
})
const excluded = computed(() => new Set(props.excludeIds))
const showOrgFilter = computed(
  () => authStore.isPlatformLevel || canBrowseOrgs.value
)
const trimmedInviteCode = computed(() => props.inviteCode.trim())
const showInviteFold = computed(() => trimmedInviteCode.value.length > 0)

const schoolChoices = computed(() => {
  const query = memberQuery.value.trim().toLowerCase()
  return members.value.filter((member) => {
    const id = Number(member.id)
    if (!Number.isFinite(id) || id <= 0) {
      return false
    }
    if (excluded.value.has(id) || id === selfId.value) {
      return false
    }
    if (query && !member.name.toLowerCase().includes(query)) {
      return false
    }
    return true
  })
})

const selectedRows = computed(() =>
  selected.value.flatMap((userId) => {
    const row = memberById.value.get(userId)
    return row ? [row] : []
  })
)

watch(visible, (open) => {
  if (!open) {
    return
  }
  selected.value = []
  memberQuery.value = ''
  orgSearchOpen.value = false
  fold.value = showInviteFold.value ? 'invite' : 'school'
  void bootstrapPicker()
})

watch(selectedOrgId, () => {
  if (!visible.value) {
    return
  }
  void loadMembers()
})

watch(memberQuery, () => {
  if (!visible.value || !orgSearchOpen.value) {
    return
  }
  void loadMembers()
})

function remember(rows: OrgMember[]): void {
  const next = new Map(memberById.value)
  for (const row of rows) {
    const id = Number(row.id)
    if (Number.isFinite(id) && id > 0) {
      next.set(id, row)
    }
  }
  memberById.value = next
}

async function readRoster(url: string): Promise<OrgMember[] | null> {
  const response = await authFetch(url)
  if (!response.ok) {
    return null
  }
  const data = (await response.json()) as { items?: OrgMember[] }
  return data.items ?? []
}

async function bootstrapPicker(): Promise<void> {
  if (authStore.isPlatformLevel) {
    const orgs = await loadSeminarInviteOrganizations()
    canBrowseOrgs.value = orgs.canBrowse
    inviteOrgs.value = orgs.items
    if (orgs.items.length > 0) {
      const home = Number(authStore.user?.schoolId ?? 0)
      const preferred =
        workshopChat.adminOrgId ??
        (Number.isFinite(home) && home > 0 && orgs.items.some((row) => row.id === home)
          ? home
          : orgs.items[0]?.id)
      selectedOrgId.value = preferred ?? null
    } else {
      selectedOrgId.value = null
    }
  } else {
    canBrowseOrgs.value = false
    inviteOrgs.value = []
    selectedOrgId.value = workshopChat.adminOrgId
  }
  await loadMembers()
}

async function loadMembers(): Promise<void> {
  loading.value = true
  loadFailed.value = false
  if (
    !showOrgFilter.value &&
    workshopChat.orgMembers.length > 0 &&
    members.value.length === 0
  ) {
    members.value = [...workshopChat.orgMembers]
    remember(members.value)
  }
  try {
    const params = new URLSearchParams({ limit: '200', offset: '0' })
    const query = memberQuery.value.trim()
    if (query) {
      params.set('q', query)
    }
    const orgId = selectedOrgId.value ?? workshopChat.adminOrgId
    if (orgId != null) {
      params.set('org_id', String(orgId))
    }
    const fromSeminar = await readRoster(`/api/mindmate/org-members?${params}`)
    const fromChat = fromSeminar ?? (await readRoster(`/api/chat/org-members?${params}`))
    const page =
      fromChat ??
      (await readRoster(`/api/mindmate/seminar/org-members?${params.toString()}`))
    if (!page) {
      if (members.value.length === 0) {
        loadFailed.value = true
        notify.errorKey('mindmate.collabMembersLoadFailed')
      }
      return
    }
    members.value = page
    remember(page)
  } catch {
    if (members.value.length === 0) {
      loadFailed.value = true
      notify.errorKey('mindmate.collabMembersLoadFailed')
    }
  } finally {
    loading.value = false
  }
}

function toggleFold(next: 'school' | 'invite'): void {
  fold.value = fold.value === next ? null : next
}

async function copyInviteCode(): Promise<void> {
  const code = trimmedInviteCode.value
  if (!code) {
    return
  }
  try {
    await navigator.clipboard.writeText(code)
    notify.successKey('mindmate.home.inviteCodeCopied')
  } catch {
    notify.errorKey('notification.copyFailed')
  }
}

async function copyInviteMessage(): Promise<void> {
  const code = trimmedInviteCode.value
  if (!code) {
    return
  }
  try {
    await navigator.clipboard.writeText(
      t('mindmate.home.brief.inviteShareText', { code })
    )
    notify.successKey('mindmate.home.brief.inviteShareCopied')
  } catch {
    notify.errorKey('notification.copyFailed')
  }
}

async function openOrgSearch(): Promise<void> {
  orgSearchOpen.value = true
  await nextTick()
  orgSearchInput.value?.focus()
  orgSearchInput.value?.select()
}

function closeOrgSearch(): void {
  orgSearchOpen.value = false
  if (memberQuery.value) {
    memberQuery.value = ''
    void loadMembers()
  }
}

function isSelected(userId: number): boolean {
  return selected.value.includes(userId)
}

function toggle(id: number, checked: boolean): void {
  if (checked) {
    if (!selected.value.includes(id)) {
      selected.value = [...selected.value, id]
    }
    return
  }
  selected.value = selected.value.filter((item) => item !== id)
}

function selectAllSchoolChoices(): void {
  for (const member of schoolChoices.value) {
    toggle(Number(member.id), true)
  }
}

function clearSchoolChoices(): void {
  for (const member of schoolChoices.value) {
    toggle(Number(member.id), false)
  }
}

function onConfirm(): void {
  if (selected.value.length === 0) {
    return
  }
  emit('confirm', [...selected.value])
}
</script>

<template>
  <ElDialog
    v-model="visible"
    width="min(680px, 94vw)"
    :title="t(props.titleKey)"
    append-to-body
    class="mm-member-dialog mm-seminar-swiss"
  >
    <div class="mm-member-dialog__picker">
      <div class="mm-member-dialog__picker-left">
        <div class="mm-member-dialog__folds">
          <div
            v-if="showInviteFold"
            class="mm-member-dialog__fold"
            :class="{ 'is-open': fold === 'invite' }"
          >
            <button
              type="button"
              class="mm-member-dialog__fold-head"
              :aria-expanded="fold === 'invite'"
              @click="toggleFold('invite')"
            >
              <span
                class="mm-member-dialog__fold-icon is-invite"
                aria-hidden="true"
              >
                <Link2 :size="16" />
              </span>
              <span class="mm-member-dialog__fold-title">
                <I18nText k="mindmate.home.brief.foldInviteCode" />
              </span>
              <ChevronDown
                class="mm-member-dialog__fold-chevron"
                :size="16"
                aria-hidden="true"
              />
            </button>
            <div
              v-if="fold === 'invite'"
              class="mm-member-dialog__fold-body mm-member-dialog__fold-body--invite"
            >
              <p class="mm-member-dialog__invite-hint">
                <I18nText k="mindmate.home.brief.inviteCodeHint" />
              </p>
              <div class="mm-member-dialog__invite-card">
                <p class="mm-member-dialog__invite-code">{{ trimmedInviteCode }}</p>
                <button
                  type="button"
                  class="mm-member-dialog__invite-primary"
                  @click="copyInviteMessage"
                >
                  <I18nText k="mindmate.home.brief.inviteCopyMessage" />
                </button>
                <div class="mm-member-dialog__invite-links">
                  <button
                    type="button"
                    class="mm-member-dialog__invite-link-btn"
                    @click="copyInviteCode"
                  >
                    <I18nText k="mindmate.home.inviteCopyCode" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div
            class="mm-member-dialog__fold"
            :class="{ 'is-open': fold === 'school' }"
          >
            <button
              type="button"
              class="mm-member-dialog__fold-head"
              :aria-expanded="fold === 'school'"
              @click="toggleFold('school')"
            >
              <span
                class="mm-member-dialog__fold-icon is-school"
                aria-hidden="true"
              >
                <School :size="16" />
              </span>
              <span class="mm-member-dialog__fold-title">
                <I18nText
                  :k="
                    showOrgFilter
                      ? 'mindmate.home.brief.foldOrgPick'
                      : 'mindmate.home.brief.foldSchool'
                  "
                />
              </span>
              <ChevronDown
                class="mm-member-dialog__fold-chevron"
                :size="16"
                aria-hidden="true"
              />
            </button>
            <div
              v-if="fold === 'school'"
              class="mm-member-dialog__fold-body mm-member-dialog__fold-body--roster"
            >
              <ElSelect
                v-if="showOrgFilter && inviteOrgs.length > 0"
                v-model="selectedOrgId"
                class="mm-member-dialog__org-select"
                filterable
                :placeholder="t('mindmate.home.brief.orgSearch')"
              >
                <ElOption
                  v-for="org in inviteOrgs"
                  :key="org.id"
                  :label="org.displayName"
                  :value="org.id"
                />
              </ElSelect>
              <p
                v-else-if="showOrgFilter"
                class="mm-member-dialog__status is-warn"
              >
                <I18nText k="mindmate.home.brief.orgListEmpty" />
              </p>
              <div class="mm-member-dialog__org-toolbar">
                <div
                  class="mm-member-dialog__org-search"
                  :class="{ 'is-open': orgSearchOpen }"
                >
                  <button
                    v-if="!orgSearchOpen"
                    type="button"
                    class="mm-member-dialog__org-search-toggle"
                    :aria-label="t('mindmate.home.brief.memberSearch')"
                    @click="openOrgSearch"
                  >
                    <Search
                      :size="15"
                      aria-hidden="true"
                    />
                  </button>
                  <div
                    v-else
                    class="mm-member-dialog__org-search-field"
                  >
                    <Search
                      class="mm-member-dialog__org-search-field-icon"
                      :size="14"
                      aria-hidden="true"
                    />
                    <input
                      ref="orgSearchInput"
                      v-model="memberQuery"
                      type="search"
                      class="mm-member-dialog__org-search-input"
                      :placeholder="t('mindmate.home.brief.memberSearch')"
                      @keydown.enter.prevent="loadMembers"
                      @keydown.escape.prevent="closeOrgSearch"
                    />
                    <button
                      type="button"
                      class="mm-member-dialog__org-search-close"
                      :aria-label="t('common.close')"
                      @click="closeOrgSearch"
                    >
                      <X
                        :size="14"
                        aria-hidden="true"
                      />
                    </button>
                  </div>
                </div>
                <div
                  v-if="schoolChoices.length > 0"
                  class="mm-member-dialog__org-bulk"
                >
                  <button
                    type="button"
                    class="mm-member-dialog__invite-link-btn"
                    @click="selectAllSchoolChoices"
                  >
                    <I18nText k="mindmate.home.brief.orgSelectAll" />
                  </button>
                  <span
                    class="mm-member-dialog__invite-dot"
                    aria-hidden="true"
                  >·</span>
                  <button
                    type="button"
                    class="mm-member-dialog__invite-link-btn"
                    @click="clearSchoolChoices"
                  >
                    <I18nText k="mindmate.home.brief.orgClearAll" />
                  </button>
                </div>
              </div>
              <p
                v-if="loading && schoolChoices.length === 0"
                class="mm-member-dialog__status"
              >
                <I18nText k="common.loading" />
              </p>
              <p
                v-else-if="loadFailed"
                class="mm-member-dialog__status is-warn"
              >
                <I18nText k="mindmate.collabMembersLoadFailed" />
              </p>
              <p
                v-else-if="schoolChoices.length === 0"
                class="mm-member-dialog__status"
              >
                <I18nText k="mindmate.home.memberDialogEmpty" />
              </p>
              <ul
                v-else
                class="mm-member-dialog__list"
              >
                <li
                  v-for="member in schoolChoices"
                  :key="member.id"
                  class="mm-member-dialog__row"
                  :class="{ 'is-on': isSelected(Number(member.id)) }"
                  @click="toggle(Number(member.id), !isSelected(Number(member.id)))"
                >
                  <span
                    class="mm-member-dialog__check"
                    :class="{ 'is-on': isSelected(Number(member.id)) }"
                    aria-hidden="true"
                  />
                  <span
                    class="mm-member-dialog__avatar"
                    :style="{
                      background: seminarAvatarTone(Number(member.id)).background,
                      color: seminarAvatarTone(Number(member.id)).color,
                    }"
                  >
                    {{ seminarAvatarSurname(member.name) }}
                  </span>
                  <span class="mm-member-dialog__name">{{ member.name }}</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <div class="mm-member-dialog__picker-right">
        <div class="mm-member-dialog__selected-head">
          <span><I18nText k="mindmate.home.brief.memberPickerTitle" /></span>
          <span class="mm-member-dialog__selected-count">
            <I18nText
              k="mindmate.home.brief.memberSelected"
              :params="{ count: selected.length }"
            />
          </span>
        </div>
        <ul
          v-if="selectedRows.length"
          class="mm-member-dialog__chosen"
        >
          <li
            v-for="row in selectedRows"
            :key="row.id"
            class="mm-member-dialog__chosen-row"
          >
            <span
              class="mm-member-dialog__avatar"
              :style="{
                background: seminarAvatarTone(Number(row.id)).background,
                color: seminarAvatarTone(Number(row.id)).color,
              }"
            >
              {{ seminarAvatarSurname(row.name) }}
            </span>
            <span class="mm-member-dialog__name">{{ row.name }}</span>
            <button
              type="button"
              class="mm-member-dialog__chip-x"
              :aria-label="t('mindmate.home.brief.remove')"
              @click="toggle(Number(row.id), false)"
            >
              ×
            </button>
          </li>
        </ul>
      </div>
    </div>

    <template #footer>
      <ElButton
        class="mm-member-dialog__confirm"
        type="primary"
        :disabled="selected.length === 0 || loading || busy"
        :loading="busy"
        @click="onConfirm"
      >
        <I18nText
          :k="props.confirmKey"
          dense
        />
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.mm-member-dialog__picker {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  height: 420px;
  max-height: min(420px, 58vh);
  border: 1px solid #e8edf5;
  border-radius: 14px;
  overflow: hidden;
  background: #fafbff;
}

.mm-member-dialog__picker-left,
.mm-member-dialog__picker-right {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.mm-member-dialog__picker-left {
  background: #f7f8fb;
  border-right: 1px solid #e7e5e4;
}

.mm-member-dialog__picker-right {
  background: #fff;
}

.mm-member-dialog__folds {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.mm-member-dialog__fold {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  min-height: 0;
  border-bottom: 1px solid #e8edf5;
}

.mm-member-dialog__fold.is-open {
  flex: 1 1 auto;
}

.mm-member-dialog__fold-head {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) 18px;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 12px;
  border: 0;
  background: transparent;
  color: #1f2937;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.mm-member-dialog__fold-head:hover {
  background: #eef2ff;
}

.mm-member-dialog__fold.is-open .mm-member-dialog__fold-head {
  background: #eff6ff;
}

.mm-member-dialog__fold-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: #f5f5f4;
  color: #57534e;
}

.mm-member-dialog__fold-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-member-dialog__fold-chevron {
  color: #9ca3af;
  transition: transform 0.18s ease;
}

.mm-member-dialog__fold.is-open .mm-member-dialog__fold-chevron {
  transform: rotate(180deg);
  color: #3b82f6;
}

.mm-member-dialog__fold-body {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 0 12px 12px;
  overflow: hidden;
  border-top: 1px solid #e8edf5;
  background: #fff;
}

.mm-member-dialog__fold-body--invite {
  gap: 10px;
  padding-top: 12px;
}

.mm-member-dialog__fold-body--roster {
  flex: 1 1 auto;
  gap: 10px;
  padding-top: 10px;
}

.mm-member-dialog__invite-hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: #78716c;
  text-align: center;
}

.mm-member-dialog__invite-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 14px 14px;
  border: 1px solid #e7e5e4;
  border-radius: 14px;
  background: linear-gradient(180deg, #fafafa 0%, #fff 100%);
}

.mm-member-dialog__invite-code {
  margin: 0;
  text-align: center;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #1c1917;
}

.mm-member-dialog__invite-primary {
  width: 100%;
  min-height: 38px;
  padding: 0 14px;
  border: 1px solid #c4b5fd;
  border-radius: 10px;
  background: #ede9fe;
  color: #5b21b6;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.mm-member-dialog__invite-primary:hover {
  background: #ddd6fe;
  color: #4c1d95;
  border-color: #a78bfa;
}

.mm-member-dialog__invite-links,
.mm-member-dialog__org-bulk {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.mm-member-dialog__org-bulk {
  justify-content: flex-end;
  flex-shrink: 0;
  margin-left: auto;
}

.mm-member-dialog__invite-link-btn {
  border: 0;
  background: transparent;
  color: #57534e;
  font: inherit;
  font-size: 12px;
  font-weight: 500;
  padding: 0;
  cursor: pointer;
}

.mm-member-dialog__invite-link-btn:hover {
  color: #1c1917;
  text-decoration: underline;
}

.mm-member-dialog__invite-dot {
  color: #d6d3d1;
  font-size: 12px;
}

.mm-member-dialog__org-select {
  width: 100%;
  flex-shrink: 0;
}

.mm-member-dialog__org-select :deep(.el-select__wrapper) {
  min-height: 36px;
  border-radius: 10px;
  box-shadow: none;
}

.mm-member-dialog__org-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  min-height: 30px;
}

.mm-member-dialog__org-search {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
}

.mm-member-dialog__org-search-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid #e7e5e4;
  border-radius: 8px;
  background: #fff;
  color: #78716c;
  cursor: pointer;
}

.mm-member-dialog__org-search-toggle:hover {
  color: #1c1917;
  border-color: #d6d3d1;
  background: #fafaf9;
}

.mm-member-dialog__org-search-field {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  min-height: 30px;
  padding: 0 8px 0 10px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.mm-member-dialog__org-search-field-icon {
  flex-shrink: 0;
  color: #9ca3af;
}

.mm-member-dialog__org-search-input {
  flex: 1 1 auto;
  min-width: 0;
  height: 28px;
  border: 0;
  background: transparent;
  color: #111827;
  font: inherit;
  font-size: 13px;
  outline: none;
}

.mm-member-dialog__org-search-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
}

.mm-member-dialog__status {
  margin: 0;
  padding: 16px 8px;
  text-align: center;
  font-size: 12px;
  color: #9ca3af;
}

.mm-member-dialog__status.is-warn {
  color: #b45309;
}

.mm-member-dialog__list,
.mm-member-dialog__chosen {
  flex: 1 1 auto;
  min-height: 0;
  margin: 0;
  padding: 0;
  overflow: auto;
  list-style: none;
}

.mm-member-dialog__row,
.mm-member-dialog__chosen-row {
  display: grid;
  grid-template-columns: 18px 32px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 4px;
  border: 0;
  background: transparent;
  text-align: left;
  font: inherit;
  cursor: pointer;
}

.mm-member-dialog__chosen-row {
  grid-template-columns: 32px minmax(0, 1fr) 22px;
  cursor: default;
  padding: 8px 12px;
}

.mm-member-dialog__row:hover,
.mm-member-dialog__row.is-on {
  background: #eef2ff;
}

.mm-member-dialog__avatar {
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

.mm-member-dialog__name {
  min-width: 0;
  font-size: 13px;
  font-weight: 600;
  color: #1c1917;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-member-dialog__check {
  width: 18px;
  height: 18px;
  border-radius: 6px;
  border: 1.5px solid #d6d3d1;
  background: #fff;
  flex-shrink: 0;
}

.mm-member-dialog__check.is-on {
  border-color: #6d5efc;
  background: #6d5efc;
  box-shadow: inset 0 0 0 3px #fff;
}

.mm-member-dialog__selected-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 14px 8px;
  font-size: 13px;
  font-weight: 600;
  color: #1c1917;
}

.mm-member-dialog__selected-count {
  font-size: 12px;
  font-weight: 500;
  color: #78716c;
}

.mm-member-dialog__chip-x {
  border: none;
  background: transparent;
  color: #a8a29e;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  padding: 0;
}

.mm-member-dialog__chip-x:hover {
  color: #1c1917;
}

@media (max-width: 640px) {
  .mm-member-dialog__picker {
    grid-template-columns: 1fr;
    height: auto;
    max-height: none;
  }

  .mm-member-dialog__picker-left {
    border-right: 0;
    border-bottom: 1px solid #e7e5e4;
    max-height: 280px;
  }

  .mm-member-dialog__picker-right {
    min-height: 140px;
  }
}
</style>

<style>
.mm-member-dialog.el-dialog {
  border-radius: 12px;
}

.mm-member-dialog .el-dialog__body {
  padding-top: 8px;
}

.mm-member-dialog .mm-member-dialog__confirm.el-button--primary {
  --el-button-bg-color: #ede9fe;
  --el-button-border-color: #c4b5fd;
  --el-button-text-color: #5b21b6;
  --el-button-hover-bg-color: #ddd6fe;
  --el-button-hover-border-color: #a78bfa;
  --el-button-hover-text-color: #4c1d95;
  --el-button-active-bg-color: #c4b5fd;
  --el-button-active-border-color: #8b5cf6;
  --el-button-disabled-bg-color: #f5f3ff;
  --el-button-disabled-border-color: #ddd6fe;
  --el-button-disabled-text-color: #a78bfa;
}
</style>
