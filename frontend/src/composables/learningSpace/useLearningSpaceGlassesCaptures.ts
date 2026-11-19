/**
 * Teacher workbench list of glasses learning-sheet photos.
 */
import { onMounted, onUnmounted, ref } from 'vue'

import { apiRequest } from '@/utils/apiClient'

export type GlassesSpecNode = {
  text: string
  children?: GlassesSpecNode[]
}

export type GlassesSpec = {
  topic: string
  children: GlassesSpecNode[]
}

export type GlassesCapture = {
  id: number
  student_name: string
  class_name: string
  ocr_status: string
  ocr_error: string
  spec: GlassesSpec | null
  image_path: string
  created_at: string
}

const POLL_MS = 3000

function asNode(value: unknown): GlassesSpecNode | null {
  if (!value || typeof value !== 'object') return null
  const row = value as { text?: unknown; children?: unknown }
  const text = typeof row.text === 'string' ? row.text.trim() : ''
  if (!text) return null
  const children = Array.isArray(row.children)
    ? row.children.map(asNode).filter((node): node is GlassesSpecNode => node !== null)
    : []
  return children.length ? { text, children } : { text }
}

function asSpec(value: unknown): GlassesSpec | null {
  if (!value || typeof value !== 'object') return null
  const row = value as { topic?: unknown; children?: unknown }
  const topic = typeof row.topic === 'string' ? row.topic.trim() : ''
  if (!topic || !Array.isArray(row.children)) return null
  const children = row.children.map(asNode).filter((node): node is GlassesSpecNode => node !== null)
  if (!children.length) return null
  return { topic, children }
}

function asCapture(value: unknown): GlassesCapture | null {
  if (!value || typeof value !== 'object') return null
  const row = value as Partial<GlassesCapture>
  if (typeof row.id !== 'number') return null
  return {
    id: row.id,
    student_name: typeof row.student_name === 'string' ? row.student_name : '',
    class_name: typeof row.class_name === 'string' ? row.class_name : '',
    ocr_status: typeof row.ocr_status === 'string' ? row.ocr_status : 'pending',
    ocr_error: typeof row.ocr_error === 'string' ? row.ocr_error : '',
    spec: asSpec(row.spec),
    image_path: typeof row.image_path === 'string' ? row.image_path : '',
    created_at: typeof row.created_at === 'string' ? row.created_at : '',
  }
}

export function useLearningSpaceGlassesCaptures() {
  const captures = ref<GlassesCapture[]>([])
  const loading = ref(true)
  const failed = ref(false)
  let timer = 0

  function stopPoll() {
    if (timer) {
      window.clearInterval(timer)
      timer = 0
    }
  }

  function schedule() {
    const waiting = captures.value.some((row) => row.ocr_status === 'pending')
    if (!waiting) {
      stopPoll()
      return
    }
    if (timer) return
    timer = window.setInterval(() => {
      void load()
    }, POLL_MS)
  }

  async function load() {
    try {
      const response = await apiRequest('/api/learning-space/glasses/captures')
      if (!response.ok) {
        failed.value = captures.value.length === 0
        return
      }
      const body = (await response.json()) as { captures?: unknown }
      captures.value = Array.isArray(body.captures)
        ? body.captures.map(asCapture).filter((row): row is GlassesCapture => row !== null)
        : []
      failed.value = false
      schedule()
    } catch {
      failed.value = captures.value.length === 0
    } finally {
      loading.value = false
    }
  }

  onMounted(() => {
    void load()
  })

  onUnmounted(stopPoll)

  return { captures, loading, failed }
}
