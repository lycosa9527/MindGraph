import { mkdirSync, writeFileSync } from 'fs'
import { dirname } from 'path'

import {
  ECHOES_REF,
  ECHOES_REPO,
  EXTRACTED_ECHOES_EN,
  EXTRACTED_ECHOES_MANIFEST,
  EXTRACTED_ECHOES_ZH,
} from './config.ts'
import { parseEchoesFromVendorTs } from './parse-echoes-ts.ts'

function writeJson(path: string, data: unknown): void {
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, 'utf8')
}

export function extractEchoesToVendorJson(): { zhCount: number; enCount: number } {
  const { zh, en } = parseEchoesFromVendorTs()
  if (zh.length === 0 || en.length === 0) {
    throw new Error(
      'No echoes .ts vendor files found. Run import with --refresh-echoes once, then --extract-echoes.'
    )
  }

  const extractedAt = new Date().toISOString()
  writeJson(EXTRACTED_ECHOES_ZH, zh)
  writeJson(EXTRACTED_ECHOES_EN, en)
  writeJson(EXTRACTED_ECHOES_MANIFEST, {
    source: {
      repo: ECHOES_REPO,
      ref: ECHOES_REF,
      license: 'CC BY-NC-SA 4.0',
    },
    extractedAt,
    zhCount: zh.length,
    enCount: en.length,
    note: 'Frozen extract shipped in repo; import reads JSON only (no upstream .ts fetch).',
  })

  return { zhCount: zh.length, enCount: en.length }
}
