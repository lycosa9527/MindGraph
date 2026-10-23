/** Runtime check for a value the caller already treats as present. */
export function must<T>(value: T | null | undefined): T {
  if (value == null) {
    throw new Error('expected a value')
  }
  return value
}
