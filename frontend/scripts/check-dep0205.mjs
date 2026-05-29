#!/usr/bin/env node
/**
 * Fail if any build-path step emits Node DEP0205 (module.register deprecation).
 * Run from frontend/: npm run check:dep0205
 */
import { spawnSync } from 'node:child_process'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const FRONTEND = join(__dirname, '..')
const NODE = process.execPath
const TRACE = ['--trace-deprecation']

const steps = [
  {
    label: 'sync-version',
    args: [...TRACE, join(FRONTEND, 'scripts/sync-version.ts')],
  },
  {
    label: 'vue-tsc',
    args: [
      ...TRACE,
      '--max-old-space-size=4096',
      join(FRONTEND, 'node_modules/vue-tsc/bin/vue-tsc.js'),
      '--noEmit',
    ],
  },
  {
    label: 'vite build',
    args: [
      ...TRACE,
      '--max-old-space-size=4096',
      join(FRONTEND, 'node_modules/vite/bin/vite.js'),
      'build',
    ],
  },
]

function runStep(label, args) {
  console.log(`\n[check:dep0205] ${label}`)
  const result = spawnSync(NODE, args, {
    cwd: FRONTEND,
    encoding: 'utf8',
    env: process.env,
  })
  const combined = `${result.stdout ?? ''}${result.stderr ?? ''}`
  if (combined.includes('DEP0205')) {
    console.error(`\n[check:dep0205] DEP0205 detected during: ${label}\n`)
    console.error(combined)
    process.exit(1)
  }
  if (result.status !== 0) {
    console.error(`\n[check:dep0205] ${label} failed (exit ${result.status})\n`)
    if (result.stdout) console.error(result.stdout)
    if (result.stderr) console.error(result.stderr)
    process.exit(result.status ?? 1)
  }
}

for (const step of steps) {
  runStep(step.label, step.args)
}

console.log('\n[check:dep0205] OK — no DEP0205 warnings')
