/**
 * Maite inquiry session API.
 */
import { maiteRequestJson } from './client'

import type {
  MaiteSelfAssessmentItem,
  MaiteSession,
  MaiteSessionSnapshot,
  MaiteTableRow,
} from '@/types/maite'

export interface CreateSessionInput {
  problem_id: number
  mode?: string
  title?: string | null
}

export interface DecomposeSubmissionInput {
  condition_table: MaiteTableRow[]
  step_table: MaiteTableRow[]
  model_table: MaiteTableRow[]
}

export async function createSession(input: CreateSessionInput): Promise<MaiteSession> {
  return maiteRequestJson<MaiteSession>('/inquiry/sessions', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function listSessions(): Promise<MaiteSession[]> {
  return maiteRequestJson<MaiteSession[]>('/inquiry/sessions')
}

export async function getSession(sessionId: number): Promise<MaiteSession> {
  return maiteRequestJson<MaiteSession>(`/inquiry/sessions/${sessionId}`)
}

export async function getSnapshot(sessionId: number): Promise<MaiteSessionSnapshot> {
  return maiteRequestJson<MaiteSessionSnapshot>(`/inquiry/sessions/${sessionId}/snapshot`)
}

export async function redoSession(sessionId: number): Promise<MaiteSession> {
  return maiteRequestJson<MaiteSession>(`/inquiry/sessions/${sessionId}/redo`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export async function completeSession(sessionId: number): Promise<MaiteSession> {
  return maiteRequestJson<MaiteSession>(`/inquiry/${sessionId}/complete`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export async function analyzeSession(sessionId: number): Promise<Record<string, unknown>> {
  return maiteRequestJson<Record<string, unknown>>(`/inquiry/${sessionId}/analysis`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export async function saveSelfAssessment(
  sessionId: number,
  items: MaiteSelfAssessmentItem[]
): Promise<Record<string, unknown>> {
  return maiteRequestJson<Record<string, unknown>>(`/inquiry/${sessionId}/self-assessment`, {
    method: 'POST',
    body: JSON.stringify({ items }),
  })
}

export async function getDecomposeTemplate(sessionId: number): Promise<Record<string, unknown>> {
  return maiteRequestJson<Record<string, unknown>>(`/inquiry/${sessionId}/decompose-template`)
}

export async function submitDecompose(
  sessionId: number,
  payload: DecomposeSubmissionInput
): Promise<Record<string, unknown>> {
  return maiteRequestJson<Record<string, unknown>>(
    `/inquiry/${sessionId}/decompose-submission`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  )
}
