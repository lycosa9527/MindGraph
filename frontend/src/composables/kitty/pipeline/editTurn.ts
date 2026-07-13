/**
 * Edit pipeline worker — S06 history → (desktop S07 hub sync) → S08 text send.
 * Mobile lane skips S07: phone is mic+chat; Redis live_spec comes from desktop/server.
 */
import { eventBus } from '@/composables/core/useEventBus'
import type {
  KittyAgentContext,
  KittyContextUpdateOptions,
} from '@/composables/kitty/kittyAgentTypes'
import type { KittyTranslateFn } from '@/composables/kitty/pipeline/errorCatalog'
import { ensureKittySessionConnected } from '@/composables/kitty/pipeline/session'
import { runKittyHubSync } from '@/composables/kitty/pipeline/hubSyncWorker'
import {
  beginKittyTurn,
  completeKittyTurn,
  failKittyTurn,
  messageForKittyFail,
  recordPipelineEvent,
} from '@/composables/kitty/pipeline/trace'
import type { KittyTurnContext } from '@/composables/kitty/pipeline/types'
import { beginKittySessionIngress } from '@/composables/kitty/useKittySessionManager'
import type { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import { useKittyPipelineStore } from '@/stores/kittyPipeline'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

export type RunKittyEditTurnDeps = {
  kitty: ReturnType<typeof useKittyAgent>
  buildContext: () => KittyAgentContext
  updateContext: (context: KittyAgentContext, options?: KittyContextUpdateOptions) => void
  getScope: () => string
  lane: 'mobile' | 'desktop'
  ensureConnected?: () => Promise<boolean>
  appendUserTurn: (text: string, requestId: string, ctx: KittyTurnContext) => Promise<boolean>
  onFailMessage: (message: string) => void
  t: KittyTranslateFn
  /** Skip create-phase / busy guards — caller already validated. */
  skipSessionEnsure?: boolean
}

export type RunKittyEditTurnInput = {
  text: string
  source: 'asr' | 'text' | 'clarify_choice'
  ctx?: KittyTurnContext
  requestId?: string
  utteranceId?: string
}

export type RunKittyEditTurnResult = {
  ok: boolean
  ctx: KittyTurnContext
  sent: boolean
}

export async function runKittyEditTurn(
  deps: RunKittyEditTurnDeps,
  input: RunKittyEditTurnInput
): Promise<RunKittyEditTurnResult> {
  const text = input.text.trim()
  const scope = deps.getScope().trim()
  const requestId = input.ctx?.requestId ?? input.requestId ?? safeRandomUUID()
  const ctx: KittyTurnContext = {
    requestId,
    utteranceId: input.ctx?.utteranceId ?? input.utteranceId,
    scope: scope || input.ctx?.scope || 'scope',
    lane: deps.lane,
    voiceSessionId: input.ctx?.voiceSessionId,
  }

  if (!text) {
    return { ok: false, ctx, sent: false }
  }

  beginKittyTurn(ctx)
  const pipeline = useKittyPipelineStore()
  eventBus.emit('kitty:edit_turn_requested', {
    ctx,
    text,
    source: input.source,
  })

  const histOk = await deps.appendUserTurn(text, requestId, ctx)
  if (!histOk) {
    const fail = pipeline.getLastFail()
    if (fail) {
      deps.onFailMessage(messageForKittyFail(fail, deps.t))
    }
    return { ok: false, ctx, sent: false }
  }

  if (!deps.skipSessionEnsure) {
    if (deps.ensureConnected) {
      recordPipelineEvent({
        ctx,
        module: 'session',
        step: 'S02_session_ready',
        status: 'started',
      })
      const connected = await deps.ensureConnected()
      if (!connected) {
        failKittyTurn({
          ctx,
          module: 'session',
          step: 'S02_session_ready',
          errorCode: 'not_connected',
        })
        deps.onFailMessage(messageForKittyFail(pipeline.getLastFail()!, deps.t))
        return { ok: false, ctx, sent: false }
      }
      recordPipelineEvent({
        ctx,
        module: 'session',
        step: 'S02_session_ready',
        status: 'ok',
      })
    } else {
      const session = await ensureKittySessionConnected({
        kitty: deps.kitty,
        getScope: deps.getScope,
        buildContext: deps.buildContext,
        lane: deps.lane,
        turnCtx: ctx,
      })
      if (!session.ok) {
        const fail = pipeline.getLastFail()
        if (fail) {
          deps.onFailMessage(messageForKittyFail(fail, deps.t))
        }
        return { ok: false, ctx, sent: false }
      }
    }
  }

  // Mobile is mic+chat only — server prefers live_spec/library; no phone pre-edit push.
  if (deps.lane !== 'mobile') {
    let hub = await runKittyHubSync({
      deps: {
        buildContext: deps.buildContext,
        updateContext: deps.updateContext,
        getScope: deps.getScope,
        isConnected: () => deps.kitty.isConnected.value,
        lane: deps.lane,
      },
      ctx,
      reason: 'edit_gate',
    })

    if (!hub.ok && !deps.kitty.isConnected.value) {
      const reconnected = deps.ensureConnected
        ? await deps.ensureConnected()
        : (
            await ensureKittySessionConnected({
              kitty: deps.kitty,
              getScope: deps.getScope,
              buildContext: deps.buildContext,
              lane: deps.lane,
              turnCtx: ctx,
            })
          ).ok
      if (reconnected) {
        hub = await runKittyHubSync({
          deps: {
            buildContext: deps.buildContext,
            updateContext: deps.updateContext,
            getScope: deps.getScope,
            isConnected: () => deps.kitty.isConnected.value,
            lane: deps.lane,
          },
          ctx,
          reason: 'edit_gate',
        })
      }
    }

    if (!hub.ok) {
      const fail = pipeline.getLastFail()
      deps.onFailMessage(
        fail
          ? messageForKittyFail(fail, deps.t)
          : deps.t(
              'canvas.mindMapOneSentence.kittyContextSyncFailed',
              'Could not sync the canvas. Please try again in a moment.'
            )
      )
      return { ok: false, ctx, sent: false }
    }
  } else {
    recordPipelineEvent({
      ctx,
      module: 'hub_sync',
      step: 'S07_hub_sync',
      status: 'skip',
      detail: 'mobile thin ingress — server live_spec',
    })
  }

  pipeline.setPhase('sending')
  recordPipelineEvent({
    ctx,
    module: 'edit_pipeline',
    step: 'S08_text_send',
    status: 'started',
  })

  const ingress = beginKittySessionIngress({
    requestId,
    source: input.source,
    text,
    utteranceId: ctx.utteranceId,
  })
  let sent = deps.kitty.sendTextMessage(text, ingress)
  if (!sent) {
    const reconnected = deps.ensureConnected
      ? await deps.ensureConnected()
      : (
          await ensureKittySessionConnected({
            kitty: deps.kitty,
            getScope: deps.getScope,
            buildContext: deps.buildContext,
            lane: deps.lane,
            turnCtx: ctx,
          })
        ).ok
    if (reconnected) {
      sent = deps.kitty.sendTextMessage(text, ingress)
    }
  }

  if (!sent) {
    failKittyTurn({
      ctx,
      module: 'edit_pipeline',
      step: 'S08_text_send',
      errorCode: 'text_send_failed',
    })
    deps.onFailMessage(messageForKittyFail(pipeline.getLastFail()!, deps.t))
    return { ok: false, ctx, sent: false }
  }

  recordPipelineEvent({
    ctx,
    module: 'edit_pipeline',
    step: 'S08_text_send',
    status: 'ok',
    detail: text.slice(0, 80),
  })
  pipeline.setPhase('awaiting_result')
  recordPipelineEvent({
    ctx,
    module: 'server',
    step: 'S09_server_llm',
    status: 'started',
    detail: 'awaiting diagram_update or reply',
  })
  return { ok: true, ctx, sent: true }
}

/** Mark S09 ok when diagram or reply arrives; complete turn on verified mutation path separately. */
export function markKittyServerStepOk(ctx: KittyTurnContext, detail?: string): void {
  recordPipelineEvent({
    ctx,
    module: 'server',
    step: 'S09_server_llm',
    status: 'ok',
    detail,
  })
}

export function markKittyEditTurnCompleted(ctx: KittyTurnContext): void {
  completeKittyTurn(ctx, 'S14_history_reply')
}
