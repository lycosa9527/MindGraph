import { describe, expect, it } from 'vitest'

import { shouldExpandWorkshopOnNavClick } from '@/utils/sidebarWorkshopPanel'

describe('shouldExpandWorkshopOnNavClick', () => {
  it('stays collapsed on first entry from another page', () => {
    expect(shouldExpandWorkshopOnNavClick(false, false)).toBe(false)
  })

  it('toggles expand when already on 研习社', () => {
    expect(shouldExpandWorkshopOnNavClick(true, false)).toBe(true)
  })

  it('does not expand when the sidebar is icon-only', () => {
    expect(shouldExpandWorkshopOnNavClick(true, true)).toBe(false)
    expect(shouldExpandWorkshopOnNavClick(false, true)).toBe(false)
  })
})
