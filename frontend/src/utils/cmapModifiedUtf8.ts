/**
 * JVM "Modified UTF-8" (Java serialization STRING payloads are length-prefixed byte runs).
 */

export function decodeJavaModifiedUtf8(input: Uint8Array): string {
  const units16: number[] = []
  let index = 0
  while (index < input.length) {
    const byte1 = input[index]
    index += 1
    if (byte1 === undefined) {
      break
    }
    if ((byte1 & 0x80) === 0) {
      units16.push(byte1)
      continue
    }
    if ((byte1 & 0xe0) === 0xc0 && index < input.length) {
      const byte2 = input[index] ?? 0
      index += 1
      if ((byte2 & 0xc0) !== 0x80) {
        units16.push(0xfffd)
        continue
      }
      if (byte1 === 0xc0 && byte2 === 0x80) {
        units16.push(0)
        continue
      }
      const unit = ((byte1 & 0x1f) << 6) | (byte2 & 0x3f)
      if (unit < 0x80) {
        units16.push(0xfffd)
        continue
      }
      units16.push(unit)
      continue
    }
    if ((byte1 & 0xf0) === 0xe0 && index + 1 < input.length) {
      const byte2 = input[index] ?? 0
      const byte3 = input[index + 1] ?? 0
      index += 2
      if ((byte2 & 0xc0) !== 0x80 || (byte3 & 0xc0) !== 0x80) {
        units16.push(0xfffd)
        continue
      }
      const unit = ((byte1 & 0x0f) << 12) | ((byte2 & 0x3f) << 6) | (byte3 & 0x3f)
      if (unit < 0x800) {
        units16.push(0xfffd)
        continue
      }
      units16.push(unit)
      continue
    }
    units16.push(0xfffd)
  }
  let out = ''
  const chunkSize = 0x7000
  for (let start = 0; start < units16.length; start += chunkSize) {
    out += String.fromCharCode(...units16.slice(start, start + chunkSize))
  }
  return out
}
