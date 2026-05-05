/** Resize / re-encode JPEG for Kitty multimodal upload (≤500 KiB, modest resolution). */

const KITTY_IMAGE_MAX_BYTES = 500 * 1024
const KITTY_IMAGE_LONG_EDGE_PREF = 960
const KITTY_IMAGE_LONG_EDGE_MAX = 1920
const KITTY_IMAGE_LONG_EDGE_MIN = 480

export async function compressImageFileForKitty(file: File): Promise<string> {
  const url = URL.createObjectURL(file)
  try {
    const img = new Image()
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject(new Error('image-load'))
      img.src = url
    })
    const natW = img.naturalWidth
    const natH = img.naturalHeight
    let longEdge = Math.min(
      Math.max(natW, natH),
      Math.min(KITTY_IMAGE_LONG_EDGE_PREF, KITTY_IMAGE_LONG_EDGE_MAX),
    )
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('no-ctx')

    const blobToBase64 = (blob: Blob) =>
      new Promise<string>((resolve, reject) => {
        const r = new FileReader()
        r.onload = () => {
          const dataUrl = String(r.result ?? '')
          const i = dataUrl.indexOf(',')
          resolve(i >= 0 ? dataUrl.slice(i + 1) : dataUrl)
        }
        r.onerror = () => reject(new Error('read-blob'))
        r.readAsDataURL(blob)
      })

    let quality = 0.84
    let outBase64: string | null = null

    while (longEdge >= KITTY_IMAGE_LONG_EDGE_MIN) {
      let w = natW
      let h = natH
      const curLong = Math.max(w, h)
      if (curLong > longEdge) {
        if (w >= h) {
          h = Math.round((h * longEdge) / w)
          w = longEdge
        } else {
          w = Math.round((w * longEdge) / h)
          h = longEdge
        }
      }
      canvas.width = w
      canvas.height = h
      ctx.drawImage(img, 0, 0, w, h)

      while (quality >= 0.38) {
        const blob = await new Promise<Blob>((resolve, reject) => {
          canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('toBlob'))), 'image/jpeg', quality)
        })
        if (blob.size <= KITTY_IMAGE_MAX_BYTES) {
          outBase64 = await blobToBase64(blob)
          break
        }
        quality -= 0.07
      }

      if (outBase64) break
      quality = 0.84
      longEdge = Math.round(longEdge * 0.85)
    }

    if (!outBase64) throw new Error('compress-limit')
    return outBase64
  } finally {
    URL.revokeObjectURL(url)
  }
}
