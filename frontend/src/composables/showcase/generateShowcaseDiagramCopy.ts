/**
 * Showcase diagram AI copy: send specs → extract node text + LLM fields.
 * Gallery images use multipart OCR (`/diagram-copy/images`).
 */
import { authFetch } from '@/utils/api'
import { apiUpload } from '@/utils/apiClient'

export type ShowcaseDiagramCopyResult = {
  description: string
  classroomApplication: string
  model: string
}

export type ShowcaseDiagramCopyRequest = {
  specs: Record<string, unknown>[]
  title: string
  subject: string
  grade: string
  diagramType: string
  signal?: AbortSignal
}

export type ShowcaseDiagramCopyImagesRequest = {
  images: File[]
  title: string
  subject: string
  grade: string
  diagramType: string
  signal?: AbortSignal
}

export type ShowcaseDiagramCopyFields = {
  description?: string
  classroomApplication?: string
}

export type ShowcaseDiagramCopyStreamHandlers = {
  onPhase?: (phase: 'extracting' | 'generating') => void
  onFields?: (fields: ShowcaseDiagramCopyFields) => void
  onDone?: (result: ShowcaseDiagramCopyResult) => void
  onError?: (message: string, errorType?: string) => void
}

function diagramCopyFingerprint(input: {
  specs: Record<string, unknown>[]
  title: string
  subject: string
  grade: string
  diagramType: string
}): string {
  let specFingerprint = ''
  try {
    specFingerprint = JSON.stringify(input.specs)
  } catch {
    specFingerprint = String(input.specs.length)
  }
  return [
    input.diagramType.trim(),
    input.title.trim(),
    input.subject.trim(),
    input.grade.trim(),
    specFingerprint,
  ].join('|')
}

function diagramCopyImagesFingerprint(input: {
  images: File[]
  title: string
  subject: string
  grade: string
  diagramType: string
}): string {
  const imageFingerprint = input.images
    .map((file) => `${file.name}:${file.size}:${file.lastModified}`)
    .join(',')
  return [
    'images',
    input.diagramType.trim(),
    input.title.trim(),
    input.subject.trim(),
    input.grade.trim(),
    imageFingerprint,
  ].join('|')
}

export { diagramCopyFingerprint, diagramCopyImagesFingerprint }

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

function buildDiagramCopyBody(input: ShowcaseDiagramCopyRequest): Record<string, unknown> {
  return {
    title: input.title.trim(),
    subject: input.subject.trim(),
    grade: input.grade.trim(),
    diagram_type: input.diagramType.trim(),
    specs: input.specs,
  }
}

function buildDiagramCopyImagesFormData(input: ShowcaseDiagramCopyImagesRequest): FormData {
  const formData = new FormData()
  formData.append('title', input.title.trim())
  formData.append('subject', input.subject.trim())
  formData.append('grade', input.grade.trim())
  formData.append('diagram_type', input.diagramType.trim())
  for (const file of input.images) {
    formData.append('files', file, file.name)
  }
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

function fieldsFromPayload(data: Record<string, unknown>): ShowcaseDiagramCopyFields {
  return {
    description: readOptionalString(data.description),
    classroomApplication: readOptionalString(data.classroom_application),
  }
}

function resultFromPayload(data: Record<string, unknown>): ShowcaseDiagramCopyResult {
  return {
    description: readOptionalString(data.description) ?? '',
    classroomApplication: readOptionalString(data.classroom_application) ?? '',
    model: readOptionalString(data.model) ?? 'qwen3.7-flash',
  }
}

async function generateShowcaseDiagramCopy(
  input: ShowcaseDiagramCopyRequest,
): Promise<ShowcaseDiagramCopyResult> {
  const response = await authFetch('/api/showcase/ai/diagram-copy', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(buildDiagramCopyBody(input)),
    signal: input.signal,
  })

  if (!response.ok) {
    const detail = await parseErrorDetail(response, 'AI generation failed')
    throw new Error(detail)
  }

  const data = (await response.json()) as {
    description?: unknown
    classroom_application?: unknown
    model?: unknown
  }

  return {
    description: typeof data.description === 'string' ? data.description : '',
    classroomApplication:
      typeof data.classroom_application === 'string' ? data.classroom_application : '',
    model: typeof data.model === 'string' ? data.model : 'qwen3.7-flash',
  }
}

async function consumeDiagramCopySse(
  response: Response,
  handlers: ShowcaseDiagramCopyStreamHandlers,
  signal?: AbortSignal,
): Promise<ShowcaseDiagramCopyResult> {
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
  let finalResult: ShowcaseDiagramCopyResult | null = null
  let streamError: string | null = null

  try {
    while (true) {
      if (signal?.aborted) {
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

  if (signal?.aborted) {
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

/**
 * Stream diagram-copy SSE into field callbacks (JSON body via authFetch).
 */
async function streamShowcaseDiagramCopy(
  input: ShowcaseDiagramCopyRequest,
  handlers: ShowcaseDiagramCopyStreamHandlers = {},
): Promise<ShowcaseDiagramCopyResult> {
  const response = await authFetch('/api/showcase/ai/diagram-copy/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(buildDiagramCopyBody(input)),
    signal: input.signal,
  })

  if (!response.ok) {
    const detail = await parseErrorDetail(response, 'AI generation failed')
    throw new Error(detail)
  }

  return consumeDiagramCopySse(response, handlers, input.signal)
}

/**
 * Stream diagram-copy SSE from gallery images (Qwen OCR → LLM).
 */
async function streamShowcaseDiagramCopyFromImages(
  input: ShowcaseDiagramCopyImagesRequest,
  handlers: ShowcaseDiagramCopyStreamHandlers = {},
): Promise<ShowcaseDiagramCopyResult> {
  if (!input.images.length) {
    throw new Error('At least one gallery image required')
  }
  const response = await apiUpload(
    '/api/showcase/ai/diagram-copy/images/stream',
    buildDiagramCopyImagesFormData(input),
    { signal: input.signal },
  )

  if (!response.ok) {
    const detail = await parseErrorDetail(response, 'AI generation failed')
    throw new Error(detail)
  }

  return consumeDiagramCopySse(response, handlers, input.signal)
}

export {
  generateShowcaseDiagramCopy,
  streamShowcaseDiagramCopy,
  streamShowcaseDiagramCopyFromImages,
}
