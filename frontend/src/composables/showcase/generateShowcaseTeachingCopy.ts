/**
 * Showcase teaching-design AI copy: upload document → extract + LLM fields.
 */
import { apiUpload } from '@/utils/apiClient'

export type ShowcaseTeachingCopyResult = {
  description: string
  designHighlights: string
  teachingReflection: string
  model: string
}

export type ShowcaseTeachingCopyRequest = {
  file: File
  title: string
  subject: string
  grade: string
  signal?: AbortSignal
}

function teachingCopyFingerprint(input: {
  file: File
  title: string
  subject: string
  grade: string
}): string {
  return [
    input.file.name,
    input.file.size,
    input.file.lastModified,
    input.title.trim(),
    input.subject.trim(),
    input.grade.trim(),
  ].join('|')
}

export { teachingCopyFingerprint }

async function parseErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown; message?: unknown }
    if (typeof data.detail === 'string' && data.detail.trim()) return data.detail
    if (typeof data.message === 'string' && data.message.trim()) return data.message
  } catch {
    // ignore parse failures
  }
  return fallback
}

export async function generateShowcaseTeachingCopy(
  input: ShowcaseTeachingCopyRequest,
): Promise<ShowcaseTeachingCopyResult> {
  const formData = new FormData()
  formData.append('file', input.file)
  formData.append('title', input.title.trim())
  formData.append('subject', input.subject.trim())
  formData.append('grade', input.grade.trim())

  const response = await apiUpload('/api/showcase/ai/teaching-copy', formData, {
    signal: input.signal,
  })

  if (!response.ok) {
    const detail = await parseErrorDetail(response, 'AI generation failed')
    throw new Error(detail)
  }

  const data = (await response.json()) as {
    description?: unknown
    design_highlights?: unknown
    teaching_reflection?: unknown
    model?: unknown
  }

  return {
    description: typeof data.description === 'string' ? data.description : '',
    designHighlights:
      typeof data.design_highlights === 'string' ? data.design_highlights : '',
    teachingReflection:
      typeof data.teaching_reflection === 'string' ? data.teaching_reflection : '',
    model: typeof data.model === 'string' ? data.model : 'qwen3.7-flash',
  }
}
