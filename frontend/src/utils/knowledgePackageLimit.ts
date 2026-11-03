/** Maximum named knowledge packages per user (File Center / Knowledge Space). */
export const MAX_KNOWLEDGE_PACKAGES = 3

/** Sources allowed inside one folder. */
export const MAX_FILES_PER_PACKAGE = 10

/** One personal-knowledge file, in bytes (50MB). */
export const MAX_KNOWLEDGE_FILE_BYTES = 50 * 1024 * 1024

export function formatPackageCountLabel(
  current: number,
  max: number = MAX_KNOWLEDGE_PACKAGES
): string {
  return `${current}/${max}`
}
