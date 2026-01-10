/**
 * Diagram Composables Index
 * Each composable provides layout calculation and data conversion for a diagram type
 *
 * 10 Thinking Map Types:
 * 1. Circle Map - useCircleMap
 * 2. Bubble Map - useBubbleMap
 * 3. Double Bubble Map - useDoubleBubbleMap
 * 4. Tree Map - useTreeMap
 * 5. Brace Map - useBraceMap
 * 6. Flow Map - useFlowMap
 * 7. Multi-Flow Map - useMultiFlowMap
 * 8. Bridge Map - useBridgeMap
 * 9. Mind Map - useMindMap
 * 10. Concept Map - useConceptMap
 */
export { useBubbleMap } from './useBubbleMap'
export { useCircleMap } from './useCircleMap'
export { useMindMap } from './useMindMap'
export { useTreeMap } from './useTreeMap'
export { useFlowMap } from './useFlowMap'
export { useBraceMap } from './useBraceMap'
export { useBridgeMap } from './useBridgeMap'
// Phase 4 additions
export { useDoubleBubbleMap } from './useDoubleBubbleMap'
export { useMultiFlowMap } from './useMultiFlowMap'
export { useConceptMap } from './useConceptMap'

// Layout configuration and constants
export * from './layoutConfig'

// Shared layout utilities
export * from './useDagreLayout'
export * from './useFlowMapLayout'
