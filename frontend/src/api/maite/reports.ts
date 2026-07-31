/**
 * Maite session report API.
 */
import { maiteRequestJson } from './client'

import type { MaiteReport } from '@/types/maite'

export async function getSessionReport(sessionId: number): Promise<MaiteReport> {
  return maiteRequestJson<MaiteReport>(`/reports/${sessionId}`)
}
