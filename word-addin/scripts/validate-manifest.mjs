#!/usr/bin/env node
/**
 * Lightweight local manifest checks (no office-addin-manifest / app-manifest tree).
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const manifestPath = join(root, 'manifest.xml')
const xml = readFileSync(manifestPath, 'utf8')

function requireMatch(label, re) {
  const m = xml.match(re)
  if (!m || !String(m[1] || '').trim()) {
    throw new Error(`Missing ${label}`)
  }
  return String(m[1]).trim()
}

const id = requireMatch('Id', /<Id>([^<]+)<\/Id>/i)
const version = requireMatch('Version', /<Version>([^<]+)<\/Version>/i)
const displayNameRaw = requireMatch(
  'DisplayName',
  /<DisplayName[^>]*DefaultValue="([^"]*)"/i
)
const displayName =
  displayNameRaw === '&#x200B;' || displayNameRaw === '\u200B'
    ? '(hidden)'
    : displayNameRaw

// Five ShowTaskpane buttons + MindMate dialog host page (ExecuteFunction).
const taskpaneUrlResources = [...xml.matchAll(/id="Taskpane\.[^"]+\.Url"/g)]
if (taskpaneUrlResources.length < 6) {
  throw new Error(
    `Expected 6 Taskpane.*Url resources, found ${taskpaneUrlResources.length}`
  )
}
if (!xml.includes('openMindMateDialog')) {
  throw new Error('Expected MindMate ExecuteFunction openMindMateDialog')
}

const httpsLocals = [...xml.matchAll(/DefaultValue="(https:\/\/localhost[^"]+)"/g)]
if (httpsLocals.length < 1) {
  throw new Error('Expected https://localhost SourceLocation / resource URLs')
}

console.log('Manifest OK')
console.log(`  Id: ${id}`)
console.log(`  Version: ${version}`)
console.log(`  DisplayName: ${displayName}`)
console.log(`  Task pane URL resources: ${taskpaneUrlResources.length}`)
console.log('  MindMate: dialog (openMindMateDialog)')
console.log(`  Localhost HTTPS refs: ${httpsLocals.length}`)
