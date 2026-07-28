/**
 * Vue Flow edge types for mind map v2 canvas (includes orthogonal mind-map edges).
 */
import { markRaw } from 'vue'

import BraceEdge from './edges/BraceEdge.vue'
import CurvedEdge from './edges/CurvedEdge.vue'
import HorizontalStepEdge from './edges/HorizontalStepEdge.vue'
import MindMapOrthogonalEdge from './edges/MindMapOrthogonalEdge.vue'
import RadialEdge from './edges/RadialEdge.vue'
import StepEdge from './edges/StepEdge.vue'
import StraightEdge from './edges/StraightEdge.vue'
import TreeEdge from './edges/TreeEdge.vue'

export const diagramCanvasEdgeTypesMindMapV2 = {
  curved: markRaw(CurvedEdge),
  mindmapOrthogonal: markRaw(MindMapOrthogonalEdge),
  straight: markRaw(StraightEdge),
  step: markRaw(StepEdge),
  horizontalStep: markRaw(HorizontalStepEdge),
  tree: markRaw(TreeEdge),
  radial: markRaw(RadialEdge),
  brace: markRaw(BraceEdge),
  bridge: markRaw(StraightEdge),
}
