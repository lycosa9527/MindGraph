import { describe, expect, it } from 'vitest'

import { shouldNackCollabOutboundOnError } from '@/composables/workshop/useWorkshopMessageHandlers'

describe('shouldNackCollabOutboundOnError', () => {
  it('nacks when client_op_id is present', () => {
    expect(shouldNackCollabOutboundOnError({ client_op_id: 'op-1' })).toBe(true)
  })

  it('nacks known update failure codes without client_op_id', () => {
    expect(shouldNackCollabOutboundOnError({ code: 'update_invalid' })).toBe(true)
    expect(shouldNackCollabOutboundOnError({ code: 'update_rejected' })).toBe(true)
    expect(shouldNackCollabOutboundOnError({ code: 'broadcast_failed' })).toBe(true)
  })

  it('does not nack lock or claim errors that lack an update op id', () => {
    expect(shouldNackCollabOutboundOnError({})).toBe(false)
    expect(shouldNackCollabOutboundOnError({ code: 'node_locked' })).toBe(false)
  })
})
