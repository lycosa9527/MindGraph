/** Shared Showcase UI helpers (cover colors, labels). */

export const COVER_COLORS = [
  'from-rose-400 to-orange-300',
  'from-violet-400 to-purple-300',
  'from-cyan-400 to-blue-300',
  'from-emerald-400 to-teal-300',
  'from-amber-400 to-yellow-300',
  'from-pink-400 to-rose-300',
  'from-indigo-400 to-blue-300',
  'from-fuchsia-400 to-pink-300',
] as const

export function getCoverColor(id: string): string {
  let hash = 0
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0
  }
  return COVER_COLORS[hash % COVER_COLORS.length]
}

export type ShowcaseCaseType = 'teaching_design' | 'diagram_case' | 'diagram_template'

export type ShowcaseDiagramAction = 'go_draw' | 'import_open' | 'apply_template'

export interface ShowcaseTypeTheme {
  headerGradient: string
  coverFallback: string
  caseTypeTagClass: string
  subjectTagClass: string
  gradeTagClass: string
}

export const CASE_TYPE_THEMES: Record<ShowcaseCaseType, ShowcaseTypeTheme> = {
  teaching_design: {
    headerGradient: 'bg-gradient-to-br from-sky-600 to-blue-500',
    coverFallback: 'from-sky-500 to-blue-400',
    caseTypeTagClass: 'bg-sky-700 text-white',
    subjectTagClass: 'bg-white text-sky-900',
    gradeTagClass: 'bg-sky-100 text-sky-900',
  },
  diagram_case: {
    headerGradient: 'bg-gradient-to-br from-violet-600 to-purple-500',
    coverFallback: 'from-violet-500 to-purple-400',
    caseTypeTagClass: 'bg-violet-700 text-white',
    subjectTagClass: 'bg-white text-violet-900',
    gradeTagClass: 'bg-violet-100 text-violet-900',
  },
  diagram_template: {
    headerGradient: 'bg-gradient-to-br from-emerald-600 to-teal-500',
    coverFallback: 'from-emerald-500 to-teal-400',
    caseTypeTagClass: 'bg-emerald-700 text-white',
    subjectTagClass: 'bg-white text-emerald-900',
    gradeTagClass: 'bg-emerald-100 text-emerald-900',
  },
}

export function caseTypeTheme(caseType: ShowcaseCaseType): ShowcaseTypeTheme {
  return CASE_TYPE_THEMES[caseType]
}

export function isRenderableShowcaseSpec(spec: unknown): spec is Record<string, unknown> {
  if (!spec || typeof spec !== 'object') return false
  const obj = spec as Record<string, unknown>
  if (obj.source === 'image_upload') return false
  if (obj.source === 'mg_upload' && !obj.topic && !obj.nodes && !obj.children && !obj.center) {
    return false
  }
  return Boolean(obj.topic || obj.nodes || obj.children || obj.center || obj.Whole)
}

export function resolveDiagramAction(params: {
  caseType: ShowcaseCaseType
  spec?: unknown
  specJsonUrl?: string | null
  sourceFileUrl?: string | null
  hasGalleryDiagram?: boolean
}): ShowcaseDiagramAction | null {
  if (params.caseType === 'teaching_design') return null
  if (params.caseType === 'diagram_template') return 'apply_template'

  // diagram_case: only .mg / personal-library diagram specs support open → canvas edit.
  // Image-only cases must not show 打开图示 / 去画一张 (spec_json_url alone is not enough —
  // gallery image posts also have a JSON sidecar).
  if (isRenderableShowcaseSpec(params.spec)) return 'import_open'
  if (params.hasGalleryDiagram) return 'import_open'

  const spec = params.spec as Record<string, unknown> | undefined
  if (spec?.source === 'gallery') {
    const gallery = spec.gallery
    if (Array.isArray(gallery)) {
      const hasDiagram = gallery.some(
        (entry) =>
          entry &&
          typeof entry === 'object' &&
          (entry as { kind?: string }).kind === 'diagram' &&
          (entry as { spec?: unknown }).spec &&
          typeof (entry as { spec?: unknown }).spec === 'object'
      )
      if (hasDiagram) return 'import_open'
    }
  }

  const source = params.sourceFileUrl ?? ''
  if (/\.mg(\?|$)/i.test(source)) return 'import_open'

  return null
}

export function caseTypeEmoji(caseType: ShowcaseCaseType): string {
  if (caseType === 'teaching_design') return '📝'
  if (caseType === 'diagram_case') return '🖼️'
  return '🗺️'
}

export function caseTypeShortLabel(caseType: ShowcaseCaseType): string {
  if (caseType === 'teaching_design') return '教'
  if (caseType === 'diagram_case') return '图'
  return '模'
}

export const SUBJECT_OPTIONS = [
  '数学',
  '语文',
  '英语',
  '物理',
  '化学',
  '生物',
  '历史',
  '地理',
  '政治',
  '信息技术',
  '跨学科',
  '其他',
] as const

export const GRADE_OPTIONS = [
  '一年级',
  '二年级',
  '三年级',
  '四年级',
  '五年级',
  '六年级',
  '七年级',
  '八年级',
  '九年级',
  '高一',
  '高二',
  '高三',
] as const

/** Keep dropdowns in teaching order even if API sort_order is stale. */
export function sortShowcaseFieldValues<T extends string>(
  values: readonly T[],
  canonical: readonly string[]
): T[] {
  const rank = new Map(canonical.map((value, index) => [value, index]))
  return [...values].sort((left, right) => {
    const leftRank = rank.get(left) ?? canonical.length
    const rightRank = rank.get(right) ?? canonical.length
    if (leftRank !== rightRank) return leftRank - rightRank
    return left.localeCompare(right, 'zh-CN')
  })
}

export const DIAGRAM_TYPE_OPTIONS = [
  { value: 'circle_map', label: '圆圈图' },
  { value: 'bubble_map', label: '气泡图' },
  { value: 'double_bubble_map', label: '双气泡图' },
  { value: 'brace_map', label: '括号图' },
  { value: 'tree_map', label: '树形图' },
  { value: 'flow_map', label: '流程图' },
  { value: 'multi_flow_map', label: '复流程图' },
  { value: 'bridge_map', label: '桥型图' },
  { value: 'mind_map', label: '思维导图' },
  { value: 'concept_map', label: '概念图' },
  { value: 'combined', label: '组合应用' },
] as const

export const CASE_TYPE_PUBLISH_OPTIONS = [
  {
    value: 'teaching_design' as const,
    labelKey: 'showcase.type.teachingDesign',
    descKey: 'showcase.publishModal.typeDesc.teachingDesign',
  },
  {
    value: 'diagram_case' as const,
    labelKey: 'showcase.type.diagramCase',
    descKey: 'showcase.publishModal.typeDesc.diagramCase',
  },
  {
    value: 'diagram_template' as const,
    labelKey: 'showcase.type.diagramTemplate',
    descKey: 'showcase.publishModal.typeDesc.diagramTemplate',
  },
] as const

export function diagramTypeLabel(value: string): string {
  return DIAGRAM_TYPE_OPTIONS.find((o) => o.value === value)?.label ?? value
}

const TEACHING_DOC_EXT = /\.(doc|docx|pdf|pptx)$/i
const DIAGRAM_IMAGE_EXT = /\.(png|jpe?g|webp|gif)$/i

export function isTeachingDocFile(name: string): boolean {
  return TEACHING_DOC_EXT.test(name)
}

export function isDiagramImageFile(name: string): boolean {
  return DIAGRAM_IMAGE_EXT.test(name)
}

export function isTemplateMgFile(name: string): boolean {
  return /\.mg$/i.test(name)
}

export function isTemplateSourceFile(name: string): boolean {
  return isTemplateMgFile(name)
}

export const TAG_MAX_LENGTH = 10
export const TAG_MAX_COUNT = 5

/**
 * Direct browser file uploads for Showcase publish (init → PUT → complete).
 * Large bytes go to private COS when enabled; local fallback uses the same API.
 */
export const SHOWCASE_DIRECT_FILE_UPLOADS_ENABLED = true

/** Client-side limits aligned with showcase helpers / upload roles. */
export const CASE_ATTACHMENT_MAX_BYTES = 20 * 1024 * 1024
/** Teaching design document upload limit (same as attachment max). */
export const CASE_TEACHING_DOC_MAX_BYTES = CASE_ATTACHMENT_MAX_BYTES
/** Cover PNG limit — matches server THUMBNAIL_MAX_BYTES (not the 20MB doc limit). */
export const CASE_THUMBNAIL_MAX_BYTES = 2 * 1024 * 1024
const THUMBNAIL_MAX_EDGE_PX = 960

export function showcaseMaxMegabytes(bytes: number): number {
  return Math.round(bytes / 1024 / 1024)
}

export const CASE_VIDEO_MAX_BYTES = 100 * 1024 * 1024
/** Gallery may include up to 15 images (20MB each) plus a cover; keep under abuse ceiling. */
export const CASE_UPLOAD_TOTAL_MAX_BYTES = 160 * 1024 * 1024

function canvasToPngBlob(canvas: HTMLCanvasElement): Promise<Blob | null> {
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), 'image/png')
  })
}

/**
 * Downscale a cover image until it fits the thumbnail byte budget.
 * Showcase covers are PNG-only on the server; large html-to-image captures must shrink.
 */
export async function shrinkPngBlobToMaxBytes(
  blob: Blob,
  maxBytes: number = CASE_THUMBNAIL_MAX_BYTES,
): Promise<Blob | null> {
  if (!blob || blob.size <= 0) return null
  if (blob.size <= maxBytes) return blob
  if (typeof createImageBitmap !== 'function') return null

  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(blob)
  } catch {
    return null
  }

  try {
    let width = bitmap.width
    let height = bitmap.height
    if (width < 1 || height < 1) return null

    const longest = Math.max(width, height)
    if (longest > THUMBNAIL_MAX_EDGE_PX) {
      const scale = THUMBNAIL_MAX_EDGE_PX / longest
      width = Math.max(1, Math.round(width * scale))
      height = Math.max(1, Math.round(height * scale))
    }

    for (let attempt = 0; attempt < 8; attempt += 1) {
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      if (!ctx) return null
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, width, height)
      ctx.drawImage(bitmap, 0, 0, width, height)
      const next = await canvasToPngBlob(canvas)
      if (next && next.size <= maxBytes) return next
      if (!next || width <= 64 || height <= 64) return null
      width = Math.max(64, Math.round(width * 0.75))
      height = Math.max(64, Math.round(height * 0.75))
    }
    return null
  } finally {
    bitmap.close()
  }
}

/** Convert an image File to PNG Blob for showcase thumbnail upload. */
export async function imageFileToPngBlob(file: File): Promise<Blob | null> {
  const url = URL.createObjectURL(file)
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image()
      el.onload = () => resolve(el)
      el.onerror = reject
      el.src = url
    })
    let width = img.naturalWidth
    let height = img.naturalHeight
    const longest = Math.max(width, height)
    if (longest > THUMBNAIL_MAX_EDGE_PX) {
      const scale = THUMBNAIL_MAX_EDGE_PX / longest
      width = Math.max(1, Math.round(width * scale))
      height = Math.max(1, Math.round(height * scale))
    }
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.drawImage(img, 0, 0, width, height)
    const blob = await canvasToPngBlob(canvas)
    if (!blob) return null
    return shrinkPngBlobToMaxBytes(blob)
  } catch {
    return null
  } finally {
    URL.revokeObjectURL(url)
  }
}

/** Suggested tags for the publish form (each ≤ {@link TAG_MAX_LENGTH} chars). */
export const RECOMMENDED_TAGS = [
  '认知冲突',
  '思辨教学',
  '思维可视化',
  '小组合作',
  '探究学习',
  '项目式学习',
  '概念建构',
  '深度学习',
  '跨学科',
  '差异化教学',
] as const

export async function dataUrlToPngBlob(dataUrl: string): Promise<Blob | null> {
  const trimmed = dataUrl?.trim()
  if (!trimmed) return null

  if (trimmed.startsWith('data:')) {
    const match = trimmed.match(/^data:([^;,]+)?(?:;[^,]*)?,(.+)$/)
    if (match?.[2]) {
      try {
        const payload = match[2]
        const binary =
          match[0].includes(';base64') || !payload.includes(',')
            ? atob(payload)
            : decodeURIComponent(payload)
        const bytes = new Uint8Array(binary.length)
        for (let i = 0; i < binary.length; i += 1) {
          bytes[i] = binary.charCodeAt(i)
        }
        const mime = match[1]?.trim() || 'image/png'
        return new Blob([bytes], { type: mime })
      } catch {
        // fall through to fetch
      }
    }
    try {
      const res = await fetch(trimmed)
      const blob = await res.blob()
      if (blob.size > 0) return blob
    } catch {
      return null
    }
  }

  if (/^https?:\/\//i.test(trimmed) || trimmed.startsWith('/')) {
    try {
      const res = await fetch(trimmed, { credentials: 'include', cache: 'no-store' })
      if (res.ok) return res.blob()
    } catch {
      return null
    }
  }

  return null
}

export function isValidThumbnailBlob(blob: Blob | null | undefined): blob is Blob {
  return Boolean(blob && blob.size > 64)
}

/** Reject all-white captures from off-screen html-to-image (shows as empty cover). */
export async function isMostlyBlankImageBlob(blob: Blob): Promise<boolean> {
  if (typeof createImageBitmap !== 'function') return false
  try {
    const bitmap = await createImageBitmap(blob)
    const sampleW = Math.min(48, bitmap.width)
    const sampleH = Math.min(48, bitmap.height)
    if (sampleW < 1 || sampleH < 1) {
      bitmap.close()
      return true
    }
    const canvas = document.createElement('canvas')
    canvas.width = sampleW
    canvas.height = sampleH
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      bitmap.close()
      return false
    }
    ctx.drawImage(bitmap, 0, 0, sampleW, sampleH)
    bitmap.close()
    const { data } = ctx.getImageData(0, 0, sampleW, sampleH)
    let nearWhite = 0
    const pixels = data.length / 4
    for (let i = 0; i < data.length; i += 4) {
      if (data[i] > 248 && data[i + 1] > 248 && data[i + 2] > 248) nearWhite += 1
    }
    return nearWhite / pixels > 0.94
  } catch {
    return false
  }
}

export async function acceptThumbnailBlob(blob: Blob | null): Promise<Blob | null> {
  if (!isValidThumbnailBlob(blob)) return null
  if (await isMostlyBlankImageBlob(blob)) return null
  const shrunk = await shrinkPngBlobToMaxBytes(blob)
  if (!isValidThumbnailBlob(shrunk)) return null
  return shrunk
}
