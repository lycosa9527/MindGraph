import { describe, expect, it } from 'vitest'

import { collabDiagramSaveFailureFromResponse } from '@/utils/mindmateCollabDiagramLibrary'

describe('collabDiagramSaveFailureFromResponse', () => {
  it('maps library full, missing preview, and access errors', () => {
    expect(collabDiagramSaveFailureFromResponse(409, 'limit_reached')).toBe('full')
    expect(collabDiagramSaveFailureFromResponse(409, 'no_spec')).toBe('missing')
    expect(collabDiagramSaveFailureFromResponse(404, 'not_found')).toBe('missing')
    expect(collabDiagramSaveFailureFromResponse(403, 'forbidden')).toBe('denied')
    expect(collabDiagramSaveFailureFromResponse(500, 'save_error')).toBe('failed')
  })
})
