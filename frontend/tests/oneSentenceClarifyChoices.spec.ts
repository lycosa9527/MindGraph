import { describe, expect, it } from 'vitest'

import {
  applyClarifyChoicesOnHydrate,
  choicesFromClarifyOptions,
  parseNumberedClarifyChoices,
  resolveMessageClarifyChoices,
} from '@/composables/canvasToolbar/oneSentenceClarifyChoices'
import type { OneSentenceChatMessage } from '@/stores/oneSentence'

function kitty(
  id: string,
  text: string,
  extras?: Partial<OneSentenceChatMessage>
): OneSentenceChatMessage {
  return { id, role: 'kitty', text, ...extras }
}

function user(id: string, text: string): OneSentenceChatMessage {
  return { id, role: 'user', text }
}

describe('parseNumberedClarifyChoices', () => {
  it('reads multiline 1) 2) 3) action offers', () => {
    expect(
      parseNumberedClarifyChoices('想怎么改这张图？\n1) 改主题\n2) 添加分支\n3) 自动补全这张图')
    ).toEqual([
      { index: 1, label: '改主题' },
      { index: 2, label: '添加分支' },
      { index: 3, label: '自动补全这张图' },
    ])
  })

  it('reads inline numbered options', () => {
    expect(parseNumberedClarifyChoices('1) 改主题 2) 添加分支 3) 自动补全这张图')).toEqual([
      { index: 1, label: '改主题' },
      { index: 2, label: '添加分支' },
      { index: 3, label: '自动补全这张图' },
    ])
  })

  it('ignores a single numbered line', () => {
    expect(parseNumberedClarifyChoices('已添加 1) 品牌 分支')).toEqual([])
  })
})

describe('choicesFromClarifyOptions', () => {
  it('keeps two or more labels', () => {
    expect(choicesFromClarifyOptions(['改主题', '添加分支'])).toEqual([
      { index: 1, label: '改主题' },
      { index: 2, label: '添加分支' },
    ])
  })

  it('drops a single label', () => {
    expect(choicesFromClarifyOptions(['only one'])).toEqual([])
  })
})

describe('applyClarifyChoicesOnHydrate', () => {
  it('keeps live chips when hydrate text differs but requestId matches', () => {
    const live = [
      user('u1', '帮我改图'),
      kitty('k1', '想怎么改这张图？', {
        requestId: 'req-1',
        choices: [
          { index: 1, label: '改主题' },
          { index: 2, label: '添加分支' },
        ],
      }),
    ]
    const hydrated = [
      user('turn-u', '帮我改图'),
      kitty(
        'turn-k',
        '想怎么改这张图？\n1) 改主题\n2) 添加分支\n请回复序号或选项内容。',
        { requestId: 'req-1' }
      ),
    ]
    const next = applyClarifyChoicesOnHydrate(hydrated, live)
    expect(next[1]?.choices).toEqual([
      { index: 1, label: '改主题' },
      { index: 2, label: '添加分支' },
    ])
  })

  it('re-parses numbered options on the last kitty turn after a text-only hydrate', () => {
    const live = [
      user('u1', '帮我改图'),
      kitty('k1', '想怎么改这张图？\n1) 改主题\n2) 添加分支', {
        choices: [
          { index: 1, label: '改主题' },
          { index: 2, label: '添加分支' },
        ],
      }),
    ]
    const hydrated = [
      user('turn-u', '帮我改图'),
      kitty('turn-k', '想怎么改这张图？\n1) 改主题\n2) 添加分支'),
    ]
    const next = applyClarifyChoicesOnHydrate(hydrated, live)
    expect(next[1]?.choices).toEqual([
      { index: 1, label: '改主题' },
      { index: 2, label: '添加分支' },
    ])
    expect(next[1]?.choicesConsumed).toBeUndefined()
  })

  it('does not revive chips when the user already answered the offer', () => {
    const live = [
      kitty('k1', '1) 改主题\n2) 添加分支', {
        requestId: 'live-req',
        choices: [
          { index: 1, label: '改主题' },
          { index: 2, label: '添加分支' },
        ],
        choicesConsumed: true,
      }),
      user('u2', '1'),
    ]
    const hydrated = [kitty('turn-k', '1) 改主题\n2) 添加分支', { requestId: 'hist-req' })]
    const next = applyClarifyChoicesOnHydrate(hydrated, live)
    expect(next[0]?.choices).toBeUndefined()
  })

  it('preserves consumed chips so they do not flash back', () => {
    const live = [
      kitty('k1', '1) 改主题\n2) 添加分支', {
        choices: [
          { index: 1, label: '改主题' },
          { index: 2, label: '添加分支' },
        ],
        choicesConsumed: true,
      }),
    ]
    const hydrated = [kitty('turn-k', '1) 改主题\n2) 添加分支')]
    const next = applyClarifyChoicesOnHydrate(hydrated, live)
    expect(next[0]?.choicesConsumed).toBe(true)
  })
})

describe('resolveMessageClarifyChoices', () => {
  it('parses the latest open kitty offer when stored choices were dropped', () => {
    const messages = [
      user('u1', '改图'),
      kitty('k1', '1) 改主题\n2) 添加分支\n3) 自动补全这张图'),
    ]
    expect(resolveMessageClarifyChoices(messages, messages[1])).toEqual([
      { index: 1, label: '改主题' },
      { index: 2, label: '添加分支' },
      { index: 3, label: '自动补全这张图' },
    ])
  })

  it('hides chips after the user already replied', () => {
    const messages = [
      kitty('k1', '1) 改主题\n2) 添加分支'),
      user('u1', '1'),
    ]
    expect(resolveMessageClarifyChoices(messages, messages[0])).toEqual([])
  })
})
