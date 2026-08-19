/**
 * Official TJCaptcha callback errorCode (Web client).
 * https://cloud.tencent.com/document/product/1110/36841
 */
export const TSEC_FRONTEND_ERROR_CODES: Readonly<Record<number, string>> = {
  1001: 'jsload_error',
  1002: 'captcha_show_timeout',
  1003: 'mid_js_load_timeout',
  1004: 'mid_js_load_error',
  1005: 'mid_js_runtime_error',
  1006: 'get_captcha_config_request_error',
  1007: 'iframe_load_timeout',
  1008: 'iframe_load_error',
  1009: 'jquery_load_error',
  1010: 'slider_js_load_error',
  1011: 'slider_js_runtime_error',
  1012: 'refresh_error_3x',
  1013: 'verify_network_error_3x',
  1085: 'silent_verify_timeout',
}

export function tsecFrontendErrorReason(
  errorCode?: number,
  errorMessage?: string
): string {
  if (errorCode != null && TSEC_FRONTEND_ERROR_CODES[errorCode]) {
    return `tsec_${errorCode}_${TSEC_FRONTEND_ERROR_CODES[errorCode]}`
  }
  const trimmed = (errorMessage || '').trim()
  return trimmed || 'tsec_failed'
}
