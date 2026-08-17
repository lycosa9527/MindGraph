/**
 * Global toast when 思维讲堂 becomes playable (MindMate or any other canvas chrome).
 */
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useMindClassroomStore } from '@/stores'

export function bindClassroomReadyToast(owner: string): void {
  const { t } = useLanguage()
  const notify = useNotifications()
  const classroomStore = useMindClassroomStore()
  eventBus.onWithOwner(
    'classroom:ready',
    () => {
      if (classroomStore.isLecturing) return
      notify.showNotification({
        title: t('canvas.mindClassroom.title'),
        message: t('canvas.mindClassroom.queue.readyHint'),
        type: 'success',
        duration: 6000,
        onClick: () => {
          classroomStore.openModal()
        },
      })
    },
    owner
  )
}
