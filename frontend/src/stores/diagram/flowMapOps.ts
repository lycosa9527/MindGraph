import {
  type InsertLabelInput,
  insertLabelGloss,
  insertLabelText,
} from '@/diagramBilingual/insertLabel'
import {
  type FlowMapStructureMode,
  type FlowSubstepArrangement,
  normalizeFlowMapStructureMode,
  normalizeFlowSubstepArrangement,
  resolveFlowMapStructureMode,
  resolveFlowMapSubstepArrangement,
} from '@/utils/flowMapSubstepArrangement'

import { type FlowSubstepEntry, findFlowSubstepEntry } from '../specLoader/flowMapSubsteps'
import { emitCtxEvent } from './events'
import { type DiagramContext, STRUCTURAL_SPEC_RELOAD } from './types'

interface FlowSecondaryMirror {
  steps?: string[]
  substeps?: Array<{ substeps?: string[] }>
}

function flowSecondaryMirror(spec: Record<string, unknown>): FlowSecondaryMirror | null {
  const raw = spec.secondary
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  return raw as FlowSecondaryMirror
}

/** Push one gloss per new slot so later translations do not shift. */
function padFlowSecondary(
  spec: Record<string, unknown>,
  options: { step?: string; substeps: string[]; groupIndex?: number }
): void {
  const secondary = flowSecondaryMirror(spec)
  if (!secondary) return
  if (options.step !== undefined) {
    secondary.steps = [...(secondary.steps ?? []), options.step]
    if (options.substeps.length > 0) {
      secondary.substeps = [...(secondary.substeps ?? []), { substeps: [...options.substeps] }]
    }
    return
  }
  const groups = secondary.substeps ?? []
  const index = options.groupIndex ?? 0
  while (groups.length <= index) groups.push({ substeps: [] })
  groups[index].substeps = [...(groups[index].substeps ?? []), ...options.substeps]
  secondary.substeps = groups
}

function insertFlowSecondaryStep(
  spec: Record<string, unknown>,
  gloss: string,
  atIndex: number
): void {
  const secondary = flowSecondaryMirror(spec)
  if (!secondary) return
  const steps = [...(secondary.steps ?? [])]
  const groups = [...(secondary.substeps ?? [])]
  while (steps.length < atIndex) steps.push('')
  while (groups.length < atIndex) groups.push({ substeps: [] })
  steps.splice(atIndex, 0, gloss)
  groups.splice(atIndex, 0, { substeps: [] })
  secondary.steps = steps
  secondary.substeps = groups
}

function insertFlowSecondarySubstep(
  spec: Record<string, unknown>,
  gloss: string,
  groupIndex: number,
  atIndex: number
): void {
  const secondary = flowSecondaryMirror(spec)
  if (!secondary) return
  const groups = [...(secondary.substeps ?? [])]
  while (groups.length <= groupIndex) groups.push({ substeps: [] })
  const kids = [...(groups[groupIndex].substeps ?? [])]
  while (kids.length < atIndex) kids.push('')
  kids.splice(atIndex, 0, gloss)
  groups[groupIndex] = { substeps: kids }
  secondary.substeps = groups
}

function bumpFlowSubstepIndexes(substeps: FlowSubstepEntry[], fromIndex: number): void {
  for (const entry of substeps) {
    if (typeof entry.stepIndex === 'number' && entry.stepIndex >= fromIndex) {
      entry.stepIndex += 1
    }
  }
}

export function useFlowMapOpsSlice(ctx: DiagramContext) {
  const { type, data } = ctx

  function toggleFlowMapOrientation(): void {
    if (!data.value || type.value !== 'flow_map') return

    const currentOrientation = (data.value as Record<string, unknown>).orientation as
      'horizontal' | 'vertical' | undefined
    const newOrientation = currentOrientation === 'horizontal' ? 'vertical' : 'horizontal'

    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec) return
    spec.orientation = newOrientation

    ctx.loadFromSpec(spec, 'flow_map', STRUCTURAL_SPEC_RELOAD)
    ctx.pushHistory(`Toggle orientation to ${newOrientation}`)
    emitCtxEvent(ctx, 'diagram:orientation_changed', { orientation: newOrientation })
  }

  function setFlowMapSubstepArrangement(mode: FlowSubstepArrangement): boolean {
    if (!data.value || type.value !== 'flow_map') return false
    const next = normalizeFlowSubstepArrangement(mode)
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec) return false
    if (normalizeFlowSubstepArrangement(spec.substepArrangement) === next) return false
    spec.substepArrangement = next
    ctx.loadFromSpec(spec, 'flow_map', STRUCTURAL_SPEC_RELOAD)
    ctx.pushHistory(`Set substep arrangement to ${next}`)
    emitCtxEvent(ctx, 'diagram:orientation_changed', { substepArrangement: next })
    return true
  }

  function getFlowMapSubstepArrangement(): FlowSubstepArrangement {
    if (!data.value || type.value !== 'flow_map') {
      return normalizeFlowSubstepArrangement(undefined)
    }
    const topic = data.value.nodes.find((n) => n.id === 'flow-topic')
    return resolveFlowMapSubstepArrangement(topic, data.value as Record<string, unknown>)
  }

  function getFlowMapStructureMode(): FlowMapStructureMode {
    if (!data.value || type.value !== 'flow_map') {
      return normalizeFlowMapStructureMode(undefined)
    }
    const topic = data.value.nodes.find((n) => n.id === 'flow-topic')
    return resolveFlowMapStructureMode(topic, data.value as Record<string, unknown>)
  }

  function setFlowMapStructureMode(mode: FlowMapStructureMode): boolean {
    if (!data.value || type.value !== 'flow_map') return false
    const next = normalizeFlowMapStructureMode(mode)
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec) return false
    const current = resolveFlowMapStructureMode(
      data.value.nodes.find((n) => n.id === 'flow-topic'),
      data.value as Record<string, unknown>
    )
    if (current === next) return false
    if (next === 'vertical') {
      spec.orientation = 'vertical'
    } else {
      spec.orientation = 'horizontal'
      spec.substepArrangement = next
    }
    ctx.loadFromSpec(spec, 'flow_map', STRUCTURAL_SPEC_RELOAD)
    ctx.pushHistory(`Set flow structure to ${next}`)
    emitCtxEvent(ctx, 'diagram:orientation_changed', {
      orientation: spec.orientation,
      substepArrangement: spec.substepArrangement,
      structureMode: next,
    })
    return true
  }

  function addFlowMapStep(
    label: InsertLabelInput,
    defaultSubsteps?: [InsertLabelInput, InsertLabelInput]
  ): boolean {
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec) return false
    const steps = spec.steps as Array<string | { id?: string; text: string }>
    return insertFlowMapStepAt(label, steps.length, defaultSubsteps)
  }

  function insertFlowMapStepAt(
    label: InsertLabelInput,
    atIndex: number,
    defaultSubsteps?: [InsertLabelInput, InsertLabelInput]
  ): boolean {
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec) return false
    const text = insertLabelText(label)
    const steps = spec.steps as Array<string | { id?: string; text: string }>
    const substeps = spec.substeps as FlowSubstepEntry[]
    const index = Math.max(0, Math.min(atIndex, steps.length))
    steps.splice(index, 0, { text })
    bumpFlowSubstepIndexes(substeps, index)
    const children = defaultSubsteps ?? []
    if (children.length > 0) {
      substeps.push({
        step: text,
        stepIndex: index,
        substeps: children.map((child) => insertLabelText(child)),
      })
    }
    insertFlowSecondaryStep(spec, insertLabelGloss(label), index)
    if (children.length > 0) {
      padFlowSecondary(spec, {
        substeps: children.map((child) => insertLabelGloss(child)),
        groupIndex: index,
      })
    }
    const orientation = (data.value as Record<string, unknown>)?.orientation ?? spec.orientation
    ctx.loadFromSpec({ ...spec, steps, substeps, orientation }, 'flow_map', STRUCTURAL_SPEC_RELOAD)
    ctx.pushHistory('Add flow step')
    emitCtxEvent(ctx, 'diagram:node_added', { node: null })
    return true
  }

  function addFlowMapSubstep(
    stepText: string,
    substepLabel: InsertLabelInput,
    stepIndex?: number,
    stepId?: string
  ): boolean {
    return insertFlowMapSubstepAt(stepText, substepLabel, undefined, stepIndex, stepId)
  }

  function insertFlowMapSubstepAt(
    stepText: string,
    substepLabel: InsertLabelInput,
    atIndex: number | undefined,
    stepIndex?: number,
    stepId?: string
  ): boolean {
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec) return false
    const substepText = insertLabelText(substepLabel)
    const substeps = spec.substeps as FlowSubstepEntry[]
    const entry = findFlowSubstepEntry(substeps, stepText, stepIndex, stepId)
    let groupIndex: number
    if (entry) {
      const kids = entry.substeps
      const index =
        atIndex === undefined ? kids.length : Math.max(0, Math.min(atIndex, kids.length))
      kids.splice(index, 0, substepText)
      groupIndex = substeps.indexOf(entry)
      insertFlowSecondarySubstep(spec, insertLabelGloss(substepLabel), groupIndex, index)
    } else {
      substeps.push({
        step: stepText,
        stepId,
        stepIndex,
        substeps: [substepText],
      })
      groupIndex = substeps.length - 1
      padFlowSecondary(spec, { substeps: [insertLabelGloss(substepLabel)], groupIndex })
    }
    const orientation = (data.value as Record<string, unknown>)?.orientation ?? spec.orientation
    ctx.loadFromSpec({ ...spec, substeps, orientation }, 'flow_map', STRUCTURAL_SPEC_RELOAD)
    ctx.pushHistory('Add flow substep')
    emitCtxEvent(ctx, 'diagram:node_added', { node: null })
    return true
  }

  return {
    toggleFlowMapOrientation,
    setFlowMapSubstepArrangement,
    getFlowMapSubstepArrangement,
    setFlowMapStructureMode,
    getFlowMapStructureMode,
    addFlowMapStep,
    insertFlowMapStepAt,
    addFlowMapSubstep,
    insertFlowMapSubstepAt,
  }
}
