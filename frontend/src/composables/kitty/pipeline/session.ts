/**
 * Kitty session connect module — ensure WS ready for a scope (S02).
 */
import { recordPipelineEvent, failKittyTurn } from '@/composables/kitty/pipeline/trace'
import type { KittyAgentContext } from '@/composables/kitty/kittyAgentTypes'
import type { KittyTurnContext } from '@/composables/kitty/pipeline/types'
import type { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

export type KittySessionConnectDeps = {
  kitty: ReturnType<typeof useKittyAgent>
  getScope: () => string
  buildContext: () => KittyAgentContext
  lane: 'mobile' | 'desktop'
  /** Optional existing turn context for correlation. */
  turnCtx?: KittyTurnContext
}

export async function ensureKittySessionConnected(
  deps: KittySessionConnectDeps
): Promise<{ ok: boolean; ctx: KittyTurnContext }> {
  const scope = deps.getScope().trim()
  const ctx: KittyTurnContext =
    deps.turnCtx ??
    ({
      requestId: safeRandomUUID(),
      scope: scope || 'scope',
      lane: deps.lane,
    } satisfies KittyTurnContext)

  if (!scope) {
    failKittyTurn({
      ctx,
      module: 'session',
      step: 'S02_session_ready',
      errorCode: 'scope_missing',
    })
    return { ok: false, ctx }
  }

  recordPipelineEvent({
    ctx: { ...ctx, scope },
    module: 'session',
    step: 'S02_session_ready',
    status: 'started',
  })

  deps.kitty.reconcileLiveState()
  if (deps.kitty.isLiveForScope(scope)) {
    recordPipelineEvent({
      ctx: { ...ctx, scope },
      module: 'session',
      step: 'S02_session_ready',
      status: 'ok',
      detail: 'already live',
    })
    return { ok: true, ctx: { ...ctx, scope } }
  }

  try {
    await deps.kitty.startConversation(scope, deps.buildContext())
    if (!deps.kitty.isConnected.value) {
      failKittyTurn({
        ctx: { ...ctx, scope },
        module: 'session',
        step: 'S02_session_ready',
        errorCode: 'not_connected',
      })
      return { ok: false, ctx: { ...ctx, scope } }
    }
    recordPipelineEvent({
      ctx: { ...ctx, scope },
      module: 'session',
      step: 'S02_session_ready',
      status: 'ok',
      detail: 'connected',
    })
    return { ok: true, ctx: { ...ctx, scope } }
  } catch {
    failKittyTurn({
      ctx: { ...ctx, scope },
      module: 'session',
      step: 'S02_session_ready',
      errorCode: 'connect_timeout',
    })
    return { ok: false, ctx: { ...ctx, scope } }
  }
}
