/**
 * Shared Dify health probe helpers for school create/edit admin flows.
 */
import { useLanguage } from '@/composables'
import { apiRequest } from '@/utils/apiClient'

export type DifyHealthStatus = {
  online: boolean
  http_status?: number | null
  error?: string | null
}

export function useSchoolDifyHealthProbe() {
  const { t } = useLanguage()

  function formatDifyAuthError(
    error: string | null | undefined,
    httpStatus?: number | null
  ): string {
    const token = (error ?? '').trim()
    if (token === 'api_key_not_configured') {
      return t('admin.schoolDifyAuthErrorNoKey')
    }
    if (token === 'base_url_not_configured') {
      return t('admin.schoolDifyAuthErrorNoUrl')
    }
    if (token === 'timeout') {
      return t('admin.schoolDifyAuthErrorTimeout')
    }
    if (token === 'network') {
      return t('admin.schoolDifyAuthErrorNetwork')
    }
    if (token.startsWith('http_401') || httpStatus === 401) {
      return t('admin.schoolDifyAuthErrorUnauthorized')
    }
    if (token.startsWith('http_403') || httpStatus === 403) {
      return t('admin.schoolDifyAuthErrorForbidden')
    }
    if (token.startsWith('http_404') || httpStatus === 404) {
      return t('admin.schoolDifyAuthErrorNotFound')
    }
    if (token.startsWith('http_')) {
      return t('admin.schoolDifyAuthErrorHttp', { detail: token })
    }
    if (token && token !== 'validation_failed') {
      return t('admin.schoolDifyAuthErrorDetail', { detail: token })
    }
    return t('admin.schoolDifyAuthTestFailed')
  }

  function isDifyAuthPassing(status: DifyHealthStatus | null): boolean {
    if (!status?.online) {
      return false
    }
    return status.error !== 'api_key_not_configured'
  }

  async function probeDraft(
    difyUrl: string,
    difyKey: string
  ): Promise<{ status: DifyHealthStatus; ok: boolean }> {
    const body: Record<string, string> = {}
    const url = difyUrl.trim()
    const key = difyKey.trim()
    if (url) {
      body.dify_api_base_url = url
    }
    if (key) {
      body.dify_api_key = key
    }
    const res = await apiRequest('/api/auth/admin/mindmate-dify-health-draft', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const data = (await res.json().catch(() => ({}))) as { detail?: string }
      const detail =
        typeof data.detail === 'string' && data.detail.trim()
          ? data.detail.trim()
          : `http_${res.status}`
      const status: DifyHealthStatus = {
        online: false,
        error: detail,
        http_status: res.status,
      }
      return { status, ok: false }
    }
    const status = (await res.json()) as DifyHealthStatus
    return { status, ok: isDifyAuthPassing(status) }
  }

  return {
    formatDifyAuthError,
    isDifyAuthPassing,
    probeDraft,
  }
}
