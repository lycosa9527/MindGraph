<script setup lang="ts">
/**
 * Provides a DiagramSession to descendant DiagramCanvas / nodes.
 * Pass an existing session, or create a readonly preview session from props.
 */
import { onBeforeUnmount, provide, watch } from 'vue'

import { DiagramSessionKey } from '@/composables/diagram/useDiagramSession'
import {
  asDiagramSession,
  createDiagramSession,
  createDiagramViewBus,
  type DiagramSession,
  type DiagramSessionMode,
} from '@/stores/diagram'
import type { DiagramType } from '@/types'

const props = withDefaults(
  defineProps<{
    /** Existing session (e.g. editor Pinia store). */
    session?: DiagramSession | null
    /** When session is omitted, create one with this mode. */
    mode?: DiagramSessionMode
    vueFlowId?: string
    /** Load this spec into a created session (preview). */
    spec?: Record<string, unknown> | null
    diagramType?: DiagramType | string | null
  }>(),
  {
    session: null,
    mode: 'readonly',
    vueFlowId: undefined,
    spec: null,
    diagramType: null,
  }
)

const ownsSession = !props.session
const viewBus = ownsSession ? createDiagramViewBus() : null
const resolvedSession: DiagramSession =
  props.session ??
  asDiagramSession(
    createDiagramSession({
      mode: props.mode,
      vueFlowId: props.vueFlowId ?? `diagram-session-${Math.random().toString(36).slice(2, 10)}`,
      viewBus: viewBus ?? undefined,
      emitDiagramEvents: props.mode === 'edit',
    })
  )

provide(DiagramSessionKey, resolvedSession)

function loadSpecIfPresent(): void {
  const spec = props.spec
  const rawType = props.diagramType
  if (!ownsSession || !spec || !rawType) return
  const diagramType = (rawType === 'mind_map' ? 'mindmap' : rawType) as DiagramType
  resolvedSession.loadFromSpec(spec, diagramType, { emitLoaded: false })
}

watch(
  () => [props.spec, props.diagramType] as const,
  () => {
    loadSpecIfPresent()
  },
  { immediate: true, deep: true }
)

onBeforeUnmount(() => {
  if (ownsSession) {
    resolvedSession.dispose()
  }
})

defineExpose({
  session: resolvedSession,
})
</script>

<template>
  <slot />
</template>
