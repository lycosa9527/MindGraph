/**
 * Maite remedy API.
 */
import { maiteRequestJson } from './client'

import type { MaiteRemedyTask } from '@/types/maite'

export type RemedyConfidence = 'unclear' | 'partial' | 'clear'

export interface RemedySubmissionInput {
  student_response: string
  student_confidence?: RemedyConfidence
}

export async function generateRemedyTasks(sessionId: number): Promise<MaiteRemedyTask[]> {
  return maiteRequestJson<MaiteRemedyTask[]>(`/inquiry/${sessionId}/remedy`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export async function prepareRemedyTask(
  sessionId: number,
  taskId: number
): Promise<Record<string, unknown>> {
  return maiteRequestJson<Record<string, unknown>>(
    `/inquiry/${sessionId}/remedy/${taskId}/prepare`,
    {
      method: 'POST',
      body: JSON.stringify({}),
    }
  )
}

export async function generateRemedyMaterial(
  sessionId: number,
  taskId: number
): Promise<Record<string, unknown>> {
  return maiteRequestJson<Record<string, unknown>>(
    `/inquiry/${sessionId}/remedy/${taskId}/material`,
    {
      method: 'POST',
      body: JSON.stringify({}),
    }
  )
}

export async function submitRemedyTask(
  sessionId: number,
  taskId: number,
  input: RemedySubmissionInput
): Promise<Record<string, unknown>> {
  return maiteRequestJson<Record<string, unknown>>(
    `/inquiry/${sessionId}/remedy/${taskId}/submit`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    }
  )
}

export async function reevaluateRemedyTask(
  sessionId: number,
  taskId: number
): Promise<Record<string, unknown>> {
  return maiteRequestJson<Record<string, unknown>>(
    `/inquiry/${sessionId}/remedy/${taskId}/reevaluate`,
    {
      method: 'POST',
      body: JSON.stringify({}),
    }
  )
}
