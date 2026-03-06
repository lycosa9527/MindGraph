/**
 * LLM Model Colors - Shared color palette for Qwen, DeepSeek, Doubao
 *
 * Used by AIModelSelector and NodePalettePanel for consistent visual identity.
 */
export interface LLMModelColor {
  bg: string
  border: string
  text: string
}

export const LLM_MODEL_COLORS: Record<string, LLMModelColor> = {
  qwen: {
    bg: 'rgba(99, 102, 241, 0.15)',
    border: 'rgba(99, 102, 241, 0.4)',
    text: '#6366f1',
  },
  deepseek: {
    bg: 'rgba(16, 185, 129, 0.15)',
    border: 'rgba(16, 185, 129, 0.4)',
    text: '#10b981',
  },
  doubao: {
    bg: 'rgba(249, 115, 22, 0.15)',
    border: 'rgba(249, 115, 22, 0.4)',
    text: '#f97316',
  },
}

/** Dark mode variants for NodePalettePanel */
export const LLM_MODEL_COLORS_DARK: Record<string, LLMModelColor> = {
  qwen: {
    bg: 'rgba(99, 102, 241, 0.2)',
    border: 'rgba(99, 102, 241, 0.5)',
    text: '#818cf8',
  },
  deepseek: {
    bg: 'rgba(16, 185, 129, 0.2)',
    border: 'rgba(16, 185, 129, 0.5)',
    text: '#34d399',
  },
  doubao: {
    bg: 'rgba(249, 115, 22, 0.2)',
    border: 'rgba(249, 115, 22, 0.5)',
    text: '#fb923c',
  },
}

export function getLLMColor(modelKey: string, isDark = false): LLMModelColor | null {
  const palette = isDark ? LLM_MODEL_COLORS_DARK : LLM_MODEL_COLORS
  return palette[modelKey] ?? null
}
