/**
 * Document Summary session clear vs discard (COS cleanup on diagram reset).
 */
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, ref } from 'vue'

import { createFileCenterActivePackage } from '@/composables/fileCenter/useFileCenterActivePackage'
import { DOC_SUMMARY_API_BASE } from '@/config/docSummaryApi'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'

const apiRequestJson = vi.fn()

vi.mock('@/utils/apiClient', () => ({
  apiRequestJson: (...args: unknown[]) => apiRequestJson(...args),
}))

vi.mock('@/config/docSummaryLite', () => ({
  DOC_SUMMARY_LITE_UI: true,
}))

vi.mock('@/composables/fileCenter/useFileCenter', async () => {
  const actual = await vi.importActual<typeof import('@/composables/fileCenter/useFileCenter')>(
    '@/composables/fileCenter/useFileCenter'
  )
  return {
    ...actual,
    usePackages: () => ({
      data: ref({ packages: [], total: 0, wiki_compile_enabled: false }),
      isLoading: ref(false),
      isFetching: ref(false),
      error: ref(null),
      refetch: vi.fn(),
    }),
    useFileCenterMutations: () => ({
      updatePackage: { mutateAsync: vi.fn() },
      createPackage: { mutateAsync: vi.fn() },
      deletePackage: { mutateAsync: vi.fn() },
    }),
  }
})

describe('createFileCenterActivePackage', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    setActivePinia(createPinia())
    apiRequestJson.mockReset()
    apiRequestJson.mockResolvedValue({ deleted: true })
  })

  function withSetup<T>(factory: () => T): T {
    let result!: T
    const app = createApp({
      setup() {
        result = factory()
        return () => null
      },
    })
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
    app.use(createPinia())
    app.use(VueQueryPlugin, { queryClient })
    app.mount(document.createElement('div'))
    return result
  }

  it('discardSession posts session/clear then clears local binding', async () => {
    const api = withSetup(() => createFileCenterActivePackage(ref(true)))
    api.rememberPendingPackage(42)

    api.discardSession({ diagramId: 'diagram-a' })

    expect(api.activePackageId.value).toBeNull()
    expect(api.sessionStarting.value).toBe(false)

    await vi.waitFor(() => {
      expect(apiRequestJson).toHaveBeenCalledWith(
        `${DOC_SUMMARY_API_BASE}/session/clear`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            package_id: 42,
            diagram_id: 'diagram-a',
          }),
        })
      )
    })
  })

  it('clearLocalSession does not call session/clear', () => {
    const api = withSetup(() => createFileCenterActivePackage(ref(true)))
    api.rememberPendingPackage(9)

    api.clearLocalSession()

    expect(api.activePackageId.value).toBeNull()
    expect(apiRequestJson).not.toHaveBeenCalled()
  })

  it('rebinds session when active diagram switches so COS follows the new diagram', async () => {
    apiRequestJson.mockImplementation(async (url: string) => {
      if (url === `${DOC_SUMMARY_API_BASE}/session/start`) {
        return {
          id: 77,
          name: 'B',
          diagram_id: 'diagram-b',
          source: 'doc_summary',
          status: 'completed',
          document_count: 1,
          completed_count: 1,
          created_at: '',
          updated_at: '',
        }
      }
      return { deleted: true }
    })

    const api = withSetup(() => createFileCenterActivePackage(ref(true)))
    const saved = useSavedDiagramsStore()
    saved.setActiveDiagram('diagram-a')
    api.rememberPendingPackage(42)
    await nextTick()

    saved.setActiveDiagram('diagram-b')
    await nextTick()

    expect(api.activePackageId.value).not.toBe(42)

    await vi.waitFor(() => {
      expect(apiRequestJson).toHaveBeenCalledWith(
        `${DOC_SUMMARY_API_BASE}/session/start`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            diagram_id: 'diagram-b',
            diagram_title: undefined,
            package_id: undefined,
            create_if_missing: false,
          }),
        })
      )
    })

    expect(api.activePackageId.value).toBe(77)
  })
})
