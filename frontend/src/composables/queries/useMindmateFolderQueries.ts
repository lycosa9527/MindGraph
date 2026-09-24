/**
 * MindMate archive folders. Conversations stay in Dify; membership is local.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'

import { useAuthStore } from '@/stores'

import { difyKeys } from './difyKeys'

export interface MindmateFolder {
  id: string
  name: string
  sort_order: number
  conversation_count: number
}

export interface MindmateFolderAssignment {
  conversation_id: string
  folder_id: string
}

export interface MindmateFolderSnapshot {
  folders: MindmateFolder[]
  assignments: MindmateFolderAssignment[]
}

function handle401(message?: string): void {
  const authStore = useAuthStore()
  authStore.handleTokenExpired(message || '您的登录已过期，请重新登录')
}

async function parseJson(response: Response): Promise<Record<string, unknown>> {
  const body: unknown = await response.json()
  if (!body || typeof body !== 'object') return {}
  return body as Record<string, unknown>
}

function asFolder(row: unknown): MindmateFolder | null {
  if (!row || typeof row !== 'object') return null
  const item = row as Record<string, unknown>
  if (typeof item.id !== 'string' || typeof item.name !== 'string') return null
  return {
    id: item.id,
    name: item.name,
    sort_order: typeof item.sort_order === 'number' ? item.sort_order : 0,
    conversation_count: typeof item.conversation_count === 'number' ? item.conversation_count : 0,
  }
}

function asAssignment(row: unknown): MindmateFolderAssignment | null {
  if (!row || typeof row !== 'object') return null
  const item = row as Record<string, unknown>
  if (typeof item.conversation_id !== 'string' || typeof item.folder_id !== 'string') return null
  return { conversation_id: item.conversation_id, folder_id: item.folder_id }
}

async function fetchMindmateFolders(): Promise<MindmateFolderSnapshot> {
  const response = await fetch('/api/mindmate-folders', { credentials: 'same-origin' })
  if (!response.ok) {
    if (response.status === 401) handle401()
    throw new Error('Failed to fetch MindMate folders')
  }
  const result = await parseJson(response)
  const folders = Array.isArray(result.folders)
    ? result.folders.map(asFolder).filter((folder): folder is MindmateFolder => folder !== null)
    : []
  const assignments = Array.isArray(result.assignments)
    ? result.assignments
        .map(asAssignment)
        .filter((row): row is MindmateFolderAssignment => row !== null)
    : []
  return { folders, assignments }
}

async function createMindmateFolder(name: string): Promise<MindmateFolder> {
  const response = await fetch('/api/mindmate-folders', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  if (!response.ok) {
    if (response.status === 401) handle401()
    throw new Error('Failed to create folder')
  }
  const created = asFolder(await parseJson(response))
  if (!created) throw new Error('Failed to create folder')
  return created
}

async function renameMindmateFolder(folderId: string, name: string): Promise<void> {
  const response = await fetch(`/api/mindmate-folders/${folderId}`, {
    method: 'PATCH',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  if (!response.ok) {
    if (response.status === 401) handle401()
    throw new Error('Failed to rename folder')
  }
}

async function deleteMindmateFolder(folderId: string): Promise<void> {
  const response = await fetch(`/api/mindmate-folders/${folderId}`, {
    method: 'DELETE',
    credentials: 'same-origin',
  })
  if (!response.ok) {
    if (response.status === 401) handle401()
    throw new Error('Failed to delete folder')
  }
}

async function moveMindmateConversation(
  conversationId: string,
  folderId: string | null
): Promise<void> {
  const response = await fetch(
    `/api/mindmate-folders/conversations/${encodeURIComponent(conversationId)}`,
    {
      method: 'PUT',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_id: folderId }),
    }
  )
  if (!response.ok) {
    if (response.status === 401) handle401()
    throw new Error('Failed to move conversation')
  }
}

export function useMindmateFolders() {
  const authStore = useAuthStore()
  return useQuery({
    queryKey: difyKeys.mindmateFolders(),
    queryFn: fetchMindmateFolders,
    staleTime: 60 * 1000,
    enabled: !!authStore.user,
  })
}

export function useCreateMindmateFolder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => createMindmateFolder(name),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: difyKeys.mindmateFolders() })
    },
  })
}

export function useRenameMindmateFolder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ folderId, name }: { folderId: string; name: string }) =>
      renameMindmateFolder(folderId, name),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: difyKeys.mindmateFolders() })
    },
  })
}

export function useDeleteMindmateFolder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (folderId: string) => deleteMindmateFolder(folderId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: difyKeys.mindmateFolders() })
    },
  })
}

export function useMoveMindmateConversation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      conversationId,
      folderId,
    }: {
      conversationId: string
      folderId: string | null
    }) => moveMindmateConversation(conversationId, folderId),
    onMutate: async ({ conversationId, folderId }) => {
      await queryClient.cancelQueries({ queryKey: difyKeys.mindmateFolders() })
      const previous = queryClient.getQueryData<MindmateFolderSnapshot>(difyKeys.mindmateFolders())
      if (previous) {
        const assignments = previous.assignments.filter(
          (row) => row.conversation_id !== conversationId
        )
        if (folderId) {
          assignments.push({ conversation_id: conversationId, folder_id: folderId })
        }
        queryClient.setQueryData<MindmateFolderSnapshot>(difyKeys.mindmateFolders(), {
          ...previous,
          assignments,
        })
      }
      return { previous }
    },
    onError: (_error, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(difyKeys.mindmateFolders(), context.previous)
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: difyKeys.mindmateFolders() })
    },
  })
}
