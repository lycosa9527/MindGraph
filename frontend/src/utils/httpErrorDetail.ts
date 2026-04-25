/**
 * Normalize FastAPI-style JSON error bodies for display (string or validation array).
 */
export function httpErrorDetail(data: unknown): string {
  if (!data || typeof data !== 'object' || !('detail' in data)) {
    return ''
  }
  const detail = (data as { detail: unknown }).detail
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) {
          return String((item as { msg: unknown }).msg)
        }
        return JSON.stringify(item)
      })
      .join('; ')
  }
  return String(detail)
}
