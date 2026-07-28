/**
 * Bind desktop Kitty / one-sentence scope to the mobile-issued session id.
 * Must run after canvas reset so a fresh blank canvas shares mobile's SoT.
 */
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import { useOneSentenceStore } from '@/stores/oneSentence'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'

export function adoptOpenCanvasSessionScope(sessionScope: string): void {
  useOneSentenceStore().adoptEphemeralScope(sessionScope)
  useSavedDiagramsStore().clearActiveDiagram()
  traceKittyWorkflow('desktop', 'desktop_nav', `adopt_scope ${sessionScope.slice(0, 12)}`, {
    scope: sessionScope,
  })
}
