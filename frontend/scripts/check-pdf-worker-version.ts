/**
 * Ensure committed pdf.worker.min.mjs matches the pinned pdfjs-dist version.
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const versionFile = join(root, 'public', 'pdf.worker.version')
const workerMjs = join(root, 'public', 'pdf.worker.min.mjs')
const packageJson = join(root, 'package.json')

const expected = readFileSync(versionFile, 'utf8').trim()
const pkg = JSON.parse(readFileSync(packageJson, 'utf8')) as {
  dependencies?: Record<string, string>
}
const dep = pkg.dependencies?.['pdfjs-dist'] ?? ''
const depVersion = dep.replace(/^[^\d]*/, '')
const pinnedVersion = expected.replace(/^pdfjs-dist@/, '')

if (depVersion && pinnedVersion && !depVersion.startsWith(pinnedVersion)) {
  console.error(
    `pdf.worker.version (${expected}) does not match package.json pdfjs-dist (${dep})`
  )
  process.exit(1)
}

const workerHead = readFileSync(workerMjs, 'utf8').slice(0, 800)
if (!workerHead.includes('Mozilla Foundation') && !workerHead.includes('pdfjs')) {
  console.error('pdf.worker.min.mjs does not look like a pdf.js worker bundle')
  process.exit(1)
}

console.log(`pdf.worker.min.mjs present (pinned ${expected})`)
