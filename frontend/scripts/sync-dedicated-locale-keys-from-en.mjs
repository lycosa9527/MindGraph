/**
 * Sync drifted English namespace files into dedicated bundles (az, th, fr, af).
 * Run from frontend/: node scripts/sync-dedicated-locale-keys-from-en.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src/locales/messages')
const en = path.join(root, 'en')
const dedicated = ['az', 'th', 'fr', 'af']
const files = ['auth.ts', 'common.ts', 'mindmate.ts', 'sidebar.ts', 'thinkingCoins.ts', 'caseSquare.ts']

for (const code of dedicated) {
  const destDir = path.join(root, code)
  for (const file of files) {
    let raw = fs.readFileSync(path.join(en, file), 'utf8')
    raw = raw.replace(/^\/\*\* English UI[^*]*\*\//, `/** ${code} UI (synced from en) */`)
    fs.writeFileSync(path.join(destDir, file), raw)
  }
  console.log('synced', code)
}
