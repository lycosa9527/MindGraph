import { describe, expect, it } from 'vitest'

/**
 * Mirrors the frontend complete gate: need ≥3 submitted variants.
 */
function canComplete(tasks: Array<{ status: string }>): boolean {
  return tasks.filter((task) => task.status === 'submitted').length >= 3
}

describe('maite inquiry complete gate', () => {
  it('blocks complete when fewer than 3 variants are submitted', () => {
    expect(
      canComplete([
        { status: 'submitted' },
        { status: 'pending' },
        { status: 'submitted' },
      ])
    ).toBe(false)
  })

  it('allows complete when at least 3 variants are submitted', () => {
    expect(
      canComplete([
        { status: 'submitted' },
        { status: 'submitted' },
        { status: 'submitted' },
        { status: 'pending' },
      ])
    ).toBe(true)
  })
})
