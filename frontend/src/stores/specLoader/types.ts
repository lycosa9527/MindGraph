/**
 * Shared type definitions for spec loaders
 */
import type { Connection, DiagramNode } from '@/types'

/**
 * Result returned by spec loader functions
 */
export interface SpecLoaderResult {
  nodes: DiagramNode[]
  connections: Connection[]
  metadata?: Record<string, unknown>
}
