/**
 * Maite learning map / graph API.
 */
import type { MaiteGraphResponse } from '@/types/maite'

import { maiteRequestJson } from './client'

export async function getGraph(): Promise<MaiteGraphResponse> {
  return maiteRequestJson<MaiteGraphResponse>('/graph')
}
