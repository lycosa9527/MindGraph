/**
 * Binds training:* bus commands to the Pinia session store.
 */
import { onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage, useNotifications } from '@/composables'
import { applyTrainingNavigate } from '@/composables/training/applyTrainingSnapshot'
import { applyTrainingUiTarget } from '@/composables/training/applyTrainingUiTarget'
import { useAuthStore } from '@/stores/auth'
import { useTrainingStore } from '@/stores/training'

const OWNER = 'TrainingSessionEngine'

export function useTrainingSessionEngine(): void {
  const { t } = useLanguage()
  const notify = useNotifications()
  const authStore = useAuthStore()
  const training = useTrainingStore()
  const router = useRouter()
  const route = useRoute()

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

  function hostName(): string {
    return (training.snapshot.instructor_name || '').trim() || '—'
  }

  async function followStage(): Promise<void> {
    const snap = training.snapshot
    if (!snap.course_id || (!snap.step && !snap.diagram_type)) return
    const moved = await applyTrainingNavigate(router, route.path, snap)
    const step = snap.step
    if (moved || step?.modal_key || step?.focus_key) {
      await applyTrainingUiTarget({
        modalKey: step?.modal_key,
        focusKey: step?.focus_key,
      })
    }
    training.markApplied(snap.seq)
  }

  async function steer(work: () => Promise<void>): Promise<void> {
    try {
      await work()
    } catch {
      notify.error(t('training.steerFailed'))
    }
  }

  async function steerThenFollow(work: () => Promise<void>): Promise<void> {
    await steer(async () => {
      await work()
      await followStage()
    })
  }

  async function announceRoomReady(): Promise<void> {
    await training.refreshReady()
    notify.success(t('training.moduleReady'))
  }

  async function onStart(): Promise<void> {
    if (training.isActive && !isForeignSession()) {
      await announceRoomReady()
      return
    }
    const code = await training.startSession()
    if (code === 'ok') {
      await announceRoomReady()
      return
    }
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
      if (training.isActive && !isForeignSession()) {
        await announceRoomReady()
        return
      }
      notify.warning(t('training.takeoverHint', { name: hostName() }))
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
      notify.warning(t('training.takeoverHint', { name: hostName() }))
      return
    }
    if (!training.isActive) {
      notify.warning(t('training.startFirst'))
      return
    }
    await steerThenFollow(() => training.playCourse(courseId))
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
    void steerThenFollow(() => training.resumeSession())
  }, OWNER)
  eventBus.onWithOwner('training:end_requested', () => {
    void steer(() => training.endSession())
  }, OWNER)
  eventBus.onWithOwner('training:takeover_requested', () => {
    void steerThenFollow(() => training.takeoverSession())
  }, OWNER)
  eventBus.onWithOwner('training:step_requested', (payload) => {
    void steerThenFollow(() => training.stepSession(payload.delta))
  }, OWNER)
  eventBus.onWithOwner('training:free_requested', (payload) => {
    const next = payload.free ?? !training.isFree
    if (next) {
      void steer(() => training.freeSession(true))
      return
    }
    void steerThenFollow(() => training.freeSession(false))
  }, OWNER)
  eventBus.onWithOwner('training:select_org_requested', (payload) => {
    void training.selectOrg(payload.orgId).then((code) => {
      if (code === 'locked') notify.warning(t('training.hostedElsewhere'))
    })
  }, OWNER)
  eventBus.onWithOwner('training:search_orgs_requested', (payload) => {
    void training.loadOrgs(payload.query)
  }, OWNER)
  eventBus.onWithOwner('training:chip_selected', (payload) => {
    training.setPendingChip(payload.option)
  }, OWNER)
  eventBus.onWithOwner('training:roster_invalidate', () => {
    if (!authStore.isPlatformLevel || !training.isActive) return
    void training.fetchRoster()
  }, OWNER)

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner(OWNER)
  })
}
