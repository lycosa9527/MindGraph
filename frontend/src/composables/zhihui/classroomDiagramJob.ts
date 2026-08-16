/**
 * Map Mind Classroom slide jobs onto the ZhiHui diagram deck shape.
 */
import type {
  MindClassroomJobDetail,
  MindClassroomRemoteStep,
  MindClassroomSlideRow,
} from '@/composables/mindMap/mindClassroomJobApi'
import type { ZhihuiGenerationItem } from '@/stores/zhihuiHistory'

function asStringList(value: unknown): string[] | null {
  if (!Array.isArray(value)) return null
  const items = value.map((item) => String(item || '').trim()).filter(Boolean)
  return items.length ? items : null
}

export function classroomSlidesToGenerations(
  detail: MindClassroomJobDetail
): ZhihuiGenerationItem[] {
  if (detail.legacy_zhihui && Array.isArray(detail.generations) && detail.generations.length) {
    return detail.generations.map((row, index) => {
      const image = typeof row.image_url === 'string' ? row.image_url : ''
      const title =
        (typeof row.slide_title === 'string' && row.slide_title) ||
        (typeof row.prompt === 'string' && row.prompt) ||
        ''
      return {
        id: String(row.id || `legacy-${index}`),
        prompt: title,
        language: typeof row.language === 'string' ? row.language : 'zh',
        image_url: image,
        slide_index: typeof row.slide_index === 'number' ? row.slide_index : index,
        slide_title: title,
        teacher_script: typeof row.teacher_script === 'string' ? row.teacher_script : null,
        focus_node_ids: asStringList(row.focus_node_ids),
        size: typeof row.size === 'string' ? row.size : null,
        conversation_id: detail.id,
      }
    })
  }

  const slides = detail.slides ?? []
  if (slides.length) {
    return slides.map((slide: MindClassroomSlideRow, index) => ({
      id: slide.id || `slide-${index}`,
      prompt: slide.title || '',
      language: 'zh',
      image_url: slide.image_url || '',
      slide_index: slide.slide_index ?? index,
      slide_title: slide.title || '',
      teacher_script: slide.teacher_script || null,
      focus_node_ids: asStringList(slide.focus_node_ids),
      size: slide.size || null,
      conversation_id: detail.id,
    }))
  }

  const steps = detail.result_json?.steps ?? []
  return steps.map((step: MindClassroomRemoteStep, index) => ({
    id: String(step.id || `step-${index}`),
    prompt: String(step.title || step.caption || ''),
    language: 'zh',
    image_url: step.image_url || '',
    slide_index: index,
    slide_title: String(step.title || ''),
    teacher_script: String(step.caption || ''),
    focus_node_ids: asStringList(step.focus_node_ids),
    conversation_id: detail.id,
  }))
}
