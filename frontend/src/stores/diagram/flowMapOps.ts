import {
  type InsertLabelInput,
  insertLabelGloss,
  insertLabelText,
} from '@/diagramBilingual/insertLabel'

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

  function addFlowMapStep(
    label: InsertLabelInput,
    defaultSubsteps?: [InsertLabelInput, InsertLabelInput]
  ): boolean {
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec) return false
    const text = insertLabelText(label)
    const steps = spec.steps as Array<string | { id?: string; text: string }>
    steps.push({ text })
    const substeps = spec.substeps as FlowSubstepEntry[]
    const children = defaultSubsteps ?? []
    if (children.length > 0) {
      substeps.push({
        step: text,
        stepIndex: steps.length - 1,
        substeps: children.map((child) => insertLabelText(child)),
      })
    }
    padFlowSecondary(spec, {
      step: insertLabelGloss(label),
      substeps: children.map((child) => insertLabelGloss(child)),
    })
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
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec) return false
    const substepText = insertLabelText(substepLabel)
    const substeps = spec.substeps as FlowSubstepEntry[]
    const entry = findFlowSubstepEntry(substeps, stepText, stepIndex, stepId)
    let groupIndex: number
    if (entry) {
      entry.substeps.push(substepText)
      groupIndex = substeps.indexOf(entry)
    } else {
      substeps.push({
        step: stepText,
        stepId,
        stepIndex,
        substeps: [substepText],
      })
      groupIndex = substeps.length - 1
    }
    padFlowSecondary(spec, { substeps: [insertLabelGloss(substepLabel)], groupIndex })
    const orientation = (data.value as Record<string, unknown>)?.orientation ?? spec.orientation
    ctx.loadFromSpec({ ...spec, substeps, orientation }, 'flow_map', STRUCTURAL_SPEC_RELOAD)
    ctx.pushHistory('Add flow substep')
    emitCtxEvent(ctx, 'diagram:node_added', { node: null })
    return true
  }

  return { toggleFlowMapOrientation, addFlowMapStep, addFlowMapSubstep }
}
