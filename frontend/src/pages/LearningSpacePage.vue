<script setup lang="ts">
/**
 * Learning Space — teacher + student homework shell.
 * Route: /learning-space
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import LearningSpaceAssignModal from '@/components/learningSpace/LearningSpaceAssignModal.vue'
import LearningSpaceHeader from '@/components/learningSpace/LearningSpaceHeader.vue'
import LearningSpaceRequirementsModal from '@/components/learningSpace/LearningSpaceRequirementsModal.vue'
import LearningSpaceReviewModal, {
  type ReviewDraft,
} from '@/components/learningSpace/LearningSpaceReviewModal.vue'
import LearningSpaceSubmissionStatusModal from '@/components/learningSpace/LearningSpaceSubmissionStatusModal.vue'
import { swissGlassConfirm, useLanguage, useNotifications } from '@/composables'
import {
  assignmentDiagramType,
  assignmentIsClosed,
  assignmentProgress,
  filterTeacherAssignments,
  formatLsDateTime,
  greetHourLabel,
  studentAssignmentDone,
  studentAssignmentPending,
  studentCanOpenAssignment,
  type AssignmentFilter,
  type StudentTab,
  type TeacherTab,
} from '@/composables/learningSpace/lsHelpers'
import { useAuthStore } from '@/stores'
import { AUTH_USER_STORAGE_KEY } from '@/stores/auth'
import { useLearningAssignmentCanvasStore } from '@/stores/learningAssignmentCanvas'
import {
  type LearningAssignment,
  type LearningClassRow,
  type LearningSpaceContext,
  type LearningStudentRow,
  type LearningSubmission,
  deleteTeacherAssignment,
  fetchLearningSpaceContext,
  listStudentAssignments,
  listStudentClassWall,
  listTeacherAssignments,
  listTeacherClasses,
  listTeacherStudents,
  listTeacherSubmissions,
  openStudentAssignment,
  saveTeacherReview,
  studentChangePassword,
  submitStudentAssignment,
} from '@/utils/learningSpaceApi'
import {
  AlertTriangle,
  ArrowLeft,
  ClipboardList,
  Clock3,
  FileText,
  Users,
} from '@lucide/vue'
import '@/styles/learning-space.css'

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const router = useRouter()
const lsShell = useLearningAssignmentCanvasStore()

const loading = ref(true)
const context = ref<LearningSpaceContext | null>(null)
const classes = ref<LearningClassRow[]>([])
const selectedClassId = ref<number | null>(null)
const teacherAssignments = ref<LearningAssignment[]>([])
const allClassAssignments = ref<LearningAssignment[]>([])
const selectedAssignmentId = ref<number | null>(null)
const submissions = ref<LearningSubmission[]>([])
const classStudents = ref<LearningStudentRow[]>([])
const studentAssignments = ref<LearningAssignment[]>([])
const studentDetailId = ref<number | null>(null)

const teacherTab = ref<TeacherTab>('dashboard')
const studentTab = ref<StudentTab>('home')
const assignmentFilter = ref<AssignmentFilter>('all')
const assignmentQuery = ref('')

const showCreateForm = ref(false)
const showSubmissionStatus = ref(false)
const showRequirements = ref(false)
const reqAssignment = ref<LearningAssignment | null>(null)
const deletingAssignmentId = ref<number | null>(null)
const showReview = ref(false)
const reviewMode = ref<'edit' | 'view'>('edit')
const reviewSubmission = ref<LearningSubmission | null>(null)
const reviewsBySubmissionId = ref<Record<number, ReviewDraft>>({})
const classWall = ref<LearningSubmission[]>([])

const newPassword = ref('')
const confirmPassword = ref('')
const changingPassword = ref(false)

const mustChangePassword = computed(
  () =>
    context.value?.must_change_password === true ||
    authStore.user?.mustChangePassword === true
)

const canLearn = computed(() => {
  if (context.value?.can_learn === true || context.value?.role === 'student' || context.value?.role === 'learner') {
    return true
  }
  if (context.value?.role === 'pilot_teacher' || context.value?.role === 'superadmin') {
    return false
  }
  return authStore.user?.role === 'student'
})
const canReview = computed(
  () =>
    context.value?.can_review === true ||
    context.value?.role === 'pilot_teacher' ||
    context.value?.role === 'assistant' ||
    context.value?.role === 'superadmin'
)
const canPublish = computed(() => context.value?.can_publish === true)
const preferTeacherShell = ref(true)
const isStudent = computed(
  () => canLearn.value && (!canReview.value || !preferTeacherShell.value)
)
const isPilot = computed(
  () => canReview.value && (!canLearn.value || preferTeacherShell.value)
)
const showLsHeader = computed(
  () => isStudent.value || isPilot.value || loading.value
)
const showShellSwitch = computed(() => canLearn.value && canReview.value)

const userName = computed(
  () => authStore.user?.username || authStore.user?.phone || t('learningSpace.userFallback')
)

const selectedClass = computed(
  () => classes.value.find((c) => c.id === selectedClassId.value) ?? null
)

const publishableClasses = computed(() =>
  classes.value.filter((c) => c.can_publish === true && c.status !== 'archived')
)

function canDeleteAssignment(a: LearningAssignment): boolean {
  return canPublish.value && publishableClasses.value.some((c) => c.id === a.class_id)
}

const filteredAssignments = computed(() =>
  filterTeacherAssignments(teacherAssignments.value, assignmentFilter.value, assignmentQuery.value)
)

const pendingGradeCount = computed(() =>
  allClassAssignments.value.reduce((sum, a) => sum + (a.submitted_count ?? 0), 0)
)

const studentTodoCount = computed(
  () => studentAssignments.value.filter((a) => studentAssignmentPending(a)).length
)

const teacherMetrics = computed(() => {
  let pending = 0
  let unsubmitted = 0
  let active = 0
  for (const a of allClassAssignments.value) {
    const p = progressFor(a)
    pending += a.submitted_count ?? 0
    unsubmitted += p.unsubmitted
    if (!assignmentIsClosed(a) && a.status !== 'draft') active += 1
  }
  return {
    pending,
    unsubmitted,
    active,
    classCount: classes.value.length,
  }
})

const greetKey = computed(() => {
  const g = greetHourLabel(new Date().getHours())
  if (g === 'morning') return 'learningSpace.greetMorning'
  if (g === 'afternoon') return 'learningSpace.greetAfternoon'
  return 'learningSpace.greetEvening'
})

const selectedAssignment = computed(
  () =>
    teacherAssignments.value.find((a) => a.id === selectedAssignmentId.value) ??
    allClassAssignments.value.find((a) => a.id === selectedAssignmentId.value) ??
    null
)

const studentDetail = computed(
  () => studentAssignments.value.find((a) => a.id === studentDetailId.value) ?? null
)

const submittedStudentIds = computed(() => {
  const ids = new Set<number>()
  for (const s of submissions.value) {
    if (s.status === 'submitted') ids.add(s.student_user_id)
  }
  return ids
})

const studentSubmittedCount = computed(
  () => studentAssignments.value.filter((a) => studentAssignmentDone(a)).length
)

const studentUrgentCount = computed(
  () =>
    studentAssignments.value.filter(
      (a) => studentAssignmentPending(a) && a.due_at && !assignmentIsClosed(a)
    ).length
)

const wallSubmissions = computed(() =>
  submissions.value.filter((s) => s.status === 'submitted')
)

const detailClassWall = computed(() => {
  const id = studentDetail.value?.id
  if (id == null) return []
  return classWall.value.filter((s) => s.assignment_id === id)
})

const myDetailSubmission = computed(() => {
  const detail = studentDetail.value
  if (!detail) return null
  const uid = authStore.user?.id
  const fromWall = detailClassWall.value.find((s) => Number(s.student_user_id) === Number(uid))
  if (fromWall) return fromWall
  const sub = detail.submission
  if (!sub || (sub.status !== 'submitted' && sub.status !== 'returned')) return null
  return {
    ...sub,
    assignment_id: detail.id,
    assignment_title: detail.title,
    student_name: authStore.user?.username || undefined,
  } as LearningSubmission
})

const myPortfolio = computed(() => {
  const uid = authStore.user?.id
  if (uid == null) return []
  const fromWall = classWall.value.filter((s) => Number(s.student_user_id) === Number(uid))
  if (fromWall.length) return fromWall
  return studentAssignments.value
    .filter((a) => a.submission && (a.submission.status === 'submitted' || a.submission.status === 'returned'))
    .map((a) => ({
      ...a.submission!,
      assignment_id: a.id,
      assignment_title: a.title,
      student_name: authStore.user?.username || undefined,
      diagram_thumbnail: a.submission?.diagram_thumbnail || a.template_thumbnail || null,
    }))
})

function goTeacherAssignments(filter: AssignmentFilter = 'all'): void {
  selectedAssignmentId.value = null
  assignmentFilter.value = filter
  teacherTab.value = 'assignments'
}

function goTeacherClasses(): void {
  selectedAssignmentId.value = null
  teacherTab.value = 'classes'
}

function statusLabel(status: string | undefined): string {
  if (status === 'submitted') return t('learningSpace.statusSubmitted')
  if (status === 'returned') return t('learningSpace.statusReturned')
  if (status === 'draft') return t('learningSpace.statusDraft')
  return t('learningSpace.notStarted')
}

function assignmentStatusBadge(a: LearningAssignment): { text: string; tone: string } {
  if (a.status === 'draft') return { text: t('learningSpace.filterDraft'), tone: 'draft' }
  if (assignmentIsClosed(a)) return { text: t('learningSpace.statusClosed'), tone: 'closed' }
  return { text: t('learningSpace.statusActive'), tone: 'active' }
}

function seedStudentContextFromAuth(): void {
  if (authStore.user?.role !== 'student') {
    return
  }
  context.value = {
    role: 'student',
    must_change_password: authStore.user.mustChangePassword === true,
  }
}

async function loadStudentAssignmentsIfReady(): Promise<void> {
  if (!canLearn.value || mustChangePassword.value) {
    return
  }
  try {
    const [asg, wall] = await Promise.all([listStudentAssignments(), listStudentClassWall()])
    studentAssignments.value = Array.isArray(asg.items) ? asg.items : []
    classWall.value = Array.isArray(wall.items) ? wall.items : []
    for (const item of classWall.value) {
      if (item.reviewed_at || item.review_comment || item.review_scores) {
        reviewsBySubmissionId.value[item.id] = {
          scores: { ...(item.review_scores ?? {}) },
          comment: item.review_comment ?? '',
          liked: Boolean(item.review_liked),
          pinned: Boolean(item.review_pinned),
        }
      }
    }
  } catch {
    notify.error(t('learningSpace.loadFailed'))
  }
}

async function loadContext(): Promise<void> {
  loading.value = true
  try {
    context.value = await fetchLearningSpaceContext()
    preferTeacherShell.value =
      context.value.can_review === true ||
      context.value.role === 'pilot_teacher' ||
      context.value.role === 'assistant' ||
      context.value.role === 'superadmin'
    if (context.value.can_learn || context.value.role === 'student' || context.value.role === 'learner') {
      await loadStudentAssignmentsIfReady()
    }
    if (
      context.value.can_review ||
      context.value.role === 'pilot_teacher' ||
      context.value.role === 'assistant' ||
      context.value.role === 'superadmin'
    ) {
      try {
        const res = await listTeacherClasses()
        classes.value = Array.isArray(res.items) ? res.items : []
      } catch {
        classes.value = []
      }
      selectedClassId.value =
        classes.value.find((row) => row.status !== 'archived')?.id ?? classes.value[0]?.id ?? null
      await refreshAllClassAssignments()
      await loadTeacherAssignments()
    } else if (context.value.role === 'none' && authStore.user?.role === 'student') {
      // Auth says student but LS context failed to classify — keep student shell usable.
      seedStudentContextFromAuth()
      await loadStudentAssignmentsIfReady()
    }
  } catch {
    if (authStore.user?.role === 'student') {
      seedStudentContextFromAuth()
      await loadStudentAssignmentsIfReady()
    } else {
      notify.error(t('learningSpace.loadFailed'))
    }
  } finally {
    loading.value = false
  }
}

async function refreshAllClassAssignments(): Promise<void> {
  const bags = await Promise.all(
    classes.value.map(async (c) => {
      try {
        const res = await listTeacherAssignments(c.id)
        return res.items
      } catch {
        return [] as LearningAssignment[]
      }
    })
  )
  allClassAssignments.value = bags.flat()
}

async function loadTeacherAssignments(): Promise<void> {
  if (selectedClassId.value == null) {
    teacherAssignments.value = []
    return
  }
  try {
    const res = await listTeacherAssignments(selectedClassId.value)
    teacherAssignments.value = res.items
  } catch {
    notify.error(t('learningSpace.loadFailed'))
  }
}

async function loadSubmissionsAndRoster(): Promise<void> {
  if (selectedAssignmentId.value == null) {
    submissions.value = []
    classStudents.value = []
    return
  }
  const asg = selectedAssignment.value
  try {
    const [subRes, stuRes] = await Promise.all([
      listTeacherSubmissions(selectedAssignmentId.value),
      asg ? listTeacherStudents(asg.class_id) : Promise.resolve({ items: [] }),
    ])
    submissions.value = subRes.items
    classStudents.value = stuRes.items
    for (const item of subRes.items) {
      if (item.reviewed_at || item.review_comment || item.review_scores) {
        reviewsBySubmissionId.value[item.id] = {
          scores: { ...(item.review_scores ?? {}) },
          comment: item.review_comment ?? '',
          liked: Boolean(item.review_liked),
          pinned: Boolean(item.review_pinned),
        }
      }
    }
  } catch {
    notify.error(t('learningSpace.loadFailed'))
  }
}

watch(selectedClassId, () => {
  selectedAssignmentId.value = null
  void loadTeacherAssignments()
  if (teacherTab.value === 'classes' && selectedClassId.value != null) {
    void loadClassRoster(selectedClassId.value)
  }
})

watch(selectedAssignmentId, () => {
  void loadSubmissionsAndRoster()
})

watch(teacherTab, (tab) => {
  if (tab !== 'assignments') {
    selectedAssignmentId.value = null
  }
  if (tab === 'classes' && selectedClassId.value != null) {
    void loadClassRoster(selectedClassId.value)
  }
})

async function loadClassRoster(classId: number): Promise<void> {
  try {
    const r = await listTeacherStudents(classId)
    classStudents.value = r.items
  } catch {
    classStudents.value = []
  }
}

watch(studentTab, () => {
  studentDetailId.value = null
})

function openCreateAssignmentModal(): void {
  if (!canPublish.value) {
    return
  }
  const owned = publishableClasses.value
  if (!owned.length) {
    notify.warning(t('learningSpace.noPublishableClass'))
    return
  }
  if (selectedClassId.value == null || !owned.some((c) => c.id === selectedClassId.value)) {
    selectedClassId.value = owned[0]?.id ?? null
  }
  showCreateForm.value = true
}

async function onAssignmentCreated(): Promise<void> {
  await loadTeacherAssignments()
  await refreshAllClassAssignments()
  teacherTab.value = 'assignments'
}

async function onChangePassword(): Promise<void> {
  if (newPassword.value.length < 6) {
    notify.warning(t('learningSpace.passwordMin6'))
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    notify.warning(t('auth.modal.passwordMismatch'))
    return
  }
  changingPassword.value = true
  try {
    await studentChangePassword(newPassword.value)
    if (authStore.user) {
      authStore.user.mustChangePassword = false
      sessionStorage.setItem(AUTH_USER_STORAGE_KEY, JSON.stringify(authStore.user))
    }
    if (context.value) {
      context.value.must_change_password = false
    }
    notify.success(t('learningSpace.savePassword'))
  } catch (error) {
    const message = error instanceof Error ? error.message.trim() : ''
    notify.error(message || t('learningSpace.saveFailed'))
    return
  } finally {
    changingPassword.value = false
  }
  try {
    const res = await listStudentAssignments()
    studentAssignments.value = res.items
  } catch {
    notify.error(t('learningSpace.loadFailed'))
  }
}

async function onOpenStudentAssignment(a: LearningAssignment): Promise<void> {
  if (!studentCanOpenAssignment(a)) {
    notify.warning(t('learningSpace.homeworkClosed'))
    return
  }
  try {
    const res = await openStudentAssignment(a.id)
    await router.push({
      path: '/canvas',
      query: {
        assignmentId: String(a.id),
        diagramId: res.submission.diagram_id,
      },
    })
  } catch {
    notify.error(t('learningSpace.openFailed'))
  }
}

async function onSubmitStudent(a: LearningAssignment): Promise<void> {
  try {
    await swissGlassConfirm(
      t('learningSpace.submitConfirm'),
      t('learningSpace.submit'),
      {
        confirmButtonText: t('learningSpace.submit'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
  } catch {
    return
  }
  try {
    await submitStudentAssignment(a.id)
    notify.success(t('learningSpace.submitSuccess'))
    const res = await listStudentAssignments()
    studentAssignments.value = res.items
    studentDetailId.value = null
  } catch {
    notify.error(t('learningSpace.submitFailed'))
  }
}

function openTeacherAssignment(a: LearningAssignment): void {
  selectedClassId.value = a.class_id
  selectedAssignmentId.value = a.id
  teacherTab.value = 'assignments'
}

function openReview(sub: LearningSubmission, mode: 'edit' | 'view' = 'edit'): void {
  reviewMode.value = mode
  reviewSubmission.value = sub
  showReview.value = true
}

function isSubmissionReviewed(submissionId: number): boolean {
  const cached = reviewsBySubmissionId.value[submissionId]
  if (cached) return true
  const fromList = submissions.value.find((s) => s.id === submissionId)
  return Boolean(fromList?.reviewed_at || fromList?.review_comment || fromList?.review_scores)
}

async function onReviewSave(payload: { submissionId: number; draft: ReviewDraft }): Promise<void> {
  try {
    const updated = await saveTeacherReview(payload.submissionId, payload.draft)
    reviewsBySubmissionId.value = {
      ...reviewsBySubmissionId.value,
      [payload.submissionId]: payload.draft,
    }
    submissions.value = submissions.value.map((s) =>
      s.id === payload.submissionId ? { ...s, ...updated } : s
    )
    notify.success(t('learningSpace.reviewSaved'))
    showReview.value = false
  } catch {
    notify.error(t('learningSpace.saveFailed'))
  }
}

function assignmentEvalDimensions(a: LearningAssignment | null): string[] {
  if (!a) return []
  const raw = a.ai_permissions as Record<string, unknown> | undefined
  const dims = raw?.evaluation_dimensions
  if (!Array.isArray(dims)) return []
  return dims.map((d) => String(d).trim()).filter(Boolean)
}

function classNameForAssignment(a: LearningAssignment): string {
  return classes.value.find((c) => c.id === a.class_id)?.name || t('learningSpace.class')
}

function rosterSizeFor(a: LearningAssignment): number | undefined {
  return classes.value.find((c) => c.id === a.class_id)?.student_count
}

function progressFor(a: LearningAssignment) {
  return assignmentProgress(a, rosterSizeFor(a))
}

function openRequirements(a: LearningAssignment): void {
  reqAssignment.value = a
  showRequirements.value = true
}

async function onDeleteAssignment(a: LearningAssignment): Promise<void> {
  if (!canDeleteAssignment(a)) {
    return
  }
  try {
    await swissGlassConfirm(
      t('learningSpace.deleteAssignmentConfirm', { title: a.title }),
      t('learningSpace.deleteAssignment'),
      {
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
  } catch {
    return
  }
  deletingAssignmentId.value = a.id
  try {
    await deleteTeacherAssignment(a.id)
    notify.success(t('learningSpace.assignmentDeleted'))
    if (selectedAssignmentId.value === a.id) {
      selectedAssignmentId.value = null
    }
    if (reqAssignment.value?.id === a.id) {
      showRequirements.value = false
      reqAssignment.value = null
    }
    await loadTeacherAssignments()
    await refreshAllClassAssignments()
  } catch {
    notify.error(t('learningSpace.deleteFailed'))
  } finally {
    deletingAssignmentId.value = null
  }
}

watch(
  () => [authStore.user?.id, authStore.user?.role] as const,
  ([userId], [prevId]) => {
    if (userId != null && userId !== prevId) {
      void loadContext()
    }
  }
)

onMounted(() => {
  if (authStore.user?.role === 'student') {
    seedStudentContextFromAuth()
  }
  void loadContext()
})

watch(
  () => lsShell.shellEpoch,
  (epoch, prev) => {
    if (prev === undefined || epoch === prev) return
    void loadContext()
  }
)
</script>

<template>
  <div class="ls-app">
    <LearningSpaceHeader
      v-if="showLsHeader"
      :mode="isStudent ? 'student' : 'teacher'"
      :teacher-tab="teacherTab"
      :student-tab="studentTab"
      :pending-badge="isStudent ? studentTodoCount : pendingGradeCount"
      :show-shell-switch="showShellSwitch"
      @update:teacher-tab="teacherTab = $event"
      @update:student-tab="studentTab = $event"
      @update:mode="preferTeacherShell = $event === 'teacher'"
    />

    <div class="ls-app__body">
      <div class="ls-app__inner">
        <p
          v-if="loading"
          class="ls-muted"
        >
          {{ t('common.loading') }}
        </p>

        <!-- Password gate -->
        <section
          v-else-if="isStudent && mustChangePassword"
          class="ls-gate"
        >
          <h2>{{ t('learningSpace.changePasswordTitle') }}</h2>
          <p class="ls-muted">{{ t('learningSpace.changePasswordHint') }}</p>
          <div class="ls-form-grid" style="margin-top: 1rem">
            <label class="ls-field">
              {{ t('auth.modal.newPassword') }}
              <input
                v-model="newPassword"
                type="password"
                autocomplete="new-password"
              />
            </label>
            <label class="ls-field">
              {{ t('auth.modal.confirmPassword') }}
              <input
                v-model="confirmPassword"
                type="password"
                autocomplete="new-password"
              />
            </label>
            <button
              type="button"
              class="ls-btn ls-btn--primary"
              :disabled="
                changingPassword ||
                newPassword.length < 6 ||
                newPassword !== confirmPassword
              "
              @click="onChangePassword"
            >
              {{ t('learningSpace.savePassword') }}
            </button>
          </div>
        </section>

        <!-- ===== Teacher ===== -->
        <template v-else-if="isPilot">
          <!-- Dashboard -->
          <template v-if="teacherTab === 'dashboard' && selectedAssignmentId == null">
            <div class="ls-page-head">
              <div>
                <h1>{{ t(greetKey, { name: userName }) }}</h1>
                <p>
                  {{
                    t('learningSpace.dashboardHint', {
                      pending: teacherMetrics.pending,
                      unsubmitted: teacherMetrics.unsubmitted,
                    })
                  }}
                </p>
              </div>
              <button
                v-if="canPublish"
                type="button"
                class="ls-btn ls-btn--primary"
                :disabled="!publishableClasses.length"
                @click="openCreateAssignmentModal"
              >
                {{ t('learningSpace.createAssignment') }}
              </button>
            </div>

            <div class="ls-metrics">
              <button
                type="button"
                class="ls-metric"
                @click="goTeacherAssignments('pending')"
              >
                <Clock3
                  class="ls-metric__icon"
                  :size="20"
                />
                <div class="ls-metric__label">{{ t('learningSpace.metricPending') }}</div>
                <div class="ls-metric__value">{{ teacherMetrics.pending }}</div>
                <div class="ls-metric__hint">{{ t('learningSpace.metricPendingHint') }}</div>
              </button>
              <button
                type="button"
                class="ls-metric ls-metric--alert"
                @click="goTeacherAssignments('all')"
              >
                <AlertTriangle
                  class="ls-metric__icon"
                  :size="20"
                />
                <div class="ls-metric__label">
                  {{ t('learningSpace.metricUnsubmitted') }}
                  <span class="ls-tag-focus">{{ t('learningSpace.focusTag') }}</span>
                </div>
                <div class="ls-metric__value">{{ teacherMetrics.unsubmitted }}</div>
                <div class="ls-metric__hint">{{ t('learningSpace.metricUnsubmittedHint') }}</div>
              </button>
              <button
                type="button"
                class="ls-metric"
                @click="goTeacherAssignments('active')"
              >
                <FileText
                  class="ls-metric__icon"
                  :size="20"
                />
                <div class="ls-metric__label">{{ t('learningSpace.metricActive') }}</div>
                <div class="ls-metric__value">{{ teacherMetrics.active }}</div>
                <div class="ls-metric__hint">{{ t('learningSpace.metricActiveHint') }}</div>
              </button>
              <button
                type="button"
                class="ls-metric"
                @click="goTeacherClasses"
              >
                <Users
                  class="ls-metric__icon"
                  :size="20"
                />
                <div class="ls-metric__label">{{ t('learningSpace.metricClasses') }}</div>
                <div class="ls-metric__value">{{ teacherMetrics.classCount }}</div>
                <div class="ls-metric__hint">{{ t('learningSpace.metricClassesHint') }}</div>
              </button>
            </div>
          </template>

          <!-- Assignments list / detail -->
          <template v-else-if="teacherTab === 'assignments' || selectedAssignmentId != null">
            <template v-if="selectedAssignmentId == null">
              <div class="ls-page-head">
                <div>
                  <h1>{{ t('learningSpace.tabAssignments') }}</h1>
                  <p>{{ t('learningSpace.assignmentsPageHint') }}</p>
                </div>
                <button
                  v-if="canPublish"
                  type="button"
                  class="ls-btn ls-btn--primary"
                  :disabled="!publishableClasses.length"
                  @click="openCreateAssignmentModal"
                >
                  {{ t('learningSpace.createAssignment') }}
                </button>
              </div>

              <div class="ls-filters">
                <div class="ls-pills">
                  <button
                    v-for="f in (
                      [
                        ['all', 'learningSpace.filterAll'],
                        ['active', 'learningSpace.filterActive'],
                        ['pending', 'learningSpace.filterPending'],
                      ] as const
                    )"
                    :key="f[0]"
                    type="button"
                    class="ls-pill"
                    :class="{ 'ls-pill--active': assignmentFilter === f[0] }"
                    @click="assignmentFilter = f[0]"
                  >
                    {{ t(f[1]) }}
                  </button>
                </div>
                <input
                  v-model="assignmentQuery"
                  class="ls-search"
                  type="search"
                  :placeholder="t('learningSpace.searchAssignments')"
                />
              </div>

              <div class="ls-class-filter">
                <span class="ls-class-filter__label">{{ t('learningSpace.class') }}</span>
                <div class="ls-pills">
                  <button
                    v-for="c in classes"
                    :key="c.id"
                    type="button"
                    class="ls-pill"
                    :class="{ 'ls-pill--active': selectedClassId === c.id }"
                    @click="selectedClassId = c.id"
                  >
                    {{ c.name }}
                    <span class="ls-pill__count">{{ c.student_count }}</span>
                    <span
                      v-if="c.status === 'archived'"
                      class="ls-pill__count"
                    >{{ t('learningSpace.filterClosed') }}</span>
                  </button>
                </div>
              </div>

              <p
                v-if="!filteredAssignments.length"
                class="ls-empty"
              >
                {{ t('learningSpace.noAssignments') }}
              </p>
              <div
                v-else
                class="ls-card-grid"
              >
                <article
                  v-for="a in filteredAssignments"
                  :key="a.id"
                  class="ls-asg-card"
                >
                  <div class="ls-asg-card__top">
                    <div>
                      <h3 class="ls-asg-card__title">{{ a.title }}</h3>
                      <p class="ls-asg-card__meta">
                        {{ classNameForAssignment(a) }} ·
                        {{ t('learningSpace.due') }}：{{ formatLsDateTime(a.due_at) }}
                      </p>
                    </div>
                    <span
                      class="ls-status"
                      :class="`ls-status--${assignmentStatusBadge(a).tone}`"
                    >
                      {{ assignmentStatusBadge(a).text }}
                    </span>
                  </div>
                  <div class="ls-progress">
                    <div class="ls-progress__row">
                      <span>
                        {{
                          t('learningSpace.submittedProgress', {
                            done: progressFor(a).submitted,
                            total: progressFor(a).total,
                          })
                        }}
                      </span>
                      <span>{{ progressFor(a).percent }}%</span>
                    </div>
                    <div class="ls-progress__bar">
                      <div
                        class="ls-progress__fill"
                        :style="{ width: `${progressFor(a).percent}%` }"
                      />
                    </div>
                  </div>
                  <div class="ls-asg-card__stats">
                    <span class="ls-stat-warn">
                      {{
                        t('learningSpace.unsubmittedCount', {
                          n: progressFor(a).unsubmitted,
                        })
                      }}
                    </span>
                    <span>
                      {{
                        t('learningSpace.pendingReviewCount', {
                          n: a.submitted_count ?? 0,
                        })
                      }}
                    </span>
                  </div>
                  <div class="ls-asg-card__foot">
                    <div class="ls-asg-card__dates">
                      {{ a.instructions || t('learningSpace.noInstructions') }}
                    </div>
                    <div class="ls-asg-card__actions">
                      <button
                        type="button"
                        class="ls-btn ls-btn--ghost ls-btn--sm"
                        @click="openRequirements(a)"
                      >
                        {{ t('learningSpace.viewRequirements') }}
                      </button>
                      <button
                        v-if="canDeleteAssignment(a)"
                        type="button"
                        class="ls-btn ls-btn--danger-soft ls-btn--sm"
                        :disabled="deletingAssignmentId === a.id"
                        @click="onDeleteAssignment(a)"
                      >
                        {{ t('learningSpace.deleteAssignment') }}
                      </button>
                      <button
                        type="button"
                        class="ls-btn ls-btn--primary ls-btn--sm"
                        @click="selectedAssignmentId = a.id"
                      >
                        {{ t('learningSpace.detailAndGrade') }}
                      </button>
                    </div>
                  </div>
                </article>
              </div>
            </template>

            <template v-else-if="selectedAssignment">
              <button
                type="button"
                class="ls-back"
                @click="selectedAssignmentId = null"
              >
                <ArrowLeft :size="15" />
                {{ t('learningSpace.backToList') }}
              </button>
              <div class="ls-page-head">
                <div>
                  <h1>{{ selectedAssignment.title }}</h1>
                  <p>
                    {{ classNameForAssignment(selectedAssignment) }} ·
                    {{ t('learningSpace.due') }}：{{ formatLsDateTime(selectedAssignment.due_at) }}
                  </p>
                </div>
                <div class="ls-page-head__actions">
                  <button
                    type="button"
                    class="ls-btn ls-btn--ghost ls-btn--sm"
                    @click="openRequirements(selectedAssignment)"
                  >
                    {{ t('learningSpace.viewRequirements') }}
                  </button>
                  <button
                    v-if="canDeleteAssignment(selectedAssignment)"
                    type="button"
                    class="ls-btn ls-btn--danger-soft ls-btn--sm"
                    :disabled="deletingAssignmentId === selectedAssignment.id"
                    @click="onDeleteAssignment(selectedAssignment)"
                  >
                    {{ t('learningSpace.deleteAssignment') }}
                  </button>
                  <button
                    type="button"
                    class="ls-btn ls-btn--primary ls-btn--sm"
                    @click="showSubmissionStatus = true"
                  >
                    {{ t('learningSpace.submissionStatus') }}
                  </button>
                </div>
              </div>

              <div class="ls-section-title">
                <h2>{{ t('learningSpace.submissionsBoard') }}</h2>
              </div>
              <p
                v-if="!wallSubmissions.length"
                class="ls-empty"
              >
                {{ t('learningSpace.noSubmissions') }}
              </p>
              <div
                v-else
                class="ls-thumb-grid"
              >
                <article
                  v-for="s in wallSubmissions"
                  :key="s.id"
                  class="ls-thumb-card"
                  role="button"
                  tabindex="0"
                  @click="openReview(s)"
                  @keydown.enter.prevent="openReview(s)"
                >
                  <div class="ls-thumb-card__cover">
                    <img
                      v-if="s.diagram_thumbnail"
                      :src="s.diagram_thumbnail"
                      alt=""
                    />
                    <div
                      v-else
                      class="ls-thumb-card__ph"
                    >
                      {{ t('learningSpace.noPreview') }}
                    </div>
                  </div>
                  <div class="ls-thumb-card__name">
                    {{ s.student_name || s.student_user_id }}
                  </div>
                  <div class="ls-thumb-card__meta">
                    {{ statusLabel(s.status) }} ·
                    {{ formatLsDateTime(s.submitted_at) }}
                  </div>
                  <button
                    type="button"
                    class="ls-btn ls-btn--sm"
                    :class="isSubmissionReviewed(s.id) ? 'ls-btn--ghost' : 'ls-btn--primary'"
                    @click.stop="openReview(s)"
                  >
                    {{
                      isSubmissionReviewed(s.id)
                        ? t('learningSpace.reviewed')
                        : t('learningSpace.goReview')
                    }}
                  </button>
                </article>
              </div>
            </template>
          </template>

          <!-- Classes -->
          <template v-else-if="teacherTab === 'classes'">
            <div class="ls-page-head">
              <div>
                <h1>{{ t('learningSpace.tabClasses') }}</h1>
                <p>{{ t('learningSpace.classesPageHint') }}</p>
              </div>
            </div>
            <div class="ls-class-row">
              <button
                v-for="c in classes"
                :key="c.id"
                type="button"
                class="ls-class-card"
                :class="{ 'ls-class-card--active': selectedClassId === c.id }"
                @click="selectedClassId = c.id"
              >
                <h3>{{ c.name }}</h3>
                <p>
                  {{ t('learningSpace.studentCount', { n: c.student_count }) }} ·
                  {{ c.class_code }}
                  <template v-if="c.status === 'archived'">
                    · {{ t('learningSpace.filterClosed') }}
                  </template>
                </p>
                <p>
                  <span class="ls-link">{{ t('learningSpace.viewRoster') }}</span>
                </p>
              </button>
            </div>
            <section
              v-if="selectedClass"
              class="ls-roster"
            >
              <h2 style="margin: 0; font-size: 1.05rem; font-weight: 720">
                {{ selectedClass.name }} — {{ t('learningSpace.rosterTitle') }}
              </h2>
              <p class="ls-muted">
                {{ t('learningSpace.rosterLoginHint', { n: classStudents.length || selectedClass.student_count }) }}
              </p>
              <p class="ls-muted ls-roster__login-how">
                {{ t('learningSpace.rosterLoginHow') }}
              </p>
              <div
                v-if="classStudents.length"
                class="ls-roster-table-wrap"
              >
                <table class="ls-roster-table">
                  <thead>
                    <tr>
                      <th>{{ t('learningSpace.rosterColName') }}</th>
                      <th>{{ t('learningSpace.rosterColClassCode') }}</th>
                      <th>{{ t('learningSpace.rosterColPassword') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="s in classStudents"
                      :key="s.id"
                    >
                      <td class="ls-roster-table__name">{{ s.name }}</td>
                      <td>
                        <code class="ls-roster-code">{{ selectedClass.class_code }}</code>
                      </td>
                      <td>
                        <code class="ls-roster-code">
                          {{ s.initial_password || t('learningSpace.passwordHidden') }}
                        </code>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p
                v-else
                class="ls-empty"
              >
                {{ t('learningSpace.rosterEmpty') }}
              </p>
            </section>
          </template>
        </template>

        <!-- ===== Student ===== -->
        <template v-else-if="isStudent">
          <template v-if="studentTab === 'home' && !studentDetail">
            <div class="ls-page-head">
              <div>
                <h1>{{ t(greetKey, { name: userName }) }}</h1>
                <p v-if="context?.class">
                  {{ context.class.name }} · {{ context.class.class_code }}
                </p>
              </div>
            </div>
            <div class="ls-metrics">
              <button
                type="button"
                class="ls-metric"
                @click="studentTab = 'assignments'"
              >
                <ClipboardList
                  class="ls-metric__icon"
                  :size="20"
                />
                <div class="ls-metric__label">{{ t('learningSpace.metricTodo') }}</div>
                <div class="ls-metric__value">{{ studentTodoCount }}</div>
              </button>
              <button
                type="button"
                class="ls-metric"
                @click="studentTab = 'assignments'"
              >
                <FileText
                  class="ls-metric__icon"
                  :size="20"
                />
                <div class="ls-metric__label">{{ t('learningSpace.metricSubmitted') }}</div>
                <div class="ls-metric__value">{{ studentSubmittedCount }}</div>
              </button>
              <button
                type="button"
                class="ls-metric"
                @click="studentTab = 'works'"
              >
                <Users
                  class="ls-metric__icon"
                  :size="20"
                />
                <div class="ls-metric__label">{{ t('learningSpace.metricWorks') }}</div>
                <div class="ls-metric__value">{{ myPortfolio.length }}</div>
              </button>
              <button
                type="button"
                class="ls-metric ls-metric--alert"
                @click="studentTab = 'assignments'"
              >
                <Clock3
                  class="ls-metric__icon"
                  :size="20"
                />
                <div class="ls-metric__label">{{ t('learningSpace.metricUrgent') }}</div>
                <div class="ls-metric__value">{{ studentUrgentCount }}</div>
              </button>
            </div>
          </template>

          <template v-else-if="studentTab === 'assignments' || studentDetail">
            <template v-if="!studentDetail">
              <div class="ls-page-head">
                <div>
                  <h1>{{ t('learningSpace.tabClassAssignments') }}</h1>
                  <p>{{ t('learningSpace.classAssignmentsHint') }}</p>
                </div>
              </div>
              <p
                v-if="!studentAssignments.length"
                class="ls-empty"
              >
                {{ t('learningSpace.noAssignments') }}
              </p>
              <div
                v-else
                class="ls-card-grid"
              >
                <article
                  v-for="a in studentAssignments"
                  :key="a.id"
                  class="ls-asg-card"
                  role="button"
                  tabindex="0"
                  @click="studentDetailId = a.id"
                  @keydown.enter.prevent="studentDetailId = a.id"
                >
                  <div class="ls-asg-card__top">
                    <h3 class="ls-asg-card__title">{{ a.title }}</h3>
                    <span
                      class="ls-status"
                      :class="`ls-status--${
                        studentAssignmentDone(a)
                          ? 'active'
                          : a.submission?.status === 'returned'
                            ? 'closed'
                            : 'draft'
                      }`"
                    >
                      {{ statusLabel(a.submission?.status) }}
                    </span>
                  </div>
                  <p class="ls-asg-card__meta">
                    {{ t('learningSpace.due') }}：{{ formatLsDateTime(a.due_at) }}
                  </p>
                  <div class="ls-asg-card__actions">
                    <button
                      type="button"
                      class="ls-btn ls-btn--primary ls-btn--sm"
                      @click.stop="studentDetailId = a.id"
                    >
                      {{ t('learningSpace.viewAssignment') }}
                    </button>
                  </div>
                </article>
              </div>
            </template>
            <template v-else-if="studentDetail">
              <button
                type="button"
                class="ls-back"
                @click="studentDetailId = null"
              >
                <ArrowLeft :size="15" />
                {{ t('learningSpace.backToList') }}
              </button>
              <div class="ls-page-head">
                <div>
                  <h1>{{ studentDetail.title }}</h1>
                  <p class="ls-detail-meta">
                    {{ t('learningSpace.diagramTypeLabel') }}
                    {{
                      t(`learningSpace.diagramType.${assignmentDiagramType(studentDetail)}`)
                    }}
                    <template v-if="studentDetail.due_at">
                      · {{ t('learningSpace.due') }} {{ formatLsDateTime(studentDetail.due_at) }}
                    </template>
                  </p>
                </div>
                <div class="ls-page-head__actions">
                  <button
                    type="button"
                    class="ls-btn ls-btn--ghost ls-btn--sm"
                    @click="openRequirements(studentDetail)"
                  >
                    {{ t('learningSpace.viewRequirements') }}
                  </button>
                  <button
                    v-if="studentCanOpenAssignment(studentDetail)"
                    type="button"
                    class="ls-btn ls-btn--primary ls-btn--sm"
                    @click="onOpenStudentAssignment(studentDetail)"
                  >
                    {{ t('learningSpace.doHomework') }}
                  </button>
                  <button
                    v-else-if="!studentAssignmentDone(studentDetail)"
                    type="button"
                    class="ls-btn ls-btn--ghost ls-btn--sm"
                    disabled
                  >
                    {{ t('learningSpace.homeworkClosed') }}
                  </button>
                  <button
                    v-else-if="myDetailSubmission"
                    type="button"
                    class="ls-btn ls-btn--primary ls-btn--sm"
                    @click="openReview(myDetailSubmission, 'view')"
                  >
                    {{ t('learningSpace.myWorkBtn') }}
                  </button>
                </div>
              </div>

              <p
                v-if="studentDetail.instructions"
                class="ls-detail-brief"
              >
                {{ studentDetail.instructions }}
              </p>

              <section>
                <div class="ls-section-title">
                  <h2>{{ t('learningSpace.assignmentWall') }}</h2>
                </div>
                <p
                  v-if="!detailClassWall.length"
                  class="ls-empty"
                >
                  {{ t('learningSpace.noClassWallYet') }}
                </p>
                <div
                  v-else
                  class="ls-thumb-grid"
                >
                  <article
                    v-for="s in detailClassWall"
                    :key="s.id"
                    class="ls-thumb-card"
                    role="button"
                    tabindex="0"
                    @click="openReview(s, 'view')"
                    @keydown.enter.prevent="openReview(s, 'view')"
                  >
                    <div class="ls-thumb-card__cover">
                      <img
                        v-if="s.diagram_thumbnail"
                        :src="s.diagram_thumbnail"
                        alt=""
                      />
                      <div
                        v-else
                        class="ls-thumb-card__ph"
                      >
                        {{ t('learningSpace.noPreview') }}
                      </div>
                    </div>
                    <div class="ls-thumb-card__name">
                      {{ s.student_name || s.student_user_id }}
                    </div>
                    <div class="ls-thumb-card__meta">
                      {{ formatLsDateTime(s.submitted_at) }}
                      <template v-if="s.reviewed_at || s.review_comment || s.review_scores">
                        · {{ t('learningSpace.reviewed') }}
                      </template>
                    </div>
                  </article>
                </div>
              </section>
            </template>
          </template>

          <template v-else-if="studentTab === 'works'">
            <div class="ls-page-head">
              <div>
                <h1>{{ t('learningSpace.tabMyPortfolio') }}</h1>
                <p>{{ t('learningSpace.myPortfolioHint') }}</p>
              </div>
            </div>
            <p
              v-if="!myPortfolio.length"
              class="ls-empty"
            >
              {{ t('learningSpace.noWorks') }}
            </p>
            <div
              v-else
              class="ls-thumb-grid"
            >
              <article
                v-for="s in myPortfolio"
                :key="s.id"
                class="ls-thumb-card"
                role="button"
                tabindex="0"
                @click="openReview(s, 'view')"
                @keydown.enter.prevent="openReview(s, 'view')"
              >
                <div class="ls-thumb-card__cover">
                  <img
                    v-if="s.diagram_thumbnail"
                    :src="s.diagram_thumbnail"
                    alt=""
                  />
                  <div
                    v-else
                    class="ls-thumb-card__ph"
                  >
                    {{ t('learningSpace.noPreview') }}
                  </div>
                </div>
                <div class="ls-thumb-card__name">
                  {{ s.assignment_title || t('learningSpace.assignments') }}
                </div>
                <div class="ls-thumb-card__meta">
                  {{ statusLabel(s.status) }}
                  <template v-if="s.reviewed_at || s.review_comment || s.review_scores">
                    · {{ t('learningSpace.reviewed') }}
                  </template>
                </div>
              </article>
            </div>
          </template>
        </template>

        <section
          v-else-if="!loading"
          class="ls-empty"
        >
          {{ t('learningSpace.noAccess') }}
        </section>
      </div>
    </div>

    <LearningSpaceAssignModal
      v-model="showCreateForm"
      :classes="publishableClasses"
      @created="onAssignmentCreated"
    />
    <LearningSpaceSubmissionStatusModal
      v-model="showSubmissionStatus"
      :class-name="selectedAssignment ? classNameForAssignment(selectedAssignment) : ''"
      :students="classStudents"
      :submitted-ids="[...submittedStudentIds]"
    />
    <LearningSpaceReviewModal
      v-model="showReview"
      :mode="reviewMode"
      :submission="reviewSubmission"
      :dimensions="
        reviewMode === 'edit'
          ? assignmentEvalDimensions(selectedAssignment)
          : assignmentEvalDimensions(
              studentAssignments.find((a) => a.id === reviewSubmission?.assignment_id) ?? null
            )
      "
      :assignment-title="
        reviewMode === 'edit'
          ? selectedAssignment?.title || ''
          : reviewSubmission?.assignment_title || ''
      "
      :initial-draft="
        reviewSubmission ? reviewsBySubmissionId[reviewSubmission.id] ?? null : null
      "
      @save="onReviewSave"
    />
    <LearningSpaceRequirementsModal
      v-model="showRequirements"
      :assignment="reqAssignment"
      :audience="isStudent ? 'student' : 'teacher'"
      :class-name="
        reqAssignment
          ? isStudent
            ? context?.class?.name || t('learningSpace.class')
            : classNameForAssignment(reqAssignment)
          : ''
      "
    />
  </div>
</template>
