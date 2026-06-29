/** Maximum named knowledge packages per user (File Center / Knowledge Space). */
export const MAX_KNOWLEDGE_PACKAGES = 3

export function formatPackageCountLabel(current: number, max: number = MAX_KNOWLEDGE_PACKAGES): string {
  return `${current}/${max}`
}
