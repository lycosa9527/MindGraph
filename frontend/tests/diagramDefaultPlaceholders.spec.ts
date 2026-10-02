/**
 * Blank-diagram labels for the 32 Settings languages.
 * Slots must survive interpolation, and machine-translation leftovers
 * (Lenovo for 联想, leaked __MG_ tokens, the wrong language) must not ship.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { INTERFACE_LANGUAGE_PICKER_CODES } from '@/i18n/locales'

const PLACEHOLDER_KEYS = [
  'diagram.defaults.attributeN',
  'diagram.defaults.branchN',
  'diagram.defaults.bridgeItemAN',
  'diagram.defaults.bridgeItemBN',
  'diagram.defaults.categoryN',
  'diagram.defaults.causeN',
  'diagram.defaults.centralTopic',
  'diagram.defaults.childNM',
  'diagram.defaults.contextN',
  'diagram.defaults.effectN',
  'diagram.defaults.itemNM',
  'diagram.defaults.mainEvent',
  'diagram.defaults.partN',
  'diagram.defaults.process',
  'diagram.defaults.rootTopic',
  'diagram.defaults.stepN',
  'diagram.defaults.subpartNM',
  'diagram.defaults.substepNM',
  'diagram.defaults.topic',
  'diagram.defaults.topicA',
  'diagram.defaults.topicB',
  'diagram.doubleBubble.differenceAn',
  'diagram.doubleBubble.differenceBn',
  'diagram.doubleBubble.similarityN',
  'diagram.conceptMap.focusQuestionPrefix',
  'diagram.conceptMap.focusQuestionSuffix',
  'diagram.conceptMap.rootConcept',
  'diagram.conceptMap.topicRootRelationship',
  'diagram.labelNode.clickToSet',
  'diagram.editable.placeholder',
  'diagram.newContext',
] as const

/** Brand and token leaks that have shown up as node text. */
const FUNNY =
  /Lenovo|Леново|لينوفو|لنوو|__MG_|NovoLenovo|treten Sie ein|Memasuki|definitor|click to specify\.\./i

/** Simplified-Chinese leftovers that are wrong outside zh / zh-tw. */
const SIMPLIFIED_LEFTOVER = /联想|类别|步骤|子项|事物A|不同点|拆解维度|分类维度|点击設定/

function readCanvas(code: string): string {
  return readFileSync(resolve(__dirname, `../src/locales/messages/${code}/canvas.ts`), 'utf8')
}

function readPlaceholders(code: string): Record<string, string> {
  const text = readCanvas(code)
  const out: Record<string, string> = {}
  for (const key of PLACEHOLDER_KEYS) {
    const pattern = new RegExp(
      `^\\s*'${key.replace(/\./g, '\\.')}':\\s*(?:'((?:\\\\'|[^'])*)'|"((?:\\\\"|[^"])*)"),`,
      'm'
    )
    const match = pattern.exec(text)
    expect(match, `${code} ${key}`).toBeTruthy()
    const raw = match?.[1] ?? match?.[2] ?? ''
    out[key] = raw.replace(/\\'/g, "'").replace(/\\"/g, '"')
  }
  return out
}

function slots(value: string): string[] {
  return [...value.matchAll(/\{([^{}]+)\}/g)].map((match) => match[1] ?? '')
}

function shown(value: string): string {
  return value.replaceAll('{n}', '1').replaceAll('{m}', '2')
}

describe('diagram default placeholders across picker locales', () => {
  const english = readPlaceholders('en')

  it('lists 32 interface languages', () => {
    expect(INTERFACE_LANGUAGE_PICKER_CODES).toHaveLength(32)
  })

  for (const code of INTERFACE_LANGUAGE_PICKER_CODES) {
    it(`${code} interpolates numbered labels and hides translation junk`, () => {
      const bundle = readPlaceholders(code)
      for (const key of PLACEHOLDER_KEYS) {
        const value = bundle[key] ?? ''
        expect(slots(value), `${code} ${key}`).toEqual(slots(english[key] ?? ''))
        expect(value, `${code} ${key}`).not.toMatch(FUNNY)
        if (code !== 'zh' && code !== 'zh-tw') {
          expect(value, `${code} ${key}`).not.toMatch(SIMPLIFIED_LEFTOVER)
        }
        const rendered = shown(value)
        expect(rendered, `${code} ${key}`).not.toMatch(/[{}]/)
        expect(rendered.trim().length, `${code} ${key}`).toBeGreaterThan(0)
      }
      const focus =
        (bundle['diagram.conceptMap.focusQuestionPrefix'] ?? '') +
        (bundle['diagram.conceptMap.focusQuestionSuffix'] ?? '')
      expect(focus, code).not.toMatch(/:[^\s]/)
    })
  }
})
