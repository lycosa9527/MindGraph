/**
 * Maite variant practice API.
 */
import { maiteRequestJson } from './client'

import type { MaiteVariantTask } from '@/types/maite'

export interface VariantSubmissionInput {
  student_answer: string
  student_strategy: string
}

export async function generateVariantTasks(sessionId: number): Promise<MaiteVariantTask[]> {
  return maiteRequestJson<MaiteVariantTask[]>(`/inquiry/${sessionId}/variants`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export async function submitVariantTask(
  sessionId: number,
  taskId: number,
  input: VariantSubmissionInput
): Promise<Record<string, unknown>> {
  return maiteRequestJson<Record<string, unknown>>(
    `/inquiry/${sessionId}/variants/${taskId}/submit`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    }
  )
}
