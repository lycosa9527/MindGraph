import { describe, expect, it } from 'vitest'

import { collectSeminarDiagramArtifacts } from '@/utils/mindmateSeminarArtifacts'

describe('collectSeminarDiagramArtifacts', () => {
  it('keeps a canvas share that only embeds the diagram id', () => {
    const diagramId = '11111111-1111-4111-8111-111111111111'
    const found = collectSeminarDiagramArtifacts([
      {
        id: 9,
        content: `勾股定理的思维导图\n![勾股定理的思维导图](/api/diagrams/${diagramId}/preview)\n<!-- mg-diagram-id:${diagramId} -->`,
      },
    ])
    expect(found).toEqual([
      {
        previewId: diagramId,
        label: '勾股定理的思维导图',
        messageId: 9,
        imagePath: `/api/diagrams/${diagramId}/preview`,
        diagramId,
      },
    ])
  })
})
