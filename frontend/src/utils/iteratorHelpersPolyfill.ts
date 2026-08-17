/**
 * ES2025 `Iterator` helpers are missing in WeChat / older iOS / Android WebViews.
 * Oxc does not lower Iterator helpers, so `build.target` cannot rewrite
 * `Iterator.from(...)` emitted in a route chunk. Install the global instead.
 */

type IteratorLike<T> = Iterable<T> | { next: () => IteratorResult<T> }

type HelperIterator<T> = IterableIterator<T> & {
  map<U>(mapper: (value: T, index: number) => U): HelperIterator<U>
  filter(predicate: (value: T, index: number) => boolean): HelperIterator<T>
  toArray(): T[]
  forEach(fn: (value: T, index: number) => void): void
}

type IteratorGlobal = {
  from: typeof iteratorFrom
}

function isIterable<T>(value: unknown): value is Iterable<T> {
  return value != null && typeof (value as Iterable<T>)[Symbol.iterator] === 'function'
}

function isIteratorLike<T>(value: unknown): value is { next: () => IteratorResult<T> } {
  return value != null && typeof (value as { next?: unknown }).next === 'function'
}

function wrap<T>(source: { next: () => IteratorResult<T> }): HelperIterator<T> {
  const iterable: HelperIterator<T> = {
    next: () => source.next(),
    [Symbol.iterator]() {
      return iterable
    },
    map<U>(mapper: (value: T, index: number) => U) {
      let index = 0
      return wrap({
        next() {
          const step = source.next()
          if (step.done) return step
          const value = mapper(step.value, index)
          index += 1
          return { value, done: false }
        },
      })
    },
    filter(predicate: (value: T, index: number) => boolean) {
      let index = 0
      return wrap({
        next() {
          let step = source.next()
          while (!step.done && !predicate(step.value, index)) {
            index += 1
            step = source.next()
          }
          if (!step.done) index += 1
          return step
        },
      })
    },
    toArray() {
      return [...iterable]
    },
    forEach(fn: (value: T, index: number) => void) {
      let index = 0
      for (const value of iterable) {
        fn(value, index)
        index += 1
      }
    },
  }
  return iterable
}

export function iteratorFrom<T>(obj: IteratorLike<T>): HelperIterator<T> {
  if (isIterable<T>(obj)) {
    return wrap(obj[Symbol.iterator]())
  }
  if (isIteratorLike<T>(obj)) {
    return wrap(obj)
  }
  throw new TypeError('Iterator.from requires an iterable or iterator')
}

export function installIteratorHelpersPolyfill(): void {
  const globalObject = globalThis as typeof globalThis & { Iterator?: IteratorGlobal }
  if (typeof globalObject.Iterator === 'function') {
    return
  }
  function IteratorCtor(): void {
    throw new TypeError('Abstract class Iterator not directly constructable')
  }
  IteratorCtor.from = iteratorFrom
  globalObject.Iterator = IteratorCtor
}

installIteratorHelpersPolyfill()
