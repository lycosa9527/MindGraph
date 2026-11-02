import type { TrainingCourse } from '@/types/training'

/** Keep the catalog card, and take the title the save response just stored. */
export function mergeSavedCourseCard(row: TrainingCourse, saved: TrainingCourse): TrainingCourse {
  return {
    ...row,
    title: saved.title,
    title_i18n: saved.title_i18n,
    description: saved.description,
    description_i18n: saved.description_i18n,
    updated_at: saved.updated_at,
  }
}

/** Bilingual title after a rename of the title currently shown on the card. */
export function titleAfterRename(
  course: Pick<TrainingCourse, 'title' | 'title_i18n'>,
  name: string
): { zh: string; en: string } {
  const trimmed = name.trim()
  const visible = course.title.trim()
  const storedZh = (course.title_i18n?.zh ?? '').trim() || visible
  const storedEn = (course.title_i18n?.en ?? '').trim() || visible
  const zh = storedZh === visible ? trimmed : storedZh
  const en = storedEn === visible ? trimmed : storedEn
  if (zh !== trimmed && en !== trimmed) return { zh: trimmed, en: trimmed }
  return { zh, en }
}
