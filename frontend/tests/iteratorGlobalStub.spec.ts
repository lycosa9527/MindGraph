import { afterEach, describe, expect, it } from 'vitest'

import { installIteratorGlobalStub } from '@/utils/iteratorGlobalStub'

type IteratorHolder = { Iterator?: { prototype?: { join?: (sep: string) => string } } }

function iteratorGlobal(): IteratorHolder {
  return globalThis as IteratorHolder
}

describe('iteratorGlobalStub', () => {
  const nativeIterator = iteratorGlobal().Iterator

  afterEach(() => {
    if (nativeIterator === undefined) {
      delete iteratorGlobal().Iterator
    } else {
      iteratorGlobal().Iterator = nativeIterator
    }
  })

  it('installs a constructable-looking Iterator when the global is missing', () => {
    delete iteratorGlobal().Iterator
    installIteratorGlobalStub()
    const ctor = iteratorGlobal().Iterator
    expect(typeof ctor).toBe('function')
    expect(ctor?.prototype).toBeTruthy()
  })

  it('lets pdfjs attach Iterator.prototype.join', () => {
    delete iteratorGlobal().Iterator
    installIteratorGlobalStub()
    const proto = iteratorGlobal().Iterator?.prototype
    expect(proto).toBeTruthy()
    if (!proto) {
      return
    }
    proto.join = function join(this: Iterable<unknown>, separator: string): string {
      return [...this].join(separator)
    }
    expect(proto.join.call(['a', 'b'], ',')).toBe('a,b')
  })

  it('is a no-op when Iterator already exists', () => {
    installIteratorGlobalStub()
    const first = iteratorGlobal().Iterator
    installIteratorGlobalStub()
    expect(iteratorGlobal().Iterator).toBe(first)
  })

  it('mirrors the constructor onto window when present', () => {
    delete iteratorGlobal().Iterator
    installIteratorGlobalStub()
    expect((window as IteratorHolder).Iterator).toBe(iteratorGlobal().Iterator)
  })
})
