/**
 * Apply Kitty diagram_update with mandatory post-apply verification,
 * Hub persist, then combined WS ack.
 */
import {
  applyVoiceDiagramAddNodes,
  applyVoiceDiagramRemoveNodes,
  applyVoiceDiagramUpdateCenter,
  applyVoiceDiagramUpdateNodes,
} from '@/composables/editor/diagramVoiceMutations'
import {
  persistVerifiedDiagramToHub,
  type DiagramHubPersistDeps,
} from '@/composables/kitty/diagramEditHubPersist'
import { useDiagramStore } from '@/stores/diagram'
import { loadSpecForDiagramType } from '@/stores/specLoader'
import type { Connection, DiagramNode, DiagramType } from '@/types'
import {
  captureDiagramFingerprint,
  resolveCreatedNodeIds,
  type DiagramEditExpectedEffect,
  type DiagramFingerprint,
  verifyMindMapEffect,
} from '@/utils/diagramEditVerify'

export type DiagramEditApplyResult = {
  applied: boolean
  verified: boolean
  hubPersistOk?: boolean
  hubRevision?: number
  verificationError?: string
  evidence: DiagramFingerprint
}

export type DiagramMutationAckSender = (payload: Record<string, unknown>) => void

function reloadFromFingerprint(
  store: ReturnType<typeof useDiagramStore>,
  fingerprint: DiagramFingerprint
): void {
  const diagramType = (store.type ?? 'mindmap') as DiagramType
  const spec = {
    nodes: fingerprint.nodes,
    connections: fingerprint.connections,
  }
  const loaded = loadSpecForDiagramType(spec, diagramType)
  if (!store.data) return
  store.data.nodes = loaded.nodes
  store.data.connections = loaded.connections
}

function applyDiagramUpdateAction(
  store: ReturnType<typeof useDiagramStore>,
  action: string,
  updates: Record<string, unknown> | unknown[]
): number {
  if (!store.data?.nodes) return 0

  switch (action) {
    case 'update_center':
      return applyVoiceDiagramUpdateCenter(store, updates as Record<string, unknown>) ? 1 : 0
    case 'update_node':
    case 'update_nodes': {
      const rows = Array.isArray(updates) ? updates : [updates]
      return applyVoiceDiagramUpdateNodes(store, rows)
    }
    case 'add_node':
    case 'add_nodes': {
      const rows = Array.isArray(updates) ? updates : [updates]
      return applyVoiceDiagramAddNodes(store, rows)
    }
    case 'delete_node':
    case 'remove_nodes': {
      const ids = Array.isArray(updates) ? updates : [updates]
      return applyVoiceDiagramRemoveNodes(store, ids)
    }
    default:
      return 0
  }
}

function sendCombinedAck(
  sendAck: DiagramMutationAckSender,
  payload: {
    mutationId: string
    verified: boolean
    hubPersistOk?: boolean
    hubRevision?: number | null
    errorCode?: string
    message?: string
    evidence?: DiagramFingerprint
    createdNodeIds?: string[]
  }
): void {
  sendAck({
    type: 'diagram_mutation_ack',
    mutation_id: payload.mutationId,
    verified: payload.verified,
    ok: payload.verified,
    hub_persist_ok: payload.hubPersistOk,
    hub_revision: payload.hubRevision ?? undefined,
    error_code: payload.errorCode,
    message: payload.message,
    revision: payload.hubRevision ?? undefined,
    created_node_ids:
      payload.createdNodeIds && payload.createdNodeIds.length > 0
        ? payload.createdNodeIds
        : undefined,
    evidence: payload.evidence
      ? { nodes: payload.evidence.nodes, connections: payload.evidence.connections }
      : undefined,
  })
}

export async function applyVerifiedDiagramUpdate(
  action: string,
  updates: Record<string, unknown> | unknown[],
  options: {
    mutationId: string
    expectedEffect?: DiagramEditExpectedEffect
    beforeFingerprint?: DiagramFingerprint
    sendAck: DiagramMutationAckSender
    hubRevision?: number | null
    hubPersist?: DiagramHubPersistDeps
  }
): Promise<DiagramEditApplyResult> {
  const store = useDiagramStore()
  const nodes = store.data?.nodes ?? []
  const connections = store.data?.connections ?? []

  const before =
    options.beforeFingerprint ??
    captureDiagramFingerprint(nodes as DiagramNode[], connections as Connection[])
  const beforeCount = before.nodes.length

  const appliedCount = applyDiagramUpdateAction(store, action, updates)
  const afterNodes = store.data?.nodes ?? []
  const afterConnections = store.data?.connections ?? []
  const evidence = captureDiagramFingerprint(
    afterNodes as DiagramNode[],
    afterConnections as Connection[]
  )

  if (appliedCount === 0) {
    sendCombinedAck(options.sendAck, {
      mutationId: options.mutationId,
      verified: false,
      hubPersistOk: false,
      hubRevision: options.hubRevision ?? null,
      errorCode: 'apply_noop',
    })
    return { applied: false, verified: false, evidence, verificationError: 'apply_noop' }
  }

  const effect = options.expectedEffect
  const diagramType = store.type === 'mind_map' ? 'mindmap' : store.type
  let verified = true
  let verificationError: string | undefined

  if (effect && diagramType === 'mindmap') {
    const report = verifyMindMapEffect(effect, evidence, beforeCount)
    verified = report.ok
    verificationError = report.error
    if (!verified) {
      reloadFromFingerprint(store, before)
      sendCombinedAck(options.sendAck, {
        mutationId: options.mutationId,
        verified: false,
        hubPersistOk: false,
        hubRevision: options.hubRevision ?? null,
        errorCode: 'verify_failed',
        message: verificationError,
      })
      return {
        applied: true,
        verified: false,
        evidence,
        verificationError,
      }
    }
  }

  let hubPersistOk = false
  let hubRevision: number | undefined

  if (options.hubPersist) {
    const persistResult = await persistVerifiedDiagramToHub(options.hubPersist)
    hubPersistOk = persistResult.ok
    hubRevision = persistResult.revision
    if (!hubPersistOk) {
      reloadFromFingerprint(store, before)
      sendCombinedAck(options.sendAck, {
        mutationId: options.mutationId,
        verified: false,
        hubPersistOk: false,
        hubRevision: options.hubRevision ?? null,
        errorCode: 'hub_persist_failed',
        message: persistResult.error,
      })
      return {
        applied: true,
        verified: false,
        hubPersistOk: false,
        evidence,
        verificationError: persistResult.error ?? 'hub_persist_failed',
      }
    }
  } else {
    hubPersistOk = true
    hubRevision =
      typeof options.hubRevision === 'number' ? options.hubRevision : undefined
  }

  sendCombinedAck(options.sendAck, {
    mutationId: options.mutationId,
    verified: true,
    hubPersistOk: true,
    hubRevision: hubRevision ?? options.hubRevision ?? null,
    evidence,
    createdNodeIds: resolveCreatedNodeIds(before, evidence, effect),
  })

  return {
    applied: true,
    verified: true,
    hubPersistOk,
    hubRevision,
    evidence,
  }
}
