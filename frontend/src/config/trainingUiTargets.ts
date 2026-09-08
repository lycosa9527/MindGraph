import { VALID_DIAGRAM_TYPES } from '@/composables/canvasPage/diagramTypeMaps'
import type { TrainingPageKey } from '@/config/trainingPages'

export type TrainingModalKey =
  | 'language-settings'
  | 'account'
  | 'thinking-coins'
  | 'update-log'
  | 'login'
  | 'online-collab'
  | 'export-community'

export interface TrainingFocusDef {
  key: string
  labelKey: string
  selector: string
  activateOnApply?: boolean
}

export interface TrainingModalDef {
  key: TrainingModalKey
  labelKey: string
  pages: TrainingPageKey[]
  focuses: TrainingFocusDef[]
}

const LANDING_PAGES: TrainingPageKey[] = ['mindgraph']
const LOGIN_PAGES: TrainingPageKey[] = [
  'library',
  'template',
  'course',
  'askonce',
  'community',
  'showcase',
]
const CANVAS_PAGES: TrainingPageKey[] = ['canvas']

export const TRAINING_MODALS: TrainingModalDef[] = [
  {
    key: 'account',
    labelKey: 'sidebar.account',
    pages: LANDING_PAGES,
    focuses: [],
  },
  {
    key: 'language-settings',
    labelKey: 'sidebar.languageSettings',
    pages: LANDING_PAGES,
    focuses: [
      {
        key: 'mindmap-v1',
        labelKey: 'settings.language.mindMapCanvasV1',
        selector: '[data-training-target="mindmap-v1"]',
      },
      {
        key: 'mindmap-v2',
        labelKey: 'settings.language.mindMapCanvasV2',
        selector: '[data-training-target="mindmap-v2"]',
      },
    ],
  },
  {
    key: 'thinking-coins',
    labelKey: 'thinkingCoins.title',
    pages: LANDING_PAGES,
    focuses: [],
  },
  {
    key: 'update-log',
    labelKey: 'auth.updateLog',
    pages: LANDING_PAGES,
    focuses: [],
  },
  {
    key: 'login',
    labelKey: 'auth.login',
    pages: LOGIN_PAGES,
    focuses: [
      {
        key: 'auth-login',
        labelKey: 'auth.login',
        selector: '[data-training-target="auth-login"]',
        activateOnApply: true,
      },
      {
        key: 'auth-register',
        labelKey: 'auth.register',
        selector: '[data-training-target="auth-register"]',
        activateOnApply: true,
      },
    ],
  },
  {
    key: 'online-collab',
    labelKey: 'canvas.zoomControls.collaborate',
    pages: CANVAS_PAGES,
    focuses: [],
  },
  {
    key: 'export-community',
    labelKey: 'canvas.topBar.shareCommunity',
    pages: CANVAS_PAGES,
    focuses: [],
  },
]

const DIAGRAM_FOCUSES: TrainingFocusDef[] = VALID_DIAGRAM_TYPES.filter(
  (type) => type !== 'mind_map'
).map((type) => ({
  key: `diagram-${type}`,
  labelKey: `sidebar.diagramType.${type}`,
  selector: `[data-training-target="diagram-${type}"]`,
}))

const PAGE_FOCUSES: Partial<Record<TrainingPageKey, TrainingFocusDef[]>> = {
  mindgraph: DIAGRAM_FOCUSES,
  auth: [
    {
      key: 'auth-login',
      labelKey: 'auth.login',
      selector: '[data-training-target="auth-login"]',
      activateOnApply: true,
    },
    {
      key: 'auth-register',
      labelKey: 'auth.register',
      selector: '[data-training-target="auth-register"]',
      activateOnApply: true,
    },
  ],
  canvas: [
    {
      key: 'canvas-add',
      labelKey: 'canvas.toolbar.addNode',
      selector: '[data-training-target="canvas-add"]',
    },
    {
      key: 'canvas-delete',
      labelKey: 'canvas.toolbar.deleteNode',
      selector: '[data-training-target="canvas-delete"]',
    },
  ],
}

export function trainingModalDef(key: string | null | undefined): TrainingModalDef | null {
  if (!key) return null
  return TRAINING_MODALS.find((modal) => modal.key === key) ?? null
}

export function trainingModalsForPage(
  pageKey: string | null | undefined
): TrainingModalDef[] {
  if (!pageKey) return []
  return TRAINING_MODALS.filter((modal) => modal.pages.includes(pageKey as TrainingPageKey))
}

export function isTrainingModalForPage(
  pageKey: string | null | undefined,
  modalKey: string | null | undefined
): boolean {
  if (!modalKey) return false
  return trainingModalsForPage(pageKey).some((modal) => modal.key === modalKey)
}

export function trainingFocusOptions(
  pageKey: string | null | undefined,
  modalKey: string | null | undefined
): TrainingFocusDef[] {
  if (isTrainingModalForPage(pageKey, modalKey)) {
    return trainingModalDef(modalKey)?.focuses ?? []
  }
  return PAGE_FOCUSES[pageKey as TrainingPageKey] ?? []
}

export function trainingFocusDef(focusKey: string | null | undefined): TrainingFocusDef | null {
  if (!focusKey) return null
  for (const modal of TRAINING_MODALS) {
    const hit = modal.focuses.find((item) => item.key === focusKey)
    if (hit) return hit
  }
  for (const items of Object.values(PAGE_FOCUSES)) {
    const hit = items.find((item) => item.key === focusKey)
    if (hit) return hit
  }
  return null
}

export function trainingFocusSelector(focusKey: string | null | undefined): string | null {
  const hit = trainingFocusDef(focusKey)
  if (hit) return hit.selector
  if (!focusKey) return null
  return `[data-training-target="${focusKey}"]`
}

export const TRAINING_MODAL_KEYS = TRAINING_MODALS.map((modal) => modal.key)

export function isTrainingFocusKey(key: string | null | undefined): boolean {
  return Boolean(trainingFocusDef(key))
}

export function shouldBlockTrainingAuthoringClick(key: string): boolean {
  return key.startsWith('diagram-')
}
