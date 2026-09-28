/**
 * Rewrite toast calls that pass t('key') into the bilingual key helpers.
 *
 *   notify.error(t('a.b'))            -> notify.errorKey('a.b')
 *   notify.error(String(t('a.b', p))) -> notify.errorKey('a.b', p)
 *   ElMessage.success(t('a.b'))       -> ElMessage.success({ message: bilingualNotifyMessage('a.b') })
 *
 * Raw API strings, ternaries, and concatenated messages are left alone.
 *   node scripts/codemod-bilingual-notify.mjs
 *   node scripts/codemod-bilingual-notify.mjs --check
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src')
const CHECK = process.argv.includes('--check')
const METHODS = ['success', 'error', 'warning', 'info']

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === 'locales' || entry.name === 'node_modules') continue
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(full, out)
    else if (entry.name.endsWith('.vue') || entry.name.endsWith('.ts')) out.push(full)
  }
  return out
}

function readBalanced(source, openIndex) {
  let depth = 0
  let quote = null
  let escaped = false
  for (let i = openIndex; i < source.length; i += 1) {
    const ch = source[i]
    if (quote) {
      if (escaped) escaped = false
      else if (ch === '\\') escaped = true
      else if (ch === quote) quote = null
      else if (quote === '`' && ch === '$' && source[i + 1] === '{') {
        const inner = readBalanced(source, i + 1)
        if (!inner) return null
        i = inner.end
      }
      continue
    }
    if (ch === "'" || ch === '"' || ch === '`') {
      quote = ch
      continue
    }
    if (ch === '(' || ch === '[' || ch === '{') depth += 1
    else if (ch === ')' || ch === ']' || ch === '}') {
      depth -= 1
      if (depth === 0) return { end: i, inner: source.slice(openIndex + 1, i) }
    }
  }
  return null
}

function splitArgs(inner) {
  const args = []
  let start = 0
  let depth = 0
  let quote = null
  let escaped = false
  for (let i = 0; i < inner.length; i += 1) {
    const ch = inner[i]
    if (quote) {
      if (escaped) escaped = false
      else if (ch === '\\') escaped = true
      else if (ch === quote) quote = null
      else if (quote === '`' && ch === '$' && inner[i + 1] === '{') {
        const wrapped = `{${inner.slice(i + 2)}`
        const innerBal = readBalanced(wrapped, 0)
        if (!innerBal) return null
        i += innerBal.end
      }
      continue
    }
    if (ch === "'" || ch === '"' || ch === '`') {
      quote = ch
      continue
    }
    if (ch === '(' || ch === '[' || ch === '{') depth += 1
    else if (ch === ')' || ch === ']' || ch === '}') depth -= 1
    else if (ch === ',' && depth === 0) {
      args.push(inner.slice(start, i))
      start = i + 1
    }
  }
  args.push(inner.slice(start))
  return args.map((part) => part.trim()).filter((part) => part.length > 0)
}

function parseTranslateCall(expr) {
  let body = expr.trim().replace(/\s+as\s+string$/, '')
  const stringWrap = body.match(/^String\s*\(([\s\S]*)\)$/)
  if (stringWrap) body = stringWrap[1].trim()
  const call = body.match(/^t\s*\(/)
  if (!call) return null
  const open = body.indexOf('(')
  const balanced = readBalanced(body, open)
  if (!balanced || balanced.end !== body.length - 1) return null
  const args = splitArgs(balanced.inner)
  if (!args || args.length < 1 || args.length > 2) return null
  let params = null
  if (args.length === 2) {
    const second = args[1]
    if (second.startsWith('{')) params = second
    else if (
      (second.startsWith("'") || second.startsWith('"')) &&
      !second.slice(1, -1).includes(second[0])
    ) {
      params = null
    } else return null
  }
  return { keyArg: args[0], params }
}

function rewriteNotifyCalls(source) {
  let changed = 0
  let cursor = 0
  let next = ''
  const pattern = /notify\.(success|error|warning|info)\s*\(/g
  for (const match of source.matchAll(pattern)) {
    const method = match[1]
    if (!METHODS.includes(method)) continue
    const open = match.index + match[0].length - 1
    const lineStart = source.lastIndexOf('\n', match.index) + 1
    const prefix = source.slice(lineStart, match.index)
    if (prefix.includes('//')) {
      continue
    }
    const balanced = readBalanced(source, open)
    if (!balanced) continue
    const args = splitArgs(balanced.inner)
    if (!args || args.length < 1 || args.length > 2) continue
    const translated = parseTranslateCall(args[0])
    if (!translated) continue
    const extra = args[1] ?? ''
    const pieces = [translated.keyArg]
    if (translated.params) pieces.push(translated.params)
    if (extra) pieces.push(extra)
    const replacement = `notify.${method}Key(${pieces.join(', ')})`
    next += source.slice(cursor, match.index) + replacement
    cursor = balanced.end + 1
    changed += 1
  }
  next += source.slice(cursor)
  return { source: changed ? next : source, changed }
}

function rewriteElMessageCalls(source) {
  let changed = 0
  let cursor = 0
  let next = ''
  const pattern = /ElMessage\.(success|error|warning|info)\s*\(/g
  for (const match of source.matchAll(pattern)) {
    const method = match[1]
    const open = match.index + match[0].length - 1
    const lineStart = source.lastIndexOf('\n', match.index) + 1
    if (source.slice(lineStart, match.index).includes('//')) continue
    const balanced = readBalanced(source, open)
    if (!balanced) continue
    const args = splitArgs(balanced.inner)
    if (!args || args.length !== 1) continue
    const translated = parseTranslateCall(args[0])
    if (!translated) continue
    const messageArgs = translated.params
      ? `${translated.keyArg}, ${translated.params}`
      : translated.keyArg
    const replacement = `ElMessage.${method}({ message: bilingualNotifyMessage(${messageArgs}) })`
    next += source.slice(cursor, match.index) + replacement
    cursor = balanced.end + 1
    changed += 1
  }
  next += source.slice(cursor)
  return { source: changed ? next : source, changed }
}

function ensureBilingualImport(source) {
  if (!source.includes('bilingualNotifyMessage(')) return source
  if (source.includes("from '@/i18n/bilingualNotifyMessage'")) return source
  const line = "import { bilingualNotifyMessage } from '@/i18n/bilingualNotifyMessage'\n"
  if (source.includes('<script setup')) {
    return source.replace('<script setup lang="ts">', `<script setup lang="ts">\n${line}`)
  }
  if (source.startsWith('<script')) {
    return source.replace(/<script[^>]*>\n/, (tag) => `${tag}${line}`)
  }
  const importAt = source.indexOf('import ')
  if (importAt === -1) return `${line}${source}`
  return `${source.slice(0, importAt)}${line}${source.slice(importAt)}`
}

function transform(source) {
  const notifyRewrite = rewriteNotifyCalls(source)
  const messageRewrite = rewriteElMessageCalls(notifyRewrite.source)
  let next = messageRewrite.source
  if (messageRewrite.changed) next = ensureBilingualImport(next)
  return {
    source: next,
    changed: notifyRewrite.changed + messageRewrite.changed,
  }
}

function selfTest() {
  const samples = [
    ["notify.error(t('a.b'))", "notify.errorKey('a.b')"],
    ["notify.success(String(t('a.b')))", "notify.successKey('a.b')"],
    ["notify.warning(t('a.b', { n: 1 }))", "notify.warningKey('a.b', { n: 1 })"],
    ["notify.info(t('a.b'), 5000)", "notify.infoKey('a.b', 5000)"],
    ["notify.error(t(dynamicKey))", "notify.errorKey(dynamicKey)"],
    ["notify.error(err || t('a.b'))", "notify.error(err || t('a.b'))"],
    [
      "ElMessage.success(t('workshop.linkCopied'))",
      "import { bilingualNotifyMessage } from '@/i18n/bilingualNotifyMessage'\nElMessage.success({ message: bilingualNotifyMessage('workshop.linkCopied') })",
    ],
  ]
  for (const [input, expected] of samples) {
    const got = transform(input).source
    if (got !== expected) {
      console.error('self-test failed\n in: ', input, '\n out:', got, '\n exp:', expected)
      process.exit(1)
    }
  }
}

selfTest()

let sites = 0
let files = 0
const pending = []
for (const file of walk(SRC)) {
  const original = fs.readFileSync(file, 'utf8')
  const result = transform(original)
  if (result.source === original) continue
  sites += result.changed
  files += 1
  pending.push([file, result.source])
}

if (CHECK) {
  if (pending.length) {
    console.error(`bilingual notify drift: ${sites} sites in ${files} files`)
    process.exit(1)
  }
  console.log('ok 0 sites in 0 files')
  process.exit(0)
}

for (const [file, next] of pending) fs.writeFileSync(file, next)
console.log(`updated ${sites} sites in ${files} files`)
