import { TJ_CAPTCHA_SRC, type TencentCaptchaConstructor } from '@/types/tsecCaptcha'

let loadPromise: Promise<TencentCaptchaConstructor> | null = null

export function loadTjCaptcha(): Promise<TencentCaptchaConstructor> {
  if (window.TencentCaptcha) {
    return Promise.resolve(window.TencentCaptcha)
  }
  if (loadPromise) {
    return loadPromise
  }

  loadPromise = new Promise<TencentCaptchaConstructor>((resolve, reject) => {
    const existing = document.querySelector(`script[src="${TJ_CAPTCHA_SRC}"]`)
    if (existing) {
      existing.addEventListener(
        'load',
        () => {
          if (window.TencentCaptcha) {
            resolve(window.TencentCaptcha)
            return
          }
          reject(new Error('jsload_error'))
        },
        { once: true }
      )
      existing.addEventListener('error', () => reject(new Error('jsload_error')), { once: true })
      return
    }

    const script = document.createElement('script')
    script.src = TJ_CAPTCHA_SRC
    script.async = true
    script.onload = () => {
      if (window.TencentCaptcha) {
        resolve(window.TencentCaptcha)
        return
      }
      reject(new Error('jsload_error'))
    }
    script.onerror = () => reject(new Error('jsload_error'))
    document.head.appendChild(script)
  }).finally(() => {
    if (!window.TencentCaptcha) {
      loadPromise = null
    }
  })

  return loadPromise
}

export function tsecUserLanguage(uiLocale: string): string {
  const normalized = uiLocale.toLowerCase().replace('_', '-')
  if (normalized === 'zh' || normalized.startsWith('zh-cn') || normalized.startsWith('zh-hans')) {
    return 'zh-cn'
  }
  if (normalized.startsWith('zh-tw') || normalized.startsWith('zh-hk') || normalized.startsWith('zh-hant')) {
    return 'zh-tw'
  }
  return 'en'
}
