/**
 * App-lifetime teaching-design Word export.
 * Fetch and download stay alive after leaving the MindMate page.
 */
import { ref } from 'vue'

import { defineStore } from 'pinia'

import { notify } from '@/composables/core/notifications'
import { i18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import type { MindMateMessage } from '@/stores/mindmateActiveThread'
import {
  downloadTeachingDesignDocx,
  teachingDesignExportFailI18nKey,
} from '@/utils/exportTeachingDesignDocx'

const STARTED_TOAST_MS = 6000
const RESULT_TOAST_MS = 6000

function translate(key: string): string {
  return i18n.global.t(key) as string
}

export const useTeachingDesignExportStore = defineStore('teachingDesignExport', () => {
  const exportingMessageId = ref<string | null>(null)

  async function exportAssistantMessage(
    message: MindMateMessage,
    userPrompt?: string
  ): Promise<void> {
    const authStore = useAuthStore()
    if (!authStore.isAuthenticated) {
      notify.error(translate('mindmate.openCanvasLoginRequired'))
      return
    }
    if (exportingMessageId.value) {
      return
    }
    exportingMessageId.value = message.id
    notify.info(translate('mindmate.exportWordTemplateStarted'), STARTED_TOAST_MS)
    try {
      await downloadTeachingDesignDocx({
        assistantMarkdown: message.content,
        replyKind: message.replyKind,
        userPrompt,
      })
      notify.success(translate('mindmate.exportWordTemplateOk'), RESULT_TOAST_MS)
    } catch (error) {
      notify.error(translate(teachingDesignExportFailI18nKey(error)), RESULT_TOAST_MS)
    } finally {
      exportingMessageId.value = null
    }
  }

  return { exportingMessageId, exportAssistantMessage }
})
