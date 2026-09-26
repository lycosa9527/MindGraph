/**
 * Admin 云点播 catalog API (same-origin; no durable VOD hosts).
 */
import { apiDelete, apiPatch, apiPost, apiRequestJson } from '@/utils/apiClient'

export type VodMediaStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface VodMediaItem {
  id: string
  organization_id: number
  owner_id: number
  owner_name: string
  file_id: string
  folder_id: string | null
  title: string
  description: string
  status: VodMediaStatus
  duration_ms: number | null
  class_id: number
  source_context: string
  created_at: string | null
  updated_at: string | null
}

export interface VodFolderItem {
  id: string
  organization_id: number
  name: string
}

export interface VodMediaListResponse {
  items: VodMediaItem[]
  total: number
  offset: number
  limit: number
}

export interface VodPlayToken {
  appId: string
  fileId: string
  psign: string
  licenseUrl: string
  licenseKey: string
  expireAt: number
  id: string
}

export interface VodPlayerConfig {
  configured: boolean
  appId: string
  licenseUrl: string
  licenseKey: string
}

export interface VodUploadSignResponse {
  signature: string
  expire_at: number
  app_id: number
  source_context: string
  media_id: string
}

export async function fetchVodConfig(): Promise<VodPlayerConfig> {
  return apiRequestJson<VodPlayerConfig>('/api/vod/config')
}

export async function listVodMedia(params: {
  q?: string
  status?: string
  organizationId?: number | null
  folderId?: string
  offset?: number
  limit?: number
}): Promise<VodMediaListResponse> {
  const search = new URLSearchParams()
  if (params.q) search.set('q', params.q)
  if (params.status) search.set('status', params.status)
  if (params.organizationId != null) search.set('organization_id', String(params.organizationId))
  if (params.folderId) search.set('folder_id', params.folderId)
  if (params.offset != null) search.set('offset', String(params.offset))
  if (params.limit != null) search.set('limit', String(params.limit))
  const query = search.toString()
  const path = query ? `/api/vod/media?${query}` : '/api/vod/media'
  return apiRequestJson<VodMediaListResponse>(path)
}

export async function signVodUpload(
  organizationId?: number | null
): Promise<VodUploadSignResponse> {
  const response = await apiPost('/api/vod/uploads/sign', {
    organization_id: organizationId ?? null,
  })
  if (!response.ok) {
    throw new Error(`vod_sign_${response.status}`)
  }
  return (await response.json()) as VodUploadSignResponse
}

export async function registerVodMedia(body: {
  fileId: string
  title: string
  description?: string
  organizationId?: number | null
  folderId?: string | null
  sourceContext?: string
}): Promise<VodMediaItem> {
  const response = await apiPost('/api/vod/media', {
    file_id: body.fileId,
    title: body.title,
    description: body.description ?? '',
    organization_id: body.organizationId ?? null,
    folder_id: body.folderId || null,
    source_context: body.sourceContext ?? '',
    refresh: true,
  })
  if (!response.ok) {
    throw new Error(`vod_register_${response.status}`)
  }
  return (await response.json()) as VodMediaItem
}

export async function refreshVodMedia(
  mediaId: string,
  organizationId?: number | null
): Promise<VodMediaItem> {
  const search = new URLSearchParams()
  if (organizationId != null) search.set('organization_id', String(organizationId))
  const query = search.toString()
  const path = query
    ? `/api/vod/media/${encodeURIComponent(mediaId)}/refresh?${query}`
    : `/api/vod/media/${encodeURIComponent(mediaId)}/refresh`
  const response = await apiPost(path)
  if (!response.ok) {
    throw new Error(`vod_refresh_${response.status}`)
  }
  return (await response.json()) as VodMediaItem
}

export async function playVodMedia(
  mediaId: string,
  organizationId?: number | null
): Promise<VodPlayToken> {
  const search = new URLSearchParams()
  if (organizationId != null) search.set('organization_id', String(organizationId))
  const query = search.toString()
  const path = query
    ? `/api/vod/media/${encodeURIComponent(mediaId)}/play?${query}`
    : `/api/vod/media/${encodeURIComponent(mediaId)}/play`
  return apiRequestJson<VodPlayToken>(path)
}

export async function deleteVodMedia(
  mediaId: string,
  organizationId?: number | null
): Promise<void> {
  const search = new URLSearchParams()
  if (organizationId != null) search.set('organization_id', String(organizationId))
  const query = search.toString()
  const path = query
    ? `/api/vod/media/${encodeURIComponent(mediaId)}?${query}`
    : `/api/vod/media/${encodeURIComponent(mediaId)}`
  const response = await apiDelete(path)
  if (!response.ok) {
    throw new Error(`vod_delete_${response.status}`)
  }
}

function withOrg(path: string, organizationId?: number | null): string {
  if (organizationId == null) return path
  const join = path.includes('?') ? '&' : '?'
  return `${path}${join}organization_id=${organizationId}`
}

export async function listVodFolders(organizationId?: number | null): Promise<VodFolderItem[]> {
  const body = await apiRequestJson<{ items: VodFolderItem[] }>(
    withOrg('/api/vod/folders', organizationId)
  )
  return body.items
}

export async function createVodFolder(
  name: string,
  organizationId?: number | null
): Promise<VodFolderItem> {
  const response = await apiPost('/api/vod/folders', {
    name,
    organization_id: organizationId ?? null,
  })
  if (!response.ok) {
    throw new Error(`vod_folder_${response.status}`)
  }
  return (await response.json()) as VodFolderItem
}

export async function renameVodFolder(
  folderId: string,
  name: string,
  organizationId?: number | null
): Promise<VodFolderItem> {
  const response = await apiPatch(`/api/vod/folders/${encodeURIComponent(folderId)}`, {
    name,
    organization_id: organizationId ?? null,
  })
  if (!response.ok) {
    throw new Error(`vod_folder_${response.status}`)
  }
  return (await response.json()) as VodFolderItem
}

export async function deleteVodFolder(
  folderId: string,
  organizationId?: number | null
): Promise<void> {
  const path = withOrg(`/api/vod/folders/${encodeURIComponent(folderId)}`, organizationId)
  const response = await apiDelete(path)
  if (!response.ok) {
    throw new Error(`vod_folder_delete_${response.status}`)
  }
}

export async function moveVodMedia(
  mediaId: string,
  folderId: string | null,
  organizationId?: number | null
): Promise<VodMediaItem> {
  const response = await apiPatch(`/api/vod/media/${encodeURIComponent(mediaId)}`, {
    folder_id: folderId,
    organization_id: organizationId ?? null,
  })
  if (!response.ok) {
    throw new Error(`vod_move_${response.status}`)
  }
  return (await response.json()) as VodMediaItem
}
