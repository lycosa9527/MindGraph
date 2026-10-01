/**
 * Learning Space admin sub-tab navigation.
 */
export const LEARNING_SPACE_SUBTABS = ['pilots', 'classes'] as const

export type LearningSpaceSubtab = (typeof LEARNING_SPACE_SUBTABS)[number]

export function isLearningSpaceSubtab(value: unknown): value is LearningSpaceSubtab {
  return typeof value === 'string' && (LEARNING_SPACE_SUBTABS as readonly string[]).includes(value)
}

export function resolveLearningSpaceSubtab(value: unknown): LearningSpaceSubtab {
  return isLearningSpaceSubtab(value) ? value : 'pilots'
}

export function learningSpaceSubtabLabelKey(subtab: LearningSpaceSubtab): string {
  if (subtab === 'classes') {
    return 'admin.learningSpace.subtabClasses'
  }
  return 'admin.learningSpace.subtabPilots'
}
