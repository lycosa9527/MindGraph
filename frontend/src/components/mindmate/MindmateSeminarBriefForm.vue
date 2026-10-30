<script setup lang="ts">
/**
 * Segmented brief the seminar host fills before a group room can open.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import {
  Building2,
  ChevronDown,
  FileText,
  Globe2,
  Plus,
  Search,
  Trash2,
  Upload,
  X,
} from '@lucide/vue'

import MindmateSeminarRoleIcon from '@/components/mindmate/MindmateSeminarRoleIcon.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { type OrgMember, useWorkshopChatStore } from '@/stores/workshopChat'
import { authFetch } from '@/utils/api'
import {
  SEMINAR_BRIEF_ROLE_OPTIONS,
  SEMINAR_BRIEF_ROW_MAX,
  SEMINAR_BRIEF_TOPIC_MAX,
  type SeminarBrief,
  type SeminarBriefParticipant,
  type SeminarBriefParticipantSource,
  type SeminarBriefRole,
  type SeminarBriefSection,
  type SeminarBriefVisibility,
  seminarBriefIsComplete,
  seminarBriefMissing,
  seminarBriefSectionFilled,
} from '@/utils/mindmateSeminarBrief'
import {
  type SeminarPhoneLookupHit,
  isValidSeminarPhone,
  lookupSeminarUserByPhone,
  normalizeSeminarPhone,
} from '@/utils/mindmateSeminarPhoneLookup'
import { seminarAvatarSurname, seminarAvatarTone } from '@/utils/seminarAvatarSurname'

const emit = defineEmits<{
  (e: 'start', brief: SeminarBrief): void
}>()

interface BriefRow {
  id: number
  text: string
}

const RESOURCE_ACCEPT = '.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.md,.png,.jpg,.jpeg,.webp,.gif'

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const workshopChat = useWorkshopChatStore()

let rowSeq = 0

function makeRow(text = ''): BriefRow {
  rowSeq += 1
  return { id: rowSeq, text }
}

function makeRows(count: number): BriefRow[] {
  return Array.from({ length: count }, () => makeRow())
}

const topic = ref('')
const goals = ref<BriefRow[]>(makeRows(2))
const visibility = ref<SeminarBriefVisibility>('organization')
const skipResources = ref(false)
const resourceFiles = ref<File[]>([])
const activeSection = ref<SeminarBriefSection | null>(null)
const members = ref<OrgMember[]>([])
const memberById = ref<Map<number, OrgMember>>(new Map())
const selectedIds = ref<number[]>([])
const rolesByUser = ref<Record<number, SeminarBriefRole>>({})
const sourceByUser = ref<Record<number, SeminarBriefParticipantSource>>({})
const phoneMetaByUser = ref<Record<number, { orgName: string; phoneMasked: string }>>({})
const membersLoading = ref(false)
const memberQuery = ref('')
const phoneQuery = ref('')
const phoneHit = ref<SeminarPhoneLookupHit | null>(null)
const phoneLooking = ref(false)
const phoneStatus = ref<'idle' | 'empty' | 'invalid' | 'error'>('idle')
/** Which accordion is open in cross-school left column. */
const networkFold = ref<'external' | 'school' | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const moreOpen = ref(false)
let memberSearchTimer: ReturnType<typeof setTimeout> | null = null

const sectionTitle: Record<SeminarBriefSection, string> = {
  topic: 'mindmate.home.brief.topic',
  goals: 'mindmate.home.brief.goals',
  participants: 'mindmate.home.brief.participants',
  resources: 'mindmate.home.brief.resources',
}

const selfId = computed(() => {
  const id = Number(authStore.user?.id)
  return Number.isFinite(id) && id > 0 ? id : 0
})

function rememberMembers(rows: OrgMember[]): void {
  const next = new Map(memberById.value)
  for (const row of rows) {
    const id = Number(row.id)
    if (Number.isFinite(id) && id > 0) {
      next.set(id, row)
    }
  }
  memberById.value = next
}

const selectedMembers = computed(() => {
  const rows = selectedIds.value.flatMap((userId) => {
    const member = memberById.value.get(userId) || (isSelf(userId) ? selfMember.value : null)
    return member ? [member] : []
  })
  if (selfId.value <= 0) {
    return rows
  }
  return rows.slice().sort((left, right) => {
    if (Number(left.id) === selfId.value) {
      return -1
    }
    if (Number(right.id) === selfId.value) {
      return 1
    }
    return 0
  })
})

const selfMember = computed<OrgMember | null>(() => {
  const id = selfId.value
  if (id <= 0) {
    return null
  }
  const cached = memberById.value.get(id)
  if (cached) {
    return cached
  }
  const user = authStore.user
  return {
    id,
    name: (user?.username || '').trim() || `User ${id}`,
    avatar: user?.avatar ?? null,
  }
})

const rosterMembers = computed(() => {
  const query = memberQuery.value.trim().toLowerCase()
  const rows = members.value.filter((member) => {
    const id = Number(member.id)
    if (!Number.isFinite(id) || id <= 0) {
      return false
    }
    if (query && !member.name.toLowerCase().includes(query)) {
      return false
    }
    return true
  })
  const self = selfMember.value
  if (self && !rows.some((row) => Number(row.id) === self.id)) {
    if (!query || self.name.toLowerCase().includes(query)) {
      rows.push(self)
    }
  }
  return rows.slice().sort((left, right) => {
    if (selfId.value > 0) {
      if (Number(left.id) === selfId.value) {
        return -1
      }
      if (Number(right.id) === selfId.value) {
        return 1
      }
    }
    return left.name.localeCompare(right.name, 'zh-Hans-CN')
  })
})

const selectedParticipants = computed<SeminarBriefParticipant[]>(() =>
  selectedMembers.value.map((member) => {
    const userId = Number(member.id)
    return {
      userId,
      name: member.name,
      role: rolesByUser.value[userId] || (userId === selfId.value ? 'leader' : 'observer'),
      source: sourceByUser.value[userId] || 'school',
    }
  })
)

const brief = computed<SeminarBrief>(() => ({
  topic: topic.value,
  goals: goals.value.map((row) => row.text),
  visibility: visibility.value,
  participants: selectedParticipants.value,
  skipRoles: false,
  resourceFiles: resourceFiles.value,
  skipResources: skipResources.value,
}))

const topicFilled = computed(() => seminarBriefSectionFilled(brief.value, 'topic'))
const goalsFilled = computed(() => seminarBriefSectionFilled(brief.value, 'goals'))
const participantsFilled = computed(() =>
  seminarBriefSectionFilled(brief.value, 'participants', selfId.value)
)
const resourcesFilled = computed(() => seminarBriefSectionFilled(brief.value, 'resources'))

function addRow(rows: BriefRow[]): void {
  rows.push(makeRow())
}

function removeRow(rows: BriefRow[], id: number): void {
  if (rows.length <= 1) {
    const only = rows[0]
    if (only) {
      only.text = ''
    }
    return
  }
  const index = rows.findIndex((row) => row.id === id)
  if (index >= 0) {
    rows.splice(index, 1)
  }
}

function setActive(section: SeminarBriefSection): void {
  activeSection.value = section
}

function clearActive(section: SeminarBriefSection): void {
  if (activeSection.value === section) {
    activeSection.value = null
  }
}

function setVisibility(next: SeminarBriefVisibility): void {
  visibility.value = next
  setActive('participants')
  phoneHit.value = null
  phoneStatus.value = 'idle'
  if (next === 'network') {
    networkFold.value = null
  }
  if (members.value.length === 0) {
    void loadMembers()
  }
}

function toggleNetworkFold(fold: 'external' | 'school'): void {
  networkFold.value = networkFold.value === fold ? null : fold
  setActive('participants')
  if (fold === 'school' && members.value.length === 0) {
    void loadMembers()
  }
}

function participantSource(userId: number): SeminarBriefParticipantSource {
  return sourceByUser.value[userId] || 'school'
}

function isSelf(userId: number): boolean {
  return selfId.value > 0 && userId === selfId.value
}

function isSelected(userId: number): boolean {
  return selectedIds.value.includes(userId)
}

function ensureSelfSelected(): void {
  const self = selfMember.value
  if (!self) {
    return
  }
  rememberMembers([self])
  if (!selectedIds.value.includes(self.id)) {
    selectedIds.value = [self.id, ...selectedIds.value.filter((id) => id !== self.id)]
  }
  rolesByUser.value = { ...rolesByUser.value, [self.id]: 'leader' }
  sourceByUser.value = { ...sourceByUser.value, [self.id]: 'school' }
}

function addSelectedMember(
  userId: number,
  source: SeminarBriefParticipantSource,
  meta?: { orgName: string; phoneMasked: string }
): void {
  if (!selectedIds.value.includes(userId)) {
    selectedIds.value = [...selectedIds.value, userId]
  }
  if (!rolesByUser.value[userId]) {
    rolesByUser.value = { ...rolesByUser.value, [userId]: 'observer' }
  }
  sourceByUser.value = { ...sourceByUser.value, [userId]: source }
  if (meta) {
    phoneMetaByUser.value = { ...phoneMetaByUser.value, [userId]: meta }
  }
  setActive('participants')
}

function toggleMember(userId: number, checked: boolean): void {
  if (isSelf(userId)) {
    ensureSelfSelected()
    return
  }
  if (checked) {
    addSelectedMember(userId, 'school')
    return
  }
  selectedIds.value = selectedIds.value.filter((id) => id !== userId)
  const nextSource = { ...sourceByUser.value }
  delete nextSource[userId]
  sourceByUser.value = nextSource
  const nextMeta = { ...phoneMetaByUser.value }
  delete nextMeta[userId]
  phoneMetaByUser.value = nextMeta
}

async function searchByPhone(): Promise<void> {
  const phone = normalizeSeminarPhone(phoneQuery.value)
  phoneQuery.value = phone
  phoneHit.value = null
  if (!isValidSeminarPhone(phone)) {
    phoneStatus.value = phone ? 'invalid' : 'idle'
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
    phoneStatus.value = 'idle'
  } catch {
    phoneStatus.value = 'error'
  } finally {
    phoneLooking.value = false
  }
}

function addPhoneHit(): void {
  const hit = phoneHit.value
  if (!hit || isSelf(hit.userId)) {
    return
  }
  rememberMembers([
    {
      id: hit.userId,
      name: hit.name,
      avatar: hit.avatar,
    },
  ])
  addSelectedMember(hit.userId, hit.sameOrg ? 'school' : 'external', {
    orgName: hit.orgName,
    phoneMasked: hit.phoneMasked,
  })
}

function removeMember(userId: number): void {
  if (isSelf(userId)) {
    return
  }
  toggleMember(userId, false)
}

function chosenRole(userId: number): SeminarBriefRole {
  if (isSelf(userId)) {
    return 'leader'
  }
  return rolesByUser.value[userId] || 'observer'
}

function setRole(userId: number, role: string): void {
  if (isSelf(userId)) {
    rolesByUser.value = { ...rolesByUser.value, [userId]: 'leader' }
    return
  }
  if (!SEMINAR_BRIEF_ROLE_OPTIONS.includes(role as Exclude<SeminarBriefRole, 'none'>)) {
    return
  }
  rolesByUser.value = { ...rolesByUser.value, [userId]: role as SeminarBriefRole }
}

function openFilePicker(): void {
  skipResources.value = false
  fileInput.value?.click()
}

function onPickFiles(event: Event): void {
  const input = event.target as HTMLInputElement
  const picked = input.files ? Array.from(input.files) : []
  input.value = ''
  if (!picked.length) {
    return
  }
  skipResources.value = false
  const names = new Set(resourceFiles.value.map((file) => `${file.name}:${file.size}`))
  const next = [...resourceFiles.value]
  for (const file of picked) {
    const key = `${file.name}:${file.size}`
    if (!names.has(key)) {
      next.push(file)
      names.add(key)
    }
  }
  resourceFiles.value = next
}

function removeFile(index: number): void {
  resourceFiles.value = resourceFiles.value.filter((_, i) => i !== index)
}

function markSkipResources(): void {
  skipResources.value = true
  resourceFiles.value = []
  setActive('resources')
}

async function readRoster(url: string): Promise<OrgMember[] | null> {
  const response = await authFetch(url)
  if (!response.ok) {
    return null
  }
  const data = (await response.json()) as { items?: OrgMember[] }
  return data.items ?? []
}

async function loadMembers(query = ''): Promise<void> {
  membersLoading.value = true
  const trimmed = query.trim()
  if (!trimmed && workshopChat.orgMembers.length > 0 && members.value.length === 0) {
    rememberMembers(workshopChat.orgMembers)
    members.value = [...workshopChat.orgMembers]
  }
  try {
    const params = new URLSearchParams({ limit: '200', offset: '0' })
    if (trimmed) {
      params.set('q', trimmed)
    }
    if (workshopChat.adminOrgId != null) {
      params.set('org_id', String(workshopChat.adminOrgId))
    }
    const fromSeminar = await readRoster(`/api/mindmate/org-members?${params}`)
    const fromChat = fromSeminar ?? (await readRoster(`/api/chat/org-members?${params}`))
    const page =
      fromChat ??
      (await readRoster(
        `/api/mindmate/seminar/org-members?limit=200&offset=0${
          trimmed ? `&q=${encodeURIComponent(trimmed)}` : ''
        }`
      ))
    if (page) {
      rememberMembers(page)
      members.value = page
    }
    ensureSelfSelected()
  } finally {
    membersLoading.value = false
  }
}

function scheduleMemberSearch(query: string): void {
  if (memberSearchTimer != null) {
    clearTimeout(memberSearchTimer)
  }
  memberSearchTimer = setTimeout(() => {
    memberSearchTimer = null
    void loadMembers(query)
  }, 250)
}

watch(memberQuery, (query) => {
  scheduleMemberSearch(query)
})

watch(phoneQuery, (raw) => {
  const next = normalizeSeminarPhone(raw)
  if (next !== raw) {
    phoneQuery.value = next
  }
  if (phoneHit.value || phoneStatus.value !== 'idle') {
    phoneHit.value = null
    phoneStatus.value = 'idle'
  }
})

function requireBrief(): SeminarBrief | null {
  const current = brief.value
  if (seminarBriefIsComplete(current, selfId.value)) {
    return current
  }
  const parts = seminarBriefMissing(current, selfId.value)
    .map((section) => t(sectionTitle[section]))
    .join(t('mindmate.home.brief.joiner'))
  notify.warningKey('mindmate.home.brief.required', { parts })
  return null
}

function onStart(): void {
  const current = requireBrief()
  if (current) {
    emit('start', current)
  }
}

onMounted(() => {
  ensureSelfSelected()
  void loadMembers()
})

watch(selfId, () => {
  ensureSelfSelected()
})

onUnmounted(() => {
  if (memberSearchTimer != null) {
    clearTimeout(memberSearchTimer)
  }
})
</script>

<template>
  <div class="mm-brief">
    <section
      class="mm-brief__section"
      :class="{
        'is-filled': topicFilled,
        'is-active': activeSection === 'topic',
      }"
    >
      <div class="mm-brief__rail">
        <span
          class="mm-brief__dot"
          :class="{
            'is-on': topicFilled,
            'is-pulse': activeSection === 'topic',
          }"
        />
      </div>
      <div class="mm-brief__main">
        <h3 class="mm-brief__title">
          <span class="mm-brief__req">*</span><I18nText k="mindmate.home.brief.topic" />
        </h3>
        <div class="mm-brief__card">
          <textarea
            v-model="topic"
            class="mm-brief__topic"
            :maxlength="SEMINAR_BRIEF_TOPIC_MAX"
            :placeholder="t('mindmate.home.brief.topicPlaceholder')"
            @focus="setActive('topic')"
            @blur="clearActive('topic')"
          />
          <div class="mm-brief__count">{{ topic.length }} / {{ SEMINAR_BRIEF_TOPIC_MAX }}</div>
        </div>
      </div>
    </section>

    <section
      class="mm-brief__section"
      :class="{
        'is-filled': participantsFilled,
        'is-active': activeSection === 'participants',
        'mm-brief__section--last': !moreOpen,
      }"
    >
      <div class="mm-brief__rail">
        <span
          class="mm-brief__dot"
          :class="{
            'is-on': participantsFilled,
            'is-pulse': activeSection === 'participants',
          }"
        />
      </div>
      <div class="mm-brief__main">
        <h3 class="mm-brief__title">
          <span class="mm-brief__req">*</span><I18nText k="mindmate.home.brief.participants" />
        </h3>
        <div
          class="mm-brief__card"
          @focusin="setActive('participants')"
        >
          <div
            class="mm-brief__scope"
            role="tablist"
            :aria-label="t('mindmate.home.brief.participants')"
          >
            <button
              type="button"
              role="tab"
              class="mm-brief__scope-btn"
              :class="{ 'is-on': visibility === 'organization' }"
              :aria-selected="visibility === 'organization'"
              @click="setVisibility('organization')"
            >
              <I18nText k="mindmate.home.brief.visibilityOrg" />
            </button>
            <button
              type="button"
              role="tab"
              class="mm-brief__scope-btn"
              :class="{ 'is-on': visibility === 'network' }"
              :aria-selected="visibility === 'network'"
              @click="setVisibility('network')"
            >
              <I18nText k="mindmate.home.brief.visibilityNetwork" />
            </button>
          </div>

          <p class="mm-brief__hint">
            <I18nText
              v-if="visibility === 'network'"
              k="mindmate.home.brief.networkHint"
            /><I18nText
              v-else
              k="mindmate.home.brief.orgHint"
            />
          </p>

          <div class="mm-brief__picker">
            <div class="mm-brief__picker-left">
              <template v-if="visibility === 'network'">
                <div class="mm-brief__folds">
                  <div
                    class="mm-brief__fold"
                    :class="{ 'is-open': networkFold === 'external' }"
                  >
                    <button
                      type="button"
                      class="mm-brief__fold-head"
                      :aria-expanded="networkFold === 'external'"
                      @click="toggleNetworkFold('external')"
                    >
                      <span
                        class="mm-brief__fold-icon is-external"
                        aria-hidden="true"
                      >
                        <Globe2 :size="16" />
                      </span>
                      <span class="mm-brief__fold-title">
                        <I18nText k="mindmate.home.brief.foldExternal" />
                      </span>
                      <ChevronDown
                        class="mm-brief__fold-chevron"
                        :size="16"
                        aria-hidden="true"
                      />
                    </button>
                    <div
                      v-if="networkFold === 'external'"
                      class="mm-brief__fold-body"
                    >
                      <div class="mm-brief__phone">
                        <input
                          v-model="phoneQuery"
                          type="tel"
                          inputmode="numeric"
                          maxlength="11"
                          class="mm-brief__phone-input"
                          :placeholder="t('mindmate.home.brief.phonePlaceholder')"
                          @focus="setActive('participants')"
                          @keydown.enter.prevent="searchByPhone"
                        />
                        <button
                          type="button"
                          class="mm-brief__phone-btn"
                          :disabled="phoneLooking"
                          @click="searchByPhone"
                        >
                          <I18nText k="mindmate.home.brief.phoneSearch" />
                        </button>
                      </div>

                      <p
                        v-if="phoneLooking"
                        class="mm-brief__hint mm-brief__hint--pad"
                      >
                        <I18nText k="common.loading" />
                      </p>
                      <p
                        v-else-if="phoneStatus === 'invalid'"
                        class="mm-brief__hint mm-brief__hint--pad mm-brief__hint--warn"
                      >
                        <I18nText k="mindmate.home.brief.phoneInvalid" />
                      </p>
                      <p
                        v-else-if="phoneStatus === 'empty'"
                        class="mm-brief__hint mm-brief__hint--pad"
                      >
                        <I18nText k="mindmate.home.brief.phoneEmpty" />
                      </p>
                      <p
                        v-else-if="phoneStatus === 'error'"
                        class="mm-brief__hint mm-brief__hint--pad mm-brief__hint--warn"
                      >
                        <I18nText k="mindmate.home.brief.phoneError" />
                      </p>

                      <div
                        v-if="phoneHit"
                        class="mm-brief__phone-hit"
                      >
                        <span
                          class="mm-brief__avatar"
                          :style="{
                            background: seminarAvatarTone(phoneHit.userId).background,
                            color: seminarAvatarTone(phoneHit.userId).color,
                          }"
                        >
                          {{ seminarAvatarSurname(phoneHit.name) }}
                        </span>
                        <div class="mm-brief__phone-meta">
                          <span class="mm-brief__person-name">{{ phoneHit.name }}</span>
                          <span class="mm-brief__phone-sub">
                            <template v-if="phoneHit.orgName">{{ phoneHit.orgName }}</template
                            ><I18nText
                              v-else
                              k="mindmate.home.brief.phoneNoOrg"
                            />
                            · {{ phoneHit.phoneMasked }}
                          </span>
                        </div>
                        <button
                          v-if="!isSelected(phoneHit.userId)"
                          type="button"
                          class="mm-brief__phone-add"
                          @click="addPhoneHit"
                        >
                          <I18nText k="mindmate.home.brief.phoneAdd" />
                        </button>
                        <span
                          v-else
                          class="mm-brief__phone-added"
                          ><I18nText k="mindmate.home.brief.phoneAdded"
                        /></span>
                      </div>
                    </div>
                  </div>

                  <div
                    class="mm-brief__fold"
                    :class="{ 'is-open': networkFold === 'school' }"
                  >
                    <button
                      type="button"
                      class="mm-brief__fold-head"
                      :aria-expanded="networkFold === 'school'"
                      @click="toggleNetworkFold('school')"
                    >
                      <span
                        class="mm-brief__fold-icon is-school"
                        aria-hidden="true"
                      >
                        <Building2 :size="16" />
                      </span>
                      <span class="mm-brief__fold-title">
                        <I18nText k="mindmate.home.brief.foldSchool" />
                      </span>
                      <ChevronDown
                        class="mm-brief__fold-chevron"
                        :size="16"
                        aria-hidden="true"
                      />
                    </button>
                    <div
                      v-if="networkFold === 'school'"
                      class="mm-brief__fold-body mm-brief__fold-body--roster"
                    >
                      <div class="mm-brief__search">
                        <Search
                          class="mm-brief__search-icon"
                          :size="16"
                          aria-hidden="true"
                        />
                        <input
                          v-model="memberQuery"
                          type="search"
                          class="mm-brief__search-input"
                          :placeholder="t('mindmate.home.brief.memberSearch')"
                          @focus="setActive('participants')"
                        />
                      </div>

                      <p
                        v-if="membersLoading && rosterMembers.length === 0"
                        class="mm-brief__hint mm-brief__hint--pad"
                      >
                        <I18nText k="common.loading" />
                      </p>
                      <p
                        v-else-if="memberQuery.trim() && rosterMembers.length === 0"
                        class="mm-brief__hint mm-brief__hint--pad"
                      >
                        <I18nText k="mindmate.home.brief.memberSearchEmpty" />
                      </p>
                      <p
                        v-else-if="rosterMembers.length === 0"
                        class="mm-brief__hint mm-brief__hint--pad"
                      >
                        <I18nText k="mindmate.home.memberDialogEmpty" />
                      </p>
                      <div
                        v-else
                        class="mm-brief__roster"
                      >
                        <button
                          v-for="member in rosterMembers"
                          :key="member.id"
                          type="button"
                          class="mm-brief__roster-row"
                          :class="{
                            'is-on': isSelected(Number(member.id)),
                            'is-self': isSelf(Number(member.id)),
                          }"
                          @click="toggleMember(Number(member.id), !isSelected(Number(member.id)))"
                        >
                          <span
                            class="mm-brief__check"
                            :class="{ 'is-on': isSelected(Number(member.id)) }"
                            aria-hidden="true"
                          />
                          <span
                            class="mm-brief__avatar"
                            :style="{
                              background: seminarAvatarTone(member.id).background,
                              color: seminarAvatarTone(member.id).color,
                            }"
                          >
                            {{ seminarAvatarSurname(member.name) }}
                          </span>
                          <span class="mm-brief__person-name">
                            {{ member.name }}
                            <span
                              v-if="isSelf(Number(member.id))"
                              class="mm-brief__you"
                              ><I18nText k="mindmate.home.brief.memberYou"
                            /></span>
                          </span>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </template>

              <template v-else>
                <div class="mm-brief__search">
                  <Search
                    class="mm-brief__search-icon"
                    :size="16"
                    aria-hidden="true"
                  />
                  <input
                    v-model="memberQuery"
                    type="search"
                    class="mm-brief__search-input"
                    :placeholder="t('mindmate.home.brief.memberSearch')"
                    @focus="setActive('participants')"
                  />
                </div>

                <div class="mm-brief__contacts-label">
                  <I18nText k="mindmate.home.brief.memberContacts" />
                </div>

                <p
                  v-if="membersLoading && rosterMembers.length === 0"
                  class="mm-brief__hint mm-brief__hint--pad"
                >
                  <I18nText k="common.loading" />
                </p>
                <p
                  v-else-if="memberQuery.trim() && rosterMembers.length === 0"
                  class="mm-brief__hint mm-brief__hint--pad"
                >
                  <I18nText k="mindmate.home.brief.memberSearchEmpty" />
                </p>
                <p
                  v-else-if="rosterMembers.length === 0"
                  class="mm-brief__hint mm-brief__hint--pad"
                >
                  <I18nText k="mindmate.home.memberDialogEmpty" />
                </p>
                <div
                  v-else
                  class="mm-brief__roster"
                >
                  <button
                    v-for="member in rosterMembers"
                    :key="member.id"
                    type="button"
                    class="mm-brief__roster-row"
                    :class="{
                      'is-on': isSelected(Number(member.id)),
                      'is-self': isSelf(Number(member.id)),
                    }"
                    @click="toggleMember(Number(member.id), !isSelected(Number(member.id)))"
                  >
                    <span
                      class="mm-brief__check"
                      :class="{ 'is-on': isSelected(Number(member.id)) }"
                      aria-hidden="true"
                    />
                    <span
                      class="mm-brief__avatar"
                      :style="{
                        background: seminarAvatarTone(member.id).background,
                        color: seminarAvatarTone(member.id).color,
                      }"
                    >
                      {{ seminarAvatarSurname(member.name) }}
                    </span>
                    <span class="mm-brief__person-name">
                      {{ member.name }}
                      <span
                        v-if="isSelf(Number(member.id))"
                        class="mm-brief__you"
                        ><I18nText k="mindmate.home.brief.memberYou"
                      /></span>
                    </span>
                  </button>
                </div>
              </template>
            </div>

            <div class="mm-brief__picker-right">
              <div class="mm-brief__selected-head">
                <span><I18nText k="mindmate.home.brief.memberPickerTitle" /></span>
                <span class="mm-brief__selected-count">
                  <I18nText
                    k="mindmate.home.brief.memberSelected"
                    :params="{ count: selectedMembers.length }"
                  />
                </span>
              </div>
              <ul class="mm-brief__chosen">
                <li
                  v-for="member in selectedMembers"
                  :key="member.id"
                  class="mm-brief__chosen-row"
                >
                  <span
                    class="mm-brief__avatar"
                    :style="{
                      background: seminarAvatarTone(member.id).background,
                      color: seminarAvatarTone(member.id).color,
                    }"
                  >
                    {{ seminarAvatarSurname(member.name) }}
                  </span>
                  <div class="mm-brief__chosen-meta">
                    <span class="mm-brief__person-name">
                      {{ member.name }}
                      <span
                        v-if="isSelf(Number(member.id))"
                        class="mm-brief__you"
                        ><I18nText k="mindmate.home.brief.memberYou"
                      /></span>
                      <span
                        v-else-if="participantSource(Number(member.id)) === 'external'"
                        class="mm-brief__pending"
                        ><I18nText k="mindmate.home.brief.pendingConsent"
                      /></span>
                    </span>
                    <span
                      v-if="phoneMetaByUser[Number(member.id)]"
                      class="mm-brief__phone-sub"
                    >
                      <template v-if="phoneMetaByUser[Number(member.id)]?.orgName">{{
                        phoneMetaByUser[Number(member.id)]?.orgName
                      }}</template
                      ><I18nText
                        v-else
                        k="mindmate.home.brief.phoneNoOrg"
                      />
                      · {{ phoneMetaByUser[Number(member.id)]?.phoneMasked }}
                    </span>
                    <span class="mm-brief__role-line">
                      <MindmateSeminarRoleIcon
                        :role="chosenRole(Number(member.id))"
                        :size="22"
                      />
                      <select
                        class="mm-brief__role"
                        :disabled="isSelf(Number(member.id))"
                        :value="chosenRole(Number(member.id))"
                        @change="
                          setRole(Number(member.id), ($event.target as HTMLSelectElement).value)
                        "
                      >
                        <option
                          v-for="role in SEMINAR_BRIEF_ROLE_OPTIONS"
                          :key="role"
                          :value="role"
                        >
                          <I18nText :k="`mindmate.home.brief.role.${role}`" />
                        </option>
                      </select>
                    </span>
                  </div>
                  <button
                    v-if="!isSelf(Number(member.id))"
                    type="button"
                    class="mm-brief__remove"
                    :aria-label="t('mindmate.home.brief.remove')"
                    @click="removeMember(Number(member.id))"
                  >
                    <X :size="14" />
                  </button>
                  <span
                    v-else
                    class="mm-brief__remove-spacer"
                    aria-hidden="true"
                  />
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>

    <button
      type="button"
      class="mm-brief__more"
      :aria-expanded="moreOpen"
      @click="moreOpen = !moreOpen"
    >
      <ChevronDown
        :size="16"
        class="mm-brief__more-chevron"
        :class="{ 'is-open': moreOpen }"
      />
      <I18nText k="mindmate.home.brief.more" />
    </button>

    <section
      v-show="moreOpen"
      class="mm-brief__section"
      :class="{
        'is-filled': goalsFilled,
        'is-active': activeSection === 'goals',
      }"
    >
      <div class="mm-brief__rail">
        <span
          class="mm-brief__dot"
          :class="{
            'is-on': goalsFilled,
            'is-pulse': activeSection === 'goals',
          }"
        />
      </div>
      <div class="mm-brief__main">
        <h3 class="mm-brief__title">
          <I18nText k="mindmate.home.brief.goals" />
          <span class="mm-brief__optional"><I18nText k="mindmate.home.brief.optional" /></span>
        </h3>
        <div class="mm-brief__card">
          <div
            v-for="row in goals"
            :key="row.id"
            class="mm-brief__line"
          >
            <input
              v-model="row.text"
              type="text"
              class="mm-brief__input"
              :maxlength="SEMINAR_BRIEF_ROW_MAX"
              :placeholder="t('mindmate.home.brief.goalPlaceholder')"
              @focus="setActive('goals')"
              @blur="clearActive('goals')"
            />
            <button
              type="button"
              class="mm-brief__icon"
              :aria-label="t('mindmate.home.brief.remove')"
              @click="removeRow(goals, row.id)"
            >
              <Trash2 :size="16" />
            </button>
          </div>
          <button
            type="button"
            class="mm-brief__add"
            :aria-label="t('mindmate.home.brief.add')"
            @click="addRow(goals)"
          >
            <Plus :size="16" />
          </button>
        </div>
      </div>
    </section>

    <section
      v-show="moreOpen"
      class="mm-brief__section mm-brief__section--last"
      :class="{
        'is-filled': resourcesFilled,
        'is-active': activeSection === 'resources',
      }"
    >
      <div class="mm-brief__rail">
        <span
          class="mm-brief__dot"
          :class="{
            'is-on': resourcesFilled,
            'is-pulse': activeSection === 'resources',
          }"
        />
      </div>
      <div class="mm-brief__main">
        <h3 class="mm-brief__title">
          <I18nText k="mindmate.home.brief.resources" />
          <span class="mm-brief__optional"><I18nText k="mindmate.home.brief.optional" /></span>
        </h3>
        <div
          class="mm-brief__card"
          @focusin="setActive('resources')"
        >
          <p class="mm-brief__hint">
            <I18nText k="mindmate.home.brief.resourceHint" />
          </p>
          <input
            ref="fileInput"
            class="mm-brief__file-input"
            type="file"
            multiple
            :accept="RESOURCE_ACCEPT"
            @change="onPickFiles"
          />
          <div class="mm-brief__upload-row">
            <button
              type="button"
              class="mm-brief__upload"
              @click="openFilePicker"
            >
              <Upload :size="16" />
              <I18nText k="mindmate.home.brief.upload" />
            </button>
            <button
              type="button"
              class="mm-brief__skip-btn"
              :class="{ 'is-on': skipResources }"
              @click="markSkipResources"
            >
              <I18nText k="mindmate.home.brief.skipResources" />
            </button>
          </div>
          <ul
            v-if="resourceFiles.length > 0"
            class="mm-brief__files"
          >
            <li
              v-for="(file, index) in resourceFiles"
              :key="`${file.name}-${file.size}-${index}`"
              class="mm-brief__file"
            >
              <FileText
                :size="16"
                aria-hidden="true"
              />
              <span class="mm-brief__file-name">{{ file.name }}</span>
              <button
                type="button"
                class="mm-brief__icon"
                :aria-label="t('mindmate.home.brief.remove')"
                @click="removeFile(index)"
              >
                <X :size="16" />
              </button>
            </li>
          </ul>
        </div>
      </div>
    </section>

    <div class="mm-brief__actions">
      <button
        type="button"
        class="mm-brief__start"
        @click="onStart"
      >
        <I18nText k="mindmate.home.brief.open" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.mm-brief {
  width: 100%;
}

.mm-brief__section {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr);
  column-gap: 14px;
}

.mm-brief__rail {
  position: relative;
}

.mm-brief__rail::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 18px;
  bottom: -6px;
  border-left: 1.5px dashed #d5dbe8;
  transform: translateX(-50%);
  transition:
    border-color 0.2s ease,
    border-left-style 0.2s ease;
}

.mm-brief__section.is-filled .mm-brief__rail::after {
  border-left-style: solid;
  border-left-color: #93c5fd;
}

.mm-brief__section.is-active .mm-brief__rail::after {
  border-left-color: #60a5fa;
}

.mm-brief__section--last .mm-brief__rail::after {
  display: none;
}

.mm-brief__dot {
  position: relative;
  z-index: 1;
  display: block;
  width: 14px;
  height: 14px;
  margin: 4px auto 0;
  box-sizing: border-box;
  border: 2px solid #c5cddb;
  border-radius: 50%;
  background: #fff;
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.mm-brief__dot.is-on {
  border-color: #1c1917;
  background: #1c1917;
  box-shadow: 0 0 0 4px rgba(28, 25, 23, 0.12);
}

.mm-brief__dot.is-pulse {
  border-color: #1c1917;
  transform: scale(1.12);
  box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.22);
  animation: mm-brief-pulse 1.2s ease-in-out infinite;
}

@keyframes mm-brief-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.18);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(59, 130, 246, 0.08);
  }
}

.mm-brief__main {
  min-width: 0;
  padding-bottom: 22px;
}

.mm-brief__title {
  margin: 0 0 10px;
  font-size: 16px;
  font-weight: 650;
  line-height: 1.4;
  color: #1f2937;
}

.mm-brief__req {
  margin-right: 4px;
  color: #ef4444;
}

.mm-brief__optional {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 500;
  color: #9ca3af;
}

.mm-brief__more {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 18px 36px;
  padding: 0;
  border: none;
  background: transparent;
  color: #44403c;
  font: inherit;
  font-size: 14px;
  font-weight: 650;
  cursor: pointer;
}

.mm-brief__more:hover {
  color: #1c1917;
}

.mm-brief__more-chevron {
  transition: transform 0.15s ease;
  transform: rotate(-90deg);
}

.mm-brief__more-chevron.is-open {
  transform: rotate(0deg);
}

.mm-brief__card {
  padding: 16px 16px 14px;
  border: 1px solid #e7e5e4;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.045);
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.mm-brief__section.is-active .mm-brief__card {
  border-color: #a8a29e;
  box-shadow: 0 12px 30px rgba(28, 25, 23, 0.06);
}

.mm-brief__topic,
.mm-brief__input,
.mm-brief__role {
  width: 100%;
  border: 1px solid #e7e5e4;
  border-radius: 10px;
  background: #fff;
  color: #111827;
  font: inherit;
  font-size: 14px;
}

.mm-brief__topic {
  display: block;
  min-height: 56px;
  padding: 10px 12px;
  resize: vertical;
  line-height: 1.5;
  background: #fff;
}

.mm-brief__input {
  height: 40px;
  padding: 0 12px;
}

.mm-brief__topic:focus,
.mm-brief__input:focus,
.mm-brief__role:focus {
  outline: none;
  border-color: #a8a29e;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(28, 25, 23, 0.08);
}

.mm-brief__count {
  margin-top: 6px;
  text-align: right;
  font-size: 12px;
  color: #9ca3af;
}

.mm-brief__line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.mm-brief__icon,
.mm-brief__add {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border-radius: 8px;
  cursor: pointer;
}

.mm-brief__icon {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: #9ca3af;
}

.mm-brief__icon:hover {
  background: #fef2f2;
  color: #ef4444;
}

.mm-brief__add {
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #6b7280;
}

.mm-brief__add:hover {
  border-color: #a8a29e;
  color: #1c1917;
}

.mm-brief__scope {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 12px;
  padding: 4px;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: #fff;
}

.mm-brief__scope-btn,
.mm-brief__upload,
.mm-brief__skip-btn {
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: #fff;
  color: #374151;
  font: inherit;
  font-size: 13px;
  line-height: 1.4;
  cursor: pointer;
}

.mm-brief__scope-btn {
  border: 0;
  padding: 7px 14px;
  background: transparent;
  color: #6b7280;
}

.mm-brief__scope-btn.is-on {
  background: #1c1917;
  color: #fafaf9;
}

.mm-brief__skip-btn.is-on {
  border-color: #1c1917;
  background: #1c1917;
  color: #fafaf9;
}

.mm-brief__hint {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.5;
  color: #9ca3af;
}

.mm-brief__hint--warn {
  color: #dc2626;
}

.mm-brief__folds {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.mm-brief__fold {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  min-height: 0;
  border-bottom: 1px solid #e7e5e4;
}

.mm-brief__fold.is-open {
  flex: 1 1 auto;
}

.mm-brief__fold-head {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) 18px;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 12px 12px;
  border: 0;
  background: transparent;
  color: #1f2937;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.mm-brief__fold-head:hover {
  background: #f5f5f4;
}

.mm-brief__fold.is-open .mm-brief__fold-head {
  background: #f5f5f4;
}

.mm-brief__fold-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
}

.mm-brief__fold-icon.is-external,
.mm-brief__fold-icon.is-school {
  background: #f5f5f4;
  color: #57534e;
}

.mm-brief__fold-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-brief__fold-chevron {
  color: #9ca3af;
  transition: transform 0.18s ease;
}

.mm-brief__fold.is-open .mm-brief__fold-chevron {
  transform: rotate(180deg);
  color: #57534e;
}

.mm-brief__fold-body {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 0 0 10px;
  overflow: hidden;
  border-top: 1px solid #e7e5e4;
  background: #fff;
}

.mm-brief__fold-body--roster {
  flex: 1 1 auto;
}

.mm-brief__fold-body--roster .mm-brief__roster {
  flex: 1 1 auto;
}

.mm-brief__phone {
  display: flex;
  gap: 8px;
  margin: 10px 10px 6px;
}

.mm-brief__phone-input {
  flex: 1 1 auto;
  min-width: 0;
  height: 36px;
  padding: 0 12px;
  border: 1px solid #e7e5e4;
  border-radius: 10px;
  background: #fff;
  color: #111827;
  font: inherit;
  font-size: 13px;
  letter-spacing: 0.04em;
}

.mm-brief__phone-input:focus {
  outline: none;
  border-color: #a8a29e;
  box-shadow: 0 0 0 3px rgba(28, 25, 23, 0.08);
}

.mm-brief__phone-btn,
.mm-brief__phone-add {
  flex-shrink: 0;
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid #e7e5e4;
  border-radius: 9999px;
  background: #f5f5f4;
  color: #44403c;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.mm-brief__phone-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.mm-brief__phone-btn:hover:not(:disabled),
.mm-brief__phone-add:hover {
  background: #e7e5e4;
  color: #1c1917;
}

.mm-brief__phone-hit {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  margin: 0 10px 8px;
  padding: 10px;
  border: 1px solid #e7e5e4;
  border-radius: 12px;
  background: #fff;
}

.mm-brief__phone-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.mm-brief__phone-sub {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: #9ca3af;
}

.mm-brief__phone-added {
  flex-shrink: 0;
  font-size: 12px;
  color: #6b7280;
}

.mm-brief__pending {
  flex-shrink: 0;
  border-radius: 999px;
  padding: 1px 6px;
  background: #fff7ed;
  color: #c2410c;
  font-size: 11px;
  font-weight: 500;
}

.mm-brief__picker {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  height: 420px;
  max-height: min(420px, 52vh);
  border: 1px solid #e7e5e4;
  border-radius: 14px;
  overflow: hidden;
  background: #fafaf9;
}

.mm-brief__picker-left,
.mm-brief__picker-right {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.mm-brief__picker-left {
  background: #f5f5f4;
  border-right: 1px solid #e7e5e4;
}

.mm-brief__picker-right {
  background: #fff;
}

.mm-brief__search {
  position: relative;
  margin: 10px 10px 6px;
}

.mm-brief__search-icon {
  position: absolute;
  top: 50%;
  left: 12px;
  color: #9ca3af;
  transform: translateY(-50%);
  pointer-events: none;
}

.mm-brief__search-input {
  width: 100%;
  height: 36px;
  padding: 0 12px 0 34px;
  border: 1px solid #e7e5e4;
  border-radius: 10px;
  background: #fff;
  color: #111827;
  font: inherit;
  font-size: 13px;
}

.mm-brief__search-input:focus {
  outline: none;
  border-color: #a8a29e;
  box-shadow: 0 0 0 3px rgba(28, 25, 23, 0.08);
}

.mm-brief__contacts-label {
  flex-shrink: 0;
  padding: 2px 14px 8px;
  font-size: 13px;
  color: #6b7280;
}

.mm-brief__hint--pad {
  padding: 8px 14px 16px;
}

.mm-brief__roster,
.mm-brief__chosen {
  flex: 1 1 auto;
  min-height: 0;
  margin: 0;
  padding: 0 0 8px;
  overflow-x: hidden;
  overflow-y: auto;
  list-style: none;
  overscroll-behavior: contain;
}

.mm-brief__roster-row,
.mm-brief__chosen-row {
  display: grid;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 12px;
  border: 0;
  background: transparent;
  text-align: left;
  font: inherit;
}

.mm-brief__roster-row {
  grid-template-columns: 18px 34px minmax(0, 1fr);
  cursor: pointer;
  color: #111827;
}

.mm-brief__roster-row:hover {
  background: #f5f5f4;
}

.mm-brief__roster-row.is-on {
  background: #e7e5e4;
}

.mm-brief__roster-row.is-self {
  cursor: default;
}

.mm-brief__check {
  width: 16px;
  height: 16px;
  border: 1.5px solid #c5cddb;
  border-radius: 50%;
  background: #fff;
  box-sizing: border-box;
}

.mm-brief__check.is-on {
  border-color: #1c1917;
  background: radial-gradient(circle at center, #1c1917 0 40%, transparent 42%), #fff;
}

.mm-brief__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  overflow: hidden;
  border-radius: 50%;
  font-size: 14px;
  font-weight: 650;
  line-height: 1;
  flex-shrink: 0;
}

.mm-brief__person-name {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  color: #111827;
}

.mm-brief__you {
  flex-shrink: 0;
  border-radius: 999px;
  padding: 1px 6px;
  background: #f5f5f4;
  color: #44403c;
  font-size: 11px;
  font-weight: 500;
}

.mm-brief__selected-head {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 14px 8px;
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.mm-brief__selected-count {
  font-size: 12px;
  font-weight: 500;
  color: #9ca3af;
}

.mm-brief__chosen-row {
  grid-template-columns: 34px minmax(0, 1fr) 28px;
}

.mm-brief__chosen-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.mm-brief__role-line {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.mm-brief__role-line .mm-brief__role {
  flex: 1;
  min-width: 0;
}

.mm-brief__role {
  width: 100%;
  height: 28px;
  padding: 0 8px;
  border: 1px solid #e7e5e4;
  border-radius: 8px;
  background: #fff;
  color: #111827;
  font: inherit;
  font-size: 12px;
}

.mm-brief__role:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.mm-brief__remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 1px solid #d1d5db;
  border-radius: 50%;
  background: #fff;
  color: #9ca3af;
  cursor: pointer;
}

.mm-brief__remove:hover {
  border-color: #fca5a5;
  color: #ef4444;
  background: #fef2f2;
}

.mm-brief__remove-spacer {
  width: 22px;
  height: 22px;
}

@media (max-width: 720px) {
  .mm-brief__picker {
    grid-template-columns: 1fr;
    height: auto;
    max-height: none;
  }

  .mm-brief__picker-left,
  .mm-brief__picker-right {
    height: 300px;
  }

  .mm-brief__picker-left {
    border-right: 0;
    border-bottom: 1px solid #e7e5e4;
  }
}

.mm-brief__file-input {
  display: none;
}

.mm-brief__upload-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.mm-brief__upload,
.mm-brief__skip-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
}

.mm-brief__files {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
}

.mm-brief__file {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  color: #4b5563;
  font-size: 13px;
}

.mm-brief__file-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-brief__actions {
  display: flex;
  margin-left: 36px;
}

.mm-brief__start {
  border: 1px solid #1c1917;
  border-radius: 9999px;
  min-height: 36px;
  padding: 8px 20px;
  background: #1c1917;
  color: #fafaf9;
  font: inherit;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.2;
  cursor: pointer;
}

.mm-brief__start:hover {
  background: #292524;
  border-color: #292524;
}

.mm-brief__start:active {
  background: #44403c;
  border-color: #44403c;
}

:global(.dark) .mm-brief__title {
  color: #f5f5f4;
}

:global(.dark) .mm-brief__card,
:global(.dark) .mm-brief__add,
:global(.dark) .mm-brief__scope,
:global(.dark) .mm-brief__upload,
:global(.dark) .mm-brief__skip-btn {
  background: #1f2937;
  border-color: #374151;
  color: #f9fafb;
}

:global(.dark) .mm-brief__scope-btn {
  color: #9ca3af;
}

:global(.dark) .mm-brief__scope-btn.is-on {
  background: #1e3a5f;
  color: #93c5fd;
}

:global(.dark) .mm-brief__topic,
:global(.dark) .mm-brief__input,
:global(.dark) .mm-brief__role,
:global(.dark) .mm-brief__search-input,
:global(.dark) .mm-brief__phone-input,
:global(.dark) .mm-brief__phone-hit,
:global(.dark) .mm-brief__picker-right {
  background: #111827;
  border-color: #374151;
  color: #f9fafb;
}

:global(.dark) .mm-brief__picker,
:global(.dark) .mm-brief__picker-left {
  background: #1f2937;
  border-color: #374151;
}

:global(.dark) .mm-brief__phone-btn,
:global(.dark) .mm-brief__phone-add {
  background: #292524;
  border-color: #44403c;
  color: #fafaf9;
}

:global(.dark) .mm-brief__fold {
  border-bottom-color: #374151;
}

:global(.dark) .mm-brief__fold-head {
  color: #f9fafb;
}

:global(.dark) .mm-brief__fold-head:hover,
:global(.dark) .mm-brief__fold.is-open .mm-brief__fold-head {
  background: #273449;
}

:global(.dark) .mm-brief__fold-body {
  background: #111827;
  border-top-color: #374151;
}

:global(.dark) .mm-brief__fold-icon.is-external {
  background: #1e3a5f;
  color: #93c5fd;
}

:global(.dark) .mm-brief__fold-icon.is-school {
  background: #292524;
  color: #d6d3d1;
}

:global(.dark) .mm-brief__pending {
  background: #431407;
  color: #fdba74;
}

:global(.dark) .mm-brief__roster-row:hover,
:global(.dark) .mm-brief__roster-row.is-on {
  background: #273449;
}

:global(.dark) .mm-brief__person-name,
:global(.dark) .mm-brief__selected-head {
  color: #f9fafb;
}

:global(.dark) .mm-brief__dot {
  background: #111827;
}

:global(.dark) .mm-brief__dot.is-on {
  background: #fafaf9;
}
</style>
