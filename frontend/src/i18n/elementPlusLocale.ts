/**
 * Element Plus locale objects — lazy-loaded to avoid bloating initial chunk.
 * For RTL UI locales, also load `element-plus/theme-chalk/dark/css-vars.css` as needed
 * and mirror layout in CSS; Element Plus 2.x follows `document.documentElement.dir`.
 */
import type { Language } from 'element-plus/es/locale'

export async function loadElementPlusLocale(code: string): Promise<Language> {
  switch (code) {
    case 'zh':
      return (await import('element-plus/es/locale/lang/zh-cn')).default
    case 'en':
      return (await import('element-plus/es/locale/lang/en')).default
    case 'az':
      return (await import('element-plus/es/locale/lang/az')).default
    default:
      return (await import('element-plus/es/locale/lang/en')).default
  }
}
