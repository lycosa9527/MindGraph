/**
 * Insert a Course Builder black-cat mascot into 研习社 markdown.
 *
 * URLs stay on /api/training/assets/roles/… so COS vs local bytes
 * follows COURSE_BUILDER_LOAD_FROM_COS, same as the builder picker.
 *
 * Role clips sit inline with neighboring words (like an emoji), not as
 * their own paragraph.
 */
import { isTrainingRoleId, trainingRoleSrc } from '@/config/trainingRoles'

const ROLE_IMAGE_MD =
  /!\[[^\]]*\]\(\/api\/training\/assets\/roles\/[^)\s]+\)/

export function buildWorkshopRoleMarkdown(roleId: string, alt: string): string {
  const id = isTrainingRoleId(roleId) ? roleId : '01-look-here'
  const safeAlt = alt.replace(/[[\]]/g, '').trim() || id
  return `![${safeAlt}](${trainingRoleSrc(id)})`
}

/** Join a role image to adjacent text so markdown-it does not break the line. */
export function inlineWorkshopRoleMarkdown(source: string): string {
  const pattern = new RegExp(`(\\n*)(${ROLE_IMAGE_MD.source})(\\n*)`, 'g')
  return source.replace(pattern, (_all, before: string, img: string, after: string) => {
    const lead = before.length > 0 ? ' ' : ''
    const trail = after.length > 0 ? ' ' : ''
    return `${lead}${img}${trail}`
  })
}
