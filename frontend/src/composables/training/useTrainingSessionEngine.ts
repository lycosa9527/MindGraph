/**
 * Binds training:* bus commands to the Pinia session store.
 */
import { onUnmounted } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { useTrainingStore } from '@/stores/training'

const OWNER = 'TrainingSessionEngine'

export function useTrainingSessionEngine(): void {
  const { t } = useLanguage()
  const notify = useNotifications()
  const authStore = useAuthStore()
  const training = useTrainingStore()

  function myUserId(): number {
    return Number(authStore.user?.id)
  }

  function isForeignSession(): boolean {
    return (
      training.isActive &&
      training.snapshot.instructor_id != null &&
      training.snapshot.instructor_id !== myUserId()
    )
  }

  async function steer(work: () => Promise<void>): Promise<void> {
    try {
      await work()
    } catch {
      notify.error(t('training.steerFailed'))
    }
  }

  async function onStart(): Promise<void> {
    const code = await training.startSession()
    if (code === 'ok') return
    if (code === 'pick_org') {
      notify.warning(t('training.pickOrgFirst'))
      return
    }
    if (code === 'instructor_busy') {
      notify.warning(t('training.hostedElsewhere'))
      return
    }
    if (code === 'confirm_mismatch') {
      notify.warning(t('training.confirmMismatch'))
      return
    }
    if (code === 'org_busy') {
      notify.warning(t('training.takeoverHint'))
      return
    }
    notify.error(t('training.startFailed'))
  }

  async function onPlay(courseId: string): Promise<void> {
    if (training.selectedOrgId == null) {
      notify.warning(t('training.pickOrgFirst'))
      return
    }
    if (isForeignSession()) {
      notify.warning(t('training.takeoverHint'))
      return
    }
    if (!training.isActive) {
      await onStart()
      if (!training.isActive) return
    }
    await steer(() => training.playCourse(courseId))
  }

  eventBus.onWithOwner('training:start_requested', () => {
    void onStart()
  }, OWNER)
  eventBus.onWithOwner('training:play_requested', (payload) => {
    void onPlay(payload.courseId)
  }, OWNER)
  eventBus.onWithOwner('training:pause_requested', () => {
    void steer(() => training.pauseSession())
  }, OWNER)
  eventBus.onWithOwner('training:resume_requested', () => {
    void steer(() => training.resumeSession())
  }, OWNER)
  eventBus.onWithOwner('training:end_requested', () => {
    void steer(() => training.endSession())
  }, OWNER)
  eventBus.onWithOwner('training:takeover_requested', () => {
    void steer(() => training.takeoverSession())
  }, OWNER)
  eventBus.onWithOwner('training:step_requested', (payload) => {
    void steer(() => training.stepSession(payload.delta))
  }, OWNER)
  eventBus.onWithOwner('training:free_requested', (payload) => {
    const next = payload.free ?? !training.isFree
    void steer(() => training.freeSession(next))
  }, OWNER)
  eventBus.onWithOwner('training:select_org_requested', (payload) => {
    void training.selectOrg(payload.orgId)
  }, OWNER)
  eventBus.onWithOwner('training:search_orgs_requested', (payload) => {
    void training.loadOrgs(payload.query)
  }, OWNER)
  eventBus.onWithOwner('training:chip_selected', (payload) => {
    training.setPendingChip(payload.option)
  }, OWNER)
  eventBus.onWithOwner('training:roster_invalidate', () => {
    void training.fetchRoster()
  }, OWNER)

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner(OWNER)
  })
}
