import { isMobileRoutePath } from '@/utils/mobileRouteRedirect'

export type TrainingPageKey =
  | 'auth'
  | 'mindgraph'
  | 'canvas'
  | 'mindmate'
  | 'askonce'
  | 'maite'
  | 'debateverse'
  | 'zhihui'
  | 'library'
  | 'template'
  | 'course'
  | 'knowledge'
  | 'showcase'
  | 'community'
  | 'voice-notes'
  | 'thinking-coins'

export interface TrainingPageDef {
  key: TrainingPageKey
  path: string
  mobilePath: string
  labelKey: string
  accent: string
}

export const TRAINING_PAGES: TrainingPageDef[] = [
  {
    key: 'auth',
    path: '/auth',
    mobilePath: '/auth',
    labelKey: 'auth.loginRegister',
    accent: '#0f766e',
  },
  {
    key: 'mindgraph',
    path: '/mindgraph',
    mobilePath: '/m/mindgraph',
    labelKey: 'sidebar.mindGraph',
    accent: '#0d9488',
  },
  {
    key: 'canvas',
    path: '/canvas',
    mobilePath: '/m/canvas',
    labelKey: 'training.builder.pageCanvas',
    accent: '#1c1917',
  },
  {
    key: 'mindmate',
    path: '/mindmate',
    mobilePath: '/m/mindmate',
    labelKey: 'sidebar.mindMate',
    accent: '#2563eb',
  },
  {
    key: 'askonce',
    path: '/askonce',
    mobilePath: '/askonce',
    labelKey: 'askonce.title',
    accent: '#0284c7',
  },
  {
    key: 'maite',
    path: '/maite',
    mobilePath: '/maite',
    labelKey: 'sidebar.mateLearning',
    accent: '#0369a1',
  },
  {
    key: 'debateverse',
    path: '/debateverse',
    mobilePath: '/debateverse',
    labelKey: 'sidebar.debateverse',
    accent: '#7c3aed',
  },
  {
    key: 'zhihui',
    path: '/zhihui',
    mobilePath: '/zhihui',
    labelKey: 'sidebar.zhihui',
    accent: '#7c3aed',
  },
  {
    key: 'library',
    path: '/library',
    mobilePath: '/library',
    labelKey: 'sidebar.library',
    accent: '#b45309',
  },
  {
    key: 'template',
    path: '/template',
    mobilePath: '/template',
    labelKey: 'sidebar.templateResources',
    accent: '#0f766e',
  },
  {
    key: 'course',
    path: '/course',
    mobilePath: '/course',
    labelKey: 'sidebar.courses',
    accent: '#be123c',
  },
  {
    key: 'knowledge',
    path: '/knowledge-space',
    mobilePath: '/knowledge-space',
    labelKey: 'sidebar.knowledgeSpace',
    accent: '#4338ca',
  },
  {
    key: 'showcase',
    path: '/showcase',
    mobilePath: '/showcase',
    labelKey: 'sidebar.showcase',
    accent: '#c2410c',
  },
  {
    key: 'community',
    path: '/community',
    mobilePath: '/community',
    labelKey: 'sidebar.community',
    accent: '#db2777',
  },
  {
    key: 'voice-notes',
    path: '/voice-notes',
    mobilePath: '/m/voice-notes',
    labelKey: 'auth.voiceNotes',
    accent: '#0e7490',
  },
  {
    key: 'thinking-coins',
    path: '/thinking-coins/upgrade',
    mobilePath: '/thinking-coins/upgrade',
    labelKey: 'thinkingCoins.upgradePageTitle',
    accent: '#ca8a04',
  },
]

const PAGE_BY_KEY = new Map(TRAINING_PAGES.map((page) => [page.key, page]))
const PAGES_BY_PATH_LEN = [...TRAINING_PAGES].sort((left, right) => right.path.length - left.path.length)

export function trainingPageDef(key: string | null | undefined): TrainingPageDef | null {
  if (!key) return null
  return PAGE_BY_KEY.get(key as TrainingPageKey) ?? null
}

export function trainingPageKeyFromPath(path: string): TrainingPageKey | null {
  const raw = path.split('?')[0] || ''
  const desktop = isMobileRoutePath(raw) ? raw.slice(2) || '/' : raw
  for (const page of PAGES_BY_PATH_LEN) {
    if (desktop === page.path || desktop.startsWith(`${page.path}/`)) {
      return page.key
    }
  }
  return null
}

export function trainingPagePath(
  routePath: string,
  key: string | null | undefined
): string | null {
  const page = trainingPageDef(key)
  if (!page) return null
  return isMobileRoutePath(routePath) ? page.mobilePath : page.path
}
