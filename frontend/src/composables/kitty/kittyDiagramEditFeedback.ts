/**
 * User-facing + workflow feedback when a verified Kitty diagram edit fails.
 */
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'

const CODE_FAIL_I18N: Record<string, string> = {
  apply_noop: 'canvas.mindMapOneSentence.kittyEditStale',
  verify_failed: 'canvas.mindMapOneSentence.kittyEditVerifyFailed',
  hub_persist_failed: 'canvas.mindMapOneSentence.kittyEditPersistFailed',
  hub_persist_timeout: 'canvas.mindMapOneSentence.kittyEditPersistFailed',
  context_mutation_rejected: 'canvas.mindMapOneSentence.kittyEditPersistFailed',
  busy_llm_generating: 'canvas.mindMapOneSentence.kittyEditBusy',
  access_denied: 'canvas.mindMapOneSentence.kittyEditAccessDenied',
  collab_active: 'canvas.mindMapOneSentence.kittyEditCollabActive',
  stale_revision: 'canvas.mindMapOneSentence.kittyEditStaleRevision',
  ack_timeout: 'canvas.mindMapOneSentence.kittyEditTimeout',
  no_owner: 'canvas.mindMapOneSentence.kittyEditNoOwner',
  branch_not_found: 'canvas.mindMapOneSentence.kittyEditBranchCompleteFailed',
}

const ACTION_FAIL_I18N: Record<string, string> = {
  add_node: 'canvas.mindMapOneSentence.kittyEditAddFailed',
  add_nodes: 'canvas.mindMapOneSentence.kittyEditAddFailed',
  update_node: 'canvas.mindMapOneSentence.kittyEditUpdateFailed',
  update_nodes: 'canvas.mindMapOneSentence.kittyEditUpdateFailed',
  update_center: 'canvas.mindMapOneSentence.kittyEditCenterFailed',
  delete_node: 'canvas.mindMapOneSentence.kittyEditDeleteFailed',
  remove_nodes: 'canvas.mindMapOneSentence.kittyEditDeleteFailed',
  auto_complete_branch: 'canvas.mindMapOneSentence.kittyEditBranchCompleteFailed',
}

export function resolveKittyEditFailureMessage(
  errorCode: string | undefined,
  translate: (key: string) => string,
  action?: string
): string {
  const codeKey = CODE_FAIL_I18N[errorCode ?? '']
  if (codeKey) {
    return translate(codeKey)
  }
  const actionKey = ACTION_FAIL_I18N[String(action ?? '').trim()]
  if (actionKey) {
    return translate(actionKey)
  }
  return translate('canvas.mindMapOneSentence.kittyEditFailed')
}

export function reportKittyDiagramEditFailure(options: {
  action: string
  errorCode: string
  message?: string
  scope?: string | null
  lane?: 'mobile' | 'desktop' | 'hub'
}): void {
  if (options.errorCode === 'busy_llm_generating') {
    // One-sentence chat queues the edit and shows a model-aware message; skip toast noise.
    eventBus.emit('kitty:diagram_edit_failed', {
      action: options.action,
      errorCode: options.errorCode,
      message: options.message,
      scope: options.scope ?? null,
    })
    return
  }

  const { t } = useLanguage()
  const notify = useNotifications()
  const userMessage = resolveKittyEditFailureMessage(options.errorCode, t, options.action)
  const detail = options.message?.trim()
    ? `${options.errorCode}: ${options.message.trim()}`
    : options.errorCode

  console.warn(
    `[KittyDiagramEdit] verified edit failed action=${options.action} code=${options.errorCode}` +
      (options.message ? ` msg=${options.message}` : '')
  )
  traceKittyWorkflow(options.lane ?? 'mobile', 'diagram_edit_fail', detail, {
    action: options.action,
    scope: options.scope ?? undefined,
  })
  notify.warning(userMessage)
  eventBus.emit('kitty:diagram_edit_failed', {
    action: options.action,
    errorCode: options.errorCode,
    message: options.message,
    scope: options.scope ?? null,
  })
}
