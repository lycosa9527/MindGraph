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

export type ShowcaseTeachingCopyFields = {
  description?: string
  designHighlights?: string
  teachingReflection?: string
}

export type ShowcaseTeachingCopyStreamHandlers = {
  onPhase?: (phase: 'extracting' | 'generating') => void
  onFields?: (fields: ShowcaseTeachingCopyFields) => void
  onDone?: (result: ShowcaseTeachingCopyResult) => void
  onError?: (message: string, errorType?: string) => void
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

function buildTeachingCopyFormData(input: ShowcaseTeachingCopyRequest): FormData {
  const formData = new FormData()
  formData.append('file', input.file)
  formData.append('title', input.title.trim())
  formData.append('subject', input.subject.trim())
  formData.append('grade', input.grade.trim())
  return formData
}

function parseSseDataLine(line: string): Record<string, unknown> | null {
  if (!line.startsWith('data: ')) {
    return null
  }
  try {
    return JSON.parse(line.slice(6)) as Record<string, unknown>
  } catch {
    return null
  }
}

function readOptionalString(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined
}

function fieldsFromPayload(data: Record<string, unknown>): ShowcaseTeachingCopyFields {
  return {
    description: readOptionalString(data.description),
    designHighlights: readOptionalString(data.design_highlights),
    teachingReflection: readOptionalString(data.teaching_reflection),
  }
}

function resultFromPayload(data: Record<string, unknown>): ShowcaseTeachingCopyResult {
  return {
    description: readOptionalString(data.description) ?? '',
    designHighlights: readOptionalString(data.design_highlights) ?? '',
    teachingReflection: readOptionalString(data.teaching_reflection) ?? '',
    model: readOptionalString(data.model) ?? 'qwen3.7-flash',
  }
}

async function generateShowcaseTeachingCopy(
  input: ShowcaseTeachingCopyRequest,
): Promise<ShowcaseTeachingCopyResult> {
  const response = await apiUpload(
    '/api/showcase/ai/teaching-copy',
    buildTeachingCopyFormData(input),
    {
      signal: input.signal,
    },
  )

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

/**
 * Stream teaching-copy SSE into field callbacks (multipart upload via apiUpload).
 */
async function streamShowcaseTeachingCopy(
  input: ShowcaseTeachingCopyRequest,
  handlers: ShowcaseTeachingCopyStreamHandlers = {},
): Promise<ShowcaseTeachingCopyResult> {
  const response = await apiUpload(
    '/api/showcase/ai/teaching-copy/stream',
    buildTeachingCopyFormData(input),
    {
      signal: input.signal,
    },
  )

  if (!response.ok) {
    const detail = await parseErrorDetail(response, 'AI generation failed')
    throw new Error(detail)
  }

  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('text/event-stream')) {
    throw new Error('AI stream response was not event-stream')
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('AI stream has no response body')
  }

  const decoder = new TextDecoder()
  let lineBuffer = ''
  let finalResult: ShowcaseTeachingCopyResult | null = null
  let streamError: string | null = null

  try {
    while (true) {
      if (input.signal?.aborted) {
        break
      }
      const { done, value } = await reader.read()
      if (done) break
      lineBuffer += decoder.decode(value, { stream: true })
      const lines = lineBuffer.split('\n')
      lineBuffer = lines.pop() ?? ''
      for (const line of lines) {
        const payload = parseSseDataLine(line.replace(/\r$/, ''))
        if (!payload) continue
        const event = payload.event
        if (event === 'phase') {
          const phase = payload.phase
          if (phase === 'extracting' || phase === 'generating') {
            handlers.onPhase?.(phase)
          }
        } else if (event === 'fields') {
          handlers.onFields?.(fieldsFromPayload(payload))
        } else if (event === 'done') {
          finalResult = resultFromPayload(payload)
          handlers.onDone?.(finalResult)
        } else if (event === 'error') {
          const message =
            typeof payload.message === 'string' && payload.message.trim()
              ? payload.message
              : 'AI generation failed'
          const errorType =
            typeof payload.error_type === 'string' ? payload.error_type : undefined
          streamError = message
          handlers.onError?.(message, errorType)
        }
      }
    }
    if (lineBuffer.trim()) {
      const payload = parseSseDataLine(lineBuffer.replace(/\r$/, ''))
      if (payload?.event === 'done') {
        finalResult = resultFromPayload(payload)
        handlers.onDone?.(finalResult)
      } else if (payload?.event === 'error') {
        const message =
          typeof payload.message === 'string' && payload.message.trim()
            ? payload.message
            : 'AI generation failed'
        streamError = message
        handlers.onError?.(
          message,
          typeof payload.error_type === 'string' ? payload.error_type : undefined,
        )
      } else if (payload?.event === 'fields') {
        handlers.onFields?.(fieldsFromPayload(payload))
      }
    }
  } finally {
    reader.releaseLock()
  }

  if (input.signal?.aborted) {
    throw new DOMException('Aborted', 'AbortError')
  }
  if (streamError) {
    throw new Error(streamError)
  }
  if (!finalResult) {
    throw new Error('AI generation failed')
  }
  return finalResult
}

export { generateShowcaseTeachingCopy, streamShowcaseTeachingCopy }
