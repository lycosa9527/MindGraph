import { type ComputedRef, type Ref, computed } from 'vue'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { isDragPracticeDiagramLocked } from '@/composables/mindMap/dragPracticeMode'
import { learningSheetPickActive } from '@/composables/mindMap/useLearningSheetCustomMode'
import { presentationDiagramEditLockedRef } from '@/composables/presentation/presentationDiagramEdit'
import { type CanvasInputMode, canvasInputUsesSlash } from '@/config/canvasInputMode'
import type { PresentationToolId } from '@/types'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'

export interface UseDiagramCanvasVueFlowUiOptions {
  diagramStore: ReturnType<typeof useDiagramSession>
  presentationRailOpen: Ref<boolean>
  handToolActive: Ref<boolean>
  presentationPointerEditMode: Ref<boolean>
  presentationHandPanMode: Ref<boolean>
  /** Readonly viewer: click selects, drag pans, wheel zooms. */
  browseMode: Ref<boolean>
  panOnDragButtons: Ref<number[] | null | undefined>
  /** Desktop e-blackboard: finger pan/pinch without taking over mouse VF pan. */
  enableTouchPanPinch: Ref<boolean>
  presentationTool: Ref<PresentationToolId>
  presentationHighlighterColor: Ref<string>
  presentationPenColor: Ref<string>
  /** Snapshot in progress: pan, zoom, drag, and selection stay off. */
  interactionFrozen?: Ref<boolean>
  /** Grab-pan: the wheel pans instead of zooming. */
  handToolPan?: Ref<boolean>
  /**
   * Canvas input profile. Laptop (default) keeps always-on marquee; mouse/board
   * reserve plain left-drag for slash, so box select needs Control.
   */
  inputMode?: Ref<CanvasInputMode>
}

export interface UseDiagramCanvasVueFlowUiResult {
  presentationStrokeToolActive: ComputedRef<boolean>
  presentationStrokeColor: ComputedRef<string>
  presentationDiagramEditLocked: ComputedRef<boolean>
  effectivePanOnDrag: ComputedRef<number[] | boolean>
  presentationToolIsNotTimer: ComputedRef<boolean>
  nodesDraggable: ComputedRef<boolean>
  elementsSelectable: ComputedRef<boolean>
  selectNodesOnDrag: ComputedRef<boolean>
  /**
   * `true` = always-on marquee. `Control` = hold Control. `null` = off.
   * Written onto the Vue Flow store (1.48 template prop is boolean | null only).
   */
  selectionKeyCode: ComputedRef<true | CanvasGroupSelectKey | null>
  panOnScroll: ComputedRef<boolean>
  zoomOnScroll: ComputedRef<boolean>
  zoomOnPinch: ComputedRef<boolean>
  vueFlowBackgroundClasses: ComputedRef<string[]>
}

/** Hold to rubber-band select when slash owns the plain left-drag. */
export const CANVAS_GROUP_SELECT_KEY = 'Control'

export type CanvasGroupSelectKey = typeof CANVAS_GROUP_SELECT_KEY

export function useDiagramCanvasVueFlowUi(
  options: UseDiagramCanvasVueFlowUiOptions
): UseDiagramCanvasVueFlowUiResult {
  const {
    diagramStore,
    presentationRailOpen,
    handToolActive,
    presentationPointerEditMode,
    presentationHandPanMode,
    browseMode,
    panOnDragButtons,
    enableTouchPanPinch,
    presentationTool,
    presentationHighlighterColor,
    presentationPenColor,
    interactionFrozen,
    handToolPan,
    inputMode,
  } = options

  function interactionHeld(): boolean {
    return Boolean(interactionFrozen?.value)
  }

  const presentationStrokeToolActive = computed(
    () =>
      presentationRailOpen.value &&
      (presentationTool.value === 'highlighter' || presentationTool.value === 'pen')
  )

  /** Block diagram edits unless presentation pointer (default edit) mode is active. */
  const presentationDiagramEditLocked = computed(
    () =>
      Boolean(diagramStore.isReadonly) ||
      presentationDiagramEditLockedRef.value ||
      (presentationRailOpen.value && !presentationPointerEditMode.value)
  )

  const presentationStrokeColor = computed(() =>
    presentationTool.value === 'pen'
      ? presentationPenColor.value
      : presentationHighlighterColor.value
  )

  /**
   * MobileCanvasPage passes panOnDragButtons — full ownership of pan (VF primary pan off).
   * Desktop e-blackboard uses enableTouchPanPinch — TouchEvents pan/pinch, mouse keeps VF pan.
   */
  const mobilePageTouchGesturesActive = computed(() => {
    const buttons = panOnDragButtons.value
    return Array.isArray(buttons) && buttons.length > 0
  })

  const touchPanPinchActive = computed(
    () => mobilePageTouchGesturesActive.value || enableTouchPanPinch.value
  )

  const effectivePanOnDrag = computed((): number[] | boolean => {
    if (interactionHeld()) return false
    if (browseMode.value) {
      return [0, 1, 2]
    }
    if (presentationHandPanMode.value) {
      return panOnDragButtons.value ?? [0, 1, 2]
    }
    if (presentationPointerEditMode.value) {
      return [1]
    }
    if (handToolActive.value) {
      return panOnDragButtons.value ?? [0, 1, 2]
    }
    if (presentationStrokeToolActive.value) {
      return false
    }
    // Phone mobile page: custom touch owns pan; disable VF button-0 pan entirely.
    if (mobilePageTouchGesturesActive.value) {
      return false
    }
    // Desktop e-blackboard: keep middle-button (and hand-tool) mouse pan.
    return [1]
  })

  const presentationToolIsNotTimer = computed(() => presentationTool.value !== 'timer')

  const nodesDraggable = computed(
    () =>
      !interactionHeld() &&
      !browseMode.value &&
      !presentationDiagramEditLocked.value &&
      !handToolActive.value &&
      !presentationHandPanMode.value &&
      !presentationStrokeToolActive.value &&
      !isDragPracticeDiagramLocked() &&
      diagramStore.type !== 'mindmap' &&
      diagramStore.type !== 'mind_map' &&
      diagramStore.type !== 'tree_map'
  )

  const elementsSelectable = computed(() => {
    if (interactionHeld()) return false
    if (isMindgraphHeadlessExportSession()) return false
    if (learningSheetPickActive.value) return false
    if (browseMode.value) return true
    if (presentationStrokeToolActive.value) return false
    if (presentationPointerEditMode.value) return true
    if (presentationDiagramEditLocked.value) return false
    if (handToolActive.value || presentationHandPanMode.value) return false
    return true
  })

  const selectNodesOnDrag = computed(() => {
    if (interactionHeld()) return false
    if (browseMode.value) return false
    if (learningSheetPickActive.value) return false
    // A finger drag must not also select the node under it.
    if (touchPanPinchActive.value) return false
    if (presentationStrokeToolActive.value) return false
    if (presentationPointerEditMode.value) return true
    if (presentationDiagramEditLocked.value) return false
    if (handToolActive.value || presentationHandPanMode.value) return false
    return true
  })

  /**
   * Separate from selectNodesOnDrag.
   * Laptop (default): always-on marquee — plain left-drag box-selects.
   * Mouse / board: Control + drag, so plain left-drag can still slash.
   * Phone page pans on the primary button, so box select stays off there.
   */
  const selectionKeyCode = computed<true | CanvasGroupSelectKey | null>(() => {
    if (interactionHeld()) return null
    if (browseMode.value) return null
    if (learningSheetPickActive.value) return null
    if (mobilePageTouchGesturesActive.value) return null
    if (presentationStrokeToolActive.value) return null
    if (presentationDiagramEditLocked.value) return null
    if (handToolActive.value || presentationHandPanMode.value) return null
    const mode = inputMode?.value ?? 'laptop'
    // Slash owns the unmodified left-drag — require Control for marquee.
    if (canvasInputUsesSlash(mode)) return CANVAS_GROUP_SELECT_KEY
    return true
  })

  const panOnScroll = computed(() => !interactionHeld() && Boolean(handToolPan?.value))
  const zoomOnScroll = computed(() => !interactionHeld() && !handToolPan?.value)
  const zoomOnPinch = computed(() => !interactionHeld())

  const vueFlowBackgroundClasses = computed(() => {
    const classes = ['bg-gray-50', 'dark:bg-gray-900']
    const t = diagramStore.type
    if (t !== null && ['circle_map', 'bubble_map', 'double_bubble_map'].includes(t)) {
      classes.push('circle-map-canvas')
    }
    if (t === 'concept_map') {
      classes.push('concept-map-canvas')
    }
    return classes
  })

  return {
    presentationStrokeToolActive,
    presentationStrokeColor,
    presentationDiagramEditLocked,
    effectivePanOnDrag,
    presentationToolIsNotTimer,
    nodesDraggable,
    elementsSelectable,
    selectNodesOnDrag,
    selectionKeyCode,
    panOnScroll,
    zoomOnScroll,
    zoomOnPinch,
    vueFlowBackgroundClasses,
  }
}
