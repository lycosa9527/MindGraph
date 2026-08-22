/**
 * pdfjs-dist evaluates `Iterator.prototype.join` at module load.
 * `typeof Iterator.prototype.join` throws when the ES2025 `Iterator` global
 * is missing. Classic `pwa-install-early.js` installs first; this covers
 * Vite / Vitest and any entry that skips that script.
 */

type IteratorHolder = {
  Iterator?: { prototype?: object }
}

function iteratorHolder(target: object): IteratorHolder {
  return target as IteratorHolder
}

function assignIteratorGlobal(ctor: object): void {
  const withProto: { prototype?: object } = ctor
  iteratorHolder(globalThis).Iterator = withProto
  if (typeof window !== 'undefined') {
    iteratorHolder(window).Iterator = withProto
  }
}

export function installIteratorGlobalStub(): void {
  if (typeof iteratorHolder(globalThis).Iterator === 'function') {
    return
  }
  function IteratorCtor(): void {
    throw new TypeError('Abstract class Iterator not directly constructable')
  }
  assignIteratorGlobal(IteratorCtor)
}

installIteratorGlobalStub()
