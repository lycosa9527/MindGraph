import { ref } from 'vue'

import {
  CLASSROOM_REMOTE_TOPICS_MAX,
  DEFAULT_CLASSROOM_REMOTE_TOPICS,
  normalizeClassroomRemoteTopic,
  readClassroomRemoteTopics,
  writeClassroomRemoteTopics,
} from '@/canvas-ribbon/classroomRemoteTopics'

export function useClassroomRemoteTopics() {
  const topics = ref<string[]>(readClassroomRemoteTopics())
  const editing = ref(false)
  const draft = ref('')

  function persist(): void {
    writeClassroomRemoteTopics(topics.value)
  }

  function setEditing(next: boolean): void {
    editing.value = next
    if (!next) {
      draft.value = ''
    }
  }

  function updateTopic(index: number, value: string): void {
    const next = normalizeClassroomRemoteTopic(value)
    if (index < 0 || index >= topics.value.length) {
      return
    }
    if (next.length === 0) {
      return
    }
    const copy = [...topics.value]
    copy[index] = next
    topics.value = copy
    persist()
  }

  function removeTopic(index: number): void {
    if (index < 0 || index >= topics.value.length) {
      return
    }
    topics.value = topics.value.filter((_, i) => i !== index)
    persist()
  }

  function addTopic(value?: string): boolean {
    const next = normalizeClassroomRemoteTopic(value ?? draft.value)
    if (next.length === 0 || topics.value.length >= CLASSROOM_REMOTE_TOPICS_MAX) {
      return false
    }
    topics.value = [...topics.value, next]
    draft.value = ''
    persist()
    return true
  }

  function resetDefaults(): void {
    topics.value = [...DEFAULT_CLASSROOM_REMOTE_TOPICS]
    persist()
  }

  return {
    topics,
    editing,
    draft,
    setEditing,
    updateTopic,
    removeTopic,
    addTopic,
    resetDefaults,
  }
}
