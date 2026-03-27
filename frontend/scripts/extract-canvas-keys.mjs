import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const p = path.join(__dirname, '../src/locales/messages/en/canvas.ts')
const s = fs.readFileSync(p, 'utf8')
const body = s
  .replace(/^\s*\/\*\*[\s\S]*?\*\/\s*export default \{\s*/, '')
  .replace(/\}\s*as const\s*$/, '')
const entries = []
let i = 0
const n = body.length
while (i < n) {
  while (i < n && /\s/.test(body[i])) i++
  if (i >= n) break
  if (body[i] !== "'") {
    i++
    continue
  }
  i++
  let key = ''
  while (i < n && body[i] !== "'") {
    key += body[i]
    i++
  }
  if (i >= n) break
  i++
  while (i < n && /\s/.test(body[i])) i++
  if (body[i] !== ':') continue
  i++
  while (i < n && /\s/.test(body[i])) i++
  if (body[i] !== "'") continue
  i++
  let val = ''
  while (i < n) {
    const c = body[i]
    if (c === '\\') {
      val += c + body[i + 1]
      i += 2
      continue
    }
    if (c === "'") {
      i++
      break
    }
    val += c
    i++
  }
  entries.push([key, val])
}
console.log('count', entries.length)
fs.writeFileSync(path.join(__dirname, '.canvas-en-pairs.json'), JSON.stringify(entries, null, 2))
