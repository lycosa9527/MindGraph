import { renderAsync } from 'docx-preview'

import { refreshWatermarkDensity, stampWatermarksInContainer } from '@/utils/showcaseWatermark'

const DOCX_PAGE_SELECTOR =
  '.showcase-docx-wrapper section, .showcase-docx-wrapper article, .showcase-docx-wrapper .showcase-docx'

function normalizeDocxSurfaceColors(container: HTMLElement): void {
  container.querySelectorAll<HTMLElement>('[style]').forEach((el) => {
    const bg = `${el.style.backgroundColor} ${el.style.background}`.toLowerCase()
    if (bg.includes('rgb(0, 0, 0)') || bg.includes('#000') || bg.includes('black')) {
      el.style.background = '#fff'
      el.style.backgroundColor = '#fff'
    }
    const color = el.style.color.toLowerCase()
    if (color === '#ffffff' || color === 'white' || color === 'rgb(255, 255, 255)') {
      el.style.color = '#111827'
    }
  })
}

function clearInlinePageBoxConstraints(container: HTMLElement): void {
  // docx-preview sets fixed Word page width/height inline — strip so CSS can fit-width.
  container.querySelectorAll<HTMLElement>(DOCX_PAGE_SELECTOR).forEach((page) => {
    page.style.width = ''
    page.style.minWidth = ''
    page.style.maxWidth = ''
    page.style.height = ''
    page.style.minHeight = ''
    page.style.padding = ''
    page.style.margin = ''
    page.style.boxShadow = ''
  })
  const wrapper = container.querySelector<HTMLElement>('.showcase-docx-wrapper')
  if (wrapper) {
    wrapper.style.width = ''
    wrapper.style.padding = ''
    wrapper.style.background = ''
  }
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
    // Continuous reader: fit container width/height instead of fixed A4 page boxes.
    ignoreWidth: true,
    ignoreHeight: true,
    breakPages: true,
    ignoreLastRenderedPageBreak: true,
    useBase64URL: true,
    renderHeaders: true,
    renderFooters: true,
    renderFootnotes: true,
    renderEndnotes: true,
  })
  normalizeDocxSurfaceColors(container)
  clearInlinePageBoxConstraints(container)

  const trimmed = watermarkText?.trim()
  if (!trimmed) return

  stampWatermarksInContainer(container, trimmed, DOCX_PAGE_SELECTOR)
  if (!container.querySelector('.showcase-page-watermark')) {
    const host = container.querySelector<HTMLElement>('.showcase-docx-wrapper') ?? container
    stampWatermarksInContainer(host, trimmed, ':scope > section, :scope > article, :scope > div')
  }
  // Second pass after layout so tall pages get a dense tile grid.
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => resolve())
  })
  refreshWatermarkDensity(container, trimmed)
}
