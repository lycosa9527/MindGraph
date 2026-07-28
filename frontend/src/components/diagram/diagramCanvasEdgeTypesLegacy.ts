/**
 * Vue Flow edge types for mind map legacy canvas (curved edges; no orthogonal chunk).
 */
import { markRaw } from 'vue'

import BraceEdge from './edges/BraceEdge.vue'
import CurvedEdge from './edges/CurvedEdge.vue'
import HorizontalStepEdge from './edges/HorizontalStepEdge.vue'
import RadialEdge from './edges/RadialEdge.vue'
import StepEdge from './edges/StepEdge.vue'
import StraightEdge from './edges/StraightEdge.vue'
import TreeEdge from './edges/TreeEdge.vue'

export const diagramCanvasEdgeTypesLegacy = {
  curved: markRaw(CurvedEdge),
  straight: markRaw(StraightEdge),
  step: markRaw(StepEdge),
  horizontalStep: markRaw(HorizontalStepEdge),
  tree: markRaw(TreeEdge),
  radial: markRaw(RadialEdge),
  brace: markRaw(BraceEdge),
  bridge: markRaw(StraightEdge),
}
