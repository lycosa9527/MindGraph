/**
 * Maite diagnosis API.
 */
import { maiteRequestJson } from './client'

import type { MaiteDiagnosisStageResult } from '@/types/maite'

export interface DiagnosisStageInput {
  student_input?: string
}

export interface DiagnosisInteractionInput {
  selected_source_rows?: string[]
  student_input?: string
}

export interface DiagnosisStageFourEvaluateInput {
  student_input?: string
  variant_text?: string
}

export async function diagnoseAuto(
  sessionId: number,
  input: DiagnosisStageInput = {}
): Promise<MaiteDiagnosisStageResult> {
  return maiteRequestJson<MaiteDiagnosisStageResult>(
    `/inquiry/${sessionId}/diagnose/auto`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    }
  )
}

export async function diagnoseStage1(
  sessionId: number,
  input: DiagnosisStageInput = {}
): Promise<MaiteDiagnosisStageResult> {
  return maiteRequestJson<MaiteDiagnosisStageResult>(
    `/inquiry/${sessionId}/diagnose/stage-1`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    }
  )
}

export async function diagnoseStage2Interaction(
  sessionId: number,
  input: DiagnosisInteractionInput
): Promise<MaiteDiagnosisStageResult> {
  return maiteRequestJson<MaiteDiagnosisStageResult>(
    `/inquiry/${sessionId}/diagnose/stage-2/interactions`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    }
  )
}

export async function diagnoseStage3Interaction(
  sessionId: number,
  input: DiagnosisInteractionInput
): Promise<MaiteDiagnosisStageResult> {
  return maiteRequestJson<MaiteDiagnosisStageResult>(
    `/inquiry/${sessionId}/diagnose/stage-3/interactions`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    }
  )
}

export async function diagnoseStage4GenerateVariant(
  sessionId: number
): Promise<Record<string, unknown>> {
  return maiteRequestJson<Record<string, unknown>>(
    `/inquiry/${sessionId}/diagnose/stage-4/generate-variant`,
    {
      method: 'POST',
      body: JSON.stringify({}),
    }
  )
}

export async function diagnoseStage4Evaluate(
  sessionId: number,
  input: DiagnosisStageFourEvaluateInput
): Promise<Record<string, unknown>> {
  return maiteRequestJson<Record<string, unknown>>(
    `/inquiry/${sessionId}/diagnose/stage-4/evaluate`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    }
  )
}

export async function diagnoseFinalize(
  sessionId: number,
  finalBlockReport: Record<string, unknown>[] = []
): Promise<Record<string, unknown>> {
  return maiteRequestJson<Record<string, unknown>>(
    `/inquiry/${sessionId}/diagnose/finalize`,
    {
      method: 'POST',
      body: JSON.stringify({ final_block_report: finalBlockReport }),
    }
  )
}
