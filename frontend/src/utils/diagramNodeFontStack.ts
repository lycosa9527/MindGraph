/**
 * Diagram node text: multiscript stack (system UI first, then Noto families from Fontsource).
 * Lazy @font-face rules load per prompt language; family names must match Fontsource metadata.
 */
/**
 * Product UI: Inter (global) + Noto (Fontsource) + system CJK fallbacks.
 * For compact surfaces (e.g. quick registration) where a single refined stack
 * is preferable to generic ui-sans-serif.
 */
export const APP_REFINED_SANS_STACK =
  "'Inter', 'Noto Sans', 'Noto Sans SC', 'Noto Sans TC', 'Segoe UI', " +
  "'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', system-ui, sans-serif"

export const MULTISCRIPT_SANS_STACK =
  "'Inter', 'Segoe UI', 'Noto Sans', 'Noto Sans SC', 'Noto Sans TC', 'PingFang SC', " +
  "'Microsoft YaHei', 'SimSun', 'Noto Sans Arabic', 'Noto Sans Hebrew', 'Noto Sans Devanagari', " +
  "'Noto Sans Bengali', 'Noto Sans Gurmukhi', 'Noto Sans Gujarati', 'Noto Sans Oriya', " +
  "'Noto Sans Tamil', 'Noto Sans Telugu', 'Noto Sans Malayalam', 'Noto Sans Kannada', " +
  "'Noto Sans Sinhala', 'Noto Sans Thai', 'Noto Sans Lao', 'Noto Sans Khmer', 'Noto Sans Myanmar', " +
  "'Noto Sans Georgian', 'Noto Sans Armenian', 'Noto Sans Ethiopic', 'Noto Serif Tibetan', " +
  "'Noto Sans JP', 'Noto Sans KR', 'Noto Sans Ol Chiki', 'Noto Sans Meetei Mayek', " +
  "'Segoe UI Symbol', system-ui, sans-serif"

export const DIAGRAM_NODE_FONT_STACK = MULTISCRIPT_SANS_STACK
