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
export { authFetch } from './api'

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
