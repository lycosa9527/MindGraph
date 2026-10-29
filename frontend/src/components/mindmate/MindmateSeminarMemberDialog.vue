<script setup lang="ts">
/**
 * Add seminar members — same card chrome as the brief form.
 * Organization rooms can also invite cross-school teachers by phone.
 */
import { computed, ref, watch } from 'vue'

import { ElButton, ElDialog } from 'element-plus'

import { ChevronDown, Globe2, School } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { type OrgMember, useWorkshopChatStore } from '@/stores/workshopChat'
import { authFetch } from '@/utils/api'
import {
  type SeminarPhoneLookupHit,
  isValidSeminarPhone,
  lookupSeminarUserByPhone,
  normalizeSeminarPhone,
} from '@/utils/mindmateSeminarPhoneLookup'
import { seminarAvatarSurname, seminarAvatarTone } from '@/utils/seminarAvatarSurname'

const visible = defineModel<boolean>({ required: true })

const props = withDefaults(
  defineProps<{
    busy?: boolean
    excludeIds?: number[]
    /** When true, show phone lookup for cross-school invites (org seminars). */
    allowExternal?: boolean
    titleKey?: string
    hintKey?: string
    confirmKey?: string
  }>(),
  {
    busy: false,
    excludeIds: () => [],
    allowExternal: true,
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
const fold = ref<'external' | 'school' | null>('school')
const memberQuery = ref('')
const phoneQuery = ref('')
const phoneHit = ref<SeminarPhoneLookupHit | null>(null)
const phoneLooking = ref(false)
const phoneStatus = ref<'idle' | 'invalid' | 'empty' | 'error'>('idle')

const selfId = computed(() => {
  const id = Number(authStore.user?.id)
  return Number.isFinite(id) && id > 0 ? id : 0
})
const excluded = computed(() => new Set(props.excludeIds))

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
  phoneQuery.value = ''
  phoneHit.value = null
  phoneStatus.value = 'idle'
  fold.value = props.allowExternal ? 'school' : 'school'
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

async function loadMembers(): Promise<void> {
  loading.value = true
  loadFailed.value = false
  if (workshopChat.orgMembers.length > 0) {
    members.value = [...workshopChat.orgMembers]
    remember(members.value)
  }
  try {
    const params = new URLSearchParams({ limit: '200', offset: '0' })
    if (workshopChat.adminOrgId != null) {
      params.set('org_id', String(workshopChat.adminOrgId))
    }
    const fromSeminar = await readRoster(`/api/mindmate/org-members?${params}`)
    const fromChat = fromSeminar ?? (await readRoster(`/api/chat/org-members?${params}`))
    const page =
      fromChat ?? (await readRoster('/api/mindmate/seminar/org-members?limit=200&offset=0'))
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

function toggleFold(next: 'external' | 'school'): void {
  fold.value = fold.value === next ? null : next
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

async function searchByPhone(): Promise<void> {
  const phone = normalizeSeminarPhone(phoneQuery.value)
  phoneQuery.value = phone
  phoneHit.value = null
  if (!isValidSeminarPhone(phone)) {
    phoneStatus.value = 'invalid'
    return
  }
  phoneLooking.value = true
  phoneStatus.value = 'idle'
  try {
    const hit = await lookupSeminarUserByPhone(phone)
    if (!hit) {
      phoneStatus.value = 'empty'
      return
    }
    phoneHit.value = hit
    remember([
      {
        id: hit.userId,
        name: hit.name,
        avatar: hit.avatar,
      },
    ])
  } catch {
    phoneStatus.value = 'error'
  } finally {
    phoneLooking.value = false
  }
}

function addPhoneHit(): void {
  const hit = phoneHit.value
  if (!hit || excluded.value.has(hit.userId) || hit.userId === selfId.value) {
    return
  }
  toggle(hit.userId, true)
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
    width="520px"
    :title="t(props.titleKey)"
    append-to-body
    class="mm-member-dialog"
  >
    <p class="mm-member-dialog__hint">
      <I18nText :k="props.hintKey" />
    </p>

    <div class="mm-member-dialog__card">
      <div class="mm-member-dialog__folds">
        <div
          v-if="allowExternal"
          class="mm-member-dialog__fold"
          :class="{ 'is-open': fold === 'external' }"
        >
          <button
            type="button"
            class="mm-member-dialog__fold-head"
            :aria-expanded="fold === 'external'"
            @click="toggleFold('external')"
          >
            <span
              class="mm-member-dialog__fold-icon is-external"
              aria-hidden="true"
            >
              <Globe2 :size="16" />
            </span>
            <span class="mm-member-dialog__fold-title">
              <I18nText k="mindmate.home.brief.foldExternal" />
            </span>
            <ChevronDown
              class="mm-member-dialog__fold-chevron"
              :size="16"
              aria-hidden="true"
            />
          </button>
          <div
            v-if="fold === 'external'"
            class="mm-member-dialog__fold-body"
          >
            <div class="mm-member-dialog__phone">
              <input
                v-model="phoneQuery"
                type="tel"
                inputmode="numeric"
                maxlength="11"
                class="mm-member-dialog__phone-input"
                :placeholder="t('mindmate.home.brief.phonePlaceholder')"
                @keydown.enter.prevent="searchByPhone"
              />
              <button
                type="button"
                class="mm-member-dialog__phone-btn"
                :disabled="phoneLooking"
                @click="searchByPhone"
              >
                <I18nText k="mindmate.home.brief.phoneSearch" />
              </button>
            </div>
            <p
              v-if="phoneLooking"
              class="mm-member-dialog__status"
            >
              <I18nText k="common.loading" />
            </p>
            <p
              v-else-if="phoneStatus === 'invalid'"
              class="mm-member-dialog__status is-warn"
            >
              <I18nText k="mindmate.home.brief.phoneInvalid" />
            </p>
            <p
              v-else-if="phoneStatus === 'empty'"
              class="mm-member-dialog__status"
            >
              <I18nText k="mindmate.home.brief.phoneEmpty" />
            </p>
            <p
              v-else-if="phoneStatus === 'error'"
              class="mm-member-dialog__status is-warn"
            >
              <I18nText k="mindmate.home.brief.phoneError" />
            </p>
            <div
              v-if="phoneHit"
              class="mm-member-dialog__phone-hit"
            >
              <span
                class="mm-member-dialog__avatar"
                :style="{
                  background: seminarAvatarTone(phoneHit.userId).background,
                  color: seminarAvatarTone(phoneHit.userId).color,
                }"
              >
                {{ seminarAvatarSurname(phoneHit.name) }}
              </span>
              <div class="mm-member-dialog__phone-meta">
                <span class="mm-member-dialog__name">{{ phoneHit.name }}</span>
                <span class="mm-member-dialog__sub">
                  <template v-if="phoneHit.orgName">{{ phoneHit.orgName }}</template
                  ><I18nText
                    v-else
                    k="mindmate.home.brief.phoneNoOrg"
                  />
                  · {{ phoneHit.phoneMasked }}
                </span>
              </div>
              <button
                v-if="!isSelected(phoneHit.userId) && !excluded.has(phoneHit.userId)"
                type="button"
                class="mm-member-dialog__phone-add"
                @click="addPhoneHit"
              >
                <I18nText k="mindmate.home.brief.phoneAdd" />
              </button>
              <span
                v-else
                class="mm-member-dialog__phone-added"
                ><I18nText k="mindmate.home.brief.phoneAdded"
              /></span>
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
              <I18nText k="mindmate.home.brief.foldSchool" />
            </span>
            <ChevronDown
              class="mm-member-dialog__fold-chevron"
              :size="16"
              aria-hidden="true"
            />
          </button>
          <div
            v-if="fold === 'school'"
            class="mm-member-dialog__fold-body"
          >
            <input
              v-model="memberQuery"
              type="search"
              class="mm-member-dialog__search"
              :placeholder="t('mindmate.home.brief.memberSearch')"
            />
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
                @click="toggle(Number(member.id), !isSelected(Number(member.id)))"
              >
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
                <span
                  class="mm-member-dialog__check"
                  :class="{ 'is-on': isSelected(Number(member.id)) }"
                  aria-hidden="true"
                />
              </li>
            </ul>
          </div>
        </div>
      </div>

      <div class="mm-member-dialog__selected">
        <p class="mm-member-dialog__selected-label">
          <I18nText
            v-if="selected.length"
            k="mindmate.home.brief.memberSelected"
            :params="{ count: selected.length }"
          /><I18nText
            v-else
            k="mindmate.home.brief.memberSelectedEmpty"
          />
        </p>
        <div
          v-if="selectedRows.length"
          class="mm-member-dialog__chips"
        >
          <span
            v-for="row in selectedRows"
            :key="row.id"
            class="mm-member-dialog__chip"
          >
            {{ row.name }}
            <button
              type="button"
              class="mm-member-dialog__chip-x"
              :aria-label="t('mindmate.home.brief.remove')"
              @click="toggle(Number(row.id), false)"
            >
              ×
            </button>
          </span>
        </div>
      </div>
    </div>

    <template #footer>
      <ElButton
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
.mm-member-dialog__hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: #78716c;
  line-height: 1.45;
}

.mm-member-dialog__card {
  border: 1px solid #e9e5ff;
  border-radius: 16px;
  background: #faf8ff;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mm-member-dialog__folds {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mm-member-dialog__fold {
  border: 1px solid #e9e5ff;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
}

.mm-member-dialog__fold-head {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  font: inherit;
  color: #1c1917;
}

.mm-member-dialog__fold-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.mm-member-dialog__fold-icon.is-external {
  background: #eff6ff;
  color: #2563eb;
}

.mm-member-dialog__fold-icon.is-school {
  background: #f5f3ff;
  color: #6d5efc;
}

.mm-member-dialog__fold-title {
  flex: 1;
  text-align: left;
  font-size: 13px;
  font-weight: 600;
}

.mm-member-dialog__fold-chevron {
  color: #a8a29e;
  transition: transform 0.15s ease;
}

.mm-member-dialog__fold.is-open .mm-member-dialog__fold-chevron {
  transform: rotate(180deg);
}

.mm-member-dialog__fold-body {
  padding: 0 12px 12px;
}

.mm-member-dialog__phone,
.mm-member-dialog__search {
  width: 100%;
}

.mm-member-dialog__phone {
  display: flex;
  gap: 8px;
}

.mm-member-dialog__phone-input,
.mm-member-dialog__search {
  height: 34px;
  border: 1px solid #e7e5e4;
  border-radius: 10px;
  padding: 0 10px;
  font: inherit;
  font-size: 13px;
  background: #fff;
}

.mm-member-dialog__phone-input {
  flex: 1;
  min-width: 0;
}

.mm-member-dialog__phone-btn,
.mm-member-dialog__phone-add {
  height: 34px;
  padding: 0 12px;
  border: 1px solid #c4b5fd;
  border-radius: 10px;
  background: #f5f3ff;
  color: #5b21b6;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.mm-member-dialog__status {
  margin: 8px 0 0;
  font-size: 12px;
  color: #78716c;
}

.mm-member-dialog__status.is-warn {
  color: #b45309;
}

.mm-member-dialog__phone-hit,
.mm-member-dialog__row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  padding: 8px;
  border-radius: 10px;
}

.mm-member-dialog__row {
  margin-top: 0;
  cursor: pointer;
}

.mm-member-dialog__row:hover {
  background: #faf8ff;
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

.mm-member-dialog__phone-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mm-member-dialog__name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 600;
  color: #1c1917;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-member-dialog__sub,
.mm-member-dialog__phone-added {
  font-size: 11px;
  color: #a8a29e;
}

.mm-member-dialog__list {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  max-height: 220px;
  overflow: auto;
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

.mm-member-dialog__selected {
  border-top: 1px dashed #ddd6fe;
  padding-top: 10px;
}

.mm-member-dialog__selected-label {
  margin: 0 0 8px;
  font-size: 12px;
  color: #78716c;
}

.mm-member-dialog__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.mm-member-dialog__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 28px;
  padding: 0 8px 0 10px;
  border-radius: 999px;
  background: #ede9fe;
  color: #5b21b6;
  font-size: 12px;
  font-weight: 600;
}

.mm-member-dialog__chip-x {
  border: none;
  background: transparent;
  color: #7c3aed;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 0 2px;
}
</style>
