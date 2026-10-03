/**
 * Learning-assignment canvas context (student homework mode on /canvas).
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { assignmentAllowsResubmit } from '@/composables/learningSpace/lsHelpers'
import { useAuthStore } from '@/stores/auth'
import {
  type LearningAiPermissions,
  type LearningAssignment,
  bindStudentDraftDiagram,
  fetchAssignmentAiPermissions,
} from '@/utils/learningSpaceApi'

export const MG_LEARNING_ASSIGNMENT_STORAGE_KEY = 'mg_learning_assignment_id'

const GRANULAR_KEYS = [
  'topic_generate',
  'file_generate',
  'web_generate',
  'voice_summary',
  'ai_brainstorm',
  'conversational_edit',
  'node_subgraph',
  'node_explain',
  'mind_classroom',
] as const

export type LearningAiCapability = (typeof GRANULAR_KEYS)[number] | 'translate' | 'ai_assist'

function writeAssignmentId(id: number | null): void {
  if (typeof sessionStorage === 'undefined') return
  if (id == null) {
    sessionStorage.removeItem(MG_LEARNING_ASSIGNMENT_STORAGE_KEY)
    return
  }
  sessionStorage.setItem(MG_LEARNING_ASSIGNMENT_STORAGE_KEY, String(id))
}

export const useLearningAssignmentCanvasStore = defineStore('learningAssignmentCanvas', () => {
  const assignmentId = ref<number | null>(null)
  const assignment = ref<LearningAssignment | null>(null)
  const permissions = ref<LearningAiPermissions | null>(null)
  const loading = ref(false)
  const loadError = ref<string | null>(null)
  /** True after the bound homework diagram is on the canvas; blocks premature autosave. */
  const draftHydrated = ref(false)

  const isActive = computed(() => assignmentId.value != null)
  const isSubmitted = computed(() => assignment.value?.submission?.status === 'submitted')
  const isHomeworkLocked = computed(
    () => isSubmitted.value && !assignmentAllowsResubmit(assignment.value)
  )
  /** Where Back returns after homework. Mobile Learning Space stays on /m. */
  const returnPath = ref('/learning-space')

  function setReturnPath(path: string): void {
    returnPath.value = path.startsWith('/m/') ? '/m/learning-space' : '/learning-space'
  }

  const aiAssistOn = computed(() => Boolean(permissions.value?.ai_assist))

  function can(capability: LearningAiCapability): boolean {
    const authStore = useAuthStore()
    if (authStore.user?.role === 'student' && !isActive.value) {
      return false
    }
    if (!isActive.value) return true
    const perms = permissions.value
    if (!perms) return false
    if (!perms.ai_assist) return false
    if (capability === 'ai_assist') return true
    return Boolean(perms[capability as keyof LearningAiPermissions])
  }

  async function activate(id: number): Promise<void> {
    const sameOpen = assignmentId.value === id
    assignmentId.value = id
    writeAssignmentId(id)
    if (!sameOpen) {
      draftHydrated.value = false
    }
    loading.value = true
    loadError.value = null
    try {
      const res = await fetchAssignmentAiPermissions(id)
      permissions.value = res.ai_permissions
      assignment.value = res.assignment
    } catch (err) {
      loadError.value = err instanceof Error ? err.message : 'load failed'
      permissions.value = null
      assignment.value = null
    } finally {
      loading.value = false
    }
  }

  function markDraftHydrated(): void {
    draftHydrated.value = true
  }

  function clear(): void {
    assignmentId.value = null
    assignment.value = null
    permissions.value = null
    loadError.value = null
    draftHydrated.value = false
    returnPath.value = '/learning-space'
    writeAssignmentId(null)
  }

  async function bindDraftDiagram(diagramId: string, opts?: { force?: boolean }): Promise<void> {
    const id = assignmentId.value
    if (id == null || !diagramId) return
    if (!opts?.force && !draftHydrated.value) return
    if (assignment.value?.submission?.diagram_id === diagramId) return
    const updated = await bindStudentDraftDiagram(id, diagramId)
    if (assignment.value) {
      assignment.value = { ...assignment.value, submission: updated }
    }
  }

  async function bindDraftForAssignment(id: number, diagramId: string): Promise<void> {
    if (!id || !diagramId) return
    await bindStudentDraftDiagram(id, diagramId)
  }

  function parseRouteAssignmentId(raw: unknown): number | null {
    const value = Array.isArray(raw) ? raw[0] : raw
    if (typeof value !== 'string' && typeof value !== 'number') return null
    const n = Number(value)
    return Number.isFinite(n) && n > 0 ? Math.trunc(n) : null
  }

  return {
    assignmentId,
    assignment,
    permissions,
    loading,
    loadError,
    draftHydrated,
    isActive,
    isSubmitted,
    isHomeworkLocked,
    returnPath,
    setReturnPath,
    aiAssistOn,
    can,
    activate,
    markDraftHydrated,
    bindDraftDiagram,
    bindDraftForAssignment,
    clear,
    parseRouteAssignmentId,
    GRANULAR_KEYS,
  }
})
