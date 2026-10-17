/**
 * Pages whose useful content is session-gated files, not public HTML.
 * The canvas URL fetch cannot see those files; the extension lists them and
 * saves the extracted markdown.
 */

const FILE_EXTRACT_HOST_SUFFIXES = ['smartedu.cn', 'cnki.net', 'wenku.baidu.com'] as const

export function urlRequiresBrowserFileExtract(raw: string): boolean {
  const trimmed = raw.trim()
  if (!trimmed) return false
  let host = ''
  try {
    host = new URL(trimmed).hostname.toLowerCase().replace(/\.$/, '')
  } catch {
    return false
  }
  return FILE_EXTRACT_HOST_SUFFIXES.some((suffix) => host === suffix || host.endsWith(`.${suffix}`))
}
