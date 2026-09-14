/**
 * Bottom-right PNG watermark for untouched LLM generations
 * (e.g. 豆包小学版). Cleared once the user edits the canvas.
 */
import type { AiContentLevelId } from '@/config/aiContentLevels'
import { isAiContentLevelId } from '@/config/aiContentLevels'
import {
  CANVAS_LLM_MODELS,
  type CanvasLlmModel,
  resolveDiagramLlmModel,
} from '@/utils/resolveDiagramLlmModel'

export const LLM_EXPORT_ATTRIBUTION_KEY = '_llm_export_attribution'

export type LlmExportAttribution = {
  model: CanvasLlmModel
  level: AiContentLevelId
}

const LEVEL_TITLE_KEYS: Record<AiContentLevelId, string> = {
  general: 'canvas.toolbar.professionalContent.level.general.title',
  primary: 'canvas.toolbar.professionalContent.level.primary.title',
  junior: 'canvas.toolbar.professionalContent.level.junior.title',
  senior: 'canvas.toolbar.professionalContent.level.senior.title',
  university: 'canvas.toolbar.professionalContent.level.university.title',
  adult: 'canvas.toolbar.professionalContent.level.adult.title',
  expert: 'canvas.toolbar.professionalContent.level.expert.title',
}

const MODEL_LABEL_ZH: Record<CanvasLlmModel, string> = {
  qwen: '千问',
  deepseek: 'DeepSeek',
  doubao: '豆包',
}

const MODEL_LABEL_EN: Record<CanvasLlmModel, string> = {
  qwen: 'Qwen',
  deepseek: 'DeepSeek',
  doubao: 'Doubao',
}

function isCanvasLlmModel(value: unknown): value is CanvasLlmModel {
  return typeof value === 'string' && (CANVAS_LLM_MODELS as readonly string[]).includes(value)
}

function usesChineseWatermarkLocale(locale: string): boolean {
  return locale === 'zh' || locale === 'zh-tw' || locale.startsWith('zh-')
}

export function parseLlmExportAttribution(value: unknown): LlmExportAttribution | null {
  if (!value || typeof value !== 'object') return null
  const record = value as Record<string, unknown>
  if (!isCanvasLlmModel(record.model) || !isAiContentLevelId(record.level)) {
    return null
  }
  return { model: record.model, level: record.level }
}

export function readLlmExportAttribution(
  data: Record<string, unknown> | null | undefined
): LlmExportAttribution | null {
  if (!data) return null
  return parseLlmExportAttribution(data[LLM_EXPORT_ATTRIBUTION_KEY])
}

export function writeLlmExportAttribution(
  data: Record<string, unknown> | null | undefined,
  attribution: LlmExportAttribution
): void {
  if (!data) return
  data[LLM_EXPORT_ATTRIBUTION_KEY] = {
    model: attribution.model,
    level: attribution.level,
  }
}

export function clearLlmExportAttribution(data: Record<string, unknown> | null | undefined): void {
  if (!data || data[LLM_EXPORT_ATTRIBUTION_KEY] === undefined) return
  delete data[LLM_EXPORT_ATTRIBUTION_KEY]
}

export function attachLlmExportAttribution(
  spec: Record<string, unknown>,
  model: string,
  level: AiContentLevelId
): Record<string, unknown> {
  return {
    ...spec,
    [LLM_EXPORT_ATTRIBUTION_KEY]: {
      model: resolveDiagramLlmModel(model),
      level,
    } satisfies LlmExportAttribution,
  }
}

export function formatLlmExportWatermarkText(
  attribution: LlmExportAttribution,
  translate: (key: string) => string,
  locale: string
): string {
  const chinese = usesChineseWatermarkLocale(locale)
  const modelLabel = chinese ? MODEL_LABEL_ZH[attribution.model] : MODEL_LABEL_EN[attribution.model]
  const levelLabel = translate(LEVEL_TITLE_KEYS[attribution.level])
  if (chinese) {
    return `${modelLabel}${levelLabel}版`
  }
  return `${modelLabel} ${levelLabel}`
}

export function resolveLlmExportWatermarkText(
  data: Record<string, unknown> | null | undefined,
  translate: (key: string) => string,
  locale: string
): string | null {
  const attribution = readLlmExportAttribution(data)
  if (!attribution) return null
  const text = formatLlmExportWatermarkText(attribution, translate, locale).trim()
  return text || null
}

export function drawLlmExportWatermark(canvas: HTMLCanvasElement, text: string): void {
  const ctx = canvas.getContext('2d')
  if (!ctx || !text) return

  const minSide = Math.min(canvas.width, canvas.height)
  const fontSize = Math.max(10, Math.min(18, Math.round(minSide * 0.016)))
  const padding = Math.max(8, Math.round(fontSize * 0.85))
  const x = canvas.width - padding
  const y = canvas.height - padding

  ctx.save()
  ctx.font = `500 ${fontSize}px "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif`
  ctx.textAlign = 'right'
  ctx.textBaseline = 'bottom'
  ctx.lineJoin = 'round'
  ctx.lineWidth = Math.max(2, Math.round(fontSize * 0.14))
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.72)'
  ctx.fillStyle = 'rgba(55, 65, 81, 0.42)'
  ctx.strokeText(text, x, y)
  ctx.fillText(text, x, y)
  ctx.restore()
}

export function applyLlmExportWatermarkToCanvas(
  canvas: HTMLCanvasElement,
  data: Record<string, unknown> | null | undefined,
  translate: (key: string) => string,
  locale: string
): void {
  const text = resolveLlmExportWatermarkText(data, translate, locale)
  if (!text) return
  drawLlmExportWatermark(canvas, text)
}
