/**
 * Utils Index
 */

export {
  getBorderStyleProps,
  resolveBorderStyle,
  type BorderStyleType,
  type BorderStyleOptions,
} from './borderStyleUtils'

// API utilities
export {
  authFetch,
  recalculateMindMapLayout,
  diagramDataToMindMapSpec,
  type MindMapSpec,
  type MindMapBranchSpec,
  type MindMapLayout,
  type MindMapNodePosition,
} from './api'

// New API client with automatic token refresh
export {
  apiRequest,
  apiGet,
  apiPost,
  apiPut,
  apiDelete,
  apiPatch,
  apiUpload,
  default as apiClient,
} from './apiClient'
