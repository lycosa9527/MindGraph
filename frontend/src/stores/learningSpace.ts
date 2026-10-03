/**
 * Learning Space product shell.
 *
 * Async loads run from actions. The open page reloads on `learningSpace:refresh`
 * (sidebar re-entry) and `auth:login_success`. Selection does not watch itself.
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { defineStore } from 'pinia'

import { notify } from '@/composables/core/notifications'
import { eventBus } from '@/composables/core/useEventBus'
import {
  type AssignmentFilter,
  type StudentTab,
  type TeacherTab,
  assignmentIsClosed,
  assignmentProgress,
  filterTeacherAssignments,
  studentAssignmentDone,
  studentAssignmentPending,
  studentCanOpenAssignment,
  studentCanViewAssignmentWall,
} from '@/composables/learningSpace/lsHelpers'
import { useAuthStore } from '@/stores/auth'
import { useLearningAssignmentCanvasStore } from '@/stores/learningAssignmentCanvas'
import {
  type LearningAssignment,
  type LearningClassRow,
  type LearningReviewPayload,
  type LearningSpaceContext,
  type LearningStudentRow,
  type LearningSubmission,
  deleteTeacherAssignment,
  extendSubmission as extendTeacherSubmission,
  fetchLearningSpaceContext,
  listStudentAssignments,
  listStudentClassWall,
  listTeacherAssignments,
  listTeacherClasses,
  listTeacherStudents,
  listTeacherSubmissions,
  listVisibleTeacherAssignments,
  openStudentAssignment as openStudentAssignmentRequest,
  returnSubmission as returnTeacherSubmission,
  saveTeacherReview,
  studentChangePassword,
} from '@/utils/learningSpaceApi'

let busBound = false
let pageOpen = false

type ShellBus = {
  refresh: () => void
  login: () => void
}

let shellBus: ShellBus | null = null

function bindLearningSpaceBus(): void {
  if (busBound) return
  busBound = true
  eventBus.on('learningSpace:refresh', () => {
    shellBus?.refresh()
  })
  eventBus.on('auth:login_success', () => {
    shellBus?.login()
  })
}

function contextCanLearn(ctx: LearningSpaceContext | null, authRole: string | undefined): boolean {
  if (ctx?.can_learn === true || ctx?.role === 'student' || ctx?.role === 'learner') {
    return true
  }
  if (ctx?.can_manage_classes === true || ctx?.role === 'pilot_teacher') {
    return false
  }
  return authRole === 'student'
}

function contextCanReview(ctx: LearningSpaceContext | null): boolean {
  return (
    ctx?.can_review === true ||
    ctx?.can_view_all === true ||
    ctx?.can_manage_classes === true ||
    ctx?.role === 'pilot_teacher' ||
    ctx?.role === 'assistant' ||
    ctx?.role === 'superadmin'
  )
}

export const useLearningSpaceStore = defineStore('learningSpace', () => {
  const authStore = useAuthStore()
  const router = useRouter()
  const canvas = useLearningAssignmentCanvasStore()

  const loading = ref(true)
  const context = ref<LearningSpaceContext | null>(null)
  const navBlocked = ref(false)
  const hydrated = ref(false)
  const classes = ref<LearningClassRow[]>([])
  const selectedClassId = ref<number | null>(null)
  const teacherAssignments = ref<LearningAssignment[]>([])
  const allClassAssignments = ref<LearningAssignment[]>([])
  const selectedAssignmentId = ref<number | null>(null)
  const submissions = ref<LearningSubmission[]>([])
  const classStudents = ref<LearningStudentRow[]>([])
  const studentAssignments = ref<LearningAssignment[]>([])
  const studentDetailId = ref<number | null>(null)
  const classWall = ref<LearningSubmission[]>([])

  const teacherTab = ref<TeacherTab>('dashboard')
  const studentTab = ref<StudentTab>('home')
  const assignmentFilter = ref<AssignmentFilter>('all')
  const assignmentQuery = ref('')
  const preferTeacherShell = ref(true)

  const showCreateForm = ref(false)
  const showSubmissionStatus = ref(false)
  const showRequirements = ref(false)
  const reqAssignment = ref<LearningAssignment | null>(null)
  const deletingAssignmentId = ref<number | null>(null)
  const showReview = ref(false)
  const reviewMode = ref<'edit' | 'view'>('edit')
  const reviewSubmission = ref<LearningSubmission | null>(null)
  const changingPassword = ref(false)

  let shellGen = 0
  let classGen = 0
  let submissionGen = 0

  const canLearn = computed(() => contextCanLearn(context.value, authStore.user?.role))
  const canReview = computed(() => contextCanReview(context.value))
  const canPublish = computed(() => context.value?.can_publish === true)
  const canOpenClassAdmin = computed(() => context.value?.can_manage_classes === true)
  const mustChangePassword = computed(
    () =>
      context.value?.must_change_password === true || authStore.user?.mustChangePassword === true
  )
  const isStudent = computed(
    () => canLearn.value && (!canReview.value || !preferTeacherShell.value)
  )
  const isPilot = computed(() => canReview.value && (!canLearn.value || preferTeacherShell.value))
  const showLsHeader = computed(() => isStudent.value || isPilot.value || loading.value)
  const showShellSwitch = computed(() => canLearn.value && canReview.value)

  const navRole = computed(() => (navBlocked.value ? null : (context.value?.role ?? null)))
  const navCanViewAll = computed(
    () =>
      !navBlocked.value &&
      (context.value?.can_view_all === true || context.value?.role === 'superadmin')
  )

  const selectedClass = computed(
    () => classes.value.find((row) => row.id === selectedClassId.value) ?? null
  )
  const publishableClasses = computed(() =>
    classes.value.filter((row) => row.can_publish === true && row.status !== 'archived')
  )
  const filteredAssignments = computed(() =>
    filterTeacherAssignments(
      teacherAssignments.value,
      assignmentFilter.value,
      assignmentQuery.value
    )
  )
  const pendingGradeCount = computed(() =>
    allClassAssignments.value.reduce((sum, row) => sum + (row.submitted_count ?? 0), 0)
  )
  const studentTodoCount = computed(
    () => studentAssignments.value.filter((row) => studentAssignmentPending(row)).length
  )
  const teacherMetrics = computed(() => {
    let pending = 0
    let unsubmitted = 0
    let active = 0
    for (const row of allClassAssignments.value) {
      const roster = classes.value.find((item) => item.id === row.class_id)?.student_count
      const progress = assignmentProgress(row, roster)
      pending += row.submitted_count ?? 0
      unsubmitted += progress.unsubmitted
      if (!assignmentIsClosed(row) && row.status !== 'draft') active += 1
    }
    return { pending, unsubmitted, active, classCount: classes.value.length }
  })
  const selectedAssignment = computed(
    () =>
      teacherAssignments.value.find((row) => row.id === selectedAssignmentId.value) ??
      allClassAssignments.value.find((row) => row.id === selectedAssignmentId.value) ??
      null
  )
  const studentDetail = computed(
    () => studentAssignments.value.find((row) => row.id === studentDetailId.value) ?? null
  )
  const submittedStudentIds = computed(() => {
    const ids = new Set<number>()
    for (const row of submissions.value) {
      if (row.status === 'submitted') ids.add(row.student_user_id)
    }
    return ids
  })
  const studentSubmittedCount = computed(
    () => studentAssignments.value.filter((row) => studentAssignmentDone(row)).length
  )
  const studentUrgentCount = computed(
    () =>
      studentAssignments.value.filter(
        (row) => studentAssignmentPending(row) && row.due_at && !assignmentIsClosed(row)
      ).length
  )
  const wallSubmissions = computed(() =>
    submissions.value.filter((row) => Boolean(String(row.diagram_id || '').trim()))
  )
  const studentCanViewDetailWall = computed(() => studentCanViewAssignmentWall(studentDetail.value))
  const detailClassWall = computed(() => {
    const id = studentDetail.value?.id
    if (id == null) return []
    return classWall.value.filter((row) => row.assignment_id === id)
  })
  const myDetailSubmission = computed(() => {
    const detail = studentDetail.value
    if (!detail) return null
    const uid = authStore.user?.id
    const fromWall = detailClassWall.value.find(
      (row) => Number(row.student_user_id) === Number(uid)
    )
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
    const fromWall = classWall.value.filter((row) => Number(row.student_user_id) === Number(uid))
    if (fromWall.length) return fromWall
    const items: LearningSubmission[] = []
    for (const row of studentAssignments.value) {
      const sub = row.submission
      if (!sub || (sub.status !== 'submitted' && sub.status !== 'returned')) continue
      items.push({
        ...sub,
        assignment_id: row.id,
        assignment_title: row.title,
        student_name: authStore.user?.username || undefined,
        diagram_thumbnail: sub.diagram_thumbnail || row.template_thumbnail || null,
      })
    }
    return items
  })

  function seedStudentContextFromAuth(): void {
    if (authStore.user?.role !== 'student') return
    context.value = {
      role: 'student',
      must_change_password: authStore.user.mustChangePassword === true,
    }
  }

  function replaceSubmission(updated: LearningSubmission): void {
    const merge = (row: LearningSubmission) =>
      row.id === updated.id ? { ...row, ...updated } : row
    submissions.value = submissions.value.map(merge)
    classWall.value = classWall.value.map(merge)
    studentAssignments.value = studentAssignments.value.map((row) => {
      if (row.submission?.id !== updated.id) return row
      return { ...row, submission: { ...row.submission, ...updated } }
    })
    if (reviewSubmission.value?.id === updated.id) {
      reviewSubmission.value = { ...reviewSubmission.value, ...updated }
    }
  }

  async function loadStudentAssignmentsIfReady(): Promise<void> {
    if (!canLearn.value || mustChangePassword.value) return
    try {
      const [asg, wall] = await Promise.all([listStudentAssignments(), listStudentClassWall()])
      studentAssignments.value = Array.isArray(asg.items) ? asg.items : []
      classWall.value = Array.isArray(wall.items) ? wall.items : []
    } catch {
      notify.errorKey('learningSpace.loadFailed')
    }
  }

  async function refreshAllClassAssignments(): Promise<void> {
    if (!classes.value.length) {
      allClassAssignments.value = []
      return
    }
    try {
      const res = await listVisibleTeacherAssignments()
      allClassAssignments.value = Array.isArray(res.items) ? res.items : []
    } catch {
      allClassAssignments.value = []
    }
  }

  async function loadTeacherAssignments(): Promise<void> {
    const gen = ++classGen
    const classId = selectedClassId.value
    if (classId == null) {
      teacherAssignments.value = []
      return
    }
    try {
      const res = await listTeacherAssignments(classId)
      if (gen !== classGen) return
      teacherAssignments.value = Array.isArray(res.items) ? res.items : []
    } catch {
      if (gen !== classGen) return
      notify.errorKey('learningSpace.loadFailed')
    }
  }

  async function loadClassRoster(classId: number): Promise<void> {
    try {
      const res = await listTeacherStudents(classId)
      if (selectedClassId.value !== classId) return
      classStudents.value = res.items
    } catch {
      if (selectedClassId.value !== classId) return
      classStudents.value = []
    }
  }

  async function loadSubmissionsAndRoster(): Promise<void> {
    const gen = ++submissionGen
    const assignmentId = selectedAssignmentId.value
    if (assignmentId == null) {
      submissions.value = []
      return
    }
    const assignment = selectedAssignment.value
    try {
      const [subRes, stuRes] = await Promise.all([
        listTeacherSubmissions(assignmentId),
        assignment ? listTeacherStudents(assignment.class_id) : Promise.resolve({ items: [] }),
      ])
      if (gen !== submissionGen) return
      submissions.value = subRes.items
      classStudents.value = stuRes.items
    } catch {
      if (gen !== submissionGen) return
      notify.errorKey('learningSpace.loadFailed')
    }
  }

  function keepClassSelection(rows: LearningClassRow[]): void {
    const still = rows.some((row) => row.id === selectedClassId.value)
    if (still) return
    selectedClassId.value = rows.find((row) => row.status !== 'archived')?.id ?? rows[0]?.id ?? null
    selectedAssignmentId.value = null
  }

  async function load(): Promise<void> {
    const gen = ++shellGen
    const firstPaint = context.value == null
    if (firstPaint) loading.value = true
    try {
      context.value = await fetchLearningSpaceContext()
      if (gen !== shellGen) return
      navBlocked.value = false
      if (!hydrated.value) {
        preferTeacherShell.value = contextCanReview(context.value)
        hydrated.value = true
      }
      if (contextCanLearn(context.value, authStore.user?.role)) {
        await loadStudentAssignmentsIfReady()
      }
      if (gen !== shellGen) return
      if (contextCanReview(context.value)) {
        try {
          const res = await listTeacherClasses()
          if (gen !== shellGen) return
          classes.value = Array.isArray(res.items) ? res.items : []
        } catch {
          if (gen !== shellGen) return
          classes.value = []
        }
        keepClassSelection(classes.value)
        await refreshAllClassAssignments()
        await loadTeacherAssignments()
        if (selectedAssignmentId.value != null) {
          await loadSubmissionsAndRoster()
        } else if (teacherTab.value === 'classes' && selectedClassId.value != null) {
          await loadClassRoster(selectedClassId.value)
        }
      } else if (context.value.role === 'none' && authStore.user?.role === 'student') {
        seedStudentContextFromAuth()
        await loadStudentAssignmentsIfReady()
      }
    } catch {
      if (gen !== shellGen) return
      if (authStore.user?.role === 'student') {
        seedStudentContextFromAuth()
        await loadStudentAssignmentsIfReady()
      } else {
        notify.errorKey('learningSpace.loadFailed')
      }
    } finally {
      if (gen === shellGen) loading.value = false
    }
  }

  async function ensureContext(featureOn: boolean): Promise<void> {
    if (!authStore.isAuthenticated || !featureOn) {
      navBlocked.value = true
      return
    }
    navBlocked.value = false
    if (authStore.user?.role === 'student') {
      if (!context.value) seedStudentContextFromAuth()
      return
    }
    try {
      context.value = await fetchLearningSpaceContext()
    } catch {
      if (!pageOpen) context.value = null
    }
  }

  function resetShell(): void {
    shellGen += 1
    hydrated.value = false
    context.value = null
    classes.value = []
    teacherAssignments.value = []
    allClassAssignments.value = []
    submissions.value = []
    classStudents.value = []
    studentAssignments.value = []
    classWall.value = []
    selectedClassId.value = null
    selectedAssignmentId.value = null
    studentDetailId.value = null
    showReview.value = false
    reviewSubmission.value = null
  }

  function attach(): void {
    pageOpen = true
    void load()
  }

  function detach(): void {
    pageOpen = false
    shellGen += 1
  }

  function setTeacherTab(tab: TeacherTab): void {
    teacherTab.value = tab
    if (tab !== 'assignments') selectedAssignmentId.value = null
    if (tab === 'classes' && selectedClassId.value != null) {
      void loadClassRoster(selectedClassId.value)
    }
  }

  function setStudentTab(tab: StudentTab): void {
    studentTab.value = tab
    studentDetailId.value = null
  }

  function setShellMode(mode: 'teacher' | 'student'): void {
    preferTeacherShell.value = mode === 'teacher'
  }

  function goTeacherAssignments(filter: AssignmentFilter = 'all'): void {
    selectedAssignmentId.value = null
    assignmentFilter.value = filter
    teacherTab.value = 'assignments'
  }

  function goTeacherClasses(): void {
    selectedAssignmentId.value = null
    teacherTab.value = 'classes'
    if (selectedClassId.value != null) void loadClassRoster(selectedClassId.value)
  }

  async function selectClass(classId: number): Promise<void> {
    if (selectedClassId.value === classId) {
      if (teacherTab.value === 'classes') await loadClassRoster(classId)
      return
    }
    selectedClassId.value = classId
    selectedAssignmentId.value = null
    submissions.value = []
    await loadTeacherAssignments()
    if (teacherTab.value === 'classes') await loadClassRoster(classId)
  }

  async function openAssignmentDetail(assignmentId: number): Promise<void> {
    selectedAssignmentId.value = assignmentId
    await loadSubmissionsAndRoster()
  }

  function closeAssignmentDetail(): void {
    selectedAssignmentId.value = null
    submissions.value = []
  }

  function openStudentDetail(assignmentId: number): void {
    studentDetailId.value = assignmentId
  }

  function closeStudentDetail(): void {
    studentDetailId.value = null
  }

  function goCreateClass(): void {
    void router.push({ path: '/admin', query: { tab: 'learning_space', subtab: 'classes' } })
  }

  function openCreateAssignment(): void {
    if (!canPublish.value) return
    const owned = publishableClasses.value
    if (!owned.length) {
      notify.warningKey('learningSpace.noPublishableClass')
      return
    }
    const currentOk = owned.some((row) => row.id === selectedClassId.value)
    if (!currentOk && owned[0]) void selectClass(owned[0].id)
    showCreateForm.value = true
  }

  async function onAssignmentCreated(): Promise<void> {
    await loadTeacherAssignments()
    await refreshAllClassAssignments()
    teacherTab.value = 'assignments'
    selectedAssignmentId.value = null
  }

  function openRequirements(assignment: LearningAssignment): void {
    reqAssignment.value = assignment
    showRequirements.value = true
  }

  function openReview(submission: LearningSubmission, mode: 'edit' | 'view' = 'edit'): void {
    reviewMode.value = mode
    reviewSubmission.value = submission
    showReview.value = true
  }

  async function changePassword(password: string): Promise<string | null> {
    changingPassword.value = true
    try {
      await studentChangePassword(password)
      if (authStore.user) {
        authStore.setUser({ ...authStore.user, mustChangePassword: false })
      }
      if (context.value) {
        context.value = { ...context.value, must_change_password: false }
      }
      await loadStudentAssignmentsIfReady()
      return null
    } catch (error) {
      const message = error instanceof Error ? error.message.trim() : ''
      return message
    } finally {
      changingPassword.value = false
    }
  }

  async function openStudentAssignment(assignment: LearningAssignment): Promise<void> {
    if (!studentCanOpenAssignment(assignment)) {
      notify.warningKey('learningSpace.homeworkClosed')
      return
    }
    try {
      const res = await openStudentAssignmentRequest(assignment.id)
      const fromMobile = router.currentRoute.value.path.startsWith('/m/')
      canvas.setReturnPath(fromMobile ? '/m/learning-space' : '/learning-space')
      await router.push({
        path: '/canvas',
        query: {
          assignmentId: String(assignment.id),
          diagramId: res.submission.diagram_id,
        },
      })
    } catch {
      notify.errorKey('learningSpace.openFailed')
    }
  }

  async function deleteAssignment(assignment: LearningAssignment): Promise<void> {
    if (!(
      canPublish.value && publishableClasses.value.some((row) => row.id === assignment.class_id)
    )) {
      return
    }
    deletingAssignmentId.value = assignment.id
    try {
      await deleteTeacherAssignment(assignment.id)
      notify.successKey('learningSpace.assignmentDeleted')
      if (selectedAssignmentId.value === assignment.id) selectedAssignmentId.value = null
      if (reqAssignment.value?.id === assignment.id) {
        showRequirements.value = false
        reqAssignment.value = null
      }
      await loadTeacherAssignments()
      await refreshAllClassAssignments()
    } catch {
      notify.errorKey('learningSpace.deleteFailed')
    } finally {
      deletingAssignmentId.value = null
    }
  }

  async function saveReview(payload: {
    submissionId: number
    draft: LearningReviewPayload
  }): Promise<void> {
    try {
      const updated = await saveTeacherReview(payload.submissionId, payload.draft)
      replaceSubmission(updated)
      notify.successKey('learningSpace.reviewSaved')
      showReview.value = false
    } catch {
      notify.errorKey('learningSpace.saveFailed')
    }
  }

  async function extendDue(payload: { submissionId: number; dueAt: string }): Promise<void> {
    try {
      const updated = await extendTeacherSubmission(payload.submissionId, payload.dueAt)
      replaceSubmission(updated)
      notify.successKey('learningSpace.extendDueDone')
    } catch {
      notify.errorKey('learningSpace.saveFailed')
    }
  }

  async function returnForRevision(submissionId: number): Promise<void> {
    try {
      const updated = await returnTeacherSubmission(submissionId)
      replaceSubmission(updated)
      notify.successKey('learningSpace.returned')
      showReview.value = false
      await refreshAllClassAssignments()
      await loadTeacherAssignments()
    } catch {
      notify.errorKey('learningSpace.saveFailed')
    }
  }

  shellBus = {
    refresh: () => {
      if (pageOpen) void load()
    },
    login: () => {
      resetShell()
      if (pageOpen) void load()
    },
  }
  bindLearningSpaceBus()

  return {
    loading,
    context,
    classes,
    selectedClassId,
    teacherAssignments,
    allClassAssignments,
    selectedAssignmentId,
    submissions,
    classStudents,
    studentAssignments,
    studentDetailId,
    classWall,
    teacherTab,
    studentTab,
    assignmentFilter,
    assignmentQuery,
    preferTeacherShell,
    showCreateForm,
    showSubmissionStatus,
    showRequirements,
    reqAssignment,
    deletingAssignmentId,
    showReview,
    reviewMode,
    reviewSubmission,
    changingPassword,
    canLearn,
    canReview,
    canPublish,
    canOpenClassAdmin,
    mustChangePassword,
    isStudent,
    isPilot,
    showLsHeader,
    showShellSwitch,
    navRole,
    navCanViewAll,
    selectedClass,
    publishableClasses,
    filteredAssignments,
    pendingGradeCount,
    studentTodoCount,
    teacherMetrics,
    selectedAssignment,
    studentDetail,
    submittedStudentIds,
    studentSubmittedCount,
    studentUrgentCount,
    wallSubmissions,
    studentCanViewDetailWall,
    detailClassWall,
    myDetailSubmission,
    myPortfolio,
    ensureContext,
    attach,
    detach,
    setTeacherTab,
    setStudentTab,
    setShellMode,
    goTeacherAssignments,
    goTeacherClasses,
    selectClass,
    openAssignmentDetail,
    closeAssignmentDetail,
    openStudentDetail,
    closeStudentDetail,
    goCreateClass,
    openCreateAssignment,
    onAssignmentCreated,
    openRequirements,
    openReview,
    changePassword,
    openStudentAssignment,
    deleteAssignment,
    saveReview,
    extendDue,
    returnForRevision,
  }
})
