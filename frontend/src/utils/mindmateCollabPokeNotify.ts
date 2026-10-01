/**
 * Show in-app toast when a colleague pokes you to join a MindMate seminar.
 */
import type { useNotifications } from '@/composables'
import type { UseLanguageTranslate } from '@/composables/core/useLanguage'

type Notify = ReturnType<typeof useNotifications>

const POKE_WOBBLE_CLASS = 'mindmate-poke-wobble'
const POKE_WOBBLE_MS = 500

let wobbleTimer: ReturnType<typeof setTimeout> | null = null

function playPokeDing(): void {
  try {
    const ctx = new AudioContext()
    const masterGain = ctx.createGain()
    masterGain.gain.value = 0.22
    masterGain.connect(ctx.destination)

    const now = ctx.currentTime
    const osc1 = ctx.createOscillator()
    const gain1 = ctx.createGain()
    osc1.type = 'sine'
    osc1.frequency.value = 880
    gain1.gain.setValueAtTime(1, now)
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.45)
    osc1.connect(gain1)
    gain1.connect(masterGain)
    osc1.start(now)
    osc1.stop(now + 0.45)

    const osc2 = ctx.createOscillator()
    const gain2 = ctx.createGain()
    osc2.type = 'sine'
    osc2.frequency.value = 1320
    gain2.gain.setValueAtTime(0.35, now)
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.2)
    osc2.connect(gain2)
    gain2.connect(masterGain)
    osc2.start(now)
    osc2.stop(now + 0.2)

    osc1.onended = () => {
      ctx.close().catch(() => undefined)
    }
  } catch {
    // Autoplay policy or missing AudioContext — the toast still shows.
  }
}

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function wobbleScreen(): void {
  if (typeof document === 'undefined' || prefersReducedMotion()) {
    return
  }
  const root = document.documentElement
  root.classList.remove(POKE_WOBBLE_CLASS)
  void root.offsetWidth
  root.classList.add(POKE_WOBBLE_CLASS)
  if (wobbleTimer != null) {
    clearTimeout(wobbleTimer)
  }
  wobbleTimer = setTimeout(() => {
    root.classList.remove(POKE_WOBBLE_CLASS)
    wobbleTimer = null
  }, POKE_WOBBLE_MS)
}

/** Ding plus a half-second screen wobble for the person who was poked. */
export function playMindmateCollabPokeCue(): void {
  playPokeDing()
  wobbleScreen()
}

export function handleMindmateCollabPokeFrame(
  data: Record<string, unknown>,
  t: UseLanguageTranslate,
  notify: Notify
): boolean {
  if (String(data.type || '') !== 'mindmate_collab_poke') {
    return false
  }
  const fromName = String(data.from_name || t('mindmate.collabPokeSomeone'))
  const roomTitle = String(data.room_title || '').trim()
  const visibility = String(data.visibility || 'organization')
  const seminarLabel =
    roomTitle ||
    (visibility === 'network' ? t('mindmate.collabSeminarPublic') : t('mindmate.collabSeminarOrg'))
  playMindmateCollabPokeCue()
  notify.infoKey('mindmate.collabPokeToast', { name: fromName, seminar: seminarLabel }, 7000)
  return true
}
