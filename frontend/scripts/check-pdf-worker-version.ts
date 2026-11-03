/**
 * Ensure the committed PDF.js worker matches the installed pdfjs-dist build.
 * The library viewer used to ship a classic worker and Adobe CMaps under public/.
 * Showcase preview loads only public/pdf.worker.min.mjs.
 */
import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const versionFile = join(root, 'public', 'pdf.worker.version')
const workerMjs = join(root, 'public', 'pdf.worker.min.mjs')
const packagedWorker = join(root, 'node_modules', 'pdfjs-dist', 'build', 'pdf.worker.min.mjs')
const packagedPackageJson = join(root, 'node_modules', 'pdfjs-dist', 'package.json')
const packageJson = join(root, 'package.json')

const retiredPublicPaths = [
  join(root, 'public', 'pdf.worker.min.js'),
  join(root, 'public', 'pdfjs'),
  join(root, 'public', 'cmaps'),
]

function fail(message: string): never {
  console.error(message)
  process.exit(1)
}

const retiredFound = retiredPublicPaths.filter((path) => existsSync(path))
if (retiredFound.length > 0) {
  fail(
    `Retired PDF.js files are still under frontend/public:\n${retiredFound
      .map((path) => `  ${path}`)
      .join('\n')}`
  )
}

const expected = readFileSync(versionFile, 'utf8').trim()
const pkg = JSON.parse(readFileSync(packageJson, 'utf8')) as {
  dependencies?: Record<string, string>
}
const dep = pkg.dependencies?.['pdfjs-dist'] ?? ''
const depVersion = dep.replace(/^[^\d]*/, '')
const pinnedVersion = expected.replace(/^pdfjs-dist@/, '')

if (!pinnedVersion || !depVersion.startsWith(pinnedVersion)) {
  fail(`pdf.worker.version (${expected}) does not match package.json pdfjs-dist (${dep})`)
}

if (!existsSync(packagedWorker) || !existsSync(packagedPackageJson)) {
  fail('Installed pdfjs-dist worker is missing. Run npm ci in frontend/.')
}

const installed = JSON.parse(readFileSync(packagedPackageJson, 'utf8')) as { version?: string }
if (installed.version !== pinnedVersion) {
  fail(
    `pdf.worker.version (${expected}) does not match installed pdfjs-dist (${installed.version ?? 'missing'})`
  )
}

function sha256(path: string): string {
  return createHash('sha256').update(readFileSync(path)).digest('hex')
}

if (sha256(workerMjs) !== sha256(packagedWorker)) {
  fail('public/pdf.worker.min.mjs does not match node_modules/pdfjs-dist/build/pdf.worker.min.mjs')
}

console.log(`pdf.worker.min.mjs matches pdfjs-dist@${pinnedVersion}`)
