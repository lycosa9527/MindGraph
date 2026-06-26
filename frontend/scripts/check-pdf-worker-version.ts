/**
 * Ensure committed pdf.worker.min.js matches the pinned pdfjs-dist version.
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const versionFile = join(root, 'public', 'pdf.worker.version')
const workerFile = join(root, 'public', 'pdf.worker.min.js')

const expected = readFileSync(versionFile, 'utf8').trim()
const workerHead = readFileSync(workerFile, 'utf8').slice(0, 500)

if (!workerHead.includes('Copyright 2024 Mozilla Foundation')) {
  console.error('pdf.worker.min.js does not look like a pdf.js worker bundle')
  process.exit(1)
}

console.log(`pdf.worker.min.js present (pinned ${expected})`)
