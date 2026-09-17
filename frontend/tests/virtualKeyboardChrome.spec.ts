import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { afterEach, describe, expect, it } from 'vitest'

import {
  isEditableTextField,
  isVirtualKeyboardChromeElement,
  isVirtualKeyboardChromeEvent,
  isVirtualKeyboardPanelOpen,
} from '@/utils/virtualKeyboardChrome'
import {
  nodeInlineEditFieldId,
  virtualKeyboardButtonToReplaceInsert,
} from '@/utils/virtualKeyboardTyping'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function readSrc(rel: string): string {
  return readFileSync(resolve(root, rel), 'utf8')
}

describe('virtual keyboard chrome vs inline edit', () => {
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('treats keyboard panel, keys, and status toggle as chrome', () => {
    document.body.innerHTML = `
      <div class="virtual-keyboard-dock" aria-hidden="false">
        <div class="virtual-keyboard-panel">
          <button data-virtual-keyboard-chrome id="ime">IME</button>
          <div class="simple-keyboard-host">
            <div class="simple-keyboard"><button id="key" class="hg-button">a</button></div>
          </div>
        </div>
      </div>
      <button data-virtual-keyboard-chrome id="status-toggle">kb</button>
      <input id="node-edit" />
    `
    expect(isVirtualKeyboardChromeElement(document.getElementById('key'))).toBe(true)
    expect(isVirtualKeyboardChromeElement(document.getElementById('ime'))).toBe(true)
    expect(isVirtualKeyboardChromeElement(document.getElementById('status-toggle'))).toBe(true)
    expect(isVirtualKeyboardChromeElement(document.getElementById('node-edit'))).toBe(false)
    const ev = new Event('pointerdown', { bubbles: true })
    document.getElementById('key')?.dispatchEvent(ev)
    expect(isVirtualKeyboardChromeEvent(ev)).toBe(true)
  })

  it('reports the teleported dock open only when aria-hidden is not true', () => {
    document.body.innerHTML = `<div class="virtual-keyboard-dock" aria-hidden="true"></div>`
    expect(isVirtualKeyboardPanelOpen()).toBe(false)
    const dock = document.querySelector('.virtual-keyboard-dock')
    dock?.setAttribute('aria-hidden', 'false')
    expect(isVirtualKeyboardPanelOpen()).toBe(true)
  })

  it('accepts only editable input/textarea targets', () => {
    const input = document.createElement('input')
    const ro = document.createElement('input')
    ro.readOnly = true
    const area = document.createElement('textarea')
    expect(isEditableTextField(input)).toBe(true)
    expect(isEditableTextField(ro)).toBe(false)
    expect(isEditableTextField(area)).toBe(true)
    expect(isEditableTextField(document.createElement('button'))).toBe(false)
  })

  it('does not mount the panel on new-canvas chrome', () => {
    const toolbar = readSrc('src/components/canvas/CanvasToolbar.vue')
    const status = readSrc('src/canvas-ribbon/MindMapStatusBar.vue')
    expect(toolbar).toContain('v-if="!useMindMapV2"')
    expect(toolbar).toContain('CanvasVirtualKeyboardPanel')
    expect(status).not.toContain('toggleVirtualKeyboard')
    expect(status).not.toContain('data-virtual-keyboard-chrome')
  })

  it('wires the editor so outside-pointer cannot kill the input', () => {
    const editor = readSrc('src/components/diagram/nodes/InlineEditableText.vue')
    const panel = readSrc('src/components/canvas/CanvasVirtualKeyboardPanel.vue')
    expect(editor).toContain('isVirtualKeyboardChromeEvent')
    expect(editor).toContain('isVirtualKeyboardPanelOpen')
    expect(panel).toContain('lastEditableField')
    expect(panel).toContain('resolveTargetField')
    expect(panel).toContain('replaceContent: true')
    expect(panel).toContain('data-testid="virtual-keyboard-ime"')
    expect(panel).toContain('toggleSystemIme')
    expect(panel).toContain("loadLayoutForPreset('english')")
    expect(panel).not.toContain('getLayoutPresetKeyForUiLocale')
    expect(panel).not.toContain('MindGraphLanguageSwitcher')
    expect(editor).toContain('replaceContent')
    expect(editor).toContain('startEditing({ replaceContent: true })')
  })

  it('maps the first selected-node tap to a replacement insert', () => {
    expect(virtualKeyboardButtonToReplaceInsert('h')).toBe('h')
    expect(virtualKeyboardButtonToReplaceInsert('{space}')).toBe(' ')
    expect(virtualKeyboardButtonToReplaceInsert('{bksp}')).toBe('')
    expect(virtualKeyboardButtonToReplaceInsert('{shift}')).toBeNull()
    expect(virtualKeyboardButtonToReplaceInsert('{enter}')).toBeNull()
    expect(nodeInlineEditFieldId('topic')).toBe('diagram-inline-edit-topic')
  })
})
