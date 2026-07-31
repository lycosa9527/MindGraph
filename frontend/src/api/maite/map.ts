/**
 * Maite learning map / graph API.
 */
import { maiteRequestJson } from './client'

import type { MaiteGraphResponse } from '@/types/maite'

export async function getGraph(): Promise<MaiteGraphResponse> {
  return maiteRequestJson<MaiteGraphResponse>('/graph')
}
