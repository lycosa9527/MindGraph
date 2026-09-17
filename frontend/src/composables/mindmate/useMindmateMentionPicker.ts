/**
 * @mention picker for MindMate seminar composer (agent + org contacts).
 */
import { nextTick, ref, type Ref } from 'vue'

import {
  type MindmateMentionCandidate,
  filterMentionCandidates,
  findMentionQueryAtCaret,
  insertMentionToken,
} from '@/utils/mindmateMention'

export function useMindmateMentionPicker(options: {
  text: () => string
  setText: (value: string) => void
  textarea: () => HTMLTextAreaElement | null
  candidates: () => readonly MindmateMentionCandidate[]
}) {
  const showMentionPicker = ref(false)
  const mentionPickerResults: Ref<MindmateMentionCandidate[]> = ref([])

  function caretPosition(): number {
    const el = options.textarea()
    return el?.selectionStart ?? options.text().length
  }

  function syncMentionPicker(): void {
    const found = findMentionQueryAtCaret(options.text(), caretPosition())
    if (!found) {
      showMentionPicker.value = false
      mentionPickerResults.value = []
      return
    }
    mentionPickerResults.value = filterMentionCandidates(options.candidates(), found.query)
    showMentionPicker.value = mentionPickerResults.value.length > 0
  }

  function insertMention(candidate: MindmateMentionCandidate): void {
    const el = options.textarea()
    const caret = caretPosition()
    const next = insertMentionToken(options.text(), caret, candidate.name)
    options.setText(next.text)
    showMentionPicker.value = false
    mentionPickerResults.value = []
    void nextTick(() => {
      if (!el) {
        return
      }
      el.focus()
      el.setSelectionRange(next.caret, next.caret)
    })
  }

  function dismissMentionPicker(): void {
    showMentionPicker.value = false
  }

  return {
    showMentionPicker,
    mentionPickerResults,
    syncMentionPicker,
    insertMention,
    dismissMentionPicker,
  }
}
