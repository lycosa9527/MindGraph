/**
 * Dify conversation routing query params (web vs bound MindBot identity).
 */

export interface DifyConversationRouteParams {
  difyUser?: string
  server?: number
  mindbotConfigId?: number | null
}

export function buildDifyConversationRouteSearchParams(
  route?: DifyConversationRouteParams,
  base?: URLSearchParams
): URLSearchParams {
  const params = base ? new URLSearchParams(base) : new URLSearchParams()
  const difyUser = route?.difyUser?.trim()
  if (difyUser) {
    params.set('dify_user', difyUser)
  }
  if (typeof route?.server === 'number' && route.server >= 1) {
    params.set('server', String(route.server))
  }
  if (typeof route?.mindbotConfigId === 'number' && route.mindbotConfigId >= 1) {
    params.set('mindbot_config_id', String(route.mindbotConfigId))
  }
  return params
}

export function difyConversationRouteQuerySuffix(route?: DifyConversationRouteParams): string {
  const query = buildDifyConversationRouteSearchParams(route).toString()
  return query ? `&${query}` : ''
}

export function appendDifyConversationRouteQuery(
  url: string,
  route?: DifyConversationRouteParams
): string {
  const query = buildDifyConversationRouteSearchParams(route).toString()
  if (!query) {
    return url
  }
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}${query}`
}
