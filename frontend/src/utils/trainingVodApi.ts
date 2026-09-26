/**
 * Course Builder and lesson playback against the online video library.
 */
import type { TrainingCourse } from '@/types/training'
import { apiPost, apiRequestJson } from '@/utils/apiClient'
import type { VodPlayToken } from '@/utils/vodApi'

export interface TrainingVodFolder {
  id: string
  organization_id: number
  name: string
}

export interface TrainingVodItem {
  id: string
  organization_id: number
  folder_id: string | null
  title: string
  status: string
  duration_ms: number | null
}

export async function fetchTrainingVodLibrary(): Promise<{
  folders: TrainingVodFolder[]
  items: TrainingVodItem[]
}> {
  return apiRequestJson('/api/training/vod/library')
}

export async function playTrainingVod(mediaId: string): Promise<VodPlayToken> {
  return apiRequestJson(`/api/training/vod/play/${encodeURIComponent(mediaId)}`)
}

export async function fetchRequiredTraining(): Promise<{ course: TrainingCourse | null }> {
  return apiRequestJson('/api/training/required')
}

export async function completeRequiredTraining(courseId: string): Promise<void> {
  const response = await apiPost(`/api/training/courses/${encodeURIComponent(courseId)}/complete`)
  if (!response.ok) {
    throw new Error(`training_complete_${response.status}`)
  }
}
