/**
 * Maite mentor decompose and follow-up API.
 */
import { consumeMaiteSseStream, MAITE_API_PREFIX, maiteRequestJson } from './client'

import type {
  MaiteDecomposeTables,
  MaiteMentorFollowUpResult,
  MaiteMentorStreamCallbacks,
} from '@/types/maite'

export interface MentorDecomposeInput {
  question: string
}

export interface MentorFollowUpInput {
  question: string
  reply: string
  history?: Record<string, unknown>[]
  decomposition?: MaiteDecomposeTables
}

export async function decompose(input: MentorDecomposeInput): Promise<MaiteDecomposeTables> {
  return maiteRequestJson<MaiteDecomposeTables>('/mentor/decompose', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function followUp(input: MentorFollowUpInput): Promise<MaiteMentorFollowUpResult> {
  return maiteRequestJson<MaiteMentorFollowUpResult>('/mentor/follow-up', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function decomposeStream(
  input: MentorDecomposeInput,
  callbacks: MaiteMentorStreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  await consumeMaiteSseStream(
    `${MAITE_API_PREFIX}/mentor/decompose/stream`,
    input,
    callbacks,
    signal
  )
}

export async function followUpStream(
  input: MentorFollowUpInput,
  callbacks: MaiteMentorStreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  await consumeMaiteSseStream(
    `${MAITE_API_PREFIX}/mentor/follow-up/stream`,
    input,
    callbacks,
    signal
  )
}
