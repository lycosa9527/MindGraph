import { afterEach, describe, expect, it } from 'vitest'

import { installIteratorHelpersPolyfill, iteratorFrom } from '@/utils/iteratorHelpersPolyfill'

type IteratorHolder = { Iterator?: { from: typeof iteratorFrom } }

function iteratorGlobal(): IteratorHolder {
  return globalThis as IteratorHolder
}

describe('iteratorHelpersPolyfill', () => {
  const nativeIterator = iteratorGlobal().Iterator

  afterEach(() => {
    if (nativeIterator === undefined) {
      delete iteratorGlobal().Iterator
    } else {
      iteratorGlobal().Iterator = nativeIterator
    }
  })

  it('installs Iterator.from when the global is missing', () => {
    delete iteratorGlobal().Iterator
    installIteratorHelpersPolyfill()
    const ctor = iteratorGlobal().Iterator
    expect(typeof ctor?.from).toBe('function')
    expect([...(ctor as { from: typeof iteratorFrom }).from([1, 2, 3])]).toEqual([1, 2, 3])
  })

  it('maps and filters through the helper wrapper', () => {
    const doubled = iteratorFrom([1, 2, 3, 4])
      .filter((value) => value % 2 === 0)
      .map((value) => value * 10)
      .toArray()
    expect(doubled).toEqual([20, 40])
  })

  it('wraps a raw iterator object', () => {
    const raw = [7, 8][Symbol.iterator]()
    expect(iteratorFrom(raw).toArray()).toEqual([7, 8])
  })

  it('rejects non-iterables', () => {
    expect(() => iteratorFrom(null as unknown as Iterable<number>)).toThrow(TypeError)
  })

  it('is a no-op when Iterator already exists', () => {
    installIteratorHelpersPolyfill()
    const first = iteratorGlobal().Iterator
    installIteratorHelpersPolyfill()
    expect(iteratorGlobal().Iterator).toBe(first)
  })
})
