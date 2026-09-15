/** Download a flagged MindMate teaching-design reply as a filled BNU DOCX. */

import { authFetch } from '@/utils/api'
import {
  isTeachingInstructionReply,
  TEACHING_INSTRUCTION_KIND,
} from '@/utils/mindmateTeachingDesignFlag'

const FILENAME_STAR_RE = /filename\*=UTF-8''([^;]+)/i
const FILENAME_RE = /filename="([^"]+)"/i
const REVOKE_OBJECT_URL_MS = 15_000

const DETAIL_TO_CODE: Record<string, TeachingDesignExportFailCode> = {
  teaching_design_not_flagged: 'not_flagged',
  teaching_design_too_large: 'too_large',
  teaching_design_template_missing: 'server',
  teaching_design_build_failed: 'server',
}

export type TeachingDesignExportFailCode =
  | 'unauthorized'
  | 'not_flagged'
  | 'too_large'
  | 'server'
  | 'network'
  | 'unknown'

export class TeachingDesignExportError extends Error {
  readonly code: TeachingDesignExportFailCode

  readonly status: number

  constructor(code: TeachingDesignExportFailCode, status: number, message: string) {
    super(message)
    this.name = 'TeachingDesignExportError'
    this.code = code
    this.status = status
  }
}

export function filenameFromDisposition(header: string | null): string {
  if (!header) {
    return '教学设计.docx'
  }
  const star = FILENAME_STAR_RE.exec(header)
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1])
    } catch {
      return star[1]
    }
  }
  const quoted = FILENAME_RE.exec(header)
  return quoted?.[1] || '教学设计.docx'
}

export function teachingDesignExportFailI18nKey(error: unknown): string {
  if (error instanceof TeachingDesignExportError) {
    switch (error.code) {
      case 'unauthorized':
        return 'mindmate.openCanvasLoginRequired'
      case 'not_flagged':
        return 'mindmate.exportWordTemplateFailNotFlagged'
      case 'too_large':
        return 'mindmate.exportWordTemplateFailTooLarge'
      case 'network':
        return 'mindmate.exportWordTemplateFailNetwork'
      case 'server':
        return 'mindmate.exportWordTemplateFailServer'
      default:
        return 'mindmate.exportWordTemplateFail'
    }
  }
  return 'mindmate.exportWordTemplateFail'
}

function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.rel = 'noopener'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => {
    URL.revokeObjectURL(url)
  }, REVOKE_OBJECT_URL_MS)
}

function failCodeFromStatus(status: number, detail: string): TeachingDesignExportFailCode {
  const mapped = DETAIL_TO_CODE[detail]
  if (mapped) {
    return mapped
  }
  if (status === 401 || status === 403) {
    return 'unauthorized'
  }
  if (status === 400) {
    return 'not_flagged'
  }
  if (status === 413) {
    return 'too_large'
  }
  if (status >= 500) {
    return 'server'
  }
  return 'unknown'
}

async function readApiDetail(response: Response): Promise<string> {
  try {
    const body = (await response.clone().json()) as { detail?: unknown }
    return typeof body.detail === 'string' ? body.detail : ''
  } catch {
    return ''
  }
}

export async function downloadTeachingDesignDocx(options: {
  assistantMarkdown: string
  replyKind?: string
  userPrompt?: string
}): Promise<void> {
  const replyKind =
    options.replyKind ||
    (isTeachingInstructionReply(options.assistantMarkdown)
      ? TEACHING_INSTRUCTION_KIND
      : undefined)
  let response: Response
  try {
    response = await authFetch('/api/export_teaching_design_docx', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        assistant_markdown: options.assistantMarkdown,
        reply_kind: replyKind,
        user_prompt: options.userPrompt || undefined,
      }),
    })
  } catch {
    throw new TeachingDesignExportError('network', 0, 'Teaching-design DOCX export network error')
  }
  if (!response.ok) {
    const detail = await readApiDetail(response)
    throw new TeachingDesignExportError(
      failCodeFromStatus(response.status, detail),
      response.status,
      detail || `Teaching-design DOCX export failed (${response.status})`
    )
  }
  const blob = await response.blob()
  triggerBlobDownload(blob, filenameFromDisposition(response.headers.get('Content-Disposition')))
}
