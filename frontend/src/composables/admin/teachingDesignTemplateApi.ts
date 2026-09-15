/**
 * Admin API for the MindMate teaching-design Word template catalog.
 */
import { useQuery } from '@tanstack/vue-query'

import { adminFetchJson } from '@/composables/queries/adminApi'
import { adminKeys } from '@/composables/queries/adminKeys'
import { apiRequest, apiUpload } from '@/utils/apiClient'
import { httpErrorDetail } from '@/utils/httpErrorDetail'

export interface TeachingDesignTemplateOption {
  key: string
  source: string
  filename: string
  name?: string
}

export interface TeachingDesignTemplateRow {
  id: string
  index: number
  name: string
  source: 'bundled' | 'uploaded'
  filename: string
  size_bytes: number
  updated_at: string | null
  uploaded_by_name: string | null
  is_default: boolean
  can_delete: boolean
}

export interface TeachingDesignTemplateCatalog {
  default_id: string
  can_restore: boolean
  templates: TeachingDesignTemplateRow[]
}

const BASE = '/api/auth/admin/teaching-design-template'

export function teachingDesignTemplateDownloadUrl(templateId: string): string {
  return `${BASE}/${encodeURIComponent(templateId)}/download`
}

export function teachingDesignTemplatePreviewUrl(templateId: string): string {
  return `${BASE}/${encodeURIComponent(templateId)}/preview`
}

async function readError(response: Response, fallback: string): Promise<Error> {
  const data = await response.json().catch(() => ({}))
  return new Error(httpErrorDetail(data) || fallback)
}

export async function fetchTeachingDesignTemplateCatalog(): Promise<TeachingDesignTemplateCatalog> {
  return adminFetchJson<TeachingDesignTemplateCatalog>(BASE, {}, 'Failed to load templates')
}

export async function fetchTeachingDesignTemplateOptions(): Promise<
  TeachingDesignTemplateOption[]
> {
  const payload = await adminFetchJson<{ options: TeachingDesignTemplateOption[] }>(
    `${BASE}/options`,
    {},
    'Failed to load template options'
  )
  return payload.options ?? []
}

export async function uploadTeachingDesignTemplate(
  file: File,
  name?: string
): Promise<TeachingDesignTemplateCatalog> {
  const form = new FormData()
  form.append('file', file)
  if (name?.trim()) {
    form.append('name', name.trim())
  }
  const response = await apiUpload(BASE, form)
  if (!response.ok) {
    throw await readError(response, 'Upload failed')
  }
  return (await response.json()) as TeachingDesignTemplateCatalog
}

export async function patchTeachingDesignTemplate(
  templateId: string,
  body: { name?: string; is_default?: boolean }
): Promise<TeachingDesignTemplateCatalog> {
  return adminFetchJson<TeachingDesignTemplateCatalog>(
    `${BASE}/${encodeURIComponent(templateId)}`,
    {
      method: 'PATCH',
      body: JSON.stringify(body),
    },
    'Failed to save template'
  )
}

export async function replaceTeachingDesignTemplateFile(
  templateId: string,
  file: File
): Promise<TeachingDesignTemplateCatalog> {
  const form = new FormData()
  form.append('file', file)
  const response = await apiUpload(`${BASE}/${encodeURIComponent(templateId)}/file`, form)
  if (!response.ok) {
    throw await readError(response, 'Upload failed')
  }
  return (await response.json()) as TeachingDesignTemplateCatalog
}

export async function deleteTeachingDesignTemplate(
  templateId: string
): Promise<TeachingDesignTemplateCatalog> {
  return adminFetchJson<TeachingDesignTemplateCatalog>(
    `${BASE}/${encodeURIComponent(templateId)}`,
    { method: 'DELETE' },
    'Failed to delete template'
  )
}

export async function restoreTeachingDesignTemplate(): Promise<TeachingDesignTemplateCatalog> {
  return adminFetchJson<TeachingDesignTemplateCatalog>(
    `${BASE}/restore`,
    { method: 'POST' },
    'Failed to restore template'
  )
}

export async function downloadTeachingDesignTemplateFile(templateId?: string): Promise<void> {
  const path = templateId
    ? `${BASE}/${encodeURIComponent(templateId)}/download`
    : `${BASE}/download`
  const response = await apiRequest(path)
  if (!response.ok) {
    throw await readError(response, 'Download failed')
  }
  const blob = await response.blob()
  const header = response.headers.get('Content-Disposition')
  const starred = /filename\*=UTF-8''([^;]+)/i.exec(header ?? '')
  const quoted = /filename="([^"]+)"/i.exec(header ?? '')
  let filename = '教学设计模板.docx'
  if (starred?.[1]) {
    try {
      filename = decodeURIComponent(starred[1])
    } catch {
      filename = starred[1]
    }
  } else if (quoted?.[1]) {
    filename = quoted[1]
  }
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 15_000)
}

export function useAdminTeachingDesignTemplate() {
  return useQuery({
    queryKey: adminKeys.teachingDesignTemplate(),
    queryFn: fetchTeachingDesignTemplateCatalog,
  })
}
