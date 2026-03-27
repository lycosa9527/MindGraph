import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const mod = await import('../src/locales/messages/en/canvas.ts')
const data = mod.default
fs.writeFileSync(path.join(__dirname, 'canvas-en-flat.json'), JSON.stringify(data, null, 2))
console.log('keys', Object.keys(data).length)
