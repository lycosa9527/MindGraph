import { describe, expect, it } from 'vitest'

import {
  orderSeminarFaces,
  removeSeminarFace,
  seminarFaceFromPayload,
  seminarFacesFromJoined,
  splitSeminarFaces,
  upsertSeminarFace,
} from '@/utils/mindmateSeminarFaces'

describe('mindmateSeminarFaces', () => {
  it('reads a joined person and ignores a blank id', () => {
    expect(seminarFaceFromPayload({ user_id: 3, name: 'Ada', avatar: '🐱' })).toEqual({
      userId: 3,
      name: 'Ada',
      avatar: '🐱',
    })
    expect(seminarFaceFromPayload({ user_id: 0, name: 'Ada' })).toBeNull()
  })

  it('keeps the snapshot, then adds and removes people', () => {
    const self = { userId: 1, name: 'You', avatar: null }
    const joined = seminarFacesFromJoined(
      [
        { user_id: 1, name: 'You' },
        { user_id: 2, username: 'Bo' },
      ],
      self
    )
    expect(joined.map((face) => face.userId)).toEqual([1, 2])
    const withCara = upsertSeminarFace(joined, { userId: 2, name: 'Bo', avatar: '🐶' })
    expect(withCara).toHaveLength(2)
    expect(withCara[1]?.avatar).toBe('🐶')
    expect(removeSeminarFace(withCara, 2).map((face) => face.userId)).toEqual([1])
    expect(seminarFacesFromJoined([], self)).toEqual([self])
  })

  it('puts you first and folds the rest into a count', () => {
    const faces = [
      { userId: 2, name: 'Bo', avatar: null },
      { userId: 1, name: 'You', avatar: null },
      { userId: 4, name: 'Cara', avatar: null },
      { userId: 3, name: 'Di', avatar: null },
      { userId: 5, name: 'Ed', avatar: null },
    ]
    const ordered = orderSeminarFaces(faces, 1)
    expect(ordered[0]?.userId).toBe(1)
    const split = splitSeminarFaces(ordered)
    expect(split.visible).toHaveLength(4)
    expect(split.overflow.map((face) => face.name)).toEqual(['Ed'])
  })
})