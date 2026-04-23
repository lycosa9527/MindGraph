/**
 * MindGraph `.mg` interchange format (obfuscation, not secret storage).
 *
 * **v1.1 (current export):** `MG` (ASCII) | major `0x01` | minor `0x01` | 12-byte IV |
 * AES-256-GCM ciphertext (includes auth tag). Human-readable label: **MG v1.1**.
 *
 * **v1.0 encrypted (legacy):** ASCII `MG1` | IV | ciphertext — still accepted on import.
 *
 * Import rejects plain-text JSON inside `.mg`; only encrypted wire formats above.
 *
 * The key is derived in-browser from a fixed label; this only deters casual reading.
 */

/** Display / diagnostics only (e.g. docs, future UI). */
export const MG_INTERCHANGE_VERSION_LABEL = '1.1'

/** Thrown when bytes are not v1.1 or legacy MG1 encrypted payload. */
export const MG_FILE_NOT_ENCRYPTED = 'MG_FILE_NOT_ENCRYPTED'

const MG_SIG = 0x4d47 // 'MG' — file type
const VERSION_MAJOR_V1_1 = 1
const VERSION_MINOR_V1_1 = 1

/** v1.1: MG + major + minor (4 bytes), then IV, then ciphertext. */
const HEADER_V1_1_BYTE_LENGTH = 4

/** Legacy v1.0 encrypted: ASCII "MG1" (3 bytes), then IV, then ciphertext. */
const LEGACY_MAGIC_MG1 = new Uint8Array([0x4d, 0x47, 0x31])

const IV_BYTE_LENGTH = 12
const AES_GCM_TAG_BYTES = 16
const KEY_DERIVE_UTF8 = 'MindGraph.MG.interchange.v1'

function subtleOrThrow(): SubtleCrypto {
  const s = globalThis.crypto?.subtle
  if (!s) {
    throw new Error('Web Crypto API unavailable (requires a secure context)')
  }
  return s
}

async function importAesGcmKey(): Promise<CryptoKey> {
  const subtle = subtleOrThrow()
  const enc = new TextEncoder()
  const hashBuffer = await subtle.digest('SHA-256', enc.encode(KEY_DERIVE_UTF8))
  const raw = new Uint8Array(hashBuffer).subarray(0, 32)
  return subtle.importKey('raw', raw, { name: 'AES-GCM' }, false, ['encrypt', 'decrypt'])
}

function isHeaderV1_1(view: Uint8Array): boolean {
  if (view.length < HEADER_V1_1_BYTE_LENGTH) return false
  const sig = (view[0] << 8) | view[1]
  return (
    sig === MG_SIG &&
    view[2] === VERSION_MAJOR_V1_1 &&
    view[3] === VERSION_MINOR_V1_1
  )
}

function isLegacyMg1EncryptedHeader(view: Uint8Array): boolean {
  if (view.length < LEGACY_MAGIC_MG1.length) return false
  for (let i = 0; i < LEGACY_MAGIC_MG1.length; i += 1) {
    if (view[i] !== LEGACY_MAGIC_MG1[i]) return false
  }
  return true
}

/**
 * Build binary contents for a `.mg` download from a JSON string (diagram spec).
 * Writes **MG v1.1** wire format.
 */
export async function encodeMgFileContents(plaintextJson: string): Promise<Uint8Array> {
  const subtle = subtleOrThrow()
  const key = await importAesGcmKey()
  const iv = crypto.getRandomValues(new Uint8Array(IV_BYTE_LENGTH))
  const plaintext = new TextEncoder().encode(plaintextJson)
  const ciphertext = await subtle.encrypt({ name: 'AES-GCM', iv }, key, plaintext)
  const ct = new Uint8Array(ciphertext)
  const out = new Uint8Array(HEADER_V1_1_BYTE_LENGTH + IV_BYTE_LENGTH + ct.length)
  out[0] = 0x4d
  out[1] = 0x47
  out[2] = VERSION_MAJOR_V1_1
  out[3] = VERSION_MINOR_V1_1
  out.set(iv, HEADER_V1_1_BYTE_LENGTH)
  out.set(ct, HEADER_V1_1_BYTE_LENGTH + IV_BYTE_LENGTH)
  return out
}

/**
 * Decode `.mg` file bytes to a UTF-8 JSON string.
 * Only **v1.1** or legacy **MG1** + GCM payloads; otherwise throws with `MG_FILE_NOT_ENCRYPTED`.
 */
export async function decodeMgFileToJsonText(buffer: ArrayBuffer): Promise<string> {
  const view = new Uint8Array(buffer)
  const minV1_1 = HEADER_V1_1_BYTE_LENGTH + IV_BYTE_LENGTH + AES_GCM_TAG_BYTES
  const minLegacy = LEGACY_MAGIC_MG1.length + IV_BYTE_LENGTH + AES_GCM_TAG_BYTES

  if (view.length >= minV1_1 && isHeaderV1_1(view)) {
    const subtle = subtleOrThrow()
    const key = await importAesGcmKey()
    const iv = view.subarray(HEADER_V1_1_BYTE_LENGTH, HEADER_V1_1_BYTE_LENGTH + IV_BYTE_LENGTH)
    const ciphertext = view.subarray(HEADER_V1_1_BYTE_LENGTH + IV_BYTE_LENGTH)
    const plaintext = await subtle.decrypt({ name: 'AES-GCM', iv }, key, ciphertext)
    return new TextDecoder('utf-8', { fatal: false }).decode(plaintext)
  }

  if (view.length >= minLegacy && isLegacyMg1EncryptedHeader(view)) {
    const subtle = subtleOrThrow()
    const key = await importAesGcmKey()
    const iv = view.subarray(LEGACY_MAGIC_MG1.length, LEGACY_MAGIC_MG1.length + IV_BYTE_LENGTH)
    const ciphertext = view.subarray(LEGACY_MAGIC_MG1.length + IV_BYTE_LENGTH)
    const plaintext = await subtle.decrypt({ name: 'AES-GCM', iv }, key, ciphertext)
    return new TextDecoder('utf-8', { fatal: false }).decode(plaintext)
  }

  throw new Error(MG_FILE_NOT_ENCRYPTED)
}
