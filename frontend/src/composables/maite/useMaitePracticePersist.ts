/**
 * Persist a Maite practice conversation (problem + session) and refresh 最近练习.
 */
import { createProblem } from '@/api/maite/problems'
import { createSession } from '@/api/maite/inquiry'
import { eventBus } from '@/composables/core/useEventBus'
import { useMaiteStore } from '@/stores/maite'

import type { MaiteMode, MaitePracticeItem, MaiteSession } from '@/types/maite'

function sessionTitle(question: string): string {
  const compact = question.replace(/\s+/g, ' ').trim()
  if (!compact) {
    return 'Practice'
  }
  if (compact.length <= 40) {
    return compact
  }
  return `${compact.slice(0, 40)}…`
}

function toPracticeItem(session: MaiteSession): MaitePracticeItem {
  return {
    id: session.id,
    title: session.title,
    status: session.status,
    current_stage: session.current_stage,
    mode: session.mode,
    updated_at: session.updated_at,
    created_at: session.created_at,
  }
}

export interface PersistPracticeInput {
  text: string
  imageUrl?: string
  mode: MaiteMode
}

export async function persistMaitePractice(
  input: PersistPracticeInput
): Promise<MaiteSession | null> {
  const question = input.text.trim()
  if (!question) {
    return null
  }

  const store = useMaiteStore()
  // DB column is String(512); keep stored relative paths short.
  const imageUrl =
    input.imageUrl && input.imageUrl.length > 512
      ? input.imageUrl.slice(0, 512)
      : (input.imageUrl ?? null)
  const problem = await createProblem({
    raw_text: question,
    clean_text: question,
    source_type: imageUrl ? 'ocr' : 'paste',
    image_url: imageUrl,
  })
  const session = await createSession({
    problem_id: problem.id,
    mode: input.mode === 'inquiry' ? 'inquiry' : 'demo',
    title: sessionTitle(question),
  })

  store.setActiveSessionId(session.id)
  const item = toPracticeItem(session)
  const rest = store.recentPractice.filter((entry) => entry.id !== item.id)
  store.setRecentPractice([item, ...rest])
  eventBus.emit('maite:practice_invalidate', { reason: 'practice_persisted' })
  eventBus.emit('maite:problem_ready', {
    problemId: problem.id,
    text: question,
    imageUrl: input.imageUrl,
  })
  return session
}
