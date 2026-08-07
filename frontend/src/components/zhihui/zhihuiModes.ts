/**
 * ZhiHui studio modes and selectable generation models.
 */

export type ZhihuiMode = 'image' | 'video' | 'diagram'

export type ZhihuiModelOption = {
  id: string
  label: string
  /** When false, generate stays disabled (future modality). */
  available: boolean
}

/** DashScope Qwen Image 3.0 size: empty = model auto resolution. */
export type ZhihuiImageSizeOption = {
  /** API `宽*高`, or empty string for auto. */
  id: string
  /** Aspect / auto label key under zhihui.size.* */
  labelKey: string
  /** Display as DashScope format, e.g. 1024*1024; empty for auto. */
  pixels: string
}

/** Segmented control order — video hidden until Wan T2V lands. */
export const ZHIHUI_MODE_ORDER: ZhihuiMode[] = ['image', 'diagram']

/** DashScope Qwen Image 3.0 (T2I / I2I multimodal-generation). */
export const ZHIHUI_IMAGE_MODELS: ZhihuiModelOption[] = [
  { id: 'qwen-image-3.0', label: 'Qwen-Image-3.0', available: true },
  { id: 'qwen-image-3.0-pro', label: 'Qwen-Image-3.0-Pro', available: true },
]

/**
 * A few common DashScope Qwen Image 3.0 sizes (`宽*高`).
 * Empty id omits `size` so the model recommends resolution from the prompt.
 */
export const ZHIHUI_IMAGE_SIZES: ZhihuiImageSizeOption[] = [
  { id: '', labelKey: 'auto', pixels: '' },
  { id: '1024*1024', labelKey: 'square', pixels: '1024*1024' },
  { id: '1664*928', labelKey: 'landscape169', pixels: '1664*928' },
  { id: '928*1664', labelKey: 'portrait916', pixels: '928*1664' },
  { id: '1280*960', labelKey: 'landscape43', pixels: '1280*960' },
  { id: '960*1280', labelKey: 'portrait34', pixels: '960*1280' },
]

export const DEFAULT_IMAGE_SIZE_ID = ''

export const ZHIHUI_MODELS: Record<ZhihuiMode, ZhihuiModelOption[]> = {
  image: ZHIHUI_IMAGE_MODELS,
  video: [
    { id: 'wan2.5-t2v-preview', label: 'Wan 2.5 T2V', available: false },
    { id: 'wan2.2-i2v', label: 'Wan 2.2 I2V', available: false },
  ],
  diagram: [
    { id: 'wan2.7-image', label: 'Wan 2.7 Image', available: true },
  ],
}

export function defaultModelId(mode: ZhihuiMode): string {
  const list = ZHIHUI_MODELS[mode]
  const first = list.find((m) => m.available) ?? list[0]
  return first?.id ?? ''
}

export function isZhihuiImageModel(modelId: string): boolean {
  return ZHIHUI_IMAGE_MODELS.some((m) => m.id === modelId && m.available)
}

export function imageSizeById(sizeId: string): ZhihuiImageSizeOption {
  return ZHIHUI_IMAGE_SIZES.find((s) => s.id === sizeId) ?? ZHIHUI_IMAGE_SIZES[0]
}
