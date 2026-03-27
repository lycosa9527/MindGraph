import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const locale = process.argv[2]
if (!locale) {
  console.error('Usage: node build-canvas-tier2.mjs <locale>')
  process.exit(1)
}

const enPath = path.join(__dirname, 'canvas-en-flat.json')
const en = JSON.parse(fs.readFileSync(enPath, 'utf8'))
const trPath = path.join(__dirname, `canvas-${locale}-flat.json`)
if (!fs.existsSync(trPath)) {
  console.error('Missing', trPath)
  process.exit(1)
}
const tr = JSON.parse(fs.readFileSync(trPath, 'utf8'))
const order = Object.keys(en)
const merged = {}
for (const k of order) {
  if (!(k in tr)) {
    console.error('Missing translation for key:', k)
    process.exit(1)
  }
  merged[k] = tr[k]
}
if (Object.keys(tr).length !== order.length) {
  const extra = Object.keys(tr).filter((k) => !order.includes(k))
  if (extra.length) console.error('Extra keys in locale file:', extra)
}

function esc(s) {
  return String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'")
}

const header = `/** ${locale} UI — canvas (translated from en; review recommended) */\n`
let out = header + 'export default {\n'
for (const k of order) {
  const v = merged[k]
  const valEsc = esc(v)
  const enLine = fs.readFileSync(
    path.join(__dirname, '../src/locales/messages/en/canvas.ts'),
    'utf8'
  )
  const useMultiline =
    v.length > 88 ||
    (enLine.includes(`'${k}':`) && enLine.split(`'${k}':`)[1]?.trimStart().startsWith('\n'))
  if (useMultiline && v.indexOf('\n') === -1) {
    out += `  '${k}':\n    '${valEsc}',\n`
  } else if (v.includes('\n')) {
    out += `  '${k}':\n    '${valEsc.replace(/\n/g, '\\n')}',\n`
  } else {
    out += `  '${k}': '${valEsc}',\n`
  }
}
out += '} as const\n'

const outPath = path.join(__dirname, `../src/locales/messages/${locale}/canvas.ts`)
fs.writeFileSync(outPath, out)
console.log('Wrote', outPath, 'keys', order.length)
