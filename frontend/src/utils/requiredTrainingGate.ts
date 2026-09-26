/**
 * Send signed-in users who have not finished a required course to that course.
 */
import { fetchRequiredTraining } from '@/utils/trainingVodApi'

const SKIP_PREFIXES = ['/auth', '/training/required', '/training/builder', '/admin']

let cache: { userId: string; courseId: string | null } | null = null
let generation = 0
const finishedIds = new Set<string>()

export function shouldSkipRequiredTraining(path: string): boolean {
  return SKIP_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`))
}

export function clearRequiredTrainingCache(): void {
  cache = null
  generation += 1
}

export function noteRequiredTrainingFinished(courseId: string): void {
  finishedIds.add(courseId)
  clearRequiredTrainingCache()
}

export async function requiredTrainingRedirect(
  path: string,
  userId: string | number | null | undefined
): Promise<{ path: string } | null> {
  if (userId == null || userId === '' || shouldSkipRequiredTraining(path)) return null
  const key = String(userId)
  if (cache && cache.userId === key && cache.courseId) {
    return { path: '/training/required' }
  }
  const gen = generation
  try {
    const courseId = await outstandingCourseId()
    if (gen !== generation) return null
    cache = { userId: key, courseId }
    return courseId ? { path: '/training/required' } : null
  } catch {
    return null
  }
}

async function outstandingCourseId(): Promise<string | null> {
  const body = await fetchRequiredTraining()
  const first = body.course?.id || ''
  if (!first || !finishedIds.has(first)) return first || null
  const again = await fetchRequiredTraining()
  const next = again.course?.id || ''
  if (!next || finishedIds.has(next)) return null
  return next
}
