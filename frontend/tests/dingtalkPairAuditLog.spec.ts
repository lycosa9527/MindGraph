import { afterEach, describe, expect, it, vi } from 'vitest'

import { logPairAudit, pairTokenTail } from '@/utils/dingtalkPairAuditLog'
import { resetFrontendLogDedupeForTests } from '@/utils/frontendLog'

describe('dingtalkPairAuditLog', () => {
  afterEach(() => {
    resetFrontendLogDedupeForTests()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('uses client prefix and token tail helper', () => {
    const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => undefined)
    logPairAudit('mint_ok', {
      purpose: 'bind',
      token: pairTokenTail('abcdefghijklmnopqrstuvwxyz'),
    }, { reportToServer: false })

    expect(infoSpy).toHaveBeenCalledOnce()
    const line = String(infoSpy.mock.calls[0]?.[0])
    expect(line).toContain('[DingtalkPair:client]')
    expect(line).toContain('mint_ok')
    expect(line).toContain('purpose=bind')
    expect(line).toContain('…stuvwxyz')
  })

  it('reports key lifecycle events to frontend_log in production', () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('PROD', true)
    vi.stubEnv('DEV', false)

    logPairAudit('pairing_completed', {
      purpose: 'bind',
      linked: true,
      generation: 2,
    })

    expect(fetchMock).toHaveBeenCalledOnce()
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    const body = JSON.parse(String(init.body)) as { source: string; message: string; level: string }
    expect(body.source).toBe('dingtalk_pair')
    expect(body.level).toBe('info')
    expect(body.message).toContain('[DingtalkPair:client]')
    expect(body.message).toContain('pairing_completed')
  })
})
