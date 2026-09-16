import {
  type FlowSubstepEntry,
  collectFlowMapSpecFromNodes,
  findFlowSubstepEntry,
} from '../specLoader/flowMapSubsteps'
import { emitCtxEvent } from './events'
import type { DiagramContext } from './types'

export function useFlowMapOpsSlice(ctx: DiagramContext) {
  const { type, data } = ctx

  function toggleFlowMapOrientation(): void {
    if (!data.value || type.value !== 'flow_map') return

    const currentOrientation = (data.value as Record<string, unknown>).orientation as
      'horizontal' | 'vertical' | undefined
    const newOrientation = currentOrientation === 'horizontal' ? 'vertical' : 'horizontal'

    const topicNode = data.value.nodes.find((n) => n.id === 'flow-topic')
    const flowTitle = topicNode?.text ?? (data.value as Record<string, unknown>).title ?? ''
    const collected = collectFlowMapSpecFromNodes(data.value.nodes)

    const newSpec = {
      title: flowTitle,
      steps: collected.steps,
      substeps: collected.substeps,
      orientation: newOrientation,
    }

    ctx.loadFromSpec(newSpec, 'flow_map', { mergePreviousNodeStyles: true })
    ctx.pushHistory(`Toggle orientation to ${newOrientation}`)
    emitCtxEvent(ctx, 'diagram:orientation_changed', { orientation: newOrientation })
  }

  function addFlowMapStep(text: string, defaultSubsteps?: [string, string]): boolean {
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec) return false
    const steps = spec.steps as Array<string | { id?: string; text: string }>
    steps.push({ text })
    const substeps = spec.substeps as FlowSubstepEntry[]
    if (defaultSubsteps && defaultSubsteps.length >= 2) {
      substeps.push({
        step: text,
        stepIndex: steps.length - 1,
        substeps: [defaultSubsteps[0], defaultSubsteps[1]],
      })
    }
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
    if (entry) {
      entry.substeps.push(substepText)
    } else {
      substeps.push({
        step: stepText,
        stepId,
        stepIndex,
        substeps: [substepText],
      })
    }
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
