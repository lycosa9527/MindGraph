/**
 * One-off: add explicit `.ts` / `.json` suffixes to relative ESM imports for Node native execution.
 * Scoped to the CLI script execution graph (scripts + locale bundles + selected i18n modules).
 *
 * Run from frontend/: node scripts/normalize-esm-import-extensions.mjs
 */
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const FRONTEND = join(__dirname, '..')

const SCOPED_DIRS = [join(FRONTEND, 'scripts'), join(FRONTEND, 'src/locales/messages')]

const SCOPED_FILES = [
  join(FRONTEND, 'src/i18n/locales.ts'),
  join(FRONTEND, 'src/i18n/supportedUiLocales.ts'),
  join(FRONTEND, 'src/i18n/supportedUiLocalesExtra.ts'),
  join(FRONTEND, 'src/i18n/keyboardLayoutForUiLocale.ts'),
]

const SPECIFIER_RE =
  /(?<=(?:import|export)\s+(?:type\s+)?(?:[\w*{}\s,$]+\sfrom\s+|))['"](\.[^'"]+)['"]/g

const EXPORT_FROM_RE = /export\s+[\s\S]*?\sfrom\s+['"](\.[^'"]+)['"]/g

const HAS_EXTENSION_RE = /\.(ts|tsx|js|mjs|cjs|json)$/

function collectFiles(dir, out) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name)
    const st = statSync(full)
    if (st.isDirectory()) {
      collectFiles(full, out)
    } else if (name.endsWith('.ts') && !name.endsWith('.d.ts')) {
      out.push(full)
    }
  }
}

function resolveRelativeSpecifier(fromFile, specifier) {
  if (HAS_EXTENSION_RE.test(specifier)) {
    return specifier
  }
  const base = resolve(dirname(fromFile), specifier)
  if (existsSync(`${base}.ts`)) {
    return `${specifier}.ts`
  }
  if (existsSync(join(base, 'index.ts'))) {
    return `${specifier}/index.ts`
  }
  if (existsSync(`${base}.json`)) {
    return `${specifier}.json`
  }
  return null
}

function rewriteSpecifiers(content, filePath) {
  let changed = false
  let unresolved = []

  const replaceIn = (re) => {
    content = content.replace(re, (match, specifier) => {
      if (!specifier.startsWith('.')) {
        return match
      }
      if (HAS_EXTENSION_RE.test(specifier)) {
        return match
      }
      const resolved = resolveRelativeSpecifier(filePath, specifier)
      if (!resolved) {
        unresolved.push(specifier)
        return match
      }
      changed = true
      return match.replace(specifier, resolved)
    })
  }

  replaceIn(SPECIFIER_RE)
  replaceIn(EXPORT_FROM_RE)

  return { content, changed, unresolved }
}

function patchAliasImports(content, filePath) {
  let changed = false
  if (filePath.endsWith('keyboardLayoutForUiLocale.ts')) {
    const next = content
      .replaceAll("from '@/i18n/locales'", "from './locales.ts'")
      .replaceAll("from '@/i18n/supportedUiLocales'", "from './supportedUiLocales.ts'")
    changed = next !== content
    content = next
  }
  if (filePath.endsWith('locales.ts')) {
    const next = content.replaceAll(
      "from '@data/prompt_language_registry.json'",
      "from '../../../data/prompt_language_registry.json'"
    )
    changed = changed || next !== content
    content = next
  }
  return { content, changed }
}

function main() {
  const files = [...SCOPED_FILES]
  for (const dir of SCOPED_DIRS) {
    collectFiles(dir, files)
  }

  const unique = [...new Set(files)].sort()
  let touched = 0
  const allUnresolved = []

  for (const filePath of unique) {
    if (filePath.endsWith('normalize-esm-import-extensions.mjs')) {
      continue
    }
    let content = readFileSync(filePath, 'utf8')
    const alias = patchAliasImports(content, filePath)
    content = alias.content
    let fileChanged = alias.changed

    const result = rewriteSpecifiers(content, filePath)
    content = result.content
    fileChanged = fileChanged || result.changed
    if (result.unresolved.length > 0) {
      allUnresolved.push({ file: relative(FRONTEND, filePath), specs: result.unresolved })
    }

    if (fileChanged) {
      writeFileSync(filePath, content, 'utf8')
      touched += 1
      console.log('updated', relative(FRONTEND, filePath))
    }
  }

  console.log(`\nDone. ${touched} file(s) updated.`)
  if (allUnresolved.length > 0) {
    console.warn('\nUnresolved relative imports (manual fix may be needed):')
    for (const row of allUnresolved) {
      console.warn(`  ${row.file}: ${row.specs.join(', ')}`)
    }
    process.exitCode = 1
  }
}

main()
