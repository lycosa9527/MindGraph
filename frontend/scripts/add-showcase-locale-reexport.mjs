import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const messagesRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src/locales/messages')
const reexport = "export { default } from '../en/showcase.ts'\n"

let indexUpdates = 0
for (const name of fs.readdirSync(messagesRoot)) {
  if (name === 'zh' || name === 'en') continue
  const dir = path.join(messagesRoot, name)
  if (!fs.statSync(dir).isDirectory()) continue
  const indexPath = path.join(dir, 'index.ts')
  if (!fs.existsSync(indexPath)) continue

  fs.writeFileSync(path.join(dir, 'showcase.ts'), reexport)
  let raw = fs.readFileSync(indexPath, 'utf8')
  if (raw.includes('showcase')) continue
  raw = raw.replace(
    "import community from './community.ts'\n",
    "import community from './community.ts'\nimport showcase from './showcase.ts'\n"
  )
  raw = raw.replace('  ...community,\n', '  ...community,\n  ...showcase,\n')
  fs.writeFileSync(indexPath, raw)
  indexUpdates += 1
}

console.log(`showcase re-export wired for locales; updated ${indexUpdates} index.ts file(s).`)
