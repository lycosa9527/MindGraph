/**
 * Maite session report API.
 */
import type { MaiteReport } from '@/types/maite'

import { maiteRequestJson } from './client'

export async function getSessionReport(sessionId: number): Promise<MaiteReport> {
  return maiteRequestJson<MaiteReport>(`/reports/${sessionId}`)
}
