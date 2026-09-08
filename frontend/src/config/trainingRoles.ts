import type { TrainingStepOverlay } from '@/types/training'

export interface TrainingRoleDef {
  id: string
  labelKey: string
}

export const TRAINING_ROLE_WIDTH_DEFAULT = 18
export const TRAINING_ROLE_WIDTH_MIN = 8
export const TRAINING_ROLE_WIDTH_MAX = 48

export const TRAINING_ROLES: TrainingRoleDef[] = [
  { id: '01-look-here', labelKey: 'training.builder.role.01-look-here' },
  { id: '02-listen', labelKey: 'training.builder.role.02-listen' },
  { id: '03-raise-hand', labelKey: 'training.builder.role.03-raise-hand' },
  { id: '04-secret', labelKey: 'training.builder.role.04-secret' },
  { id: '05-open-book', labelKey: 'training.builder.role.05-open-book' },
  { id: '06-eureka', labelKey: 'training.builder.role.06-eureka' },
  { id: '07-build-blocks', labelKey: 'training.builder.role.07-build-blocks' },
  { id: '08-zoom', labelKey: 'training.builder.role.08-zoom' },
  { id: '09-orbit', labelKey: 'training.builder.role.09-orbit' },
  { id: '10-erase', labelKey: 'training.builder.role.10-erase' },
  { id: '11-clap', labelKey: 'training.builder.role.11-clap' },
  { id: '12-cheer', labelKey: 'training.builder.role.12-cheer' },
  { id: '13-pat-head', labelKey: 'training.builder.role.13-pat-head' },
  { id: '14-take-notes', labelKey: 'training.builder.role.14-take-notes' },
  { id: '15-countdown', labelKey: 'training.builder.role.15-countdown' },
  { id: '16-pace-think', labelKey: 'training.builder.role.16-pace-think' },
  { id: '17-telescope', labelKey: 'training.builder.role.17-telescope' },
  { id: '18-magic-light', labelKey: 'training.builder.role.18-magic-light' },
  { id: '19-drink-ink', labelKey: 'training.builder.role.19-drink-ink' },
  { id: '20-dismiss', labelKey: 'training.builder.role.20-dismiss' },
]

const ROLE_IDS = new Set(TRAINING_ROLES.map((row) => row.id))

export function isTrainingRoleId(value: string | undefined): boolean {
  return Boolean(value && ROLE_IDS.has(value))
}

/** App-relative URL. API 302s to COS when COURSE_BUILDER_LOAD_FROM_COS is true. */
export function trainingRoleSrc(id: string): string {
  return `/api/training/assets/roles/${safeRoleId(id)}.webp`
}

export function trainingRoleThumb(id: string): string {
  return `/api/training/assets/roles/${safeRoleId(id)}-thumb.webp`
}

export function trainingRolePlaybackSrc(id: string): string {
  return trainingRoleSrc(id)
}

export function trainingRoleMarkSrc(
  id: string,
  options: { still?: boolean; remote?: boolean } = {}
): string {
  if (options.still) return trainingRoleThumb(id)
  if (options.remote) return trainingRolePlaybackSrc(id)
  return trainingRoleSrc(id)
}

function safeRoleId(id: string): string {
  return isTrainingRoleId(id) ? id : '01-look-here'
}

export function clampRoleWidth(value: number): number {
  if (!Number.isFinite(value)) return TRAINING_ROLE_WIDTH_DEFAULT
  const rounded = Math.round(value * 10) / 10
  return Math.min(TRAINING_ROLE_WIDTH_MAX, Math.max(TRAINING_ROLE_WIDTH_MIN, rounded))
}

export function roleWidth(overlay: TrainingStepOverlay): number {
  return clampRoleWidth(overlay.w ?? TRAINING_ROLE_WIDTH_DEFAULT)
}

export function resizeRoleWidth(overlay: TrainingStepOverlay, pointerX: number): void {
  const centerX = overlay.x ?? 82
  const left = centerX - roleWidth(overlay) / 2
  overlay.w = clampRoleWidth(pointerX - left)
}
