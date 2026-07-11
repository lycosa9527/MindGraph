/**
 * App-level QueryClient holder for use outside Vue setup/injection context
 * (Pinia actions, async auth callbacks).
 */
import type { QueryClient } from '@tanstack/vue-query'

let appQueryClient: QueryClient | null = null

export function setAppQueryClient(client: QueryClient): void {
  appQueryClient = client
}

export function getAppQueryClient(): QueryClient | null {
  return appQueryClient
}
