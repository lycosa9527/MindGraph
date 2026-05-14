/**
 * IHMC ConceptMap semantic graph from parsed Java serialization handles.
 */
import { normalizeLabel } from '@/utils/cmapLabels'
import {
  type InstanceParsed,
  JavaParseError,
  instanceFieldMap,
  parseJavaSerializationStream,
} from '@/utils/javaSerializationParse'

export interface CmapConceptUnit {
  id: string
  label: string
}

export interface CmapGraphRelationship {
  fromId: string
  toId: string
  label: string
}

export interface CmapGraphDiagnostics {
  conceptMapRootCandidates: number
  connectionEdgeFallbackUsed: boolean
  propositionEdgesUsed: boolean
}

export interface CmapGraphExtract {
  concept_units: CmapConceptUnit[]
  relationships: CmapGraphRelationship[]
  topicHint?: string
  focusQuestion?: string
  diagnostics: CmapGraphDiagnostics
}

function resolveInstance(val: unknown): InstanceParsed | null {
  if (val && typeof val === 'object' && (val as InstanceParsed).kind === 'instance') {
    return val as InstanceParsed
  }
  return null
}

/** Every other entry after a key in Hashtable custom serialization (values at odd indices). */
function hashtableStoredValues(table: InstanceParsed): unknown[] {
  const ann = table.annotations ?? []
  const payload: unknown[] = []
  for (let index = 1; index < ann.length; index += 2) {
    payload.push(ann[index])
  }
  return payload
}

function hashtablePairsToMap(ht: InstanceParsed): Map<string, unknown> {
  const out = new Map<string, unknown>()
  const ann = ht.annotations ?? []
  for (let i = 0; i + 1 < ann.length; i += 2) {
    const key = ann[i]
    const value = ann[i + 1]
    if (typeof key === 'string') {
      out.set(key, value)
    }
  }
  return out
}

function extHashtableInnerHashtable(htWrapper: InstanceParsed): InstanceParsed | null {
  if (htWrapper.classDesc.name !== 'nlk.base.ExtHashtable') {
    return null
  }
  const inner = resolveInstance(instanceFieldMap(htWrapper).get('_container'))
  if (!inner || inner.classDesc.name !== 'java.util.Hashtable') {
    return null
  }
  return inner
}

/**
 * Resolved IHMC/BaseStorable `java.util.Hashtable` key/value blob for one instance chain.
 */
export function extractIhmcStorablePropMap(root: InstanceParsed): Map<string, unknown> {
  const frontier: InstanceParsed[] = [root]
  const seen = new Set<InstanceParsed>()
  while (frontier.length > 0) {
    const node = frontier.pop()
    if (!node || seen.has(node)) {
      continue
    }
    seen.add(node)

    const map = instanceFieldMap(node)

    const dataCandidate = resolveInstance(map.get('_data'))
    const extHashtableInstance =
      dataCandidate?.classDesc.name === 'nlk.base.ExtHashtable' ? dataCandidate : null
    if (extHashtableInstance) {
      const tableEncapsulated = extHashtableInnerHashtable(extHashtableInstance)
      if (tableEncapsulated) {
        return hashtablePairsToMap(tableEncapsulated)
      }
    }

    const directHashtable =
      dataCandidate?.classDesc.name === 'java.util.Hashtable' ? dataCandidate : null
    if (directHashtable) {
      return hashtablePairsToMap(directHashtable)
    }

    const wrapper = resolveInstance(map.get('_baseStorableWrapper'))
    const traversalNext: InstanceParsed[] = []
    if (wrapper && !seen.has(wrapper)) {
      traversalNext.push(wrapper)
    }
    if (dataCandidate && dataCandidate !== wrapper && !seen.has(dataCandidate)) {
      traversalNext.push(dataCandidate)
    }
    frontier.push(...traversalNext)
  }
  return new Map()
}

function unwrapJavaLangNumber(val: unknown): number | null {
  const inst = resolveInstance(val)
  if (!inst) {
    return null
  }
  const className = inst.classDesc.name
  if (
    className !== 'java.lang.Integer' &&
    className !== 'java.lang.Short' &&
    className !== 'java.lang.Byte'
  ) {
    return null
  }
  const v = inst.values[0]
  if (typeof v === 'number') {
    return Math.trunc(v)
  }
  return null
}

function javaVectorElements(vec: InstanceParsed): unknown[] {
  if (vec.classDesc.name !== 'java.util.Vector') {
    return []
  }
  const mapped = instanceFieldMap(vec)
  const countCandidate = unwrapJavaLangNumber(mapped.get('elementCount'))
  const fallbackCount =
    typeof mapped.get('elementCount') === 'number'
      ? Math.trunc(mapped.get('elementCount') as number)
      : null
  const count = typeof countCandidate === 'number' ? countCandidate : fallbackCount
  const raw = mapped.get('elementData')
  if (!Array.isArray(raw)) {
    return []
  }
  const limit =
    typeof count === 'number' && Number.isFinite(count)
      ? Math.min(Math.max(0, count), raw.length)
      : raw.length
  return raw.slice(0, limit)
}

function extVectorElements(wrapper: InstanceParsed): InstanceParsed[] {
  if (wrapper.classDesc.name !== 'nlk.base.ExtVector') {
    return []
  }
  const inner = resolveInstance(instanceFieldMap(wrapper).get('_v'))
  if (!inner || inner.classDesc.name !== 'java.util.Vector') {
    return []
  }
  return javaVectorElements(inner)
    .map((element) => resolveInstance(element))
    .filter((node): node is InstanceParsed => node !== null)
}

function instancesFromSemanticContainer(
  blob: unknown,
  expectedExactClassNames: readonly string[]
): InstanceParsed[] {
  const boxed = resolveInstance(blob)
  if (!boxed) {
    return []
  }

  function classMatches(candidate: InstanceParsed): boolean {
    return expectedExactClassNames.includes(candidate.classDesc.name)
  }

  function collectFromPairs(tableInstance: InstanceParsed): InstanceParsed[] {
    const unique = new Map<InstanceParsed, true>()
    const ordered: InstanceParsed[] = []
    for (const value of hashtableStoredValues(tableInstance)) {
      const boxedValue = resolveInstance(value)
      if (!boxedValue || !classMatches(boxedValue)) {
        continue
      }
      if (!unique.has(boxedValue)) {
        unique.set(boxedValue, true)
        ordered.push(boxedValue)
      }
    }
    return ordered
  }

  if (boxed.classDesc.name === 'nlk.base.ExtVector') {
    return extVectorElements(boxed).filter((node) => classMatches(node))
  }

  if (boxed.classDesc.name === 'nlk.base.ExtHashtable') {
    const innerTable = extHashtableInnerHashtable(boxed)
    return innerTable ? collectFromPairs(innerTable) : []
  }

  if (boxed.classDesc.name === 'java.util.Hashtable') {
    return collectFromPairs(boxed)
  }

  return []
}

function instancesMatchingClassPredicate(
  blob: unknown,
  matches: (name: string) => boolean
): InstanceParsed[] {
  const boxed = resolveInstance(blob)
  if (!boxed) {
    return []
  }

  function collectFromPairs(tableInstance: InstanceParsed): InstanceParsed[] {
    const unique = new Map<InstanceParsed, true>()
    const ordered: InstanceParsed[] = []
    for (const value of hashtableStoredValues(tableInstance)) {
      const boxedValue = resolveInstance(value)
      if (!boxedValue || !matches(boxedValue.classDesc.name)) {
        continue
      }
      if (!unique.has(boxedValue)) {
        unique.set(boxedValue, true)
        ordered.push(boxedValue)
      }
    }
    return ordered
  }

  if (boxed.classDesc.name === 'nlk.base.ExtVector') {
    return extVectorElements(boxed).filter((node) => matches(node.classDesc.name))
  }
  if (boxed.classDesc.name === 'nlk.base.ExtHashtable') {
    const innerTable = extHashtableInnerHashtable(boxed)
    return innerTable ? collectFromPairs(innerTable) : []
  }
  if (boxed.classDesc.name === 'java.util.Hashtable') {
    return collectFromPairs(boxed)
  }

  return []
}

function propositionClassMatcher(className: string): boolean {
  return className === 'nlk.base.Proposition' || /\.Proposition$/i.test(className)
}

function conceptKeySemanticRank(propertyKey: string): number {
  const k = propertyKey.toLowerCase()
  if (
    /\bleft\b|^l$|^from$|^first|concept[\s_-]?1|\bc1\b|subject|antecedent|\bstart\b|^source\b/.test(
      k
    )
  ) {
    return 0
  }
  if (
    /\bright\b|^r$|^to$|^second|concept[\s_-]?2|\bc2\b|object|\bend\b|^target\b|succ|\bdestination\b/.test(
      k
    )
  ) {
    return 200
  }
  if (/middle|between|predicate|linkingphrase|phrase/.test(k)) {
    return 100
  }
  return 50
}

function edgeFromPropositionInstance(
  inst: InstanceParsed,
  instToConceptId: Map<InstanceParsed, string>,
  registerConceptStub: (node: InstanceParsed) => string
): CmapGraphRelationship | null {
  const props = extractIhmcStorablePropMap(inst)
  const conceptRows: Array<{ key: string; rank: number; node: InstanceParsed }> = []
  const linkerNodes: InstanceParsed[] = []

  for (const [key, val] of props) {
    const node = resolveInstance(val)
    if (!node) {
      continue
    }
    if (node.classDesc.name === 'nlk.base.Concept') {
      conceptRows.push({ key, rank: conceptKeySemanticRank(key), node })
      continue
    }
    if (node.classDesc.name === 'nlk.base.LinkingPhrase') {
      linkerNodes.push(node)
    }
  }

  conceptRows.sort((a, b) => a.rank - b.rank || a.key.localeCompare(b.key))
  if (conceptRows.length < 2) {
    return null
  }

  let phraseLabel = ''
  for (const link of linkerNodes) {
    phraseLabel = phraseFromStorable(link) ?? ''
    if (phraseLabel.length > 0) {
      break
    }
  }
  if (!phraseLabel) {
    return null
  }

  const leftNode = conceptRows[0]?.node
  const rightNode = conceptRows[conceptRows.length - 1]?.node
  if (!leftNode || !rightNode || leftNode === rightNode) {
    return null
  }

  const fromId = instToConceptId.get(leftNode) ?? registerConceptStub(leftNode)
  const toId = instToConceptId.get(rightNode) ?? registerConceptStub(rightNode)
  return {
    fromId,
    toId,
    label: phraseLabel,
  }
}

function phraseFromStorable(inst: InstanceParsed): string | null {
  const props = extractIhmcStorablePropMap(inst)
  const message = props.get('_phrase')
  if (typeof message !== 'string') {
    return null
  }
  const label = normalizeLabel(message)
  return label.length > 0 ? label : null
}

function connectionEnds(inst: InstanceParsed): { first: unknown; second: unknown } | null {
  const props = extractIhmcStorablePropMap(inst)
  const left = props.get('_firstNode')
  const right = props.get('_secondNode')
  if (left === undefined || right === undefined) {
    return null
  }
  return { first: left, second: right }
}

function semanticWeight(inst: InstanceParsed): number {
  const pm = extractIhmcStorablePropMap(inst)
  let score = instancesFromSemanticContainer(pm.get('_concepts'), ['nlk.base.Concept']).length << 14
  score +=
    instancesFromSemanticContainer(pm.get('_connections'), ['nlk.base.Connection']).length << 10
  score +=
    instancesFromSemanticContainer(pm.get('_linkingPhrases'), ['nlk.base.LinkingPhrase']).length <<
    10
  score +=
    instancesMatchingClassPredicate(pm.get('_propositions'), propositionClassMatcher).length << 12
  return score
}

function chooseConceptMapRoot(roots: InstanceParsed[]): InstanceParsed | null {
  if (roots.length === 0) {
    return null
  }
  if (roots.length === 1) {
    return roots[0]
  }
  const sorted = [...roots].sort((left, right) => semanticWeight(right) - semanticWeight(left))
  return sorted[0] ?? null
}

export function extractConceptGraphFromHandles(handles: unknown[]): CmapGraphExtract | null {
  const roots: InstanceParsed[] = []
  for (const item of handles) {
    const inst = resolveInstance(item)
    if (inst?.classDesc.name === 'nlk.base.ConceptMap') {
      roots.push(inst)
    }
  }
  const conceptRootCandidate = chooseConceptMapRoot(roots)
  const diagnosticCandidates = roots.length
  if (!conceptRootCandidate) {
    return null
  }

  const propertyMap = extractIhmcStorablePropMap(conceptRootCandidate)
  const topicSource = propertyMap.get('_resourceName')
  const topicText =
    typeof topicSource === 'string'
      ? normalizeLabel(topicSource.replace(/\.cmap$/i, '').trim()) || normalizeLabel(topicSource)
      : ''
  const resourceDescriptionRaw = propertyMap.get('_resourceDescription')
  const focusQuestion =
    typeof resourceDescriptionRaw === 'string' ? normalizeLabel(resourceDescriptionRaw) : ''

  const conceptInstList = instancesFromSemanticContainer(propertyMap.get('_concepts'), [
    'nlk.base.Concept',
  ])
  const linkingInstList = instancesFromSemanticContainer(propertyMap.get('_linkingPhrases'), [
    'nlk.base.LinkingPhrase',
  ])
  const connectionInstList = instancesFromSemanticContainer(propertyMap.get('_connections'), [
    'nlk.base.Connection',
  ])
  const propositionInstList = instancesMatchingClassPredicate(
    propertyMap.get('_propositions'),
    propositionClassMatcher
  )

  const phraseLookup = new Map<InstanceParsed, string>()
  const linkingSet = new Set<InstanceParsed>(linkingInstList)
  const instToConceptId = new Map<InstanceParsed, string>()
  const conceptUnits: CmapConceptUnit[] = []

  let nextOrdinalId = 0
  let consumedTopicPlaceholder = false

  function allocateConceptIdentity(node: InstanceParsed, forcedLabel?: string): string | null {
    let label = phraseLookup.get(node) ?? phraseFromStorable(node) ?? forcedLabel ?? ''
    label = normalizeLabel(typeof label === 'string' ? label : '')
    if (!label.length) {
      return null
    }

    phraseLookup.set(node, label)

    const idCandidate: string | null = instToConceptId.get(node) ?? null
    if (idCandidate) {
      return idCandidate
    }
    let idResolved: string
    if (
      consumedTopicPlaceholder &&
      topicText.length > 0 &&
      label === topicText &&
      !instToConceptId.has(node)
    ) {
      idResolved = `topic-extra-${nextOrdinalId}`
      nextOrdinalId += 1
    } else if (!consumedTopicPlaceholder && topicText.length > 0 && label === topicText) {
      idResolved = 'topic'
      consumedTopicPlaceholder = true
    } else {
      idResolved = `cim-${nextOrdinalId}`
      nextOrdinalId += 1
    }
    instToConceptId.set(node, idResolved)
    conceptUnits.push({ id: idResolved, label })
    return idResolved
  }

  for (const node of conceptInstList) {
    const label = phraseFromStorable(node)
    if (!label) {
      continue
    }
    if (topicText.length > 0 && label === topicText) {
      if (!consumedTopicPlaceholder) {
        allocateConceptIdentity(node)
      }
      phraseLookup.set(node, label)
      continue
    }
    allocateConceptIdentity(node)
  }

  for (const node of linkingInstList) {
    const label = phraseFromStorable(node)
    if (label) phraseLookup.set(node, label)
  }

  connectionInstList.forEach((conn) => {
    const endpoints = connectionEnds(conn)
    if (!endpoints) return
    const head = resolveInstance(endpoints.first)
    const tail = resolveInstance(endpoints.second)
    if (head && !phraseLookup.has(head)) {
      const resolved = phraseFromStorable(head)
      if (resolved) phraseLookup.set(head, resolved)
    }
    if (tail && !phraseLookup.has(tail)) {
      const resolved = phraseFromStorable(tail)
      if (resolved) phraseLookup.set(tail, resolved)
    }
  })

  let unreferencedStubCounter = 0
  function registerConceptStubExternal(node: InstanceParsed): string {
    const labeled = phraseFromStorable(node)
    if (!labeled) {
      const anonId = `cim-unlabeled-${unreferencedStubCounter}`
      unreferencedStubCounter += 1
      instToConceptId.set(node, anonId)
      conceptUnits.push({ id: anonId, label: `? (${anonId})` })
      phraseLookup.set(node, `? (${anonId})`)
      return anonId
    }
    const assigned = allocateConceptIdentity(node, labeled)
    if (!assigned) {
      const anonId = `cim-unlabeled-${unreferencedStubCounter}`
      unreferencedStubCounter += 1
      instToConceptId.set(node, anonId)
      conceptUnits.push({ id: anonId, label: labeled })
      phraseLookup.set(node, labeled)
      return anonId
    }
    return assigned
  }

  function pushDedupSignature(
    signatures: Set<string>,
    accumulator: CmapGraphRelationship[],
    fromId: string,
    toId: string,
    middleLabel: string
  ): void {
    if (!fromId || !toId || !middleLabel || fromId === toId) {
      return
    }
    const normalized = normalizeLabel(middleLabel)
    if (!normalized.length) return
    const signature = `${fromId}\0${toId}\0${normalized}`
    if (signatures.has(signature)) {
      return
    }
    signatures.add(signature)
    accumulator.push({
      fromId,
      toId,
      label: normalized,
    })
  }

  const propositionRelationships: CmapGraphRelationship[] = []
  if (propositionInstList.length > 0) {
    for (const proposition of propositionInstList) {
      const edge = edgeFromPropositionInstance(
        proposition,
        instToConceptId,
        registerConceptStubExternal
      )
      if (edge) propositionRelationships.push(edge)
    }
  }

  function dedupePush(
    accumulator: CmapGraphRelationship[],
    signatures: Set<string>,
    relation: CmapGraphRelationship
  ): void {
    pushDedupSignature(signatures, accumulator, relation.fromId, relation.toId, relation.label)
  }

  const propositionSignatures = new Set<string>()
  const propositionDeduped: CmapGraphRelationship[] = []
  for (const rel of propositionRelationships) {
    dedupePush(propositionDeduped, propositionSignatures, rel)
  }

  const connectionSignatures = new Set<string>()
  const connectionDeduped: CmapGraphRelationship[] = []
  const connectionFallbackUsedFlag = propositionDeduped.length === 0

  if (connectionFallbackUsedFlag) {
    for (const linking of linkingInstList) {
      const linkPhrase = phraseLookup.get(linking) ?? phraseFromStorable(linking) ?? ''
      if (!linkPhrase) continue

      const inboundSubjects: InstanceParsed[] = []
      const outboundSubjects: InstanceParsed[] = []
      connectionInstList.forEach((wire) => {
        const terminals = connectionEnds(wire)
        if (!terminals) return
        const first = resolveInstance(terminals.first)
        const second = resolveInstance(terminals.second)
        if (!first || !second) return
        if (second === linking && !linkingSet.has(first)) {
          inboundSubjects.push(first)
        }
        if (first === linking && !linkingSet.has(second)) {
          outboundSubjects.push(second)
        }
      })

      const uniqueInbound = [...new Set(inboundSubjects)]
      const uniqueOutbound = [...new Set(outboundSubjects)]

      for (const fromNode of uniqueInbound) {
        const tailLabel = phraseLookup.get(fromNode) ?? phraseFromStorable(fromNode) ?? null
        if (
          !tailLabel ||
          (topicText.length > 0 && tailLabel === topicText) ||
          linkingSet.has(fromNode)
        ) {
          continue
        }

        const fromIdResolved = instToConceptId.get(fromNode) ?? allocateConceptIdentity(fromNode)
        if (!fromIdResolved) continue

        for (const toward of uniqueOutbound) {
          const heading = phraseLookup.get(toward) ?? phraseFromStorable(toward) ?? null
          if (
            !heading ||
            (topicText.length > 0 && heading === topicText) ||
            linkingSet.has(toward)
          ) {
            continue
          }

          const toIdResolved = instToConceptId.get(toward) ?? allocateConceptIdentity(toward)
          if (!toIdResolved) continue

          pushDedupSignature(
            connectionSignatures,
            connectionDeduped,
            fromIdResolved,
            toIdResolved,
            linkPhrase
          )
        }
      }
    }
  }

  const finalRelationships = propositionDeduped.length > 0 ? propositionDeduped : connectionDeduped

  const concept_units = [...conceptUnits].sort((elementA, elementB) => {
    if (elementA.id === 'topic' && elementB.id !== 'topic') return -1
    if (elementB.id === 'topic' && elementA.id !== 'topic') return 1
    return elementA.id.localeCompare(elementB.id)
  })

  const hasRenderableUnits = concept_units.some((cu) => !cu.label.startsWith('? ('))

  if (finalRelationships.length === 0 && !hasRenderableUnits && !topicText) {
    return null
  }

  return {
    concept_units,
    relationships: finalRelationships,
    topicHint: topicText.length > 0 ? topicText : undefined,
    focusQuestion:
      focusQuestion.length > 0 && focusQuestion !== topicText ? focusQuestion : undefined,
    diagnostics: {
      conceptMapRootCandidates: diagnosticCandidates,
      connectionEdgeFallbackUsed: connectionFallbackUsedFlag,
      propositionEdgesUsed: propositionDeduped.length > 0,
    },
  }
}

export function extractConceptGraphFromCmapBytes(cmapBytes: Uint8Array): CmapGraphExtract | null {
  try {
    const parsed = parseJavaSerializationStream(cmapBytes)
    return extractConceptGraphFromHandles(parsed.handles)
  } catch (error) {
    if (error instanceof JavaParseError) {
      return null
    }
    throw error
  }
}
