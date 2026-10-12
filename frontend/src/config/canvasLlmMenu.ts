/**
 * New-canvas model menu. One choice runs at a time. Express stays the default.
 * Legacy deepseek/doubao keys stay valid for saved diagrams and are not listed.
 */

export type CanvasLlmLogo = 'deepseek' | 'qwen' | 'kimi' | 'doubao'

export interface CanvasLlmMenuItem {
  id: string
  labelKey: string
  modelKey: string
  logo: CanvasLlmLogo
}

/** Drop a trailing YYMMDD snapshot, such as `-260828`, from a menu label. */
export function canvasMenuModelDisplayName(modelId: string): string {
  return modelId.replace(/-(\d{6})$/, '')
}

/** Gray name in the canvas menu. A live id wins; otherwise the translated fallback. */
export function canvasMenuModelLabel(
  id: string,
  live: Readonly<Record<string, string>> | null | undefined,
  fallback: string
): string {
  const name = live?.[id]
  if (typeof name === 'string' && name.trim()) {
    return canvasMenuModelDisplayName(name.trim())
  }
  return fallback
}

/** Compact mark for a canvas model id. School override stays on the Qwen mark. */
export function canvasLlmLogo(id: string): CanvasLlmLogo {
  if (id === 'kimi') {
    return 'kimi'
  }
  if (id === 'doubao' || id === 'doubao21') {
    return 'doubao'
  }
  if (id === 'express' || id === 'deepseek') {
    return 'deepseek'
  }
  return 'qwen'
}

export const CANVAS_LLM_MENU: readonly CanvasLlmMenuItem[] = [
  {
    id: 'express',
    labelKey: 'aiModel.menu.express',
    modelKey: 'aiModel.menu.expressModel',
    logo: 'deepseek',
  },
  {
    id: 'qwen3.8-flash',
    labelKey: 'aiModel.menu.qwen',
    modelKey: 'aiModel.menu.qwenModel',
    logo: 'qwen',
  },
  {
    id: 'qwen3-max',
    labelKey: 'aiModel.menu.max',
    modelKey: 'aiModel.menu.maxModel',
    logo: 'qwen',
  },
  {
    id: 'kimi',
    labelKey: 'aiModel.menu.kimi',
    modelKey: 'aiModel.menu.kimiModel',
    logo: 'kimi',
  },
  {
    id: 'doubao21',
    labelKey: 'aiModel.menu.doubao',
    modelKey: 'aiModel.menu.doubaoModel',
    logo: 'doubao',
  },
]

const MENU_IDS = CANVAS_LLM_MENU.map((item) => item.id)

/** Menu ids plus older canvas keys still stored on diagrams. */
export const CANVAS_LLM_MODELS = [...MENU_IDS, 'deepseek', 'doubao'] as const

export type CanvasLlmModel = (typeof CANVAS_LLM_MODELS)[number]

const CANVAS_LLM_SET = new Set<string>(CANVAS_LLM_MODELS)

export function isCanvasLlmModel(value: string | null | undefined): value is CanvasLlmModel {
  return typeof value === 'string' && CANVAS_LLM_SET.has(value)
}

/** Model id for the next canvas generation or brainstorm. School override stays on qwen. */
export function canvasRunModel(selected: string | null | undefined, customLlm: boolean): string {
  if (customLlm) {
    return 'qwen'
  }
  if (selected && CANVAS_LLM_MENU.some((item) => item.id === selected)) {
    return selected
  }
  return 'express'
}
