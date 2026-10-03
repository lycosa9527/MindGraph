/**
 * Keep a bilingual `secondary` mirror aligned when diagram operations edit
 * the primary spec arrays. Mono specs have no mirror and are left unchanged.
 */

function mirrorOf(spec: Record<string, unknown>): Record<string, unknown> | null {
  const raw = spec.secondary
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  return raw as Record<string, unknown>
}

function writeLabel(item: Record<string, unknown>, text: string): void {
  if ('name' in item && !('text' in item)) {
    item.name = text
    return
  }
  if ('step' in item && !('text' in item)) {
    item.step = text
    return
  }
  item.text = text
}

function writeGloss(item: Record<string, unknown>, gloss: string): void {
  if ('name' in item && !('text' in item)) {
    item.name = gloss
    return
  }
  if ('step' in item && !('text' in item)) {
    item.step = gloss
    return
  }
  item.text = gloss
}

/** Write `textSecondary` onto an object node. Undefined leaves the gloss alone. */
export function writeNodeGloss(
  item: Record<string, unknown>,
  textSecondary: string | undefined
): void {
  if (textSecondary === undefined) return
  const trimmed = textSecondary.trim()
  if (trimmed) {
    item.textSecondary = trimmed
    return
  }
  delete item.textSecondary
}

export function writeMirrorScalar(
  spec: Record<string, unknown>,
  key: string,
  textSecondary: string | undefined
): void {
  if (textSecondary === undefined) return
  const mirror = mirrorOf(spec)
  if (!mirror) return
  mirror[key] = textSecondary.trim()
}

export function writeMirrorIndex(
  spec: Record<string, unknown>,
  field: string,
  index: number,
  textSecondary: string | undefined
): void {
  if (textSecondary === undefined) return
  const mirror = mirrorOf(spec)
  const arr = mirror?.[field]
  if (!Array.isArray(arr) || index < 0 || index >= arr.length) return
  const gloss = textSecondary.trim()
  const current = arr[index]
  if (current && typeof current === 'object') {
    writeGloss(current as Record<string, unknown>, gloss)
    return
  }
  arr[index] = gloss
}

/** Push an empty gloss so a new primary slot does not shift later translations. */
export function padMirrorStringList(spec: Record<string, unknown>, field: string): void {
  const arr = mirrorOf(spec)?.[field]
  if (!Array.isArray(arr)) return
  if (arr.some((item) => item && typeof item === 'object')) return
  arr.push('')
}

export function spliceMirrorList(
  spec: Record<string, unknown>,
  field: string,
  index: number
): void {
  const arr = mirrorOf(spec)?.[field]
  if (!Array.isArray(arr) || index < 0 || index >= arr.length) return
  arr.splice(index, 1)
}

/**
 * Update one array slot. Object entries keep their shape (`text` / `name` / `step`
 * plus `textSecondary`). String entries stay strings; the gloss goes on the mirror.
 */
export function applySpecArrayText(
  spec: Record<string, unknown>,
  field: string,
  index: number,
  text: string,
  textSecondary: string | undefined
): void {
  const arr = spec[field]
  if (!Array.isArray(arr) || index < 0 || index >= arr.length) return
  const current = arr[index]
  if (current && typeof current === 'object') {
    const item = current as Record<string, unknown>
    writeLabel(item, text)
    writeNodeGloss(item, textSecondary)
  } else {
    arr[index] = text
  }
  writeMirrorIndex(spec, field, index, textSecondary)
}
