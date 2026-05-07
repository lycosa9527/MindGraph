/**
 * CmapTools `.cmap` import (ZIP-wrapped Java serialization).
 *
 * Extracts human-readable TC_STRING values from the serialized ConceptMap blob and
 * rebuilds topic / concepts / relationships using ordering heuristics tuned for IHMC
 * exports. When possible, also parses graphical instances for `_layout_positions_by_label`.
 * Curved edges are applied by MindGraph when rendering (same as native maps).
 */
import { unzipSync } from 'fflate'

import { normalizeLabel } from '@/utils/cmapLabels'
import { extractCmapLayoutPositionsByLabel } from '@/utils/cmapLayoutExtract'

/** Thrown when bytes are not a recognizable `.cmap` payload. */
export const CMAP_PARSE_FAILED = 'CMAP_PARSE_FAILED'

const TOPIC_SENTINEL = '__CMAP_TOPIC__'

function isLikelyInternalId(value: string): boolean {
  if (/^ge:[A-Za-z0-9_-]+$/.test(value)) return true
  if (/^\d[\d_]+$/.test(value) && value.includes('_')) return true
  if (/^[A-Z0-9]{12,}$/.test(value)) return true
  if (/^1[A-Z0-9]{3,}(?:-[A-Z0-9_-]+)+$/.test(value)) return true
  return false
}

function shouldSkipRawString(value: string): boolean {
  if (value.startsWith('nlk.') || value.startsWith('java.') || value.startsWith('Ljavax')) {
    return true
  }
  if (value.startsWith('[L') || value.startsWith('Ljava') || value.startsWith('Lnlk')) {
    return true
  }
  if (value.includes('/') && value.includes(';')) return true
  if (value.includes('nlk.base.graphical')) return true
  return false
}

/**
 * Walk Java serialization stream and collect TC_STRING (0x74) UTF payloads.
 */
export function extractJavaTcStrings(data: Uint8Array): string[] {
  const out: string[] = []
  let i = 0
  while (i < data.length - 5) {
    if (data[i] === 0x74) {
      const ln = (data[i + 1] << 8) | data[i + 2]
      if (ln >= 1 && ln <= 8000 && i + 3 + ln <= data.length) {
        const payload = data.subarray(i + 3, i + 3 + ln)
        let printable = 0
        for (let k = 0; k < payload.length; k += 1) {
          const b = payload[k]
          if ((b >= 32 && b < 127) || b >= 0xe0) printable += 1
        }
        if (printable >= Math.max(3, payload.length * 0.35)) {
          const text = new TextDecoder('utf-8', { fatal: false }).decode(payload)
          if (!shouldSkipRawString(text)) {
            out.push(text)
          }
          i += 3 + ln
          continue
        }
      }
    }
    i += 1
  }
  return out
}

function metadataFollower(strings: string[], key: string): string | null {
  const idx = strings.indexOf(key)
  if (idx >= 0 && idx + 1 < strings.length) {
    const v = strings[idx + 1]
    return typeof v === 'string' ? v : null
  }
  return null
}

function stripNoiseHumanStrings(raw: string[], ownerHint: string | null): string[] {
  const dropName = (s: string): boolean => {
    const t = s.trim()
    if (t.length === 0) return true
    if (t === 'x-cmap' || t === 'x-storable') return true
    if (t === 'en' || t === 'Description') return true
    if (t === 'Verdana' || t === 'SanSerif' || t === 'Times') return true
    if (/^1\.0+$/.test(t)) return true
    if (t.startsWith('//*@')) return true
    if (t.endsWith('.cmap')) return true
    if (t.includes('IHMC')) return true
    if (t.includes('@') && t.includes('.edu')) return true
    if (/Fig\.|Figure\b/i.test(t)) return true
    if (ownerHint && normalizeLabel(t) === normalizeLabel(ownerHint)) return true
    return false
  }

  const out: string[] = []
  for (const s of raw) {
    if (!s || s.startsWith('_')) continue
    if (isLikelyInternalId(s)) continue
    if (dropName(s)) continue
    out.push(s)
  }
  return out
}

function containsCjk(text: string): boolean {
  return /\p{Script=Han}/u.test(text)
}

/** Heuristic: linking phrase vs concept node text (CmapTools mixes both in the string stream). */
export function looksLikeLinkingPhrase(text: string): boolean {
  const t = text.trim()
  if (t.length === 0 || t.length > 120) return false
  if (/^\d+\.\s/m.test(t)) return false
  if (/\n\s*\d+\.\s/.test(t)) return false
  if (t.endsWith(':') || t.endsWith('：')) return true
  if (t.includes('\n')) return false
  if (!containsCjk(t)) {
    const singleLatinWord = t.length <= 18 && !/\s/.test(t) && /^[\p{L}\p{N}_-]+$/u.test(t)
    if (singleLatinWord) {
      return !/^\p{Lu}/u.test(t)
    }
    return t.length <= 52
  }
  return t.length <= 18
}

export interface CmapRelationship {
  from: string
  to: string
  label?: string
}

function conceptIndicesBetween(
  items: string[],
  startIdx: number,
  endIdx: number,
  topicNorm: string
): number[] {
  const lo = Math.max(0, startIdx)
  const hi = Math.min(items.length - 1, endIdx)
  const idxs: number[] = []
  for (let j = lo; j <= hi; j += 1) {
    const s = items[j]
    if (looksLikeLinkingPhrase(s)) continue
    const n = normalizeLabel(s)
    if (n.length === 0 || n === topicNorm) continue
    idxs.push(j)
  }
  return idxs
}

/**
 * Build directed edges from linking phrases placed between concepts in the serialization
 * string order (IHMC builds streams as link–concept runs).
 */
export function relationshipsFromOrderedHumanStrings(
  humanOrdered: string[],
  topicText: string
): CmapRelationship[] {
  const topicNorm = normalizeLabel(topicText)
  const linkIndices: number[] = []
  for (let i = 0; i < humanOrdered.length; i += 1) {
    if (looksLikeLinkingPhrase(humanOrdered[i])) linkIndices.push(i)
  }
  const edges: CmapRelationship[] = []
  for (let li = 0; li < linkIndices.length; li += 1) {
    const i = linkIndices[li]
    const prevBoundary = li === 0 ? -1 : linkIndices[li - 1]
    const nextBoundary = li === linkIndices.length - 1 ? humanOrdered.length : linkIndices[li + 1]
    const beforeIdxs = conceptIndicesBetween(humanOrdered, prevBoundary + 1, i - 1, topicNorm)
    const afterIdxs = conceptIndicesBetween(humanOrdered, i + 1, nextBoundary - 1, topicNorm)
    const label = normalizeLabel(humanOrdered[i])
    if (afterIdxs.length >= 2) {
      const from = normalizeLabel(humanOrdered[afterIdxs[0]])
      const to = normalizeLabel(humanOrdered[afterIdxs[1]])
      edges.push({ from, to, label })
    } else if (afterIdxs.length === 1 && beforeIdxs.length >= 1) {
      const from = normalizeLabel(humanOrdered[beforeIdxs[beforeIdxs.length - 1]])
      const to = normalizeLabel(humanOrdered[afterIdxs[0]])
      edges.push({ from, to, label })
    } else if (afterIdxs.length === 1) {
      edges.push({ from: TOPIC_SENTINEL, to: normalizeLabel(humanOrdered[afterIdxs[0]]), label })
    }
  }
  return edges
}

function substituteTopic(edges: CmapRelationship[], topicText: string): CmapRelationship[] {
  const topic = normalizeLabel(topicText)
  return edges.map((e) => ({
    from: e.from === TOPIC_SENTINEL ? topic : e.from,
    to: e.to === TOPIC_SENTINEL ? topic : e.to,
    label: e.label,
  }))
}

function dedupeRelationships(rel: CmapRelationship[]): CmapRelationship[] {
  const seen = new Set<string>()
  const out: CmapRelationship[] = []
  for (const r of rel) {
    const key = `${r.from}\0${r.to}\0${normalizeLabel(r.label ?? '')}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push(r)
  }
  return out
}

/**
 * Decode `.cmap` (ZIP + Java serialization `cmap` entry) into a MindGraph concept_map template
 * (`topic`, `concepts`, `relationships`, `focus_question`).
 */
export function decodeCmapToConceptMapSpec(buffer: ArrayBuffer): Record<string, unknown> {
  let unpacked: Record<string, Uint8Array>
  try {
    unpacked = unzipSync(new Uint8Array(buffer))
  } catch {
    throw new Error(CMAP_PARSE_FAILED)
  }
  const cmapBytes = unpacked.cmap
  if (!cmapBytes || cmapBytes.length < 16) {
    throw new Error(CMAP_PARSE_FAILED)
  }
  const magic = (cmapBytes[0] << 8) | cmapBytes[1]
  if (magic !== 0xaced) {
    throw new Error(CMAP_PARSE_FAILED)
  }
  const strings = extractJavaTcStrings(cmapBytes)
  const resourceName = metadataFollower(strings, '_resourceName')
  const resourceDescription = metadataFollower(strings, '_resourceDescription')
  const ownerName = metadataFollower(strings, '_owner')
  let topicRaw =
    resourceName?.replace(/\.cmap$/i, '').trim() ||
    resourceDescription?.trim() ||
    'Imported concept map'
  topicRaw = topicRaw.replace(/^\d+/, '').trim() || topicRaw
  const topicText = normalizeLabel(topicRaw)

  const humanOrdered = stripNoiseHumanStrings(strings, ownerName)
  let edges = relationshipsFromOrderedHumanStrings(humanOrdered, topicText)
  edges = substituteTopic(edges, topicText)
  edges = dedupeRelationships(edges)

  const conceptSet = new Set<string>()
  for (const e of edges) {
    if (e.from !== topicText) conceptSet.add(e.from)
    if (e.to !== topicText) conceptSet.add(e.to)
  }
  for (const s of humanOrdered) {
    if (!looksLikeLinkingPhrase(s)) {
      const n = normalizeLabel(s)
      if (n.length > 0 && n !== topicText) conceptSet.add(n)
    }
  }

  const concepts = Array.from(conceptSet)

  const relationships = edges
    .filter((e) => e.from !== e.to)
    .map((e) => ({
      from: e.from,
      to: e.to,
      label: e.label ?? '',
    }))

  const spec: Record<string, unknown> = {
    type: 'concept_map',
    topic: topicText,
    concepts,
    relationships,
  }
  try {
    const layout = extractCmapLayoutPositionsByLabel(cmapBytes)
    if (Object.keys(layout).length > 0) {
      spec._layout_positions_by_label = layout
    }
  } catch {
    /* layout is optional; string-level decode already succeeded */
  }
  const fq =
    resourceDescription && normalizeLabel(resourceDescription).length > 0
      ? normalizeLabel(resourceDescription)
      : ''
  if (fq) {
    spec.focus_question = fq
  }
  return spec
}
