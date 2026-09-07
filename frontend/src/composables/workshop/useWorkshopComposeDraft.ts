import { nextTick, ref, watch } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useRenderedMarkdown } from '@/composables/core/useRenderedMarkdown'
import { TRAINING_ROLES } from '@/config/trainingRoles'
import { type OrgMember, useWorkshopChatStore } from '@/stores/workshopChat'
import { apiUpload } from '@/utils/apiClient'
import { stripMindmateDiagramIdComments } from '@/utils/mindmateDiagramMeta'
import {
  type ComposeFormatType,
  applyComposeFormat,
  insertTextAtCursor,
} from '@/utils/workshopComposeFormat'
import { buildWorkshopRoleMarkdown, inlineWorkshopRoleMarkdown } from '@/utils/workshopRoleEmbed'

export function useWorkshopComposeDraft() {
  const { t } = useLanguage()
  const store = useWorkshopChatStore()

  const content = ref('')
  const isPreview = ref(false)
  const textareaRef = ref<HTMLTextAreaElement>()
  const fileInputRef = ref<HTMLInputElement>()
  const uploading = ref(false)
  const showEmojiPicker = ref(false)
  const showRolePicker = ref(false)
  const showDiagramPicker = ref(false)
  const showMentionPicker = ref(false)
  const mentionQuery = ref('')
  const mentionPickerResults = ref<OrgMember[]>([])

  const { html: previewHtml } = useRenderedMarkdown(() =>
    inlineWorkshopRoleMarkdown(stripMindmateDiagramIdComments(content.value))
  )

  let mentionFetchTimer: ReturnType<typeof setTimeout> | null = null

  function localMentionMatches(): OrgMember[] {
    const q = mentionQuery.value.trim().toLowerCase()
    return store.orgMembers
      .filter((member) => {
        const label = (member.name || `User ${member.id}`).toLowerCase()
        return label.includes(q)
      })
      .slice(0, 8)
  }

  watch(
    [mentionQuery, showMentionPicker],
    () => {
      if (!showMentionPicker.value) {
        mentionPickerResults.value = []
        return
      }
      if (mentionFetchTimer != null) {
        clearTimeout(mentionFetchTimer)
      }
      const raw = mentionQuery.value.trim()
      if (!raw) {
        mentionPickerResults.value = localMentionMatches()
        return
      }
      mentionFetchTimer = setTimeout(async () => {
        mentionFetchTimer = null
        mentionPickerResults.value = await store.searchOrgMembers(raw, 12)
      }, 200)
    },
    { flush: 'post' }
  )

  watch(
    () => store.orgMembers.length,
    () => {
      if (showMentionPicker.value && !mentionQuery.value.trim()) {
        mentionPickerResults.value = localMentionMatches()
      }
    }
  )

  function applyToTextarea(result: { text: string; start: number; end: number }): void {
    content.value = result.text
    nextTick(() => {
      const el = textareaRef.value
      if (!el) return
      el.focus()
      el.setSelectionRange(result.start, result.end)
    })
  }

  function syncMentionPicker(): void {
    const el = textareaRef.value
    if (!el) return
    const pos = el.selectionStart ?? 0
    const text = content.value
    let at = pos - 1
    while (at >= 0 && text.charAt(at) !== '@') {
      if (/\s/.test(text.charAt(at))) {
        showMentionPicker.value = false
        return
      }
      at -= 1
    }
    if (at < 0 || text.charAt(at) !== '@') {
      showMentionPicker.value = false
      return
    }
    if (at > 0 && !/\s/.test(text.charAt(at - 1))) {
      showMentionPicker.value = false
      return
    }
    mentionQuery.value = text.slice(at + 1, pos)
    showMentionPicker.value = true
  }

  function insertMentionUser(member: OrgMember): void {
    const el = textareaRef.value
    if (!el) return
    const pos = el.selectionStart ?? content.value.length
    const text = content.value
    let at = pos - 1
    while (at >= 0 && text.charAt(at) !== '@') {
      if (/\s/.test(text.charAt(at))) return
      at -= 1
    }
    if (at < 0 || text.charAt(at) !== '@') return
    if (at > 0 && !/\s/.test(text.charAt(at - 1))) return
    const rawName = member.name || `User ${member.id}`
    const safeName = rawName.replace(/\*/g, '').trim() || `User ${member.id}`
    const insert = `@**${safeName}**`
    content.value = text.slice(0, at) + insert + text.slice(pos)
    showMentionPicker.value = false
    nextTick(() => {
      el.focus()
      const caret = at + insert.length
      el.setSelectionRange(caret, caret)
    })
  }

  function handleFormat(type: ComposeFormatType): void {
    if (isPreview.value) return
    const el = textareaRef.value
    const start = el?.selectionStart ?? content.value.length
    const end = el?.selectionEnd ?? start
    applyToTextarea(applyComposeFormat(content.value, start, end, type))
  }

  function handleEmojiSelect(_name: string, code: string): void {
    showEmojiPicker.value = false
    const el = textareaRef.value
    const start = el?.selectionStart ?? content.value.length
    const end = el?.selectionEnd ?? start
    applyToTextarea(insertTextAtCursor(content.value, start, end, code))
  }

  function handleDiagramInsert(markdown: string): void {
    const el = textareaRef.value
    const start = el?.selectionStart ?? content.value.length
    const end = el?.selectionEnd ?? start
    const prefix = start > 0 && content.value.charAt(start - 1) !== '\n' ? '\n' : ''
    applyToTextarea(insertTextAtCursor(content.value, start, end, `${prefix}${markdown}\n`))
  }

  function handleRolePick(roleId: string): void {
    showRolePicker.value = false
    const role = TRAINING_ROLES.find((row) => row.id === roleId)
    const alt = role ? t(role.labelKey) : roleId
    const markdown = buildWorkshopRoleMarkdown(roleId, alt)
    const el = textareaRef.value
    const start = el?.selectionStart ?? content.value.length
    const end = el?.selectionEnd ?? start
    applyToTextarea(insertTextAtCursor(content.value, start, end, markdown))
  }

  function onEmojiPickerVisible(open: boolean): void {
    showEmojiPicker.value = open
    if (open) {
      showRolePicker.value = false
    }
  }

  function onRolePickerVisible(open: boolean): void {
    showRolePicker.value = open
    if (open) {
      showEmojiPicker.value = false
    }
  }

  function openDiagramPicker(): void {
    showEmojiPicker.value = false
    showRolePicker.value = false
    showDiagramPicker.value = true
  }

  function triggerFileUpload(): void {
    fileInputRef.value?.click()
  }

  async function handleFileChange(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return
    input.value = ''

    uploading.value = true
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await apiUpload('/api/chat/upload', formData)
      if (res.ok) {
        const data = (await res.json()) as { filename?: string; file_path?: string }
        if (!data.file_path) return
        const isImage = file.type.startsWith('image/')
        const mdLink = isImage
          ? `![${data.filename || file.name}](${data.file_path})`
          : `[${data.filename || file.name}](${data.file_path})`
        const el = textareaRef.value
        const start = el?.selectionStart ?? content.value.length
        const end = el?.selectionEnd ?? start
        applyToTextarea(insertTextAtCursor(content.value, start, end, mdLink))
      }
    } catch (err) {
      console.error('[WorkshopComposeDraft] upload failed:', err)
    } finally {
      uploading.value = false
    }
  }

  function onTextareaInput(): void {
    syncMentionPicker()
  }

  function focusTextarea(): void {
    nextTick(() => {
      const el = textareaRef.value
      if (!el) return
      el.focus()
      const end = el.value.length
      el.setSelectionRange(end, end)
    })
  }

  return {
    content,
    isPreview,
    previewHtml,
    textareaRef,
    fileInputRef,
    uploading,
    showEmojiPicker,
    showRolePicker,
    showDiagramPicker,
    showMentionPicker,
    mentionPickerResults,
    applyToTextarea,
    syncMentionPicker,
    insertMentionUser,
    handleFormat,
    handleEmojiSelect,
    handleDiagramInsert,
    handleRolePick,
    onEmojiPickerVisible,
    onRolePickerVisible,
    openDiagramPicker,
    triggerFileUpload,
    handleFileChange,
    onTextareaInput,
    focusTextarea,
  }
}
