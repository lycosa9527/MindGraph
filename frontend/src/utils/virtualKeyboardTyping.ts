import { isEditableTextField } from '@/utils/virtualKeyboardChrome'

export const NODE_INLINE_EDIT_FIELD_ID_PREFIX = 'diagram-inline-edit-'

export function nodeInlineEditFieldId(nodeId: string): string {
  return `${NODE_INLINE_EDIT_FIELD_ID_PREFIX}${nodeId}`
}

export function findNodeInlineEditField(
  nodeId: string
): HTMLInputElement | HTMLTextAreaElement | null {
  const el = document.getElementById(nodeInlineEditFieldId(nodeId))
  return isEditableTextField(el) ? el : null
}

export function isLiveNodeInlineEditField(el: EventTarget | null): boolean {
  return isEditableTextField(el) && el.id.startsWith(NODE_INLINE_EDIT_FIELD_ID_PREFIX)
}

/** First printable tap (or backspace) on a selected node replaces its label. */
export function virtualKeyboardButtonToReplaceInsert(button: string): string | null {
  if (button === '{space}') return ' '
  if (button === '{bksp}') return ''
  if (!button || button.startsWith('{')) return null
  return button
}

export async function waitForNodeInlineEditField(
  nodeId: string,
  timeoutMs = 400
): Promise<HTMLInputElement | HTMLTextAreaElement | null> {
  const started = Date.now()
  let found = findNodeInlineEditField(nodeId)
  while (!found && Date.now() - started < timeoutMs) {
    await new Promise<void>((resolve) => {
      window.requestAnimationFrame(() => resolve())
    })
    found = findNodeInlineEditField(nodeId)
  }
  return found
}
