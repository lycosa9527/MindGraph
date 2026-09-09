import { createApp, h } from 'vue'

import { describe, expect, it } from 'vitest'

import EmojiPicker from '@/components/workshop-chat/EmojiPicker.vue'
import { EMOJI_PICKER_CATEGORIES, orderEmojiCategories } from '@/config/emojiPickerCategories'

function mountPicker(props: Record<string, unknown> = {}) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = createApp({
    render() {
      return h(EmojiPicker, props)
    },
  })
  app.mount(host)
  return { app, host }
}

describe('emojiPickerCategories', () => {
  it('keeps default order when no lead category is set', () => {
    const keys = orderEmojiCategories(EMOJI_PICKER_CATEGORIES).map((category) => category.key)
    expect(keys).toEqual(['smileys', 'gestures', 'hearts', 'objects'])
  })

  it('moves objects to the first tab when led for canvas insert', () => {
    const keys = orderEmojiCategories(EMOJI_PICKER_CATEGORIES, 'objects').map(
      (category) => category.key
    )
    expect(keys).toEqual(['objects', 'smileys', 'gestures', 'hearts'])
  })

  it('includes office and education emojis on the objects tab', () => {
    const objects = EMOJI_PICKER_CATEGORIES.find((category) => category.key === 'objects')
    expect(objects?.emojis.slice(0, 20).map((emoji) => emoji.code)).toEqual([
      '📚',
      '📖',
      '📓',
      '🎓',
      '✏️',
      '🖊️',
      '📏',
      '📐',
      '🧮',
      '🏫',
      '📊',
      '📈',
      '📋',
      '📁',
      '📅',
      '💻',
      '💼',
      '📧',
      '🎯',
      '🗒️',
    ])
  })
})

describe('EmojiPicker canvas insert mode', () => {
  it('keeps search for workshop chat', () => {
    const { app, host } = mountPicker()
    expect(host.querySelector('.emoji-picker__search')).not.toBeNull()
    expect(host.querySelector('.emoji-picker__tab--active')?.textContent?.trim()).toBe('😊')
    app.unmount()
    host.remove()
  })

  it('hides search and leads with objects for canvas insert', () => {
    const { app, host } = mountPicker({ hideSearch: true, leadCategory: 'objects' })
    expect(host.querySelector('.emoji-picker__search')).toBeNull()
    const tabs = [...host.querySelectorAll('.emoji-picker__tab')].map((tab) =>
      tab.textContent?.trim()
    )
    expect(tabs[0]).toBe('📎')
    expect(host.querySelector('.emoji-picker__tab--active')?.textContent?.trim()).toBe('📎')
    expect(host.textContent).toContain('📚')
    expect(host.textContent).toContain('🎓')
    app.unmount()
    host.remove()
  })
})
