/**
 * One-off: generate zh-tw namespace files from zh using OpenCC cn→tw.
 * Run: npx tsx scripts/build-zhtw-from-zh.ts
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import * as OpenCC from 'opencc-js'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '../src/locales/messages')
const ZH = join(ROOT, 'zh')
const ZH_TW = join(ROOT, 'zh-tw')

const FILES = [
  'admin.ts',
  'auth.ts',
  'canvas.ts',
  'common.ts',
  'community.ts',
  'knowledge.ts',
  'mindmate.ts',
  'notification.ts',
  'sidebar.ts',
  'workshop.ts',
] as const

function convertFileContent(text: string, convert: (s: string) => string): string {
  const lines = text.split('\n')
  const out: string[] = []
  const lineRe = /^(\s*'[^']+'\s*:\s*)'([^']*)'(\s*,?)\s*$/
  for (const line of lines) {
    const m = line.match(lineRe)
    if (m) {
      out.push(`${m[1]}'${convert(m[2])}'${m[3]}`)
    } else {
      if (line.includes('/** Chinese UI')) {
        out.push(line.replace('Chinese UI', 'Traditional Chinese (zh-TW) UI'))
      } else if (line.includes('/** zh UI')) {
        out.push(line.replace('zh UI', 'zh-tw UI'))
      } else {
        out.push(line)
      }
    }
  }
  return out.join('\n')
}

async function main(): Promise<void> {
  const convert = OpenCC.Converter({ from: 'cn', to: 'tw' })
  if (!existsSync(ZH_TW)) {
    mkdirSync(ZH_TW, { recursive: true })
  }
  for (const name of FILES) {
    const src = readFileSync(join(ZH, name), 'utf8')
    const dst = convertFileContent(src, convert)
    writeFileSync(join(ZH_TW, name), dst, 'utf8')
    console.log('wrote', name)
  }
  const indexSrc = readFileSync(join(ZH, 'index.ts'), 'utf8')
  writeFileSync(
    join(ZH_TW, 'index.ts'),
    indexSrc.replace('zh UI messages', 'zh-tw (Traditional Chinese) UI messages'),
    'utf8'
  )
  console.log('wrote index.ts')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
