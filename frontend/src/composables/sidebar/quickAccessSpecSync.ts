/**
 * Server copies of quick-access diagrams: built-in presets and edited prompts.
 */
import { ref } from 'vue'

import {
  type QuickAccessDefaultSpecCache,
  type QuickAccessSavedSpec,
  type QuickAccessSpecCache,
  nextQuickAccessSpecCache,
  parseQuickAccessDefaultSpecs,
  parseQuickAccessSpecCache,
  resolveQuickAccessSavedSpec,
} from '@/composables/sidebar/quickAccessRemoteModel'
import {
  LANDING_PROMPT_MAX_LENGTH,
  type LandingPromptExampleKey,
} from '@/config/landingQuickAccess'
import { useAuthStore } from '@/stores'
import { authFetch } from '@/utils/api'

const SPECS_PATH = '/api/auth/quick-access-specs'

const defaultSpecs = ref<QuickAccessDefaultSpecCache>({})
const savedSpecs = ref<QuickAccessSpecCache>({})
let specRevision = 0
let loadedUserId: string | null = null

export function resolveQuickAccessSpec(
  key: LandingPromptExampleKey,
  text: string,
  defaultText: string
): QuickAccessSavedSpec | null {
  return resolveQuickAccessSavedSpec(savedSpecs.value, defaultSpecs.value, key, text, defaultText)
}

export async function loadQuickAccessSpecs(): Promise<void> {
  const authStore = useAuthStore()
  const userId = authStore.user?.id ?? null
  if (!authStore.isAuthenticated || userId == null) {
    specRevision += 1
    loadedUserId = null
    defaultSpecs.value = {}
    savedSpecs.value = {}
    return
  }
  if (loadedUserId !== userId) {
    specRevision += 1
    loadedUserId = userId
    defaultSpecs.value = {}
    savedSpecs.value = {}
  }
  const seen = specRevision
  const response = await authFetch(SPECS_PATH)
  if (seen !== specRevision || !response.ok) {
    return
  }
  const data = (await response.json().catch(() => ({}))) as {
    defaults?: unknown
    saved?: unknown
  }
  if (seen !== specRevision) {
    return
  }
  defaultSpecs.value = parseQuickAccessDefaultSpecs(data.defaults)
  savedSpecs.value = parseQuickAccessSpecCache(
    JSON.stringify(data.saved ?? {}),
    LANDING_PROMPT_MAX_LENGTH
  )
}

export async function rememberQuickAccessSpec(
  key: LandingPromptExampleKey,
  saved: QuickAccessSavedSpec
): Promise<void> {
  specRevision += 1
  const seen = specRevision
  savedSpecs.value = nextQuickAccessSpecCache(savedSpecs.value, key, saved)
  const authStore = useAuthStore()
  if (!authStore.isAuthenticated) {
    return
  }
  const response = await authFetch(SPECS_PATH, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      key,
      text: saved.text,
      diagramType: saved.diagramType,
      spec: saved.spec,
    }),
  })
  if (seen !== specRevision || !response.ok) {
    return
  }
  const data = (await response.json().catch(() => ({}))) as { saved?: unknown }
  if (seen !== specRevision) {
    return
  }
  specRevision += 1
  savedSpecs.value = parseQuickAccessSpecCache(
    JSON.stringify(data.saved ?? savedSpecs.value),
    LANDING_PROMPT_MAX_LENGTH
  )
}
