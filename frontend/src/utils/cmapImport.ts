/**
 * CmapTools `.cmap` import (ZIP-wrapped Java serialization).
 *
 * Primary path parses the IHMC ConceptMap graph (Concept / LinkingPhrase / Connection /
 * optional Propositions) plus GraphicalConcept positions. Fallback uses TC_STRING order
 * heuristics when the semantic graph lacks usable edges.
 */
import { unzipSync } from 'fflate'

import { extractConceptGraphFromCmapBytes } from '@/utils/cmapGraphExtract'
import { normalizeLabel } from '@/utils/cmapLabels'
import { extractCmapLayoutPositionsByLabel } from '@/utils/cmapLayoutExtract'
import { decodeJavaModifiedUtf8 } from '@/utils/cmapModifiedUtf8'

/** Thrown when bytes are not a recognizable `.cmap` payload. */
export const CMAP_PARSE_FAILED = 'CMAP_PARSE_FAILED'

export interface CmapImportConceptUnit {
  id: string
  label: string
}

export interface CmapImportMeta {
  semantics: 'ihmc_graph' | 'heuristic_strings'
  concept_map_roots_found: number
  relationship_source: 'proposition' | 'connection_graph' | 'heuristic_ordered_strings'
  layout_keys_recovered: number
  layout_label_collisions: number
  /** Concepts without a harvested `_layout_positions_by_label` entry (normalized label match). */
  units_missing_layout?: number
}

const TOPIC_SENTINEL = '__CMAP_TOPIC__'
const TC_STRING = 0x74
const TC_LONGSTRING = 0x7c

function finalizeTopicLabel(rawCandidate: string | null | undefined): string {
  let topicRaw =
    (rawCandidate && rawCandidate.replace(/\.cmap$/i, '').trim()) || 'Imported concept map'
  topicRaw = topicRaw.replace(/^\d+/, '').trim() || topicRaw
  return normalizeLabel(topicRaw)
}

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
 * Walk Java serialization stream and collect TC_STRING (0x74) and TC_LONGSTRING (0x7c)
 * payloads decoded as JVM modified UTF-8.
 */
export function extractJavaTcStrings(data: Uint8Array): string[] {
  const out: string[] = []

  function pushDecodedPayload(payload: Uint8Array): void {
    let printable = 0
    for (let k = 0; k < payload.length; k += 1) {
      const byte = payload[k]
      if ((byte !== undefined && byte >= 32 && byte < 127) || byte >= 0x80) printable += 1
    }
    if (printable >= Math.max(3, payload.length * 0.35)) {
      const text = decodeJavaModifiedUtf8(payload)
      if (!shouldSkipRawString(text)) {
        out.push(text)
      }
    }
  }

  let offset = 0
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength)

  while (offset < data.length - 5) {
    if (data[offset] === TC_STRING) {
      const ln = (data[offset + 1] << 8) | data[offset + 2]
      if (ln >= 1 && ln <= 8000 && offset + 3 + ln <= data.length) {
        pushDecodedPayload(data.subarray(offset + 3, offset + 3 + ln))
        offset += 3 + ln
        continue
      }
    }
    if (data[offset] === TC_LONGSTRING && offset + 9 <= data.length) {
      const hi = view.getInt32(offset + 1, false)
      const lo = view.getUint32(offset + 5, false)
      const lnBig = (BigInt(hi) << 32n) | BigInt(lo)
      if (
        lnBig > 0n &&
        lnBig <= 120_000n &&
        BigInt(Number(lnBig)) === lnBig &&
        offset + 9 + Number(lnBig) <= data.length
      ) {
        const lnNum = Number(lnBig)
        pushDecodedPayload(data.subarray(offset + 9, offset + 9 + lnNum))
        offset += 9 + lnNum
        continue
      }
    }
    offset += 1
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
  const dropName = (candidate: string): boolean => {
    const trimmed = candidate.trim()
    if (trimmed.length === 0) return true
    if (trimmed === 'x-cmap' || trimmed === 'x-storable') return true
    if (trimmed === 'en' || trimmed === 'Description') return true
    if (trimmed === 'Verdana' || trimmed === 'SanSerif' || trimmed === 'Times') return true
    if (/^1\.0+$/.test(trimmed)) return true
    if (trimmed.startsWith('//*@')) return true
    if (trimmed.endsWith('.cmap')) return true
    if (trimmed.includes('IHMC')) return true
    if (trimmed.includes('@') && trimmed.includes('.edu')) return true
    if (/Fig\.|Figure\b/i.test(trimmed)) return true
    if (ownerHint && normalizeLabel(trimmed) === normalizeLabel(ownerHint)) return true
    return false
  }

  const stripped: string[] = []
  for (const chunk of raw) {
    if (!chunk || chunk.startsWith('_')) continue
    if (isLikelyInternalId(chunk)) continue
    if (dropName(chunk)) continue
    stripped.push(chunk)
  }
  return stripped
}

function containsCjk(text: string): boolean {
  return /\p{Script=Han}/u.test(text)
}

/** Heuristic: linking phrase vs concept node text (CmapTools mixes both in the string stream). */
export function looksLikeLinkingPhrase(text: string): boolean {
  const trimmed = text.trim()
  if (trimmed.length === 0 || trimmed.length > 120) return false
  if (/^\d+\.\s/m.test(trimmed)) return false
  if (/\n\s*\d+\.\s/.test(trimmed)) return false
  if (trimmed.endsWith(':') || trimmed.endsWith('：')) return true
  if (trimmed.includes('\n')) return false
  if (!containsCjk(trimmed)) {
    const singleLatinWord =
      trimmed.length <= 18 && !/\s/.test(trimmed) && /^[\p{L}\p{N}_-]+$/u.test(trimmed)
    if (singleLatinWord) {
      return !/^\p{Lu}/u.test(trimmed)
    }
    return trimmed.length <= 52
  }
  return trimmed.length <= 18
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
    if (!s || looksLikeLinkingPhrase(s)) continue
    const normalized = normalizeLabel(s)
    if (normalized.length === 0 || normalized === topicNorm) continue
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
  for (let idx = 0; idx < humanOrdered.length; idx += 1) {
    const str = humanOrdered[idx]
    if (str !== undefined && looksLikeLinkingPhrase(str)) linkIndices.push(idx)
  }
  const edges: CmapRelationship[] = []
  for (let li = 0; li < linkIndices.length; li += 1) {
    const center = linkIndices[li]
    if (center === undefined) continue
    const prevBoundary = li === 0 ? -1 : (linkIndices[li - 1] ?? -1)
    const nextBoundary =
      li === linkIndices.length - 1
        ? humanOrdered.length
        : (linkIndices[li + 1] ?? humanOrdered.length)
    const beforeIdxs = conceptIndicesBetween(humanOrdered, prevBoundary + 1, center - 1, topicNorm)
    const afterIdxs = conceptIndicesBetween(humanOrdered, center + 1, nextBoundary - 1, topicNorm)
    const centerPhrase = humanOrdered[center]
    const label = centerPhrase !== undefined ? normalizeLabel(centerPhrase) : ''
    if (afterIdxs.length >= 2) {
      const firstAfter = humanOrdered[afterIdxs[0]]
      const secondAfter = humanOrdered[afterIdxs[1]]
      edges.push({
        from: normalizeLabel(firstAfter ?? ''),
        to: normalizeLabel(secondAfter ?? ''),
        label,
      })
    } else if (afterIdxs.length === 1 && beforeIdxs.length >= 1) {
      const fromIdx = beforeIdxs[beforeIdxs.length - 1]
      const towardIdx = afterIdxs[0]
      edges.push({
        from: normalizeLabel(humanOrdered[fromIdx] ?? ''),
        to: normalizeLabel(humanOrdered[towardIdx] ?? ''),
        label,
      })
    } else if (afterIdxs.length === 1 && afterIdxs[0] !== undefined) {
      const towardIdxOnly = afterIdxs[0]
      edges.push({
        from: TOPIC_SENTINEL,
        to: normalizeLabel(humanOrdered[towardIdxOnly] ?? ''),
        label,
      })
    }
  }
  return edges
}

function substituteTopic(edges: CmapRelationship[], topicText: string): CmapRelationship[] {
  const topic = normalizeLabel(topicText)
  return edges.map((item) => ({
    from: item.from === TOPIC_SENTINEL ? topic : item.from,
    to: item.to === TOPIC_SENTINEL ? topic : item.to,
    label: item.label,
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

function countDuplicateLabelAssignments(labels: Iterable<string>): number {
  const tallies = new Map<string, number>()
  for (const label of labels) {
    tallies.set(label, (tallies.get(label) ?? 0) + 1)
  }
  let collisions = 0
  for (const n of tallies.values()) {
    if (n > 1) {
      collisions += n - 1
    }
  }
  return collisions
}

function buildHeuristicDistribution(
  topicLabelNormalized: string,
  branchSequences: string[],
  relationshipsNormalized: CmapRelationship[]
): { concept_units: CmapImportConceptUnit[]; relationships: CmapRelationship[] } {
  const concept_units: CmapImportConceptUnit[] = [{ id: 'topic', label: topicLabelNormalized }]
  const buckets = new Map<string, string[]>()

  branchSequences.forEach((rawLabel, index) => {
    const trimmed = normalizeLabel(rawLabel)
    if (!trimmed.length || trimmed === topicLabelNormalized) {
      return
    }
    const id = `cim-h-${index}`
    concept_units.push({ id, label: trimmed })
    const list = buckets.get(trimmed) ?? []
    list.push(id)
    buckets.set(trimmed, list)
  })

  const relationships: CmapRelationship[] = []
  for (const link of relationshipsNormalized) {
    if (link.from === link.to) {
      continue
    }
    let fromResolved: string | undefined
    if (normalizeLabel(link.from) === topicLabelNormalized) {
      fromResolved = 'topic'
    } else {
      const fromBucket = buckets.get(normalizeLabel(link.from))
      fromResolved = fromBucket?.shift()
    }

    let toResolved: string | undefined
    if (normalizeLabel(link.to) === topicLabelNormalized) {
      toResolved = 'topic'
    } else {
      const toBucket = buckets.get(normalizeLabel(link.to))
      toResolved = toBucket?.shift()
    }

    if (!fromResolved || !toResolved) {
      continue
    }
    relationships.push({
      from: fromResolved,
      to: toResolved,
      label: normalizeLabel(link.label ?? ''),
    })
  }

  return { concept_units, relationships }
}

function collectHints(meta: CmapImportMeta): string[] {
  const hints: string[] = []
  if (meta.semantics === 'heuristic_strings') {
    hints.push('canvas.import.cmapHeuristicSemantics')
  } else if (meta.relationship_source !== 'proposition') {
    hints.push('canvas.import.cmapConnectionFallback')
  }
  return hints
}

function unitsMissingLayoutCount(units: CmapImportConceptUnit[], layoutKeys: string[]): number {
  if (layoutKeys.length === 0) return 0
  const labeled = new Set(layoutKeys.map((k) => normalizeLabel(k)))
  let missing = 0
  for (const u of units) {
    if (!labeled.has(normalizeLabel(u.label))) {
      missing += 1
    }
  }
  return missing
}

function augmentLayoutHints(
  hintsIn: string[],
  layoutDiag: { recovered: number; hadStreamError: boolean },
  collisions: number
): void {
  if (layoutDiag.hadStreamError) {
    hintsIn.push('canvas.import.cmapLayoutFailed')
    return
  }
  if (layoutDiag.recovered === 0) {
    hintsIn.push('canvas.import.cmapEmptyLayout')
  }
  if (collisions > 0) {
    hintsIn.push('canvas.import.cmapLayoutLabelCollision')
  }
}

function attachLayout(
  cmapBytes: Uint8Array,
  spec: Record<string, unknown>
): {
  recovered: number
  hadStreamError: boolean
  layoutKeys: string[]
} {
  delete spec['_import_cmap_fit_view_pending']

  delete spec['_import_cmap_measured_relax_pending']

  try {
    const topicSource = typeof spec.topic === 'string' ? spec.topic : ''
    const topicLabelNormalized = normalizeLabel(topicSource)
    const topicForFit = topicLabelNormalized.length > 0 ? topicLabelNormalized : null

    const semanticUnitCount = Array.isArray(spec.concept_units) ? spec.concept_units.length : 0

    const layout = extractCmapLayoutPositionsByLabel(cmapBytes, {
      topicLabelNormalized: topicForFit ?? undefined,
      semanticUnitCount: semanticUnitCount > 0 ? semanticUnitCount : undefined,
    })

    const layoutKeys = Object.keys(layout)

    if (layoutKeys.length === 0) {
      return { recovered: 0, hadStreamError: false, layoutKeys: [] }
    }

    spec._layout_positions_by_label = layout
    spec['_import_cmap_fit_view_pending'] = true

    spec['_import_cmap_measured_relax_pending'] = true
    return { recovered: layoutKeys.length, hadStreamError: false, layoutKeys }
  } catch {
    return { recovered: 0, hadStreamError: true, layoutKeys: [] }
  }
}

/**
 * Decode `.cmap` (ZIP + Java serialization `cmap` entry) into a MindGraph concept_map template
 * (`topic`, `concept_units`, relationships by id, optional `relationships`/legacy duplicates...).
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

  const nativeGraph = extractConceptGraphFromCmapBytes(cmapBytes)

  const topicBootstrap = finalizeTopicLabel(
    nativeGraph?.topicHint ?? resourceName ?? resourceDescription ?? undefined
  )

  const useNativeSemantics =
    nativeGraph !== null &&
    nativeGraph.relationships.length > 0 &&
    nativeGraph.concept_units.some((u) => !u.label.startsWith('? ('))

  const metaBase: Omit<CmapImportMeta, 'layout_keys_recovered' | 'layout_label_collisions'> = {
    semantics: useNativeSemantics ? 'ihmc_graph' : 'heuristic_strings',
    concept_map_roots_found: nativeGraph?.diagnostics.conceptMapRootCandidates ?? 1,
    relationship_source: useNativeSemantics
      ? nativeGraph?.diagnostics.propositionEdgesUsed
        ? 'proposition'
        : 'connection_graph'
      : 'heuristic_ordered_strings',
  }

  if (useNativeSemantics && nativeGraph) {
    const topicTextFinal = finalizeTopicLabel(
      nativeGraph.topicHint ??
        topicBootstrap ??
        resourceName ??
        resourceDescription ??
        'Imported concept map'
    )

    let graphRelationships = nativeGraph.relationships.map((link) => ({
      from: link.fromId,
      to: link.toId,
      label: normalizeLabel(link.label),
    }))
    graphRelationships = dedupeRelationships(graphRelationships).map((edge) => ({
      from: edge.from,
      to: edge.to,
      label: normalizeLabel(edge.label ?? ''),
    }))
    graphRelationships = graphRelationships.filter((edge) => edge.from !== edge.to)

    let concept_units: CmapImportConceptUnit[] = nativeGraph.concept_units.map((u) => ({
      id: u.id,
      label: u.label,
    }))

    const topicUnitExists = concept_units.some((u) => u.id === 'topic')
    if (!topicUnitExists && topicTextFinal.length > 0) {
      concept_units = [{ id: 'topic', label: topicTextFinal }, ...concept_units]
    }

    const specSemantic: Record<string, unknown> = {
      type: 'concept_map',
      topic: topicTextFinal,
      concept_units,
      concepts: concept_units.filter((u) => u.id !== 'topic').map((u) => u.label),
      relationships: graphRelationships.map((edge) => ({
        from: edge.from,
        to: edge.to,
        label: edge.label ?? '',
      })),
    }

    const layoutHintLabels = concept_units.map((u) => u.label)
    const layoutSemantic = attachLayout(cmapBytes, specSemantic)

    const importMetaSemantic: CmapImportMeta = {
      ...metaBase,
      semantics: 'ihmc_graph',
      layout_keys_recovered: layoutSemantic.recovered,
      layout_label_collisions: countDuplicateLabelAssignments(layoutHintLabels),
      units_missing_layout: unitsMissingLayoutCount(concept_units, layoutSemantic.layoutKeys),
    }

    const hintsNa = [...collectHints(importMetaSemantic)]
    augmentLayoutHints(hintsNa, layoutSemantic, importMetaSemantic.layout_label_collisions)

    specSemantic._import_meta = importMetaSemantic
    specSemantic._import_hints = [...new Set(hintsNa)]

    const focusNative =
      nativeGraph.focusQuestion ??
      (resourceDescription && normalizeLabel(resourceDescription).length > 0
        ? normalizeLabel(resourceDescription)
        : '')
    if (focusNative) {
      specSemantic.focus_question = focusNative
    }
    return specSemantic
  }

  let topicDisplay = topicBootstrap

  let edgesWorking = relationshipsFromOrderedHumanStrings(
    stripNoiseHumanStrings(strings, ownerName),
    topicDisplay
  )
  edgesWorking = substituteTopic(edgesWorking, topicDisplay)
  edgesWorking = dedupeRelationships(edgesWorking)

  topicDisplay = finalizeTopicLabel(
    resourceName?.replace(/\.cmap$/i, '').trim() || resourceDescription || topicDisplay
  )

  const topicNormEarly = normalizeLabel(topicDisplay)
  const humanOrdered = stripNoiseHumanStrings(strings, ownerName)

  const branchSequences: string[] = []
  for (const chunk of edgesWorking) {
    if (normalizeLabel(chunk.from) !== topicNormEarly) {
      branchSequences.push(normalizeLabel(chunk.from))
    }
    if (normalizeLabel(chunk.to) !== topicNormEarly) {
      branchSequences.push(normalizeLabel(chunk.to))
    }
  }
  for (const raw of humanOrdered) {
    if (!raw || looksLikeLinkingPhrase(raw)) continue
    const n = normalizeLabel(raw)
    if (n.length === 0 || n === topicNormEarly) continue
    branchSequences.push(n)
  }

  edgesWorking = edgesWorking.filter((edge) => edge.from !== edge.to)

  const { concept_units, relationships: heuristicRels } = buildHeuristicDistribution(
    topicNormEarly,
    branchSequences,
    edgesWorking.map((edge) => ({
      from: edge.from,
      to: edge.to,
      label: edge.label ?? '',
    }))
  )

  const heuristicRelationships = dedupeRelationships(
    heuristicRels.map((relation) => ({
      from: relation.from,
      to: relation.to,
      label: relation.label ?? '',
    }))
  )

  const specHeuristic: Record<string, unknown> = {
    type: 'concept_map',
    topic: topicDisplay,
    concept_units,
    concepts: concept_units.filter((u) => u.id !== 'topic').map((u) => u.label),
    relationships: heuristicRelationships.map((relation) => ({
      from: relation.from,
      to: relation.to,
      label: relation.label ?? '',
    })),
  }

  const heuristicLabelPool = concept_units.map((u) => u.label)
  const layoutHeuristic = attachLayout(cmapBytes, specHeuristic)
  const collisionHeuristic = countDuplicateLabelAssignments(heuristicLabelPool)

  const heuristicMetaFinal: CmapImportMeta = {
    semantics: 'heuristic_strings',
    concept_map_roots_found: metaBase.concept_map_roots_found,
    relationship_source: 'heuristic_ordered_strings',
    layout_keys_recovered: layoutHeuristic.recovered,
    layout_label_collisions: collisionHeuristic,
    units_missing_layout: unitsMissingLayoutCount(concept_units, layoutHeuristic.layoutKeys),
  }

  const hintsHeuristic = [...collectHints(heuristicMetaFinal)]
  augmentLayoutHints(hintsHeuristic, layoutHeuristic, collisionHeuristic)

  specHeuristic._import_meta = heuristicMetaFinal
  specHeuristic._import_hints = [...new Set(hintsHeuristic)]

  const fq =
    resourceDescription && normalizeLabel(resourceDescription).length > 0
      ? normalizeLabel(resourceDescription)
      : ''
  if (fq) {
    specHeuristic.focus_question = fq
  }

  return specHeuristic
}
