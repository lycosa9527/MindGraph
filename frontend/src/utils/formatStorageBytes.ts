const BYTES_PER_KIB = 1024
const BYTES_PER_MIB = BYTES_PER_KIB ** 2
const BYTES_PER_GIB = BYTES_PER_KIB ** 3

function formatScaled(value: number, unit: string): string {
  if (value >= 100 || Number.isInteger(value)) {
    return `${Math.round(value)} ${unit}`
  }
  return `${value.toFixed(1)} ${unit}`
}

/** Human-readable storage size (B / KB / MB / GB). */
export function formatStorageBytes(bytes: number): string {
  const safe = Math.max(0, bytes)
  if (safe < BYTES_PER_KIB) {
    return `${safe} B`
  }
  if (safe < BYTES_PER_MIB) {
    return formatScaled(safe / BYTES_PER_KIB, 'KB')
  }
  if (safe < BYTES_PER_GIB) {
    return formatScaled(safe / BYTES_PER_MIB, 'MB')
  }
  return formatScaled(safe / BYTES_PER_GIB, 'GB')
}

/** Remaining storage — floors GB to 0.1 when usage is non-zero so it stays below the limit. */
export function formatStorageRemainingBytes(remainingBytes: number, usedBytes: number): string {
  const remaining = Math.max(0, remainingBytes)
  if (usedBytes <= 0) {
    return formatStorageBytes(remaining)
  }
  if (remaining >= BYTES_PER_GIB) {
    const gb = remaining / BYTES_PER_GIB
    const floored = Math.floor(gb * 10) / 10
    if (floored >= 10) {
      return `${Math.round(floored)} GB`
    }
    return `${floored.toFixed(1)} GB`
  }
  return formatStorageBytes(remaining)
}
