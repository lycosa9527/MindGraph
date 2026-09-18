/**
 * Google Translate batch helper (google-translate-api-x).
 * Call from the Windows host — WSL cannot reach Google.
 */
import translate from 'google-translate-api-x'

import { PLACEHOLDER_RE } from './keepFill.ts'

export function googleToForLocale(code: string, htmlLang: string): string {
  const h = htmlLang.toLowerCase()
  if (h === 'fil' || code === 'tl') {
    return 'tl'
  }
  if (code === 'pt') {
    return 'pt'
  }
  const seg = htmlLang.split('-')[0]
  if (seg.toLowerCase() === 'fil') {
    return 'tl'
  }
  return seg
}

export function protectPlaceholders(s: string): { text: string; tokens: string[] } {
  const tokens: string[] = []
  let i = 0
  const text = s.replace(PLACEHOLDER_RE, (m) => {
    tokens.push(m)
    return `__MG_${i++}__`
  })
  return { text, tokens }
}

export function restorePlaceholders(s: string, tokens: string[]): string {
  let out = s
  for (let i = 0; i < tokens.length; i++) {
    out = out.replace(`__MG_${i}__`, tokens[i])
  }
  return out
}

const BATCH_TIMEOUT_MS = 40_000
const CHUNK_SIZE = 12

async function sleep(ms: number): Promise<void> {
  await new Promise((r) => {
    setTimeout(r, ms)
  })
}

function withTimeout<T>(work: Promise<T>, ms: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(`translate timeout ${ms}ms`))
    }, ms)
    work.then(
      (value) => {
        clearTimeout(timer)
        resolve(value)
      },
      (err: unknown) => {
        clearTimeout(timer)
        reject(err)
      }
    )
  })
}

export async function translateBatch(texts: string[], to: string): Promise<string[]> {
  if (texts.length === 0) {
    return []
  }
  const prepared = texts.map((t) => protectPlaceholders(t))
  const out: string[] = []
  for (let c = 0; c < prepared.length; c += CHUNK_SIZE) {
    const slice = prepared.slice(c, c + CHUNK_SIZE)
    const inputs = slice.map((p) => p.text)
    const end = c + slice.length
    console.log(`    ${to} ${c + 1}-${end}/${prepared.length}`)
    let attempt = 0
    let ok = false
    let lastErr: unknown = null
    while (attempt < 5 && !ok) {
      try {
        const res = await withTimeout(
          translate(inputs, {
            from: 'zh-CN',
            to,
            forceTo: true,
            forceBatch: true,
          }),
          BATCH_TIMEOUT_MS
        )
        const arr = Array.isArray(res) ? res : [res]
        for (let i = 0; i < slice.length; i++) {
          const raw = (arr[i] as { text?: string } | undefined)?.text ?? ''
          out.push(restorePlaceholders(raw, slice[i].tokens))
        }
        ok = true
      } catch (err) {
        lastErr = err
        attempt += 1
        console.warn(`    ${to} retry ${attempt}/5 at ${c + 1}: ${String(err)}`)
        await sleep(2000 * attempt)
      }
    }
    if (!ok) {
      console.error(`batch failed (${to}) at ${c}`, lastErr)
      for (let i = 0; i < slice.length; i++) {
        out.push('')
      }
    }
    await sleep(400)
  }
  return out
}
