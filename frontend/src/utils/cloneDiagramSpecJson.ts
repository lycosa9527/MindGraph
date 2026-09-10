import { toRaw } from 'vue'

/**
 * JSON-safe diagram spec clone (strips Vue proxies that break structuredClone).
 */
export function cloneDiagramSpecJson(spec: Record<string, unknown>): Record<string, unknown> {
  const raw = toRaw(spec)
  return JSON.parse(JSON.stringify(raw)) as Record<string, unknown>
}
