/**
 * Scan frontend/src for Element Plus component usage (explicit imports + templates).
 *
 * Usage:
 *   npx tsx scripts/audit-element-plus-usage.ts
 *
 * Bundle verification (after vite.config manualChunks split):
 *   ANALYZE=1 npm run build
 *   Open dist/stats.html — confirm vendor-ep-data is not imported by index/App entry.
 *   DevTools → Network → hard refresh /mindmate — vendor-ep-data should not load on cold visit.
 */
import { readdirSync, readFileSync, statSync } from 'fs'
import { join, relative } from 'path'
import { fileURLToPath } from 'url'
import { dirname } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SRC_ROOT = join(__dirname, '../src')

const SKIP_DIRS = new Set(['node_modules', 'dist', '.git'])

const EL_IMPORT_RE = /from\s+['"]element-plus(?:\/[^'"]*)?['"]/g
const EL_NAMED_IMPORT_RE = /import\s*\{([^}]+)\}\s*from\s*['"]element-plus/g
const TEMPLATE_EL_RE = /<(el-[a-z][a-z0-9-]*)/gi

function walk(dir: string, files: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name)
    if (SKIP_DIRS.has(name)) {
      continue
    }
    const st = statSync(full)
    if (st.isDirectory()) {
      walk(full, files)
    } else if (/\.(vue|ts|tsx)$/.test(name)) {
      files.push(full)
    }
  }
  return files
}

type FileReport = {
  path: string
  namedImports: string[]
  templateTags: string[]
}

function parseFile(filePath: string): FileReport {
  const text = readFileSync(filePath, 'utf-8')
  const namedImports = new Set<string>()
  for (const match of text.matchAll(EL_NAMED_IMPORT_RE)) {
    const block = match[1] ?? ''
    for (const part of block.split(',')) {
      const name = part.trim().split(/\s+as\s+/)[0]?.trim()
      if (name && /^El[A-Z]/.test(name)) {
        namedImports.add(name)
      }
    }
  }
  const templateTags = new Set<string>()
  for (const match of text.matchAll(TEMPLATE_EL_RE)) {
    templateTags.add(match[1] ?? '')
  }
  return {
    path: relative(SRC_ROOT, filePath).replace(/\\/g, '/'),
    namedImports: [...namedImports].sort(),
    templateTags: [...templateTags].sort(),
  }
}

function main(): void {
  const files = walk(SRC_ROOT)
  const reports: FileReport[] = []
  const componentCounts = new Map<string, number>()

  for (const file of files) {
    const content = readFileSync(file, 'utf-8')
    const report = parseFile(file)
    const hasEpImport = EL_IMPORT_RE.test(content)
    if (report.namedImports.length === 0 && report.templateTags.length === 0 && !hasEpImport) {
      continue
    }
    if (report.namedImports.length > 0 || report.templateTags.length > 0 || hasEpImport) {
      reports.push(report)
    }
    for (const name of report.namedImports) {
      componentCounts.set(name, (componentCounts.get(name) ?? 0) + 1)
    }
    for (const tag of report.templateTags) {
      const key = tag
      componentCounts.set(key, (componentCounts.get(key) ?? 0) + 1)
    }
  }

  const sortedComponents = [...componentCounts.entries()].sort((a, b) => b[1] - a[1])

  console.log('Element Plus usage audit\n')
  console.log(`Files with EP usage: ${reports.length}\n`)
  console.log('Top components / tags:')
  for (const [name, count] of sortedComponents.slice(0, 40)) {
    console.log(`  ${count.toString().padStart(3)}  ${name}`)
  }
  if (sortedComponents.length > 40) {
    console.log(`  ... and ${sortedComponents.length - 40} more`)
  }
  console.log('\nPer-file breakdown (first 30 files):')
  for (const r of reports.slice(0, 30)) {
    const parts: string[] = []
    if (r.namedImports.length > 0) {
      parts.push(`imports: ${r.namedImports.join(', ')}`)
    }
    if (r.templateTags.length > 0) {
      parts.push(`tags: ${r.templateTags.join(', ')}`)
    }
    console.log(`  ${r.path}`)
    console.log(`    ${parts.join(' | ')}`)
  }
  if (reports.length > 30) {
    console.log(`  ... and ${reports.length - 30} more files`)
  }
}

main()
