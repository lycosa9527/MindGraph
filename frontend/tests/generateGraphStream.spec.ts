import { describe, expect, it } from 'vitest'

import { consumeGenerateGraphStream } from '@/utils/generateGraphStream'

function sseResponse(lines: string[]): Response {
  const body = new ReadableStream({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(new TextEncoder().encode(`${line}\n`))
      }
      controller.close()
    },
  })
  return new Response(body, {
    headers: { 'content-type': 'text/event-stream' },
  })
}

describe('consumeGenerateGraphStream', () => {
  it('maps accepted, waiting, streaming, and complete events', async () => {
    const phases: string[] = []
    let completePayload: Record<string, unknown> | undefined

    const response = sseResponse([
      'data: {"event":"accepted"}',
      'data: {"event":"waiting"}',
      'data: {"event":"streaming","model":"qwen"}',
      'data: {"event":"complete","success":true,"diagram_type":"mindmap","spec":{"topic":"T"}}',
    ])

    const result = await consumeGenerateGraphStream(response, {
      onPhase: (phase) => phases.push(phase),
      onComplete: (payload) => {
        completePayload = payload
      },
    })

    expect(result.usedStream).toBe(true)
    expect(phases).toEqual(['accepted', 'waiting', 'streaming'])
    expect(completePayload?.success).toBe(true)
    expect(completePayload?.diagram_type).toBe('mindmap')
  })

  it('maps detecting, requirements, progress, and complete metadata', async () => {
    const phases: string[] = []
    let progressTopic = ''
    let progressDiagramType = ''

    const response = sseResponse([
      'data: {"event":"accepted"}',
      'data: {"event":"detecting"}',
      'data: {"event":"requirements"}',
      'data: {"event":"progress","topic":"Animals","diagram_type":"tree_map"}',
      'data: {"event":"waiting"}',
      'data: {"event":"streaming","model":"qwen"}',
      'data: {"event":"complete","success":true,"diagram_type":"tree_map","show_guidance":false}',
    ])

    await consumeGenerateGraphStream(response, {
      onPhase: (phase) => phases.push(phase),
      onProgress: (metadata) => {
        progressTopic = metadata.topic ?? ''
        progressDiagramType = metadata.diagram_type ?? ''
      },
    })

    expect(phases).toEqual([
      'accepted',
      'detecting',
      'requirements',
      'progress',
      'waiting',
      'streaming',
    ])
    expect(progressTopic).toBe('Animals')
    expect(progressDiagramType).toBe('tree_map')
  })

  it('returns usedStream=false for non-SSE responses', async () => {
    const response = new Response(JSON.stringify({ success: true }), {
      headers: { 'content-type': 'application/json' },
    })

    const result = await consumeGenerateGraphStream(response, {})
    expect(result.usedStream).toBe(false)
  })

  it('invokes onError for error events', async () => {
    let errorMessage = ''
    const response = sseResponse(['data: {"event":"error","message":"Rate limited"}'])

    await consumeGenerateGraphStream(response, {
      onError: (message) => {
        errorMessage = message
      },
    })

    expect(errorMessage).toBe('Rate limited')
  })
})
