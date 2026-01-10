/**
 * API Utilities
 * Centralized API calls with authentication support
 *
 * Note: Authentication is now handled via httpOnly cookies (set by backend).
 * The Authorization header is no longer needed - cookies are sent automatically.
 */
import { apiRequest } from './apiClient'

const API_BASE = '/api'

/**
 * Make an authenticated fetch request
 * Uses the new apiClient with automatic token refresh
 */
export async function authFetch(endpoint: string, options: RequestInit = {}): Promise<Response> {
  const url = endpoint.startsWith('/') ? endpoint : `${API_BASE}/${endpoint}`
  return apiRequest(url, options)
}

/**
 * Mind map spec format for backend layout
 */
export interface MindMapSpec {
  topic: string
  children?: MindMapBranchSpec[]
  _layout?: MindMapLayout
  _node_styles?: Record<string, unknown>
  _customPositions?: Record<string, { x: number; y: number }>
}

export interface MindMapBranchSpec {
  text: string
  children?: MindMapBranchSpec[]
}

export interface MindMapLayout {
  positions: Record<string, MindMapNodePosition>
  canvas?: { width: number; height: number }
}

export interface MindMapNodePosition {
  x: number
  y: number
  width?: number
  height?: number
  text?: string
  type?: string
}

/**
 * Recalculate mind map layout using backend MindMapAgent
 * Called when nodes are added/removed to get new positions
 */
export async function recalculateMindMapLayout(
  spec: MindMapSpec
): Promise<{ success: boolean; spec?: MindMapSpec; error?: string }> {
  try {
    const response = await authFetch('/api/recalculate_mindmap_layout', {
      method: 'POST',
      body: JSON.stringify({ spec }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      return {
        success: false,
        error: errorData.detail || `Layout recalculation failed: ${response.status}`,
      }
    }

    const data = await response.json()

    if (data.success && data.spec) {
      return { success: true, spec: data.spec }
    }

    return { success: false, error: 'Invalid response from layout endpoint' }
  } catch (error) {
    console.error('Layout recalculation error:', error)
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Network error',
    }
  }
}

/**
 * Convert diagram store data to mind map spec format for backend
 */
export function diagramDataToMindMapSpec(
  topic: string,
  leftBranches: { text: string; children?: { text: string }[] }[],
  rightBranches: { text: string; children?: { text: string }[] }[]
): MindMapSpec {
  // Combine branches - the backend handles left/right positioning
  const children: MindMapBranchSpec[] = []

  // Add left branches
  leftBranches.forEach((branch) => {
    children.push({
      text: branch.text,
      children: branch.children?.map((c) => ({ text: c.text })),
    })
  })

  // Add right branches
  rightBranches.forEach((branch) => {
    children.push({
      text: branch.text,
      children: branch.children?.map((c) => ({ text: c.text })),
    })
  })

  return { topic, children }
}
