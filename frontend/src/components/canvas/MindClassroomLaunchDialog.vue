<script setup lang="ts">
/**
 * 思维讲堂 settings dialog. Opened from the Teaching tab; the corner tutor stays unmounted.
 */
import { storeToRefs } from 'pinia'

import { ElDialog } from 'element-plus'

import AiGenerateGlassHero from '@/components/canvas/AiGenerateGlassHero.vue'
import MindClassroomLaunchContent from '@/components/canvas/MindClassroomLaunchContent.vue'
import '@/components/canvas/aiGenerateGlass.css'
import { useEventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useMindClassroomStore } from '@/stores'

const { t } = useLanguage()
const notify = useNotifications()
const eventBus = useEventBus('MindClassroomLaunchDialog')
const classroomStore = useMindClassroomStore()
const { modalOpen, jobError } = storeToRefs(classroomStore)

function handleModalClose(): void {
  classroomStore.closeModal()
}

eventBus.on('classroom:queue_result', (result) => {
  if (!result.ok) {
    if (result.reason === 'cancelled') return
    if (result.reason === 'failed') {
      notify.error(jobError.value || t('canvas.mindClassroom.lecture.queueFailed'))
      return
    }
    if (result.reason === 'unauthenticated') {
      notify.warningKey('canvas.mindClassroom.queue.loginRequired')
      return
    }
    notify.warning(
      result.reason === 'no_diagram'
        ? t('canvas.mindClassroom.lecture.needDiagram')
        : t('canvas.mindClassroom.lecture.emptySteps')
    )
    return
  }
  if (result.action === 'start' && result.phase === 'playing') {
    classroomStore.closeModal()
  }
})
</script>

<template>
  <ElDialog
    v-model="modalOpen"
    width="min(600px, 92vw)"
    top="12vh"
    append-to-body
    destroy-on-close
    :show-close="false"
    class="mc-classroom-dialog mm-canvas-upper-dialog ai-gen-shell ai-gen-shell--classroom"
    @close="handleModalClose"
  >
    <template #header>
      <AiGenerateGlassHero
        variant="classroom"
        @close="handleModalClose"
      />
    </template>
    <MindClassroomLaunchContent variant="modal" />
  </ElDialog>
</template>
