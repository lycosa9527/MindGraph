/**
 * Rasterize frontend/public/favicon.svg at native pixel sizes (no PNG upscaling).
 * Run: node scripts/generate-pwa-icons.mjs
 */
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import sharp from 'sharp'

const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = join(__dirname, '..')
const repoRoot = join(frontendRoot, '..')
const publicDir = join(frontendRoot, 'public')
const svgPath = join(publicDir, 'favicon.svg')
const chromeIconsDir = join(repoRoot, 'chrome-extension', 'icons')
const wechatDir = join(publicDir, 'wechat')
const fileReaderAssets = join(repoRoot, 'clients', 'file-reader', 'assets')

const PNG_OUTPUTS = [
  { file: join(publicDir, 'pwa-192x192.png'), size: 192 },
  { file: join(publicDir, 'pwa-512x512.png'), size: 512 },
  { file: join(publicDir, 'apple-touch-icon.png'), size: 180 },
  { file: join(wechatDir, 'icon28.png'), size: 28 },
  { file: join(wechatDir, 'icon108.png'), size: 108 },
  { file: join(chromeIconsDir, 'icon16.png'), size: 16 },
  { file: join(chromeIconsDir, 'icon32.png'), size: 32 },
  { file: join(chromeIconsDir, 'icon48.png'), size: 48 },
  { file: join(chromeIconsDir, 'icon128.png'), size: 128 },
  { file: join(chromeIconsDir, 'icon300.png'), size: 300 },
  { file: join(fileReaderAssets, 'icon.png'), size: 256 },
]

const ICO_SIZES = [16, 32, 48, 64, 128, 256]

async function renderPng(svgSource, size) {
  const sizedSvg = svgSource.replace(/<svg\b/, `<svg width="${size}" height="${size}"`)
  return sharp(Buffer.from(sizedSvg)).png().toBuffer()
}

function buildIco(images) {
  const count = images.length
  const header = Buffer.alloc(6)
  header.writeUInt16LE(0, 0)
  header.writeUInt16LE(1, 2)
  header.writeUInt16LE(count, 4)

  let offset = 6 + 16 * count
  const entries = []
  const payloads = []
  for (const { size, png } of images) {
    const entry = Buffer.alloc(16)
    const stored = size >= 256 ? 0 : size
    entry.writeUInt8(stored, 0)
    entry.writeUInt8(stored, 1)
    entry.writeUInt16LE(1, 4)
    entry.writeUInt16LE(32, 6)
    entry.writeUInt32LE(png.length, 8)
    entry.writeUInt32LE(offset, 12)
    entries.push(entry)
    payloads.push(png)
    offset += png.length
  }
  return Buffer.concat([header, ...entries, ...payloads])
}

async function main() {
  const svgSource = await readFile(svgPath, 'utf8')
  const written = []

  for (const { file, size } of PNG_OUTPUTS) {
    await mkdir(dirname(file), { recursive: true })
    await writeFile(file, await renderPng(svgSource, size))
    written.push(file)
  }

  const icoImages = []
  for (const size of ICO_SIZES) {
    icoImages.push({ size, png: await renderPng(svgSource, size) })
  }
  const icoPath = join(fileReaderAssets, 'icon.ico')
  await mkdir(dirname(icoPath), { recursive: true })
  await writeFile(icoPath, buildIco(icoImages))
  written.push(icoPath)

  console.log(`Rasterized ${written.length} icons from ${svgPath}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
