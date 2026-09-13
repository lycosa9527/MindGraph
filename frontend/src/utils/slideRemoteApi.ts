import { apiRequest } from '@/utils/apiClient'
import type { MindMapSlideTraversalMode } from '@/utils/mindMapSlides'

const API = '/api/slides/remote'

export type SlideRemoteState = 'idle' | 'live' | 'ended'

export interface SlideRemoteSnapshot {
  state: SlideRemoteState
  session_id: string
  diagram_id: string
  title: string
  slide_index: number
  slide_count: number
  traversal: MindMapSlideTraversalMode
  autoplay: boolean
  can_prev: boolean
  can_next: boolean
  seq: number
}

export type SlideRemoteCommand =
  | { action: 'next' }
  | { action: 'prev' }
  | { action: 'quit' }
  | { action: 'start'; diagram_id: string }
  | { action: 'autoplay'; on?: boolean }
  | { action: 'traversal'; mode: MindMapSlideTraversalMode }

export interface SlideRemoteCommandRow extends Record<string, unknown> {
  id?: string
  action: SlideRemoteCommand['action']
  on?: boolean
  mode?: MindMapSlideTraversalMode
  diagram_id?: string
}

export interface SlideRemotePublishBody {
  diagram_id: string
  title: string
  slide_index: number
  slide_count: number
  traversal: MindMapSlideTraversalMode
  autoplay: boolean
  can_prev: boolean
  can_next: boolean
}

async function readJson<T>(res: Response): Promise<T> {
  return (await res.json()) as T
}

export async function publishSlideRemoteSession(
  body: SlideRemotePublishBody
): Promise<SlideRemoteSnapshot | null> {
  const res = await apiRequest(`${API}/sessions`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) return null
  return readJson(res)
}

export async function fetchActiveSlideRemote(): Promise<SlideRemoteSnapshot | null> {
  const res = await apiRequest(`${API}/sessions/active`)
  if (!res.ok) return null
  return readJson(res)
}

export async function drainSlideRemoteCommands(): Promise<SlideRemoteCommandRow[]> {
  const res = await apiRequest(`${API}/commands`)
  if (!res.ok) return []
  const body = (await readJson<{ items?: SlideRemoteCommandRow[] }>(res))
  return Array.isArray(body.items) ? body.items : []
}

export async function postSlideRemoteCommand(
  command: SlideRemoteCommand
): Promise<boolean> {
  const res = await apiRequest(`${API}/command`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(command),
  })
  return res.ok
}

export async function endSlideRemoteSession(): Promise<void> {
  await apiRequest(`${API}/end`, { method: 'POST' })
}
