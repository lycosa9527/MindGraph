#!/usr/bin/env node
/**
 * Fail if @vueuse/core dist still contains Rolldown-invalid #__PURE__ annotations.
 * Matches upstream vueuse/vueuse#5388 until a release > 14.3.0 ships the fix.
 *
 * Run from frontend/: npm run check:vueuse-pure
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const distPath = join(__dirname, '..', 'node_modules', '@vueuse', 'core', 'dist', 'index.js')

let source
try {
  source = readFileSync(distPath, 'utf8')
} catch {
  console.error(`[check:vueuse-pure] Missing ${distPath} — run npm ci first`)
  process.exit(1)
}

const violations = []

for (const [index, line] of source.split('\n').entries()) {
  const trimmed = line.trim()
  if (trimmed === '/* #__PURE__ */') {
    violations.push({ line: index + 1, text: trimmed, reason: 'standalone #__PURE__ comment' })
  }
  if (/\(\/\* #__PURE__ \*\/\s*\{/.test(line)) {
    violations.push({
      line: index + 1,
      text: trimmed,
      reason: '#__PURE__ on object literal (not a call expression)',
    })
  }
}

if (violations.length > 0) {
  console.error('[check:vueuse-pure] Invalid #__PURE__ annotations in @vueuse/core dist:\n')
  for (const v of violations) {
    console.error(`  line ${v.line}: ${v.reason}`)
    console.error(`    ${v.text}`)
  }
  console.error(
    '\nApply patches/@vueuse+core+14.3.0.patch (postinstall) or upgrade @vueuse/core when > 14.3.0 is published.',
  )
  process.exit(1)
}

console.log('[check:vueuse-pure] OK — no invalid #__PURE__ annotations in @vueuse/core')
