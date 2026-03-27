import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const locale = process.argv[2] || 'ja'
const mod = await import(`../src/locales/messages/${locale}/canvas.ts`)
const data = mod.default
fs.writeFileSync(path.join(__dirname, `canvas-${locale}-flat.json`), JSON.stringify(data, null, 2))
console.log('keys', Object.keys(data).length)
