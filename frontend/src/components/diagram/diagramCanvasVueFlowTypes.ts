/**
 * Vue Flow node and edge type registries for DiagramCanvas (markRaw for performance).
 */
import { markRaw } from 'vue'

import BraceEdge from './edges/BraceEdge.vue'
import CurvedEdge from './edges/CurvedEdge.vue'
import HorizontalStepEdge from './edges/HorizontalStepEdge.vue'
import RadialEdge from './edges/RadialEdge.vue'
import StepEdge from './edges/StepEdge.vue'
import StraightEdge from './edges/StraightEdge.vue'
import TreeEdge from './edges/TreeEdge.vue'
import BoundaryNode from './nodes/BoundaryNode.vue'
import BraceNode from './nodes/BraceNode.vue'
import BranchNode from './nodes/BranchNode.vue'
import BubbleNode from './nodes/BubbleNode.vue'
import CircleNode from './nodes/CircleNode.vue'
import ConceptNode from './nodes/ConceptNode.vue'
import FlowNode from './nodes/FlowNode.vue'
import FlowSubstepNode from './nodes/FlowSubstepNode.vue'
import LabelNode from './nodes/LabelNode.vue'
import TopicNode from './nodes/TopicNode.vue'

export const diagramCanvasNodeTypes = {
  topic: markRaw(TopicNode),
  bubble: markRaw(BubbleNode),
  branch: markRaw(BranchNode),
  flow: markRaw(FlowNode),
  flowSubstep: markRaw(FlowSubstepNode),
  brace: markRaw(BraceNode),
  boundary: markRaw(BoundaryNode),
  label: markRaw(LabelNode),
  circle: markRaw(CircleNode),
  concept: markRaw(ConceptNode),
  tree: markRaw(BranchNode),
  bridge: markRaw(BranchNode),
}

export const diagramCanvasEdgeTypes = {
  curved: markRaw(CurvedEdge),
  straight: markRaw(StraightEdge),
  step: markRaw(StepEdge),
  horizontalStep: markRaw(HorizontalStepEdge),
  tree: markRaw(TreeEdge),
  radial: markRaw(RadialEdge),
  brace: markRaw(BraceEdge),
  bridge: markRaw(StraightEdge),
}
