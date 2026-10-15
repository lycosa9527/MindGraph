/**
 * Same UUID for a leftover mind-map id on every client and the server.
 * UUID v5 of the leftover string, namespace shared with ``mindmap_identity.py``.
 */

const IDENTITY_NAMESPACE = 'f915c4fc-7887-5ebd-b5cf-633c332afe83'

function rotl(value: number, shift: number): number {
  return ((value << shift) | (value >>> (32 - shift))) >>> 0
}

function sha1(message: Uint8Array): Uint8Array {
  const bitLength = message.length * 8
  const paddedLength = Math.ceil((message.length + 9) / 64) * 64
  const bytes = new Uint8Array(paddedLength)
  bytes.set(message)
  bytes[message.length] = 0x80
  const view = new DataView(bytes.buffer)
  view.setUint32(paddedLength - 4, bitLength >>> 0, false)

  let h0 = 0x67452301
  let h1 = 0xefcdab89
  let h2 = 0x98badcfe
  let h3 = 0x10325476
  let h4 = 0xc3d2e1f0
  const words = new Uint32Array(80)

  for (let offset = 0; offset < paddedLength; offset += 64) {
    for (let index = 0; index < 16; index += 1) {
      words[index] = view.getUint32(offset + index * 4, false)
    }
    for (let index = 16; index < 80; index += 1) {
      words[index] = rotl(
        words[index - 3] ^ words[index - 8] ^ words[index - 14] ^ words[index - 16],
        1
      )
    }
    let a = h0
    let b = h1
    let c = h2
    let d = h3
    let e = h4
    for (let index = 0; index < 80; index += 1) {
      let mixed: number
      let constant: number
      if (index < 20) {
        mixed = (b & c) | (~b & d)
        constant = 0x5a827999
      } else if (index < 40) {
        mixed = b ^ c ^ d
        constant = 0x6ed9eba1
      } else if (index < 60) {
        mixed = (b & c) | (b & d) | (c & d)
        constant = 0x8f1bbcdc
      } else {
        mixed = b ^ c ^ d
        constant = 0xca62c1d6
      }
      const next = (rotl(a, 5) + mixed + e + constant + words[index]) >>> 0
      e = d
      d = c
      c = rotl(b, 30)
      b = a
      a = next
    }
    h0 = (h0 + a) >>> 0
    h1 = (h1 + b) >>> 0
    h2 = (h2 + c) >>> 0
    h3 = (h3 + d) >>> 0
    h4 = (h4 + e) >>> 0
  }

  const digest = new Uint8Array(20)
  const digestView = new DataView(digest.buffer)
  digestView.setUint32(0, h0, false)
  digestView.setUint32(4, h1, false)
  digestView.setUint32(8, h2, false)
  digestView.setUint32(12, h3, false)
  digestView.setUint32(16, h4, false)
  return digest
}

function uuidBytes(uuidText: string): Uint8Array {
  const hex = uuidText.replace(/-/g, '')
  const out = new Uint8Array(16)
  for (let index = 0; index < 16; index += 1) {
    out[index] = Number.parseInt(hex.slice(index * 2, index * 2 + 2), 16)
  }
  return out
}

const NAMESPACE_BYTES = uuidBytes(IDENTITY_NAMESPACE)

function formatUuid(bytes: Uint8Array): string {
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

/** UUID shared by every client and the server for this leftover branch id. */
export function stableMindMapIdentityId(leftoverId: string): string {
  const name = new TextEncoder().encode(leftoverId)
  const input = new Uint8Array(NAMESPACE_BYTES.length + name.length)
  input.set(NAMESPACE_BYTES)
  input.set(name, NAMESPACE_BYTES.length)
  const digest = sha1(input).slice(0, 16)
  digest[6] = (digest[6] & 0x0f) | 0x50
  digest[8] = (digest[8] & 0x3f) | 0x80
  return formatUuid(digest)
}
