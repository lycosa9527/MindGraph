/**
 * Show in-app toast when a colleague pokes you to join a MindMate seminar.
 */
import type { useNotifications } from '@/composables'
import type { UseLanguageTranslate } from '@/composables/core/useLanguage'

type Notify = ReturnType<typeof useNotifications>

export function handleMindmateCollabPokeFrame(
  data: Record<string, unknown>,
  t: UseLanguageTranslate,
  notify: Notify,
): boolean {
  if (String(data.type || '') !== 'mindmate_collab_poke') {
    return false
  }
  const fromName = String(data.from_name || t('mindmate.collabPokeSomeone'))
  const roomTitle = String(data.room_title || '').trim()
  const visibility = String(data.visibility || 'organization')
  const seminarLabel =
    roomTitle ||
    (visibility === 'network'
      ? t('mindmate.collabSeminarPublic')
      : t('mindmate.collabSeminarOrg'))
  notify.info(
    t('mindmate.collabPokeToast', { name: fromName, seminar: seminarLabel }),
    7000,
  )
  return true
}
