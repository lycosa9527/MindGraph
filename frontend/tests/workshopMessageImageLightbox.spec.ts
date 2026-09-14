import { describe, expect, it } from 'vitest'

import {
  filenameFromWorkshopImage,
  isWorkshopLightboxImage,
  workshopImageLightboxFromClick,
} from '@/utils/workshopMessageImageLightbox'

function makeImg(src: string, alt = ''): HTMLImageElement {
  const img = document.createElement('img')
  img.setAttribute('src', src)
  img.alt = alt
  return img
}

function clickOn(target: EventTarget): Event {
  const event = new MouseEvent('click', { bubbles: true, cancelable: true })
  Object.defineProperty(event, 'target', { value: target })
  return event
}

describe('isWorkshopLightboxImage', () => {
  it('accepts library and attachment images', () => {
    expect(isWorkshopLightboxImage(makeImg('/api/chat/attachments/9/download'))).toBe(true)
  })

  it('skips Course Builder role stickers', () => {
    expect(
      isWorkshopLightboxImage(makeImg('/api/training/assets/roles/01-look-here.png'))
    ).toBe(false)
  })
})

describe('filenameFromWorkshopImage', () => {
  it('uses a human alt over mg:uuid', () => {
    expect(filenameFromWorkshopImage(makeImg('/api/chat/attachments/9/download', '背影.png'), '图示')).toBe(
      '背影.png'
    )
  })

  it('falls back for library mg:uuid alt', () => {
    const id = 'd1d7a7fc-eaa1-436d-abd2-2a7b1230c537'
    expect(
      filenameFromWorkshopImage(makeImg('/api/chat/attachments/9/download', `mg:${id}`), '图示')
    ).toBe('图示')
  })

  it('uses a file-like last path segment', () => {
    expect(filenameFromWorkshopImage(makeImg('/uploads/lesson-map.png', ''), '图示')).toBe(
      'lesson-map.png'
    )
  })
})

describe('workshopImageLightboxFromClick', () => {
  it('opens a library diagram image and stops the link', () => {
    const img = makeImg('/api/chat/attachments/9/download', 'mg:d1d7a7fc-eaa1-436d-abd2-2a7b1230c537')
    const event = clickOn(img)
    const hit = workshopImageLightboxFromClick(event, '图示')
    expect(hit).toEqual({ src: '/api/chat/attachments/9/download', filename: '图示' })
    expect(event.defaultPrevented).toBe(true)
  })

  it('ignores role stickers and plain text clicks', () => {
    const role = makeImg('/api/training/assets/roles/01-look-here.png', '看这里')
    expect(workshopImageLightboxFromClick(clickOn(role), '图示')).toBeNull()
    expect(workshopImageLightboxFromClick(clickOn(document.createElement('span')), '图示')).toBeNull()
  })
})
