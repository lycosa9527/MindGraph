/**
 * Voice-notes PCM helpers — Float32 → 16 kHz PCM16 base64 for Fun-ASR.
 */

export const VOICE_NOTES_TARGET_SAMPLE_RATE = 16000
export const VOICE_NOTES_SPEECH_RMS_THRESHOLD = 0.012

export function arrayBufferToBase64(buffer: ArrayBuffer): string {
  let binary = ''
  const bytes = new Uint8Array(buffer)
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i] as number)
  }
  return window.btoa(binary)
}

export function float32Rms(input: Float32Array): number {
  if (input.length === 0) return 0
  let sum = 0
  for (let i = 0; i < input.length; i++) {
    const sample = input[i] as number
    sum += sample * sample
  }
  return Math.sqrt(sum / input.length)
}

export function float32ToPcm16Base64(input: Float32Array, inputRate: number): string {
  if (inputRate === VOICE_NOTES_TARGET_SAMPLE_RATE) {
    const pcm = new Int16Array(input.length)
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i] as number))
      pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff
    }
    return arrayBufferToBase64(pcm.buffer)
  }

  const ratio = inputRate / VOICE_NOTES_TARGET_SAMPLE_RATE
  const outLen = Math.floor(input.length / ratio)
  const pcm = new Int16Array(outLen)
  for (let i = 0; i < outLen; i++) {
    const start = Math.floor(i * ratio)
    const end = Math.min(Math.floor((i + 1) * ratio), input.length)
    let sum = 0
    for (let j = start; j < end; j++) {
      sum += input[j] as number
    }
    const avg = sum / Math.max(1, end - start)
    const s = Math.max(-1, Math.min(1, avg))
    pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return arrayBufferToBase64(pcm.buffer)
}
