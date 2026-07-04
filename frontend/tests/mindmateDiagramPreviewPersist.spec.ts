import { afterEach, describe, expect, it, vi } from 'vitest'

import { hasGeneratedDiagramImage } from '@/utils/mindmateDiagramMeta'
import {
  queueMindmateDiagramPreviewPersist,
  queueMindmateDiagramPreviewsForMessages,
} from '@/utils/mindmateDiagramPreviewPersist'
import { resolveMindmateDiagramPreviewBlob } from '@/utils/mindmateDiagramPreviewResolve'

vi.mock('@/utils/mindmateDiagramPreviewResolve', () => ({
  resolveMindmateDiagramPreviewBlob: vi.fn().mockResolvedValue(null),
}))

const DIAGRAM_MARKDOWN =
  '![](https://host/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x&exp=1)'

describe('queueMindmateDiagramPreviewPersist', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('skips unrelated markdown', () => {
    queueMindmateDiagramPreviewPersist('hello')
    expect(resolveMindmateDiagramPreviewBlob).not.toHaveBeenCalled()
  })

  it('queues resolve for generate_dingtalk preview markdown', async () => {
    expect(hasGeneratedDiagramImage(DIAGRAM_MARKDOWN)).toBe(true)
    queueMindmateDiagramPreviewPersist(DIAGRAM_MARKDOWN)
    await Promise.resolve()
    expect(resolveMindmateDiagramPreviewBlob).toHaveBeenCalledWith(
      expect.objectContaining({
        content: DIAGRAM_MARKDOWN,
      })
    )
  })
})

describe('queueMindmateDiagramPreviewsForMessages', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('warms assistant messages only', async () => {
    queueMindmateDiagramPreviewsForMessages([
      { role: 'user', content: DIAGRAM_MARKDOWN },
      { role: 'assistant', content: DIAGRAM_MARKDOWN },
      { role: 'assistant', content: 'plain text' },
    ])
    await Promise.resolve()
    expect(resolveMindmateDiagramPreviewBlob).toHaveBeenCalledTimes(1)
  })
})
