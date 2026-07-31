/**
 * Maite problem and OCR API.
 */
import { apiUpload } from '@/utils/apiClient'

import { maiteRequestJson } from './client'

import type { MaiteOcrResult, MaiteProblem, MaiteProblemBankItem } from '@/types/maite'

export interface CreateProblemInput {
  raw_text: string
  clean_text?: string
  source_type?: string
  subject?: string
  grade_level?: string | null
  topic_tags?: string[]
  difficulty?: string | null
  image_url?: string | null
}

export async function createProblem(input: CreateProblemInput): Promise<MaiteProblem> {
  return maiteRequestJson<MaiteProblem>('/problems', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function ocrProblem(file: File): Promise<MaiteOcrResult> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiUpload('/api/maite/problems/ocr', formData)
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail =
      payload && typeof payload === 'object' && 'detail' in payload
        ? String((payload as { detail: unknown }).detail)
        : response.statusText
    throw new Error(detail)
  }
  return response.json() as Promise<MaiteOcrResult>
}

export async function getProblemBank(): Promise<MaiteProblemBankItem[]> {
  return maiteRequestJson<MaiteProblemBankItem[]>('/problem-bank')
}
