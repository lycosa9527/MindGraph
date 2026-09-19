export const CLASSROOM_REMOTE_TABS = ['view', 'edit', 'teaching', 'topics', 'ai', 'file'] as const

export type ClassroomRemoteTabId = (typeof CLASSROOM_REMOTE_TABS)[number]

const CLASSROOM_REMOTE_TAB_SET = new Set<string>(CLASSROOM_REMOTE_TABS)

export function isClassroomRemoteTabId(
  value: string | null | undefined
): value is ClassroomRemoteTabId {
  return typeof value === 'string' && CLASSROOM_REMOTE_TAB_SET.has(value)
}

export const CLASSROOM_REMOTE_TAB_LABEL_KEYS: Record<ClassroomRemoteTabId, string> = {
  view: 'canvas.classroomRemote.tabView',
  topics: 'canvas.classroomRemote.tabTopics',
  edit: 'canvas.ribbon.tabEdit',
  ai: 'canvas.ribbon.tabDraw',
  teaching: 'canvas.ribbon.tabTeaching',
  file: 'canvas.ribbon.tabFile',
}

export const DEFAULT_CLASSROOM_REMOTE_TAB: ClassroomRemoteTabId = 'view'

export const CLASSROOM_REMOTE_STORAGE_KEY = 'mg.classroom-remote.v1'
export const CLASSROOM_REMOTE_MARGIN_PX = 8
export const CLASSROOM_REMOTE_EDGE_GAP_PX = 16
export const CLASSROOM_REMOTE_STATUS_GAP_PX = 56
export const CLASSROOM_REMOTE_DEFAULT_WIDTH_PX = 188
export const CLASSROOM_REMOTE_DEFAULT_HEIGHT_PX = 420
export const CLASSROOM_REMOTE_DRAG_THRESHOLD_PX = 4

export type ClassroomRemotePersisted = {
  left: number
  top: number
  hidden: boolean
  tab: ClassroomRemoteTabId
}
