/**
 * One-off diagnostics: decode `.cmap` samples and report layout vs concept overlap.
 * Usage: npx tsx scripts/analyze-cmap-folder.ts [folderPath]
 */
import { unzipSync } from 'fflate'
import fs from 'node:fs'
import path from 'node:path'

import { extractIhmcStorablePropMap } from '../src/utils/cmapGraphExtract'
import { decodeCmapToConceptMapSpec } from '../src/utils/cmapImport'
import {
  type InstanceParsed,
  JavaParseError,
  instanceFieldMap,
  parseJavaSerializationStream,
} from '../src/utils/javaSerializationParse'

function resolveInstance(val: unknown): InstanceParsed | null {
  if (val && typeof val === 'object' && (val as InstanceParsed).kind === 'instance') {
    return val as InstanceParsed
  }
  return null
}

function toArrayBuffer(u8: Uint8Array): ArrayBuffer {
  return u8.buffer.slice(u8.byteOffset, u8.byteOffset + u8.byteLength) as ArrayBuffer
}

function analyzeOne(filePath: string): void {
  const base = path.basename(filePath)
  const raw = fs.readFileSync(filePath)
  const u8 = new Uint8Array(raw)
  let spec: Record<string, unknown>
  try {
    spec = decodeCmapToConceptMapSpec(toArrayBuffer(u8))
  } catch (e) {
    console.log(base, 'DECODE_FAIL', e instanceof Error ? e.message : String(e))
    return
  }
  const concepts = Array.isArray(spec.concepts) ? (spec.concepts as string[]) : []
  const rel = spec.relationships as unknown[]
  const layout = spec._layout_positions_by_label as
    | Record<string, { x: number; y: number }>
    | undefined
  const layoutKeys = layout ? Object.keys(layout) : []
  const matched = concepts.filter((c) => layoutKeys.includes(c)).length

  const importMeta = spec._import_meta as
    | {
        concept_map_roots_found?: number
        semantics?: string
        relationship_source?: string
        proposition_edges_used?: boolean
      }
    | undefined

  const unpacked = unzipSync(u8)
  const cmapBytes = unpacked.cmap
  let coordHits = 0
  const graphicalConceptLike = new Set<string>()
  if (cmapBytes && cmapBytes.length > 0) {
    try {
      const parsed = parseJavaSerializationStream(cmapBytes)
      for (const h of parsed.handles) {
        const inst = resolveInstance(h)
        if (!inst) continue
        const cn = inst.classDesc.name
        if (
          (cn.includes('GraphicalConcept') || cn.includes('GraphicalLinkingPhrase')) &&
          !cn.includes('GraphicalConceptMap')
        ) {
          graphicalConceptLike.add(cn)
          const storMap = extractIhmcStorablePropMap(inst)
          const x = storMap.get('_x') ?? instanceFieldMap(inst).get('_x')
          const y = storMap.get('_y') ?? instanceFieldMap(inst).get('_y')
          if (x !== undefined && y !== undefined) coordHits += 1
        }
      }
    } catch (e) {
      const detail =
        e instanceof JavaParseError ? ` offset=${e.offset} byte=${cmapBytes[e.offset]}` : ''
      console.log(base, 'PARSE_STREAM_FAIL', e instanceof Error ? e.message : String(e), detail)
    }
  }

  console.log(
    `${base}\tconcepts=${concepts.length}\trel=${rel.length}\tlayoutKeys=${layoutKeys.length}\tmatched=${matched}\tcoordInstances=${coordHits}\tcmapRoots=${importMeta?.concept_map_roots_found ?? '?'}\tsemantics=${importMeta?.semantics ?? '?'}\trelsrc=${importMeta?.relationship_source ?? '?'}`
  )
  if (graphicalConceptLike.size > 0) {
    console.log(`  GraphicalConcept classes: ${[...graphicalConceptLike].join(', ')}`)
  }
  if (layoutKeys.length > 0 && matched < concepts.length) {
    const missing = concepts.filter((c) => !layoutKeys.includes(c)).slice(0, 6)
    console.log(`  layout missing sample: ${missing.join(' | ')}`)
  }
  if (layoutKeys.length === 0 && coordHits > 0) {
    console.log(
      '  note: coords present but layout extraction returned nothing (phrase/type mismatch?)'
    )
  }
}

const defaultDir = path.join(process.env.USERPROFILE ?? '', 'Desktop', '概念图案例')
const dirArg = process.argv[2] ?? defaultDir
if (!fs.existsSync(dirArg)) {
  console.error('Folder not found:', dirArg)
  process.exit(1)
}
const files = fs.readdirSync(dirArg).filter((f) => f.toLowerCase().endsWith('.cmap'))
for (const f of files.sort()) {
  analyzeOne(path.join(dirArg, f))
}
