/**
 * Resize chrome-extension icon128 into PWA manifest sizes.
 * Run: node scripts/generate-pwa-icons.mjs
 */
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import sharp from 'sharp'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = join(__dirname, '..')
const sourceIcon = join(frontendRoot, '..', 'chrome-extension', 'icons', 'icon128.png')
const publicDir = join(frontendRoot, 'public')

async function main() {
  await sharp(sourceIcon).resize(192, 192).png().toFile(join(publicDir, 'pwa-192x192.png'))
  await sharp(sourceIcon).resize(512, 512).png().toFile(join(publicDir, 'pwa-512x512.png'))
  await sharp(sourceIcon).resize(180, 180).png().toFile(join(publicDir, 'apple-touch-icon.png'))
  console.log('Generated PWA icons in frontend/public/')
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
