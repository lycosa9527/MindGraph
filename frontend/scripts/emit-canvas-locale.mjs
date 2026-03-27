import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const locale = process.argv[2]
if (!locale) {
  console.error('Usage: node emit-canvas-locale.mjs <locale>')
  process.exit(1)
}
const trPath = path.join(__dirname, `canvas-${locale}-flat.json`)
if (!fs.existsSync(trPath)) {
  console.error('Missing', trPath)
  process.exit(1)
}
const data = JSON.parse(fs.readFileSync(trPath, 'utf8'))
const keys = Object.keys(data).sort()
const header = `/** ${locale} UI — canvas (translated from en; review recommended) */\n`
let out = header + 'export default {\n'
for (const k of keys) {
  const v = data[k]
  const esc = String(v).replace(/\\/g, '\\\\').replace(/'/g, "\\'")
  const keyEsc = k.replace(/'/g, "\\'")
  if (v.length > 70 || v.includes('\n')) {
    out += `  '${keyEsc}':\n    '${esc.replace(/\n/g, '\\n')}',\n`
  } else {
    out += `  '${keyEsc}': '${esc}',\n`
  }
}
out += '} as const\n'
const outPath = path.join(__dirname, `../src/locales/messages/${locale}/canvas.ts`)
fs.writeFileSync(outPath, out)
console.log('Wrote', outPath, 'keys', keys.length)
