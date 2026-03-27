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
    case 'zh-tw':
      return (await import('element-plus/es/locale/lang/zh-tw')).default
    case 'en':
      return (await import('element-plus/es/locale/lang/en')).default
    case 'az':
      return (await import('element-plus/es/locale/lang/az')).default
    case 'th':
      return (await import('element-plus/es/locale/lang/th')).default
    case 'fr':
      return (await import('element-plus/es/locale/lang/fr')).default
    case 'de':
      return (await import('element-plus/es/locale/lang/de')).default
    case 'ja':
      return (await import('element-plus/es/locale/lang/ja')).default
    case 'ko':
      return (await import('element-plus/es/locale/lang/ko')).default
    case 'pt':
      return (await import('element-plus/es/locale/lang/pt-br')).default
    case 'ru':
      return (await import('element-plus/es/locale/lang/ru')).default
    case 'ar':
      return (await import('element-plus/es/locale/lang/ar')).default
    case 'nl':
      return (await import('element-plus/es/locale/lang/nl')).default
    case 'it':
      return (await import('element-plus/es/locale/lang/it')).default
    case 'hi':
      return (await import('element-plus/es/locale/lang/hi')).default
    case 'id':
      return (await import('element-plus/es/locale/lang/id')).default
    case 'vi':
      return (await import('element-plus/es/locale/lang/vi')).default
    case 'tr':
      return (await import('element-plus/es/locale/lang/tr')).default
    case 'pl':
      return (await import('element-plus/es/locale/lang/pl')).default
    case 'uk':
      return (await import('element-plus/es/locale/lang/uk')).default
    case 'ms':
      return (await import('element-plus/es/locale/lang/ms')).default
    case 'es':
      return (await import('element-plus/es/locale/lang/es')).default
    case 'sv':
      return (await import('element-plus/es/locale/lang/sv')).default
    case 'da':
      return (await import('element-plus/es/locale/lang/da')).default
    case 'fi':
      return (await import('element-plus/es/locale/lang/fi')).default
    case 'no':
      return (await import('element-plus/es/locale/lang/no')).default
    case 'cs':
      return (await import('element-plus/es/locale/lang/cs')).default
    case 'ro':
      return (await import('element-plus/es/locale/lang/ro')).default
    case 'el':
      return (await import('element-plus/es/locale/lang/el')).default
    case 'he':
      return (await import('element-plus/es/locale/lang/he')).default
    case 'fa':
      return (await import('element-plus/es/locale/lang/fa')).default
    case 'sw':
      return (await import('element-plus/es/locale/lang/sw')).default
    case 'tl':
      return (await import('element-plus/es/locale/lang/en')).default
    case 'bn':
      return (await import('element-plus/es/locale/lang/bn')).default
    case 'ta':
      return (await import('element-plus/es/locale/lang/ta')).default
    case 'ca':
      return (await import('element-plus/es/locale/lang/ca')).default
    case 'bg':
      return (await import('element-plus/es/locale/lang/bg')).default
    case 'hr':
      return (await import('element-plus/es/locale/lang/hr')).default
    case 'hu':
      return (await import('element-plus/es/locale/lang/hu')).default
    case 'hy':
      return (await import('element-plus/es/locale/lang/hy-am')).default
    case 'am':
      return (await import('element-plus/es/locale/lang/en')).default
    case 'ka':
      return (await import('element-plus/es/locale/lang/en')).default
    case 'km':
      return (await import('element-plus/es/locale/lang/km')).default
    case 'kk':
      return (await import('element-plus/es/locale/lang/kk')).default
    case 'ky':
      return (await import('element-plus/es/locale/lang/ky')).default
    case 'lo':
      return (await import('element-plus/es/locale/lang/lo')).default
    case 'mn':
      return (await import('element-plus/es/locale/lang/mn')).default
    case 'my':
      return (await import('element-plus/es/locale/lang/my')).default
    case 'ne':
      return (await import('element-plus/es/locale/lang/en')).default
    case 'si':
      return (await import('element-plus/es/locale/lang/en')).default
    case 'sr':
      return (await import('element-plus/es/locale/lang/sr')).default
    case 'tg':
      return (await import('element-plus/es/locale/lang/en')).default
    case 'tk':
      return (await import('element-plus/es/locale/lang/tk')).default
    case 'ug':
      return (await import('element-plus/es/locale/lang/ug-cn')).default
    case 'ur':
      return (await import('element-plus/es/locale/lang/en')).default
    case 'uz':
      return (await import('element-plus/es/locale/lang/uz-uz')).default
    case 'af':
      return (await import('element-plus/es/locale/lang/af')).default
    case 'ha':
    case 'ig':
    case 'so':
    case 'ss':
    case 'st':
    case 'tn':
    case 'xh':
    case 'yo':
    case 'zu':
      return (await import('element-plus/es/locale/lang/en')).default
    default:
      return (await import('element-plus/es/locale/lang/en')).default
  }
}
