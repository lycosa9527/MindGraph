import { describe, expect, it } from 'vitest'

import {
  workshopUserIsCollabGuest,
  workshopUserOwnsDiagram,
} from '@/composables/workshop/workshopOwnerIdentity'

describe('workshopUserOwnsDiagram', () => {
  it('treats a canvas with no known owner as the current user', () => {
    expect(workshopUserOwnsDiagram(null, 3)).toBe(true)
    expect(workshopUserOwnsDiagram(undefined, 3)).toBe(true)
  })

  it('fails closed while a room is live and owner id has not arrived', () => {
    expect(workshopUserOwnsDiagram(null, 3, true)).toBe(false)
  })

  it('compares owner id after the room code is gone', () => {
    expect(workshopUserOwnsDiagram(3, 3)).toBe(true)
    expect(workshopUserOwnsDiagram(3, '3')).toBe(true)
    expect(workshopUserOwnsDiagram(3, 4846)).toBe(false)
  })

  it('is not the owner when the user id is missing', () => {
    expect(workshopUserOwnsDiagram(3, null)).toBe(false)
    expect(workshopUserOwnsDiagram(3, '')).toBe(false)
  })
})

describe('workshopUserIsCollabGuest', () => {
  it('is false until an owner id is known', () => {
    expect(workshopUserIsCollabGuest(null, 4846)).toBe(false)
    expect(workshopUserIsCollabGuest(3, null)).toBe(false)
  })

  it('stays true for the guest after the workshop code is cleared', () => {
    expect(workshopUserIsCollabGuest(3, 4846)).toBe(true)
    expect(workshopUserIsCollabGuest(3, '4846')).toBe(true)
    expect(workshopUserIsCollabGuest(3, 3)).toBe(false)
  })
})
