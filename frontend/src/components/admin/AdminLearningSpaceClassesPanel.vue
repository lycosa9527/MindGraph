<script setup lang="ts">
/**
 * Learning Space admin — class management sub-page.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import AdminLearningSpaceModal from '@/components/admin/AdminLearningSpaceModal.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import { normalizeSchoolTier } from '@/constants/schoolTier'
import {
  type AccountImportPreviewRow,
  type ImportPreviewRow,
  type LearningClassAssistant,
  type LearningClassRow,
  type LearningPilot,
  type LearningStudentRow,
  adminResetPassword,
  createAdminClass,
  listAdminClasses,
  listAdminPilots,
  listAdminStudents,
  patchAdminClass,
  previewAdminAccountImport,
  previewAdminImport,
  runAdminAccountImport,
  runAdminImport,
} from '@/utils/learningSpaceApi'
import { userRoleLabel } from '@/utils/userRoleDisplay'

const CLASS_CODE_RE = /^[A-Za-z0-9]{4,16}$/

const { t } = useLanguage()
const notify = useNotifications()
const { can } = useAdminAccess()
const route = useRoute()

const canEdit = computed(() => can('tab.learning_space.edit'))

const loading = ref(false)
const pilots = ref<LearningPilot[]>([])
const classes = ref<LearningClassRow[]>([])
const students = ref<LearningStudentRow[]>([])

const className = ref('')
const classPilotTeacherId = ref<number | ''>('')
const classMaxStudents = ref(60)
const filterTeacherId = ref<number | ''>('')
const filterStatus = ref<'all' | 'active' | 'archived'>('all')

const actionClass = ref<LearningClassRow | null>(null)
const showImportModal = ref(false)
const showAccountImportModal = ref(false)
const showDetailModal = ref(false)
const showEditModal = ref(false)

const editName = ref('')
const editMaxStudents = ref(60)
const editClassCode = ref('')
const editAssistants = ref<LearningClassAssistant[]>([])
const assistantPhone = ref('')
const importNamesText = ref('')
const importPreview = ref<ImportPreviewRow[]>([])
const accountPhonesText = ref('')
const accountPreview = ref<AccountImportPreviewRow[]>([])
const lastPasswords = ref('')
const detailLoading = ref(false)

const enabledPilots = computed(() => pilots.value.filter((p) => p.enabled))

const filteredClasses = computed(() => {
  return classes.value.filter((c) => {
    if (filterTeacherId.value !== '' && c.teacher_user_id !== Number(filterTeacherId.value)) {
      return false
    }
    if (filterStatus.value !== 'all' && c.status !== filterStatus.value) {
      return false
    }
    return true
  })
})

function parseNames(text: string): string[] {
  return text
    .split(/[\n,，;；]+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

function pilotLabel(pilot: LearningPilot): string {
  const name = pilot.teacher_name?.trim() || '—'
  const org = pilot.organization_name?.trim()
  return org ? `${name} · ${org}` : name
}

function sanitizeClassCodeInput(raw: string): string {
  return raw
    .replace(/[^A-Za-z0-9]/g, '')
    .slice(0, 16)
    .toUpperCase()
}

function onEditClassCodeInput(event: Event): void {
  const target = event.target as HTMLInputElement
  editClassCode.value = sanitizeClassCodeInput(target.value)
}

function applyTeacherPrefillFromRoute(): void {
  const raw = route.query.teacher_user_id
  if (typeof raw !== 'string' || !raw.trim()) return
  const id = Number(raw)
  if (!Number.isFinite(id) || id <= 0) return
  classPilotTeacherId.value = id
  filterTeacherId.value = id
}

async function loadAll(): Promise<void> {
  loading.value = true
  try {
    const [p, c] = await Promise.all([listAdminPilots(), listAdminClasses()])
    pilots.value = p.items
    classes.value = c.items
    applyTeacherPrefillFromRoute()
    if (actionClass.value != null) {
      const refreshed = classes.value.find((row) => row.id === actionClass.value?.id) ?? null
      actionClass.value = refreshed
    }
  } catch {
    notify.errorKey('admin.learningSpace.loadFailed')
  } finally {
    loading.value = false
  }
}

async function loadStudents(classId: number): Promise<void> {
  detailLoading.value = true
  try {
    const res = await listAdminStudents(classId)
    students.value = res.items
  } catch {
    notify.errorKey('admin.learningSpace.loadFailed')
  } finally {
    detailLoading.value = false
  }
}

async function onCreateClass(): Promise<void> {
  const teacherId = Number(classPilotTeacherId.value)
  if (!className.value.trim() || !Number.isFinite(teacherId) || teacherId <= 0) {
    notify.warningKey('admin.learningSpace.fillClassFields')
    return
  }
  try {
    await createAdminClass({
      name: className.value.trim(),
      teacher_user_id: teacherId,
      max_students: classMaxStudents.value || 60,
    })
    className.value = ''
    notify.successKey('admin.learningSpace.classCreated')
    await loadAll()
  } catch {
    notify.errorKey('admin.learningSpace.saveFailed')
  }
}

function closeModals(): void {
  showImportModal.value = false
  showAccountImportModal.value = false
  showDetailModal.value = false
  showEditModal.value = false
  actionClass.value = null
  importNamesText.value = ''
  importPreview.value = []
  accountPhonesText.value = ''
  accountPreview.value = []
  lastPasswords.value = ''
  students.value = []
  editAssistants.value = []
  assistantPhone.value = ''
}

function openImport(row: LearningClassRow): void {
  actionClass.value = row
  importNamesText.value = ''
  importPreview.value = []
  lastPasswords.value = ''
  showDetailModal.value = false
  showEditModal.value = false
  showAccountImportModal.value = false
  showImportModal.value = true
}

function openAccountImport(row: LearningClassRow): void {
  actionClass.value = row
  accountPhonesText.value = ''
  accountPreview.value = []
  showDetailModal.value = false
  showEditModal.value = false
  showImportModal.value = false
  showAccountImportModal.value = true
}

async function openDetail(row: LearningClassRow): Promise<void> {
  actionClass.value = row
  showImportModal.value = false
  showAccountImportModal.value = false
  showEditModal.value = false
  showDetailModal.value = true
  lastPasswords.value = ''
  await loadStudents(row.id)
}

function openEdit(row: LearningClassRow): void {
  actionClass.value = row
  editName.value = row.name
  editMaxStudents.value = row.max_students ?? 60
  editClassCode.value = row.class_code
  editAssistants.value = [...(row.assistants ?? [])]
  assistantPhone.value = ''
  showImportModal.value = false
  showAccountImportModal.value = false
  showDetailModal.value = false
  showEditModal.value = true
}

async function onSaveEdit(): Promise<void> {
  if (actionClass.value == null || !editName.value.trim()) {
    notify.warningKey('admin.learningSpace.fillClassFields')
    return
  }
  const code = sanitizeClassCodeInput(editClassCode.value)
  if (!CLASS_CODE_RE.test(code)) {
    notify.warningKey('admin.learningSpace.classCodeInvalid')
    return
  }
  try {
    await patchAdminClass(actionClass.value.id, {
      name: editName.value.trim(),
      max_students: editMaxStudents.value || 60,
      class_code: code,
      assistant_user_ids: editAssistants.value.map((a) => a.id),
    })
    notify.successKey('admin.learningSpace.classUpdated')
    showEditModal.value = false
    actionClass.value = null
    await loadAll()
  } catch {
    notify.errorKey('admin.learningSpace.saveFailed')
  }
}

async function onToggleClassLogin(row: LearningClassRow): Promise<void> {
  const disabling = row.status !== 'archived'
  try {
    await swissGlassConfirm(
      disabling
        ? t('admin.learningSpace.disableClassConfirm', { name: row.name })
        : t('admin.learningSpace.enableClassConfirm', { name: row.name }),
      disabling ? t('admin.learningSpace.disableClass') : t('admin.learningSpace.enableClass'),
      {
        type: disabling ? 'warning' : 'info',
        confirmButtonText: disabling
          ? t('admin.learningSpace.disableClass')
          : t('admin.learningSpace.enableClass'),
        cancelButtonText: t('common.cancel'),
      }
    )
  } catch {
    return
  }
  try {
    await patchAdminClass(row.id, { status: disabling ? 'archived' : 'active' })
    notify.success(
      disabling ? t('admin.learningSpace.classDisabled') : t('admin.learningSpace.classEnabled')
    )
    await loadAll()
  } catch {
    notify.errorKey('admin.learningSpace.saveFailed')
  }
}

async function onArchiveToggle(): Promise<void> {
  if (actionClass.value == null) return
  const row = actionClass.value
  showEditModal.value = false
  actionClass.value = null
  await onToggleClassLogin(row)
}

async function onCopyCode(code: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(code)
    notify.successKey('admin.learningSpace.codeCopied')
  } catch {
    notify.errorKey('admin.learningSpace.saveFailed')
  }
}

async function onPreviewImport(): Promise<void> {
  if (actionClass.value == null) return
  const names = parseNames(importNamesText.value)
  if (names.length === 0) {
    notify.warningKey('admin.learningSpace.enterNames')
    return
  }
  try {
    const res = await previewAdminImport(actionClass.value.id, names)
    importPreview.value = res.items
  } catch {
    notify.errorKey('admin.learningSpace.saveFailed')
  }
}

async function onRunImport(): Promise<void> {
  if (actionClass.value == null) return
  const names = parseNames(importNamesText.value)
  if (names.length === 0) {
    notify.warningKey('admin.learningSpace.enterNames')
    return
  }
  try {
    const res = await runAdminImport(actionClass.value.id, names)
    lastPasswords.value = res.created
      .map((row) => `${row.name}\t${row.initial_password}`)
      .join('\n')
    notify.successKey('admin.learningSpace.importDone', {
      ok: res.created.length,
      fail: res.failed.length,
    })
    importNamesText.value = ''
    importPreview.value = []
    await loadAll()
  } catch {
    notify.errorKey('admin.learningSpace.saveFailed')
  }
}

async function onPreviewAccountImport(): Promise<void> {
  if (actionClass.value == null) return
  const phones = parseNames(accountPhonesText.value)
  if (phones.length === 0) {
    notify.warningKey('admin.learningSpace.enterPhones')
    return
  }
  try {
    const res = await previewAdminAccountImport(actionClass.value.id, phones)
    accountPreview.value = res.items
  } catch {
    notify.errorKey('admin.learningSpace.saveFailed')
  }
}

async function onRunAccountImport(): Promise<void> {
  if (actionClass.value == null) return
  const phones = parseNames(accountPhonesText.value)
  if (phones.length === 0) {
    notify.warningKey('admin.learningSpace.enterPhones')
    return
  }
  try {
    const res = await runAdminAccountImport(actionClass.value.id, phones)
    notify.successKey('admin.learningSpace.importDone', {
      ok: res.created.length,
      fail: res.failed.length,
    })
    accountPhonesText.value = ''
    accountPreview.value = []
    showAccountImportModal.value = false
    actionClass.value = null
    await loadAll()
  } catch {
    notify.errorKey('admin.learningSpace.saveFailed')
  }
}

function accountImportError(code: string | null): string {
  if (!code) return '—'
  const key = `admin.learningSpace.accountImportError.${code}`
  const translated = t(key)
  return translated === key ? code : translated
}

function memberKindLabel(row: LearningStudentRow): string {
  if (row.member_kind === 'enrolled') {
    if (row.membership_role === 'assistant') {
      return t('admin.learningSpace.memberAssistant')
    }
    return t('admin.learningSpace.memberEnrolled')
  }
  return t('admin.learningSpace.memberClassroom')
}

function memberOrgLabel(row: LearningStudentRow): string {
  const org = (row.organization_name || '').trim()
  if (org) return org
  if (row.member_kind === 'enrolled' && row.role) {
    return userRoleLabel(t, row.role, row.school_tier ? normalizeSchoolTier(row.school_tier) : null)
  }
  return '—'
}

function removeAssistant(userId: number): void {
  editAssistants.value = editAssistants.value.filter((a) => a.id !== userId)
}

async function onAddAssistant(): Promise<void> {
  if (actionClass.value == null) return
  const phones = parseNames(assistantPhone.value)
  if (phones.length === 0) {
    notify.warningKey('admin.learningSpace.enterPhones')
    return
  }
  try {
    const res = await previewAdminAccountImport(actionClass.value.id, phones)
    let added = 0
    for (const row of res.items) {
      if (row.user_id == null) {
        notify.warning(accountImportError(row.error))
        continue
      }
      if (row.error === 'classroom_student' || row.error === 'is_class_teacher') {
        notify.warning(accountImportError(row.error))
        continue
      }
      if (editAssistants.value.some((a) => a.id === row.user_id)) {
        continue
      }
      editAssistants.value = [
        ...editAssistants.value,
        {
          id: row.user_id,
          name: row.name || row.phone,
          phone: row.phone,
          organization_name: row.organization_name || '',
        },
      ]
      added += 1
    }
    if (added > 0) {
      assistantPhone.value = ''
    }
  } catch {
    notify.errorKey('admin.learningSpace.saveFailed')
  }
}

async function onResetPassword(studentId: number): Promise<void> {
  try {
    const res = await adminResetPassword(studentId)
    lastPasswords.value = `${res.name}\t${res.initial_password}`
    notify.successKey('admin.learningSpace.passwordReset', { name: res.name })
    if (actionClass.value != null) {
      await loadStudents(actionClass.value.id)
    }
  } catch {
    notify.errorKey('admin.learningSpace.saveFailed')
  }
}

async function onCopyPasswords(): Promise<void> {
  if (!lastPasswords.value) return
  try {
    await navigator.clipboard.writeText(lastPasswords.value)
    notify.successKey('admin.learningSpace.passwordsCopied')
  } catch {
    notify.errorKey('admin.learningSpace.saveFailed')
  }
}

function studentPassword(row: LearningStudentRow): string {
  return (row.initial_password || '').trim()
}

function exportStudentRoster(): void {
  if (actionClass.value == null || !students.value.length) {
    notify.warningKey('admin.learningSpace.studentsEmpty')
    return
  }
  const header = [
    'ID',
    t('auth.name'),
    t('admin.learningSpace.memberKind'),
    t('admin.learningSpace.organization'),
    t('admin.learningSpace.initialPassword'),
  ].join(',')
  const lines = students.value.map((s) => {
    const name = `"${(s.name || '').replace(/"/g, '""')}"`
    const org = `"${memberOrgLabel(s).replace(/"/g, '""')}"`
    return [s.id, name, memberKindLabel(s), org, studentPassword(s)].join(',')
  })
  const csv = `\uFEFF${[header, ...lines].join('\n')}`
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  const safeName = (actionClass.value.name || 'class').replace(/[\\/:*?"<>|]/g, '_')
  anchor.href = url
  anchor.download = `${safeName}-students.csv`
  anchor.click()
  URL.revokeObjectURL(url)
  notify.successKey('admin.learningSpace.exportDone')
}

watch(
  () => route.query.teacher_user_id,
  () => {
    applyTeacherPrefillFromRoute()
  }
)

onMounted(() => {
  void loadAll()
})

defineExpose({ reload: loadAll })
</script>

<template>
  <div class="ls-admin-stack">
    <p
      v-if="loading"
      class="ls-muted"
    >
      <I18nText k="common.loading" />
    </p>

    <section class="ls-admin-card">
      <div class="ls-section-title">
        <h2><I18nText k="admin.learningSpace.createClassSection" /></h2>
      </div>
      <div
        v-if="canEdit"
        class="ls-toolbar"
      >
        <input
          v-model="className"
          type="text"
          class="ls-control"
          :placeholder="t('admin.learningSpace.className')"
        />
        <select
          v-model="classPilotTeacherId"
          class="ls-control ls-control--select"
        >
          <option value="">
            <I18nText k="admin.learningSpace.selectPilotTeacher" />
          </option>
          <option
            v-for="p in enabledPilots"
            :key="p.id"
            :value="p.teacher_user_id"
          >
            {{ pilotLabel(p) }}
          </option>
        </select>
        <input
          v-model.number="classMaxStudents"
          type="number"
          class="ls-control ls-control--narrow"
          min="1"
          max="200"
          :title="t('admin.learningSpace.maxStudents')"
        />
        <button
          type="button"
          class="ls-btn ls-btn--primary"
          :disabled="!className.trim() || !classPilotTeacherId || !enabledPilots.length"
          @click="onCreateClass"
        >
          <I18nText k="admin.learningSpace.addClass" />
        </button>
      </div>
      <p
        v-if="canEdit && !enabledPilots.length"
        class="ls-muted"
      >
        <I18nText k="admin.learningSpace.needEnabledPilot" />
      </p>
    </section>

    <section class="ls-admin-card">
      <div class="ls-section-title">
        <h2><I18nText k="admin.learningSpace.classList" /></h2>
      </div>
      <div class="ls-toolbar">
        <select
          v-model="filterTeacherId"
          class="ls-control ls-control--select"
        >
          <option value="">
            <I18nText k="admin.learningSpace.filterAllTeachers" />
          </option>
          <option
            v-for="p in pilots"
            :key="p.id"
            :value="p.teacher_user_id"
          >
            {{ pilotLabel(p) }}
          </option>
        </select>
        <select
          v-model="filterStatus"
          class="ls-control ls-control--select"
        >
          <option value="all">
            <I18nText k="admin.learningSpace.filterAllStatus" />
          </option>
          <option value="active">
            <I18nText k="admin.learningSpace.statusActive" />
          </option>
          <option value="archived">
            <I18nText k="admin.learningSpace.statusDisabled" />
          </option>
        </select>
      </div>
      <p
        v-if="!filteredClasses.length && !loading"
        class="ls-muted"
      >
        <I18nText k="admin.learningSpace.classesEmpty" />
      </p>
      <div
        v-else
        class="ls-table-wrap"
      >
        <table class="ls-table">
          <thead>
            <tr>
              <th><I18nText k="admin.learningSpace.className" /></th>
              <th><I18nText k="admin.learningSpace.classCode" /></th>
              <th><I18nText k="admin.learningSpace.teacher" /></th>
              <th><I18nText k="admin.learningSpace.students" /></th>
              <th><I18nText k="admin.learningSpace.assignmentCount" /></th>
              <th><I18nText k="admin.learningSpace.submissionCount" /></th>
              <th><I18nText k="admin.learningSpace.status" /></th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="c in filteredClasses"
              :key="c.id"
            >
              <td>{{ c.name }}</td>
              <td>
                <code>{{ c.class_code }}</code>
                <button
                  type="button"
                  class="ls-link"
                  @click="onCopyCode(c.class_code)"
                >
                  <I18nText k="admin.learningSpace.copy" />
                </button>
              </td>
              <td>{{ c.teacher_name || '—' }}</td>
              <td>{{ c.student_count }}</td>
              <td>{{ c.assignment_count ?? 0 }}</td>
              <td>{{ c.submission_count ?? 0 }}</td>
              <td>
                <I18nText
                  v-if="c.status === 'archived'"
                  k="admin.learningSpace.statusDisabled"
                /><I18nText
                  v-else
                  k="admin.learningSpace.statusActive"
                />
              </td>
              <td class="ls-actions">
                <button
                  v-if="canEdit"
                  type="button"
                  class="ls-btn ls-btn--ghost ls-btn--sm"
                  :disabled="c.status === 'archived'"
                  @click="openAccountImport(c)"
                >
                  <I18nText k="admin.learningSpace.importAccounts" />
                </button>
                <button
                  v-if="canEdit"
                  type="button"
                  class="ls-btn ls-btn--ghost ls-btn--sm"
                  :disabled="c.status === 'archived'"
                  @click="openImport(c)"
                >
                  <I18nText k="admin.learningSpace.importStudents" />
                </button>
                <button
                  type="button"
                  class="ls-btn ls-btn--ghost ls-btn--sm"
                  @click="openDetail(c)"
                >
                  <I18nText k="admin.learningSpace.viewDetail" />
                </button>
                <button
                  v-if="canEdit"
                  type="button"
                  class="ls-btn ls-btn--ghost ls-btn--sm"
                  @click="openEdit(c)"
                >
                  <I18nText k="admin.learningSpace.edit" />
                </button>
                <button
                  v-if="canEdit"
                  type="button"
                  class="ls-btn ls-btn--ghost ls-btn--sm"
                  @click="onToggleClassLogin(c)"
                >
                  <I18nText
                    v-if="c.status === 'archived'"
                    k="admin.learningSpace.enableClass"
                  /><I18nText
                    v-else
                    k="admin.learningSpace.disableClass"
                  />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <AdminLearningSpaceModal
      v-model="showImportModal"
      wide
      :title="t('admin.learningSpace.importStudents')"
      :eyebrow="actionClass?.name || ''"
      :hint="t('admin.learningSpace.importHint')"
      @close="closeModals"
    >
      <div
        v-if="actionClass"
        class="ls-form-grid"
      >
        <textarea
          v-model="importNamesText"
          class="ls-control"
          rows="6"
          :placeholder="t('admin.learningSpace.importPlaceholder')"
          :disabled="!canEdit || actionClass.status === 'archived'"
        />
        <div
          v-if="canEdit && actionClass.status !== 'archived'"
          class="ls-toolbar"
        >
          <button
            type="button"
            class="ls-btn ls-btn--ghost"
            :disabled="!importNamesText.trim()"
            @click="onPreviewImport"
          >
            <I18nText k="admin.learningSpace.preview" />
          </button>
          <button
            type="button"
            class="ls-btn ls-btn--primary"
            :disabled="!importNamesText.trim()"
            @click="onRunImport"
          >
            <I18nText k="admin.learningSpace.import" />
          </button>
        </div>
        <table
          v-if="importPreview.length"
          class="ls-table"
        >
          <thead>
            <tr>
              <th><I18nText k="auth.name" /></th>
              <th><I18nText k="admin.learningSpace.initialPassword" /></th>
              <th><I18nText k="admin.learningSpace.status" /></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, idx) in importPreview"
              :key="idx"
            >
              <td>{{ row.name }}</td>
              <td>{{ row.initial_password }}</td>
              <td>{{ row.ok ? 'OK' : row.error }}</td>
            </tr>
          </tbody>
        </table>
        <div
          v-if="lastPasswords"
          class="ls-passwords"
        >
          <div class="ls-toolbar">
            <h4 class="ls-subh"><I18nText k="admin.learningSpace.passwordsOnce" /></h4>
            <button
              type="button"
              class="ls-btn ls-btn--ghost ls-btn--sm"
              @click="onCopyPasswords"
            >
              <I18nText k="admin.learningSpace.copyPasswords" />
            </button>
          </div>
          <pre>{{ lastPasswords }}</pre>
        </div>
      </div>
    </AdminLearningSpaceModal>

    <AdminLearningSpaceModal
      v-model="showAccountImportModal"
      wide
      :title="t('admin.learningSpace.importAccounts')"
      :eyebrow="actionClass?.name || ''"
      :hint="t('admin.learningSpace.importAccountsHint')"
      @close="closeModals"
    >
      <div
        v-if="actionClass"
        class="ls-form-grid"
      >
        <textarea
          v-model="accountPhonesText"
          class="ls-control"
          rows="6"
          :placeholder="t('admin.learningSpace.importAccountsPlaceholder')"
          :disabled="!canEdit || actionClass.status === 'archived'"
        />
        <div
          v-if="canEdit && actionClass.status !== 'archived'"
          class="ls-toolbar"
        >
          <button
            type="button"
            class="ls-btn ls-btn--ghost ls-btn--sm"
            :disabled="!accountPhonesText.trim()"
            @click="onPreviewAccountImport"
          >
            <I18nText k="admin.learningSpace.preview" />
          </button>
          <button
            type="button"
            class="ls-btn ls-btn--primary"
            :disabled="!accountPhonesText.trim()"
            @click="onRunAccountImport"
          >
            <I18nText k="admin.learningSpace.import" />
          </button>
        </div>
        <table
          v-if="accountPreview.length"
          class="ls-table"
        >
          <thead>
            <tr>
              <th><I18nText k="admin.learningSpace.phone" /></th>
              <th><I18nText k="auth.name" /></th>
              <th><I18nText k="admin.learningSpace.organization" /></th>
              <th><I18nText k="admin.learningSpace.status" /></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, idx) in accountPreview"
              :key="idx"
            >
              <td>{{ row.phone }}</td>
              <td>{{ row.name || '—' }}</td>
              <td>{{ row.organization_name || '—' }}</td>
              <td>{{ row.ok ? 'OK' : accountImportError(row.error) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </AdminLearningSpaceModal>

    <AdminLearningSpaceModal
      v-model="showDetailModal"
      wide
      :title="t('admin.learningSpace.manageClass', { name: actionClass?.name || '' })"
      :eyebrow="
        actionClass ? `${t('admin.learningSpace.classCode')}: ${actionClass.class_code}` : ''
      "
      :hint="t('admin.learningSpace.detailHint')"
      @close="closeModals"
    >
      <div
        v-if="actionClass"
        class="ls-form-grid"
      >
        <div class="ls-toolbar">
          <button
            type="button"
            class="ls-btn ls-btn--primary"
            :disabled="!students.length"
            @click="exportStudentRoster"
          >
            <I18nText k="admin.learningSpace.exportRoster" />
          </button>
          <button
            type="button"
            class="ls-btn ls-btn--ghost ls-btn--sm"
            @click="onCopyCode(actionClass.class_code)"
          >
            <I18nText k="admin.learningSpace.copyCode" />
          </button>
        </div>
        <p
          v-if="detailLoading"
          class="ls-muted"
        >
          <I18nText k="common.loading" />
        </p>
        <table
          v-else
          class="ls-table"
        >
          <thead>
            <tr>
              <th>ID</th>
              <th><I18nText k="auth.name" /></th>
              <th><I18nText k="admin.learningSpace.memberKind" /></th>
              <th><I18nText k="admin.learningSpace.organization" /></th>
              <th><I18nText k="admin.learningSpace.phone" /></th>
              <th><I18nText k="admin.learningSpace.initialPassword" /></th>
              <th><I18nText k="admin.learningSpace.mustChangePassword" /></th>
              <th v-if="canEdit" />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in students"
              :key="s.id"
            >
              <td>{{ s.id }}</td>
              <td>{{ s.name }}</td>
              <td>{{ memberKindLabel(s) }}</td>
              <td>{{ memberOrgLabel(s) }}</td>
              <td>{{ s.phone || '—' }}</td>
              <td>
                <code>{{ studentPassword(s) || '—' }}</code>
              </td>
              <td>
                <I18nText
                  v-if="s.must_change_password"
                  k="admin.learningSpace.yes"
                /><I18nText
                  v-else
                  k="admin.learningSpace.no"
                />
              </td>
              <td v-if="canEdit">
                <button
                  v-if="s.member_kind !== 'enrolled'"
                  type="button"
                  class="ls-btn ls-btn--ghost ls-btn--sm"
                  @click="onResetPassword(s.id)"
                >
                  <I18nText k="admin.learningSpace.resetPassword" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <p
          v-if="!detailLoading && !students.length"
          class="ls-muted"
        >
          <I18nText k="admin.learningSpace.studentsEmpty" />
        </p>
        <div
          v-if="lastPasswords"
          class="ls-passwords"
        >
          <div class="ls-toolbar">
            <h4 class="ls-subh"><I18nText k="admin.learningSpace.passwordsOnce" /></h4>
            <button
              type="button"
              class="ls-btn ls-btn--ghost ls-btn--sm"
              @click="onCopyPasswords"
            >
              <I18nText k="admin.learningSpace.copyPasswords" />
            </button>
          </div>
          <pre>{{ lastPasswords }}</pre>
        </div>
      </div>
    </AdminLearningSpaceModal>

    <AdminLearningSpaceModal
      v-model="showEditModal"
      :title="t('admin.learningSpace.editClass', { name: actionClass?.name || '' })"
      :eyebrow="t('admin.learningSpace.edit')"
      :hint="t('admin.learningSpace.classCodeHint')"
      @close="closeModals"
    >
      <div
        v-if="actionClass && canEdit"
        class="ls-form-grid"
      >
        <div class="ls-form-grid">
          <label class="ls-field">
            <I18nText k="admin.learningSpace.className" />
            <input
              v-model="editName"
              type="text"
              class="ls-control ls-control--block"
            />
          </label>
          <label class="ls-field">
            <I18nText k="admin.learningSpace.classCode" />
            <input
              :value="editClassCode"
              type="text"
              class="ls-control ls-control--block"
              maxlength="16"
              autocomplete="off"
              spellcheck="false"
              :placeholder="t('admin.learningSpace.classCodeHint')"
              @input="onEditClassCodeInput"
            />
          </label>
          <label class="ls-field">
            <I18nText k="admin.learningSpace.maxStudents" />
            <input
              v-model.number="editMaxStudents"
              type="number"
              class="ls-control ls-control--narrow"
              min="1"
              max="200"
            />
          </label>
          <div class="ls-field">
            <I18nText k="admin.learningSpace.assistants" />
            <p class="ls-muted"><I18nText k="admin.learningSpace.assistantsHint" /></p>
            <ul
              v-if="editAssistants.length"
              class="ls-assistant-list"
            >
              <li
                v-for="a in editAssistants"
                :key="a.id"
              >
                <span>{{ a.name }}{{ a.phone ? ` · ${a.phone}` : '' }}</span>
                <button
                  type="button"
                  class="ls-btn ls-btn--ghost ls-btn--sm"
                  @click="removeAssistant(a.id)"
                >
                  <I18nText k="common.delete" />
                </button>
              </li>
            </ul>
            <div class="ls-toolbar">
              <input
                v-model="assistantPhone"
                type="text"
                class="ls-control"
                :placeholder="t('admin.learningSpace.assistantPhonePlaceholder')"
                @keydown.enter.prevent="onAddAssistant"
              />
              <button
                type="button"
                class="ls-btn ls-btn--ghost ls-btn--sm"
                :disabled="!assistantPhone.trim()"
                @click="onAddAssistant"
              >
                <I18nText k="admin.learningSpace.addAssistant" />
              </button>
            </div>
          </div>
        </div>
        <div class="ls-toolbar">
          <button
            type="button"
            class="ls-btn ls-btn--primary"
            :disabled="
              !editName.trim() || !CLASS_CODE_RE.test(sanitizeClassCodeInput(editClassCode))
            "
            @click="onSaveEdit"
          >
            <I18nText k="common.save" />
          </button>
          <button
            type="button"
            class="ls-btn ls-btn--ghost ls-btn--sm"
            @click="onArchiveToggle"
          >
            <I18nText
              v-if="actionClass.status === 'archived'"
              k="admin.learningSpace.enableClass"
            /><I18nText
              v-else
              k="admin.learningSpace.disableClass"
            />
          </button>
          <button
            type="button"
            class="ls-btn ls-btn--ghost ls-btn--sm"
            @click="closeModals"
          >
            <I18nText k="common.cancel" />
          </button>
        </div>
      </div>
    </AdminLearningSpaceModal>
  </div>
</template>
