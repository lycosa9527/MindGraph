import { mkdirSync, writeFileSync } from 'fs'
import { dirname } from 'path'

import {
  ECHOES_CATEGORIES,
  ECHOES_REF,
  ECHOES_REPO,
  VENDOR_ECHOES_DIR,
  VENDOR_LOCK_PATH,
  VENDOR_WISDOM_EN,
  VENDOR_WISDOM_ZH,
  WISDOM_QUOTES_REF,
  WISDOM_QUOTES_REPO,
  rawGitHubUrl,
} from './config.ts'

async function download(url: string): Promise<string> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to download ${url}: ${response.status} ${response.statusText}`)
  }
  return response.text()
}

export async function refreshWisdomQuotesVendor(): Promise<void> {
  mkdirSync(dirname(VENDOR_WISDOM_ZH), { recursive: true })

  const wisdomZhUrl = rawGitHubUrl(WISDOM_QUOTES_REPO, WISDOM_QUOTES_REF, 'chinese_sentences.json')
  const wisdomEnUrl = rawGitHubUrl(WISDOM_QUOTES_REPO, WISDOM_QUOTES_REF, 'quotes_database.json')

  console.log(`Downloading ${wisdomZhUrl}`)
  writeFileSync(VENDOR_WISDOM_ZH, await download(wisdomZhUrl), 'utf8')

  console.log(`Downloading ${wisdomEnUrl}`)
  writeFileSync(VENDOR_WISDOM_EN, await download(wisdomEnUrl), 'utf8')
}

export async function refreshEchoesVendorTs(): Promise<void> {
  mkdirSync(VENDOR_ECHOES_DIR, { recursive: true })

  for (const category of ECHOES_CATEGORIES) {
    const url = rawGitHubUrl(ECHOES_REPO, ECHOES_REF, `src/lib/data/${category}.ts`)
    const target = `${VENDOR_ECHOES_DIR}/${category}.ts`
    console.log(`Downloading ${url}`)
    writeFileSync(target, await download(url), 'utf8')
  }
}

export async function refreshVendorSnapshots(
  options: {
    wisdom?: boolean
    echoes?: boolean
  } = {}
): Promise<void> {
  const refreshWisdom = options.wisdom ?? true
  const refreshEchoes = options.echoes ?? false

  if (refreshWisdom) {
    await refreshWisdomQuotesVendor()
  }
  if (refreshEchoes) {
    await refreshEchoesVendorTs()
  }

  writeFileSync(
    VENDOR_LOCK_PATH,
    `${JSON.stringify(
      {
        'wisdom-quotes': { repo: WISDOM_QUOTES_REPO, ref: WISDOM_QUOTES_REF },
        echoes: {
          repo: ECHOES_REPO,
          ref: ECHOES_REF,
          note: 'Use --refresh-echoes + --extract-echoes to refresh frozen JSON; normal import uses extracted/ only.',
        },
        refreshedAt: new Date().toISOString(),
      },
      null,
      2
    )}\n`,
    'utf8'
  )

  console.log('Vendor snapshots updated.')
}
