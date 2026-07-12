/**
 * Mobile Kitty camera capture stub — compress for future OCR; never call Omni append_image.
 */
import { compressImageFileForKitty } from '@/composables/kitty/compressImageForKitty'

export type MobileKittyPhotoCaptureResult =
  | { ok: true; compressedBase64: string }
  | { ok: false; reason: 'no_file' | 'compress_failed' }

/**
 * Prepare a captured photo for future LLM OCR ingress.
 * Does not send to Kitty Omni (append_image is retired).
 */
export async function prepareMobileKittyPhotoCapture(
  file: File | null | undefined
): Promise<MobileKittyPhotoCaptureResult> {
  if (!file) {
    return { ok: false, reason: 'no_file' }
  }
  try {
    const compressedBase64 = await compressImageFileForKitty(file)
    return { ok: true, compressedBase64 }
  } catch {
    return { ok: false, reason: 'compress_failed' }
  }
}
