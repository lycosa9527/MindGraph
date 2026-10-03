import { type FlowSubstepEntry, findFlowSubstepEntry } from '../specLoader/flowMapSubsteps'
import { emitCtxEvent } from './events'
import type { DiagramContext } from './types'

interface FlowSecondaryMirror {
  steps?: string[]
  substeps?: Array<{ substeps?: string[] }>
}

function flowSecondaryMirror(spec: Record<string, unknown>): FlowSecondaryMirror | null {
  const raw = spec.secondary
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  return raw as FlowSecondaryMirror
}

function padFlowSecondary(
  spec: Record<string, unknown>,
  options: { step: boolean; substeps: number; groupIndex?: number }
): void {
  const secondary = flowSecondaryMirror(spec)
  if (!secondary) return
  if (options.step) {
    secondary.steps = [...(secondary.steps ?? []), '']
    if (options.substeps > 0) {
      const blank = Array.from({ length: options.substeps }, () => '')
      secondary.substeps = [...(secondary.substeps ?? []), { substeps: blank }]
    }
    return
  }
  const groups = secondary.substeps ?? []
  const index = options.groupIndex ?? 0
  while (groups.length <= index) groups.push({ substeps: [] })
  const lines = groups[index].substeps ?? []
  for (let count = 0; count < options.substeps; count += 1) lines.push('')
  groups[index].substeps = lines
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

    ctx.loadFromSpec(spec, 'flow_map', { mergePreviousNodeStyles: true })
    ctx.pushHistory(`Toggle orientation to ${newOrientation}`)
    emitCtxEvent(ctx, 'diagram:orientation_changed', { orientation: newOrientation })
  }

  function addFlowMapStep(text: string, defaultSubsteps?: [string, string]): boolean {
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec) return false
    const steps = spec.steps as Array<string | { id?: string; text: string }>
    steps.push({ text })
    const substeps = spec.substeps as FlowSubstepEntry[]
    const addedSubsteps = Boolean(defaultSubsteps && defaultSubsteps.length >= 2)
    if (addedSubsteps && defaultSubsteps) {
      substeps.push({
        step: text,
        stepIndex: steps.length - 1,
        substeps: [defaultSubsteps[0], defaultSubsteps[1]],
      })
    }
    padFlowSecondary(spec, { step: true, substeps: addedSubsteps ? 2 : 0 })
    const orientation = (data.value as Record<string, unknown>)?.orientation ?? spec.orientation
    ctx.loadFromSpec({ ...spec, steps, substeps, orientation }, 'flow_map', {
      mergePreviousNodeStyles: true,
    })
    ctx.pushHistory('Add flow step')
    emitCtxEvent(ctx, 'diagram:node_added', { node: null })
    return true
  }

  function addFlowMapSubstep(
    stepText: string,
    substepText: string,
    stepIndex?: number,
    stepId?: string
  ): boolean {
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec) return false
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
    padFlowSecondary(spec, { step: false, substeps: 1, groupIndex })
    const orientation = (data.value as Record<string, unknown>)?.orientation ?? spec.orientation
    ctx.loadFromSpec({ ...spec, substeps, orientation }, 'flow_map', {
      mergePreviousNodeStyles: true,
    })
    ctx.pushHistory('Add flow substep')
    emitCtxEvent(ctx, 'diagram:node_added', { node: null })
    return true
  }

  return { toggleFlowMapOrientation, addFlowMapStep, addFlowMapSubstep }
}
