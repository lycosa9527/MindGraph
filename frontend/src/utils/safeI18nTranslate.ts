/**
 * vue-i18n JIT compile throws SyntaxError (numeric code in production) on
 * malformed `{…}` / `@:` in a message. Keep the UI up instead of rejecting.
 *
 * Production ``SyntaxError: 26`` is *not* a compile error — it is
 * ``MUST_BE_CALL_SETUP_TOP`` from ``useI18n()``. Fix that in ``useLanguage``.
 */
export function safeI18nTranslate(
  translate: (key: string, named?: Record<string, unknown>) => unknown,
  key: string,
  second?: string | Record<string, unknown>
): string {
  try {
    if (second === undefined) {
      return String(translate(key))
    }
    if (typeof second === 'string') {
      const result = translate(key)
      if (result === key) return second
      return String(result)
    }
    return String(translate(key, second))
  } catch {
    return typeof second === 'string' ? second : key
  }
}
