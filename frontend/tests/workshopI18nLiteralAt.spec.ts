import { createPinia, setActivePinia } from 'pinia'

import { baseCompile } from '@intlify/message-compiler'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n, loadLocaleMessages } from '@/i18n'
import { resolveBilingual } from '@/i18n/resolveBilingual'
import { translateForUiLocale } from '@/i18n/translateForUiLocale'
import deAdmin from '@/locales/messages/de/admin'
import enMessages from '@/locales/messages/en'
import esCanvas from '@/locales/messages/es/canvas'
import { useUIStore } from '@/stores/ui'

type CatalogModule = Record<string, unknown>

const catalogs = import.meta.glob<CatalogModule>(
  ['../src/locales/messages/*/*.ts', '!../src/locales/messages/*/index.ts'],
  { eager: true }
)

function renderMessage(source: string): string {
  const { code } = baseCompile(source, {
    onError(err) {
      throw err
    },
  })
  const fn = new Function(`return ${code}`)() as (ctx: {
    normalize: (parts: readonly unknown[]) => string
  }) => string
  return fn({
    normalize: (parts) => parts.map((part) => (typeof part === 'string' ? part : '')).join(''),
  })
}

function assertMessageCompiles(source: string): void {
  baseCompile(source, {
    onError(err) {
      throw err
    },
  })
}

function collectStrings(value: unknown, keyPath: string, out: Array<[string, string]>): void {
  if (typeof value === 'string') {
    out.push([keyPath, value])
    return
  }
  if (value == null || typeof value !== 'object') return
  for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
    collectStrings(child, keyPath ? `${keyPath}.${key}` : key, out)
  }
}

describe('workshop messages with a literal @', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
  })

  it('compiles every UI catalog string', () => {
    const failures: string[] = []
    let checked = 0
    for (const [path, mod] of Object.entries(catalogs)) {
      const strings: Array<[string, string]> = []
      collectStrings(mod, '', strings)
      for (const [key, value] of strings) {
        checked += 1
        try {
          assertMessageCompiles(value)
        } catch (err) {
          const message = err instanceof Error ? err.message : String(err)
          failures.push(`${path} ${key}: ${message}`)
        }
      }
    }
    expect(checked).toBeGreaterThan(1000)
    expect(failures).toEqual([])
  })

  it('shows a literal @ on the workshop lines that used to crash', async () => {
    await loadLocaleMessages('zh')
    const welcome = translateForUiLocale('workshop.welcomeMessagesBody', 'zh')
    expect(welcome).toContain('回复、@同事、附件')
    expect(welcome).not.toContain("{'@'}")
    const roadmap = translateForUiLocale('workshop.phase2RoadmapGroupsAlerts', 'zh')
    expect(roadmap).toContain('@群组')
    expect(roadmap).not.toContain("{'@'}")
    const roadmapEn = translateForUiLocale('workshop.phase2RoadmapGroupsAlerts', 'en')
    expect(roadmapEn).toContain('@group')
    expect(roadmapEn).not.toContain("{'@'}")
    expect(translateForUiLocale('mindmate.collabInputPlaceholder', 'zh')).toContain('@MindMate')
    expect(translateForUiLocale('admin.emailPlaceholder', 'zh')).toBe('name@example.com')

    setActivePinia(createPinia())
    const ui = useUIStore()
    ui.language = 'zh'
    ui.bilingualUiEnabled = false
    const copy = resolveBilingual('workshop.welcomeMessagesBody')
    expect(copy.primary).toContain('回复、@同事、附件')
    expect(copy.secondary).toBeNull()
    expect(renderMessage(enMessages['admin.mindbot.difyInputsJsonHint'])).toContain(
      '\'"grade":"7"\''
    )
    expect(renderMessage(deAdmin['admin.mindbot.difyInputsJsonHint'])).toContain('\'"grade":"7"\'')
    expect(renderMessage(esCanvas['canvas.toolbar.mathKeyboardEqEuler'])).toBe('e^{iθ}')
  })

  it('returns the key when a message has an unescaped @', () => {
    i18n.global.mergeLocaleMessage('en', { 'test.rawAt': 'hello @world' })
    try {
      expect(translateForUiLocale('test.rawAt', 'en')).toBe('test.rawAt')
    } finally {
      i18n.global.setLocaleMessage('en', { ...enMessages })
    }
  })
})
