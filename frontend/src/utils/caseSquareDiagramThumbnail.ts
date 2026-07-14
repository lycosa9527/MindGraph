import type { DiagramType } from '@/types'
import { toRaw } from 'vue'
import { decodeMgFileToJsonText } from '@/utils/mgInterchange'

export async function decodeMgUploadSpec(file: File): Promise<Record<string, unknown> | null> {
  try {
    const text = await decodeMgFileToJsonText(await file.arrayBuffer())
    const parsed = JSON.parse(text) as unknown
    if (!parsed || typeof parsed !== 'object') return null
    return parsed as Record<string, unknown>
  } catch {
    return null
  }
}

export function inferDiagramTypeFromSpec(
  spec: Record<string, unknown>,
  fallback: string
): string {
  const raw = spec.type
  if (typeof raw === 'string' && raw.trim()) {
    return raw === 'mindmap' ? 'mind_map' : raw
  }
  return fallback
}

export function normalizeCaseSquareDiagramType(raw: string | null | undefined): DiagramType {
  const trimmed = (raw ?? '').trim()
  const value = trimmed || 'mind_map'
  return (value === 'mind_map' ? 'mindmap' : value) as DiagramType
}

export function resolveCaseSquareDiagramType(
  spec: Record<string, unknown> | null | undefined,
  diagramTypeHint?: string | null,
  fallback = 'mind_map'
): DiagramType {
  const hint = (diagramTypeHint ?? '').trim()
  if (hint) {
    return normalizeCaseSquareDiagramType(hint)
  }
  if (spec) {
    return normalizeCaseSquareDiagramType(inferDiagramTypeFromSpec(spec, fallback))
  }
  return normalizeCaseSquareDiagramType(fallback)
}

/** Clone diagram spec for preview/submit (JSON-safe; handles Vue reactive proxies). */
export function cloneCaseSquareDiagramSpec(
  spec: Record<string, unknown>
): Record<string, unknown> {
  const raw = toRaw(spec) as Record<string, unknown>
  try {
    return JSON.parse(JSON.stringify(raw)) as Record<string, unknown>
  } catch {
    try {
      return structuredClone(raw)
    } catch {
      return { ...(raw as object) } as Record<string, unknown>
    }
  }
}

export async function fetchDiagramSpecPngBlob(
  spec: Record<string, unknown>,
  diagramType: string
): Promise<Blob | null> {
  const normalizedType = diagramType === 'mindmap' ? 'mind_map' : diagramType
  try {
    const response = await fetch('/api/export_png', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        diagram_data: spec,
        diagram_type: normalizedType,
        width: 1200,
        height: 800,
        scale: 2,
      }),
    })
    if (!response.ok) return null
    const blob = await response.blob()
    if (blob.size < 64) return null
    return blob
  } catch {
    return null
  }
}
