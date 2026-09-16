import { describe, expect, it } from 'vitest'

import { loadSpecForDiagramType } from '@/stores/specLoader'
import { loadFlowMapSpec } from '@/stores/specLoader/flowMap'
import { collectFlowMapSpecFromNodes } from '@/stores/specLoader/flowMapSubsteps'
import type { Connection, DiagramNode } from '@/types'
import { isLeftoverFlowMapId, resolveFlowMapAliasId } from '@/utils/flowMapIdentity'
import { migrateFlowMapIdentityIds } from '@/utils/flowMapIdentityMigrate'

function leftoverFlowNodes(): DiagramNode[] {
  return [
    {
      id: 'flow-topic',
      type: 'topic',
      text: 'Process',
      position: { x: 0, y: 0 },
    },
    {
      id: 'flow-step-0',
      type: 'flow',
      text: 'First',
      position: { x: 120, y: 0 },
    },
    {
      id: 'flow-step-1',
      type: 'flow',
      text: 'Second',
      position: { x: 280, y: 0 },
    },
    {
      id: 'flow-substep-0-0',
      type: 'flowSubstep',
      text: 'A1',
      position: { x: 120, y: 80 },
    },
    {
      id: 'flow-substep-1-0',
      type: 'flowSubstep',
      text: 'B1',
      position: { x: 280, y: 80 },
    },
  ]
}

function leftoverFlowConnections(): Connection[] {
  return [
    { id: 'edge-flow-topic-flow-step-0', source: 'flow-topic', target: 'flow-step-0' },
    { id: 'edge-flow-step-0-flow-step-1', source: 'flow-step-0', target: 'flow-step-1' },
    { id: 'edge-flow-step-0-flow-substep-0-0', source: 'flow-step-0', target: 'flow-substep-0-0' },
    { id: 'edge-flow-step-1-flow-substep-1-0', source: 'flow-step-1', target: 'flow-substep-1-0' },
  ]
}

describe('flowMapIdentity', () => {
  it('migrates leftover slot ids to UUIDs and keeps leftover aliases', () => {
    const migrated = migrateFlowMapIdentityIds(leftoverFlowNodes(), leftoverFlowConnections())
    const steps = migrated.nodes.filter((node) => node.type === 'flow')
    const subs = migrated.nodes.filter((node) => node.type === 'flowSubstep')

    expect(steps).toHaveLength(2)
    expect(subs).toHaveLength(2)
    for (const node of [...steps, ...subs]) {
      expect(isLeftoverFlowMapId(node.id)).toBe(false)
    }
    expect(steps[0]?.data?.flowMapLegacyId).toBe('flow-step-0')
    expect(resolveFlowMapAliasId('flow-step-0', migrated.nodes)).toBe(steps[0]?.id)
    expect(resolveFlowMapAliasId('flow-substep-1-0', migrated.nodes)).toBe(subs[1]?.id)
    expect(migrated.connections[0]?.target).toBe(steps[0]?.id)
    expect(subs[0]?.data?.parentStepId).toBe(steps[0]?.id)
    expect(subs[1]?.data?.parentStepId).toBe(steps[1]?.id)
  })

  it('preserves UUIDs across collect then loadFromSpec', () => {
    const first = loadFlowMapSpec({
      title: 'Process',
      steps: ['First', 'Second'],
      substeps: [
        { step: 'First', stepIndex: 0, substeps: ['A1'] },
        { step: 'Second', stepIndex: 1, substeps: ['B1'] },
      ],
      orientation: 'horizontal',
    })
    const collected = collectFlowMapSpecFromNodes(first.nodes)
    const second = loadFlowMapSpec({
      title: 'Process',
      steps: collected.steps,
      substeps: collected.substeps,
      orientation: 'horizontal',
    })

    expect(second.nodes.filter((node) => node.type === 'flow').map((node) => node.id)).toEqual(
      first.nodes.filter((node) => node.type === 'flow').map((node) => node.id)
    )
    expect(
      second.nodes.filter((node) => node.type === 'flowSubstep').map((node) => node.id)
    ).toEqual(first.nodes.filter((node) => node.type === 'flowSubstep').map((node) => node.id))
  })

  it('migrates leftover ids on generic saved-spec load', () => {
    const loaded = loadSpecForDiagramType(
      {
        nodes: leftoverFlowNodes(),
        connections: leftoverFlowConnections(),
      },
      'flow_map'
    )
    const steps = loaded.nodes.filter((node) => node.type === 'flow')
    expect(steps).toHaveLength(2)
    expect(isLeftoverFlowMapId(steps[0]?.id ?? '')).toBe(false)
    expect(resolveFlowMapAliasId('flow-step-1', loaded.nodes)).toBe(steps[1]?.id)
  })
})
