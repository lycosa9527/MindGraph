import { emitEvent } from './events'
import type { DiagramContext } from './types'

export function useFlowMapOpsSlice(ctx: DiagramContext) {
  const { type, data } = ctx

  function toggleFlowMapOrientation(): void {
    if (!data.value || type.value !== 'flow_map') return

    const currentOrientation = (data.value as Record<string, unknown>).orientation as
      | 'horizontal'
      | 'vertical'
      | undefined
    const newOrientation = currentOrientation === 'horizontal' ? 'vertical' : 'horizontal'

    const topicNode = data.value.nodes.find((n) => n.id === 'flow-topic')
    const flowTitle = topicNode?.text ?? (data.value as Record<string, unknown>).title ?? ''
    const stepNodes = data.value.nodes.filter((n) => n.type === 'flow')
    const substepNodes = data.value.nodes.filter((n) => n.type === 'flowSubstep')

    const steps = stepNodes.map((node) => node.text)

    const stepToSubsteps: Record<string, string[]> = {}
    substepNodes.forEach((node) => {
      const match = node.id.match(/flow-substep-(\d+)-/)
      if (match) {
        const stepIndex = parseInt(match[1], 10)
        if (stepIndex < stepNodes.length) {
          const stepText = stepNodes[stepIndex].text
          if (!stepToSubsteps[stepText]) {
            stepToSubsteps[stepText] = []
          }
          stepToSubsteps[stepText].push(node.text)
        }
      }
    })

    const substeps = Object.entries(stepToSubsteps).map(([step, subs]) => ({
      step,
      substeps: subs,
    }))

    const newSpec = {
      title: flowTitle,
      steps,
      substeps,
      orientation: newOrientation,
    }

    ctx.loadFromSpec(newSpec, 'flow_map')
    ctx.pushHistory(`Toggle orientation to ${newOrientation}`)
    emitEvent('diagram:orientation_changed', { orientation: newOrientation })
  }

  function addFlowMapStep(text: string, defaultSubsteps?: [string, string]): boolean {
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec) return false
    const steps = spec.steps as string[]
    steps.push(text)
    const substeps = spec.substeps as Array<{ step: string; substeps: string[] }>
    if (defaultSubsteps && defaultSubsteps.length >= 2) {
      substeps.push({ step: text, substeps: [defaultSubsteps[0], defaultSubsteps[1]] })
    }
    const orientation = (data.value as Record<string, unknown>)?.orientation ?? spec.orientation
    ctx.loadFromSpec({ ...spec, steps, substeps, orientation }, 'flow_map')
    ctx.pushHistory('Add flow step')
    emitEvent('diagram:node_added', { node: null })
    return true
  }

  function addFlowMapSubstep(stepText: string, substepText: string): boolean {
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec) return false
    const substeps = spec.substeps as Array<{ step: string; substeps: string[] }>
    const entry = substeps.find((e) => e.step === stepText)
    if (entry) {
      entry.substeps.push(substepText)
    } else {
      substeps.push({ step: stepText, substeps: [substepText] })
    }
    const orientation = (data.value as Record<string, unknown>)?.orientation ?? spec.orientation
    ctx.loadFromSpec({ ...spec, substeps, orientation }, 'flow_map')
    ctx.pushHistory('Add flow substep')
    emitEvent('diagram:node_added', { node: null })
    return true
  }

  return { toggleFlowMapOrientation, addFlowMapStep, addFlowMapSubstep }
}
