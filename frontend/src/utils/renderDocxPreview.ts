import { renderAsync } from 'docx-preview'

import { stampWatermarksInContainer } from '@/utils/showcaseWatermark'

function normalizeDocxSurfaceColors(container: HTMLElement): void {
  container.querySelectorAll<HTMLElement>('[style]').forEach((el) => {
    const bg = `${el.style.backgroundColor} ${el.style.background}`.toLowerCase()
    if (
      bg.includes('rgb(0, 0, 0)') ||
      bg.includes('#000') ||
      bg.includes('black')
    ) {
      el.style.background = '#fff'
      el.style.backgroundColor = '#fff'
    }
    const color = el.style.color.toLowerCase()
    if (color === '#ffffff' || color === 'white' || color === 'rgb(255, 255, 255)') {
      el.style.color = '#111827'
    }
  })
}

export async function renderDocxPreview(
  blob: Blob,
  container: HTMLElement,
  watermarkText?: string
): Promise<void> {
  container.replaceChildren()
  await renderAsync(blob, container, container, {
    className: 'showcase-docx',
    inWrapper: true,
    ignoreWidth: false,
    ignoreHeight: false,
    breakPages: true,
    ignoreLastRenderedPageBreak: true,
    useBase64URL: true,
    renderHeaders: true,
    renderFooters: true,
    renderFootnotes: true,
    renderEndnotes: true,
  })
  normalizeDocxSurfaceColors(container)
  if (watermarkText?.trim()) {
    stampWatermarksInContainer(
      container,
      watermarkText.trim(),
      '.showcase-docx-wrapper section, .showcase-docx-wrapper article, .showcase-docx-wrapper .docx, .showcase-docx-wrapper > div'
    )
    if (!container.querySelector('.showcase-page-watermark')) {
      const host =
        container.querySelector<HTMLElement>('.showcase-docx-wrapper') ?? container
      stampWatermarksInContainer(host, watermarkText.trim(), ':scope > section, :scope > article, :scope > div')
    }
  }
}
