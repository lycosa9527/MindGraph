/**
 * Seed frontend/public/fonts with TrueType faces for mind-map PDF export.
 *
 * jsPDF cannot encode Noto CJK OTF/CFF (glyphFor fails). We vendor static
 * TrueType from @fontsource/noto-sans-sc (already an app dependency) so the
 * publish step stays offline after npm install.
 *
 * Production runtime loads fonts via `/api/mindmap_export_fonts/*` (COS-backed).
 * After vendoring, publish once:
 *   python scripts/db/publish_mindmap_export_fonts_to_cos.py
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import fontverter from 'fontverter'

const require = createRequire(import.meta.url)
const __dirname = dirname(fileURLToPath(import.meta.url))
const fontsDir = join(__dirname, '..', 'public', 'fonts')

const FONTS = [
  {
    file: 'NotoSansSC-Regular.ttf',
    woff2: 'noto-sans-sc/files/noto-sans-sc-chinese-simplified-400-normal.woff2',
  },
  {
    file: 'NotoSansSC-Bold.ttf',
    woff2: 'noto-sans-sc/files/noto-sans-sc-chinese-simplified-700-normal.woff2',
  },
]

function resolveFontsourceWoff2(relPath) {
  return require.resolve(`@fontsource/${relPath}`)
}

mkdirSync(fontsDir, { recursive: true })
for (const font of FONTS) {
  const dest = join(fontsDir, font.file)
  if (existsSync(dest) && dest.endsWith('.ttf')) {
    const existing = readFileSync(dest)
    // TrueType sfnt version 0x00010000
    if (
      existing.length > 1024 &&
      existing[0] === 0x00 &&
      existing[1] === 0x01 &&
      existing[2] === 0x00 &&
      existing[3] === 0x00
    ) {
      console.log(`skip (exists TTF): ${dest}`)
      continue
    }
  }
  const srcPath = resolveFontsourceWoff2(font.woff2)
  console.log(`convert: ${srcPath} -> ${dest}`)
  const woff2 = readFileSync(srcPath)
  const ttf = await fontverter.convert(woff2, 'truetype')
  const out = Buffer.from(ttf)
  if (out.length < 1024 || out.readUInt32BE(0) !== 0x00010000) {
    throw new Error(`TrueType conversion failed for ${font.file}`)
  }
  writeFileSync(dest, out)
  console.log(`wrote: ${dest} (${out.length} bytes)`)
}
console.log('Mind-map export fonts ready (TrueType /fonts/*.ttf).')
