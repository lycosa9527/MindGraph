import { computed } from 'vue'

import { PLACEHOLDER_TEXTS } from './constants'
import type { DiagramContext } from './types'

export function useTitleSlice(ctx: DiagramContext) {
  const { data, title, isUserEditedTitle } = ctx

  function getTopicNodeText(): string | null {
    const topicNode = data.value?.nodes?.find(
      (n) => n.type === 'topic' || n.type === 'center' || n.id === 'root'
    )
    if (!topicNode?.text) return null
    const text = topicNode.text.trim()
    if (PLACEHOLDER_TEXTS.includes(text)) return null
    return text
  }

  const effectiveTitle = computed(() => {
    if (isUserEditedTitle.value && title.value) {
      return title.value
    }
    const topicText = getTopicNodeText()
    if (topicText) {
      return topicText
    }
    return title.value
  })

  function setTitle(newTitle: string, userEdited: boolean = false): void {
    title.value = newTitle
    if (userEdited) {
      isUserEditedTitle.value = true
    }
  }

  function initTitle(defaultTitle: string): void {
    title.value = defaultTitle
    isUserEditedTitle.value = false
  }

  function resetTitle(): void {
    title.value = ''
    isUserEditedTitle.value = false
  }

  function shouldAutoUpdateTitle(): boolean {
    return !isUserEditedTitle.value
  }

  return {
    effectiveTitle,
    getTopicNodeText,
    setTitle,
    initTitle,
    resetTitle,
    shouldAutoUpdateTitle,
  }
}
