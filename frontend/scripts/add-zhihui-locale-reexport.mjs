/**
 * Wire ZhiHui locale bundles: re-export en/zhihui.ts + sidebar keys for all locales.
 * Run from frontend/: node scripts/add-zhihui-locale-reexport.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const messagesRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../src/locales/messages'
)
const SIDEBAR_KEYS_EN = [
  ["sidebar.zhihui", 'ZhiHui'],
  ["sidebar.zhihuiHistory.title", 'Generation history'],
  ["sidebar.zhihuiHistory.empty", 'No generations yet'],
  ["sidebar.zhihuiHistory.deleteConfirm", 'Delete this generation? This cannot be undone.'],
]

const SIDEBAR_KEYS_ZH_TW = [
  ["sidebar.zhihui", '智繪'],
  ["sidebar.zhihuiHistory.title", '生成歷史'],
  ["sidebar.zhihuiHistory.empty", '暫無生成記錄'],
  ["sidebar.zhihuiHistory.deleteConfirm", '確定刪除這條生成記錄嗎？此操作不可撤銷。'],
]

let indexUpdates = 0
let sidebarUpdates = 0

for (const name of fs.readdirSync(messagesRoot)) {
  if (name === 'zh' || name === 'en' || name === 'it_test') continue
  const dir = path.join(messagesRoot, name)
  if (!fs.statSync(dir).isDirectory()) continue
  const indexPath = path.join(dir, 'index.ts')
  if (!fs.existsSync(indexPath)) continue

  const reexport =
    name === 'zh-tw'
      ? "export { default } from '../zh/zhihui.ts'\n"
      : "export { default } from '../en/zhihui.ts'\n"
  fs.writeFileSync(path.join(dir, 'zhihui.ts'), reexport)

  let raw = fs.readFileSync(indexPath, 'utf8')
  if (!raw.includes("from './zhihui.ts'") && !raw.includes('from "./zhihui.ts"')) {
    if (raw.includes("import showcase from './showcase.ts'\n")) {
      raw = raw.replace(
        "import showcase from './showcase.ts'\n",
        "import showcase from './showcase.ts'\nimport zhihui from './zhihui.ts'\n"
      )
    } else if (raw.includes("import community from './community.ts'\n")) {
      raw = raw.replace(
        "import community from './community.ts'\n",
        "import community from './community.ts'\nimport zhihui from './zhihui.ts'\n"
      )
    } else {
      throw new Error(`Cannot wire zhihui import in ${indexPath}`)
    }
    if (raw.includes('  ...showcase,\n')) {
      raw = raw.replace('  ...showcase,\n', '  ...showcase,\n  ...zhihui,\n')
    } else if (raw.includes('  ...community,\n')) {
      raw = raw.replace('  ...community,\n', '  ...community,\n  ...zhihui,\n')
    } else {
      throw new Error(`Cannot wire zhihui spread in ${indexPath}`)
    }
    fs.writeFileSync(indexPath, raw)
    indexUpdates += 1
  }

  const sidebarPath = path.join(dir, 'sidebar.ts')
  if (!fs.existsSync(sidebarPath)) continue
  let sidebar = fs.readFileSync(sidebarPath, 'utf8')
  if (sidebar.includes("'sidebar.zhihui'")) continue
  const anchor = "'sidebar.showcase'"
  const pos = sidebar.indexOf(anchor)
  if (pos < 0) {
    throw new Error(`Missing sidebar.showcase in ${sidebarPath}`)
  }
  const lineEnd = sidebar.indexOf('\n', pos)
  let cursor = lineEnd + 1
  while (cursor < sidebar.length) {
    const nextEnd = sidebar.indexOf('\n', cursor)
    const end = nextEnd < 0 ? sidebar.length : nextEnd
    const line = sidebar.slice(cursor, end)
    const stripped = line.trim()
    if (stripped.startsWith("'sidebar.") || stripped.startsWith('} as const')) {
      break
    }
    cursor = end + 1
  }
  const sidebarKeys = name === 'zh-tw' ? SIDEBAR_KEYS_ZH_TW : SIDEBAR_KEYS_EN
  const block = sidebarKeys.map(([key, value]) => `  '${key}': '${value}',\n`).join('')
  sidebar = sidebar.slice(0, cursor) + block + sidebar.slice(cursor)
  fs.writeFileSync(sidebarPath, sidebar)
  sidebarUpdates += 1
}

console.log(
  `zhihui re-export wired; updated ${indexUpdates} index.ts and ${sidebarUpdates} sidebar.ts file(s).`
)
