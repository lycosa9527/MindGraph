import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const frontendDir = resolve(scriptDir, '../..')

export const VENDOR_DIR = resolve(frontendDir, 'scripts/vendor/sidebar-quotes')
export const ASSETS_DIR = resolve(frontendDir, 'src/assets')
export const ATTRIBUTIONS_PATH = resolve(VENDOR_DIR, 'ATTRIBUTIONS.md')

export const WISDOM_QUOTES_REPO = 'snakeek/wisdom-quotes'
/** Pinned upstream commit for reproducible vendor snapshots. */
export const WISDOM_QUOTES_REF = 'bdd95ba6d7662fadfc95a4d7135a9f03972060cc'
export const ECHOES_REPO = 'Luminoid/echoes'
/** Pinned upstream commit for reproducible vendor snapshots. */
export const ECHOES_REF = '4cee3e9bb71ff24ec63f53a77381f5dee82da1ab'

export const MIN_ZH_QUOTES = 8000
export const MIN_EN_QUOTES = 1000
export const MIN_EXTRACTED_ECHOES_ZH = 1000
export const MIN_EXTRACTED_ECHOES_EN = 1000

export const ECHOES_CATEGORIES = [
  'activists',
  'architects',
  'artists',
  'cinema',
  'comedians',
  'designers',
  'economists',
  'essayists',
  'filmmakers',
  'historians',
  'musicians',
  'philosophers',
  'photographers',
  'playwrights',
  'poets',
  'psychologists',
  'scientists',
  'writers',
] as const

export function rawGitHubUrl(repo: string, ref: string, filePath: string): string {
  return `https://raw.githubusercontent.com/${repo}/${ref}/${filePath}`
}

export const VENDOR_WISDOM_ZH = resolve(VENDOR_DIR, 'wisdom-quotes/chinese_sentences.json')
export const VENDOR_WISDOM_EN = resolve(VENDOR_DIR, 'wisdom-quotes/quotes_database.json')
export const VENDOR_ECHOES_DIR = resolve(VENDOR_DIR, 'echoes')
export const EXTRACTED_ECHOES_DIR = resolve(VENDOR_DIR, 'extracted')
export const EXTRACTED_ECHOES_ZH = resolve(EXTRACTED_ECHOES_DIR, 'echoes-zh.json')
export const EXTRACTED_ECHOES_EN = resolve(EXTRACTED_ECHOES_DIR, 'echoes-en.json')
export const EXTRACTED_ECHOES_MANIFEST = resolve(
  EXTRACTED_ECHOES_DIR,
  'echoes-extract-manifest.json'
)
export const VENDOR_LOCK_PATH = resolve(VENDOR_DIR, 'VENDOR_LOCK.json')

export const OUTPUT_ZH = resolve(ASSETS_DIR, 'sidebar-quotes-zh.json')
export const OUTPUT_EN = resolve(ASSETS_DIR, 'sidebar-quotes-en.json')
