/**
 * Minimal LaTeX-ish math text to Unicode for Maite display.
 */

const SUPERSCRIPT_MAP: Record<string, string> = {
  '0': '⁰',
  '1': '¹',
  '2': '²',
  '3': '³',
  '4': '⁴',
  '5': '⁵',
  '6': '⁶',
  '7': '⁷',
  '8': '⁸',
  '9': '⁹',
  '+': '⁺',
  '-': '⁻',
  '=': '⁼',
  '(': '⁽',
  ')': '⁾',
  n: 'ⁿ',
}

const SUBSCRIPT_MAP: Record<string, string> = {
  '0': '₀',
  '1': '₁',
  '2': '₂',
  '3': '₃',
  '4': '₄',
  '5': '₅',
  '6': '₆',
  '7': '₇',
  '8': '₈',
  '9': '₉',
  '+': '₊',
  '-': '₋',
  '=': '₌',
  '(': '₍',
  ')': '₎',
}

const SYMBOL_MAP: Record<string, string> = {
  alpha: 'α',
  beta: 'β',
  gamma: 'γ',
  delta: 'δ',
  epsilon: 'ε',
  theta: 'θ',
  lambda: 'λ',
  mu: 'μ',
  pi: 'π',
  sigma: 'σ',
  phi: 'φ',
  omega: 'ω',
  Delta: 'Δ',
  Sigma: 'Σ',
  Omega: 'Ω',
  times: '×',
  cdot: '·',
  div: '÷',
  pm: '±',
  leq: '≤',
  geq: '≥',
  neq: '≠',
  approx: '≈',
  infty: '∞',
  sqrt: '√',
  degree: '°',
}

function toSuperscript(content: string): string {
  return [...content].map((char) => SUPERSCRIPT_MAP[char] ?? char).join('')
}

function toSubscript(content: string): string {
  return [...content].map((char) => SUBSCRIPT_MAP[char] ?? char).join('')
}

function replaceSymbols(text: string): string {
  let result = text
  for (const [key, value] of Object.entries(SYMBOL_MAP)) {
    result = result.replaceAll(`\\${key}`, value)
  }
  return result
}

function replaceFractions(text: string): string {
  return text.replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, '($1)/($2)')
}

function replaceSqrt(text: string): string {
  return text.replace(/\\sqrt\{([^}]+)\}/g, '√($1)')
}

function replaceScripts(text: string): string {
  let result = text
  result = result.replace(/\^\{([^}]+)\}/g, (_, content: string) => toSuperscript(content))
  result = result.replace(/\^([0-9a-zA-Z+-])/g, (_, content: string) => toSuperscript(content))
  result = result.replace(/_\{([^}]+)\}/g, (_, content: string) => toSubscript(content))
  result = result.replace(/_([0-9a-zA-Z+-])/g, (_, content: string) => toSubscript(content))
  return result
}

function stripMathDelimiters(text: string): string {
  return text
    .replace(/\$\$/g, '')
    .replace(/\$/g, '')
    .replace(/\\\(/g, '')
    .replace(/\\\)/g, '')
    .replace(/\\\[/g, '')
    .replace(/\\\]/g, '')
}

/**
 * Convert a small subset of LaTeX math markup to readable Unicode text.
 */
export function renderMathText(input: string): string {
  if (!input) {
    return ''
  }
  let text = stripMathDelimiters(input)
  text = replaceFractions(text)
  text = replaceSqrt(text)
  text = replaceSymbols(text)
  text = replaceScripts(text)
  return text.replace(/\s+/g, ' ').trim()
}
