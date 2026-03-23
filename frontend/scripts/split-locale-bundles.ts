/**
 * One-off / maintenance: split monolithic locale default export into namespace files.
 * Run from frontend/: npx tsx scripts/split-locale-bundles.ts
 */
import * as fs from 'node:fs'
import * as path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

import az from '../src/locales/messages/az'
import en from '../src/locales/messages/en'
import zh from '../src/locales/messages/zh'

type LocaleMessages = Record<string, string>

const LOCALES = { zh, en, az } as const

/** Map first path segment of i18n key to bundle filename (without .ts). */
function bundleForKey(key: string): string {
  const segment = key.split('.')[0]
  switch (segment) {
    case 'common':
    case 'app':
    case 'settings':
    case 'demo':
    case 'publicDashboard':
    case 'askOnce':
    case 'askonce':
    case 'diagramTemplate':
    case 'diagramTemplates':
      return 'common'
    case 'mindmate':
    case 'panels':
    case 'panel':
    case 'nodePalette':
    case 'focusQuestion':
    case 'rootConceptModal':
    case 'conceptMapPicker':
    case 'aiModel':
    case 'autoComplete':
      return 'mindmate'
    case 'canvas':
    case 'canvasPage':
    case 'editor':
    case 'flowMap':
    case 'braceMap':
    case 'conceptMap':
    case 'diagram':
    case 'mindgraphLanding':
    case 'landing':
      return 'canvas'
    case 'workshop':
    case 'workshopCanvas':
    case 'collab':
      return 'workshop'
    case 'admin':
    case 'teacher':
      return 'admin'
    case 'knowledge':
    case 'knowledgeSpace':
    case 'rag':
    case 'chunkTest':
    case 'chunkTestResults':
      return 'knowledge'
    case 'community':
    case 'library':
    case 'libraryViewer':
    case 'debateverse':
      return 'community'
    case 'sidebar':
      return 'sidebar'
    case 'auth':
      return 'auth'
    case 'notification':
      return 'notification'
    default:
      throw new Error(`Unhandled key prefix for "${key}" (segment: ${segment})`)
  }
}

function splitMessages(messages: LocaleMessages): Map<string, LocaleMessages> {
  const buckets = new Map<string, LocaleMessages>()
  for (const key of Object.keys(messages).sort()) {
    const bundle = bundleForKey(key)
    if (!buckets.has(bundle)) {
      buckets.set(bundle, {})
    }
    const b = buckets.get(bundle)
    if (b) {
      b[key] = messages[key]
    }
  }
  return buckets
}

function stringifyBundle(obj: LocaleMessages, localeLabel: string, bundleName: string): string {
  const keys = Object.keys(obj).sort()
  const lines = keys.map((k) => {
    const v = obj[k]
    return `    ${JSON.stringify(k)}: ${JSON.stringify(v)},`
  })
  return `/** ${localeLabel} — ${bundleName} */\nexport default {\n${lines.join('\n')}\n} as const\n`
}

const bundles = ['common', 'mindmate', 'canvas', 'workshop', 'admin', 'knowledge', 'community', 'sidebar', 'auth', 'notification'] as const

function main(): void {
  const root = path.join(__dirname, '..', 'src', 'locales', 'messages')
  for (const locale of ['zh', 'en', 'az'] as const) {
    const messages = LOCALES[locale] as LocaleMessages
    const byBundle = splitMessages(messages)
    const localeDir = path.join(root, locale)
    fs.mkdirSync(localeDir, { recursive: true })
    for (const name of bundles) {
      const part = byBundle.get(name)
      if (!part) {
        throw new Error(`Missing bundle ${name} for ${locale}`)
      }
      const filePath = path.join(localeDir, `${name}.ts`)
      const label = locale === 'zh' ? 'Chinese UI' : locale === 'en' ? 'English UI' : 'Azerbaijani UI'
      fs.writeFileSync(filePath, stringifyBundle(part, label, name), 'utf8')
    }
    const indexPath = path.join(localeDir, 'index.ts')
    const imports = bundles.map((b) => `import ${b} from './${b}'`).join('\n')
    const spreads = bundles.map((b) => `  ...${b}`).join(',\n')
    const indexContent = `/**\n * ${locale} UI messages — merged namespace bundles.\n */\n${imports}\n\nexport default {\n${spreads},\n} as const\n`
    fs.writeFileSync(indexPath, indexContent, 'utf8')
  }

  for (const locale of ['zh', 'en', 'az'] as const) {
    const legacyPath = path.join(root, `${locale}.ts`)
    const indexContent = `/**\n * ${locale} UI messages — re-export merged bundles.\n */\nexport { default } from './${locale}/index'\n`
    fs.writeFileSync(legacyPath, indexContent, 'utf8')
  }

  console.log('Wrote locale bundles under src/locales/messages/{zh,en,az}/')
}

main()
