import { describe, expect, it } from 'vitest'

import { animateViewportTransition, cancelViewportTransition } from '@/utils/viewportTransition'

const from = { x: 0, y: 0, zoom: 1 }
const to = { x: 40, y: 0, zoom: 2 }

describe('viewport transition lanes', () => {
  it('cancels the demo camera without settling the editor camera', async () => {
    let editorSettled = false
    const editor = animateViewportTransition(from, to, 5000, () => undefined).then(() => {
      editorSettled = true
    })
    const demo = animateViewportTransition(from, to, 5000, () => undefined, 'library-demo')

    cancelViewportTransition('library-demo')
    await demo
    await Promise.resolve()
    expect(editorSettled).toBe(false)

    cancelViewportTransition()
    await editor
    expect(editorSettled).toBe(true)
  })

  it('replaces only the camera on the same lane', async () => {
    let firstSettled = false
    const first = animateViewportTransition(from, to, 5000, () => undefined, 'library-demo').then(
      () => {
        firstSettled = true
      }
    )
    const second = animateViewportTransition(from, to, 5000, () => undefined, 'library-demo')
    await Promise.resolve()
    expect(firstSettled).toBe(true)
    await first

    cancelViewportTransition('library-demo')
    await second
  })
})
