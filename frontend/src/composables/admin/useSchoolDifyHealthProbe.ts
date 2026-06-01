/**
 * Shared Dify health probe helpers for school create/edit admin flows.
 */
import { useLanguage } from '@/composables'
import { useProbeAdminMindmateDifyHealthDraft } from '@/composables/queries'

export type DifyHealthStatus = {
  online: boolean
  http_status?: number | null
  error?: string | null
}

export function useSchoolDifyHealthProbe() {
  const { t } = useLanguage()
  const probeMutation = useProbeAdminMindmateDifyHealthDraft()

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
    return t('admin.schoolDifyAuthErrorTestFailed')
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
    try {
      const status = (await probeMutation.mutateAsync(body)) as DifyHealthStatus
      return { status, ok: isDifyAuthPassing(status) }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      const status: DifyHealthStatus = {
        online: false,
        error: message,
      }
      return { status, ok: false }
    }
  }

  return {
    formatDifyAuthError,
    isDifyAuthPassing,
    probeDraft,
  }
}
