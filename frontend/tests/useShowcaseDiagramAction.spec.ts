import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

const pushMock = vi.fn()
const saveDiagramMock = vi.fn()
const clearActiveDiagramMock = vi.fn()
const setActiveDiagramMock = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('@/composables', () => ({
  useLanguage: () => ({ t: (key: string) => key }),
  useNotifications: () => ({
    warning: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
  }),
}))

vi.mock('@/stores', () => ({
  useAuthStore: () => ({ isAuthenticated: true }),
  useUIStore: () => ({ setSelectedChartType: vi.fn() }),
}))

vi.mock('@/stores/savedDiagrams', () => ({
  useSavedDiagramsStore: () => ({
    saveDiagram: saveDiagramMock,
    clearActiveDiagram: clearActiveDiagramMock,
    setActiveDiagram: setActiveDiagramMock,
    error: null,
  }),
}))

vi.mock('@/utils/fetchShowcaseAsset', () => ({
  fetchShowcaseAsset: vi.fn(),
}))

describe('useShowcaseDiagramAction', () => {
  beforeEach(() => {
    pushMock.mockReset()
    saveDiagramMock.mockReset()
    clearActiveDiagramMock.mockReset()
    setActiveDiagramMock.mockReset()
    pushMock.mockResolvedValue(undefined)
  })

  it('saves template to library and opens canvas without pre-setting activeDiagramId', async () => {
    const { useShowcaseDiagramAction } = await import(
      '@/composables/showcase/useShowcaseDiagramAction'
    )
    saveDiagramMock.mockResolvedValue({
      id: 'lib-1',
      title: 'Template A',
      diagram_type: 'mind_map',
      spec: { topic: 'Root', children: [] },
    })

    const { handleDiagramAction } = useShowcaseDiagramAction()
    const closeModal = vi.fn()
    await handleDiagramAction(
      {
        id: 'post-1',
        title: 'Template A',
        description: null,
        tags: [],
        case_type: 'diagram_template',
        subject: null,
        grade: null,
        diagram_type: 'mind_map',
        thumbnail_url: null,
        status: 'approved',
        is_expert_recommended: false,
        author: { id: 1, name: 'Author' },
        likes_count: 0,
        views_count: 0,
        created_at: '',
        is_liked: false,
        is_favorited: false,
      },
      { topic: 'Root', children: [] },
      { closeModal }
    )

    expect(saveDiagramMock).toHaveBeenCalledOnce()
    expect(clearActiveDiagramMock).toHaveBeenCalledOnce()
    expect(setActiveDiagramMock).not.toHaveBeenCalled()
    expect(closeModal).toHaveBeenCalledOnce()
    expect(pushMock).toHaveBeenCalledWith({
      path: '/canvas',
      query: { diagramId: 'lib-1' },
    })
  })

  it('labels apply_template action', async () => {
    const { useShowcaseDiagramAction } = await import(
      '@/composables/showcase/useShowcaseDiagramAction'
    )
    const { actionLabel, resolveActionForPost } = useShowcaseDiagramAction()
    const action = resolveActionForPost({
      id: 'post-1',
      title: 'T',
      description: null,
      tags: [],
      case_type: 'diagram_template',
      subject: null,
      grade: null,
      diagram_type: 'mind_map',
      thumbnail_url: null,
      status: 'approved',
      is_expert_recommended: false,
      author: { id: 1, name: 'Author' },
      likes_count: 0,
      views_count: 0,
      created_at: '',
      is_liked: false,
      is_favorited: false,
    })
    expect(action).toBe('apply_template')
    expect(actionLabel(action)).toBe('showcase.action.applyTemplate')
  })

  it('hides open action for image-only diagram cases', async () => {
    const { useShowcaseDiagramAction } = await import(
      '@/composables/showcase/useShowcaseDiagramAction'
    )
    const { resolveActionForPost } = useShowcaseDiagramAction()
    const action = resolveActionForPost(
      {
        id: 'post-img',
        title: 'Images',
        description: null,
        tags: [],
        case_type: 'diagram_case',
        subject: null,
        grade: null,
        diagram_type: 'mind_map',
        thumbnail_url: '/static/case_square/cover.png',
        source_file_url: '/static/case_square/photo.png',
        spec_json_url: '/static/case_square/post-img.json',
        status: 'approved',
        is_expert_recommended: false,
        author: { id: 1, name: 'Author' },
        likes_count: 0,
        views_count: 0,
        created_at: '',
        is_liked: false,
        is_favorited: false,
        gallery_items: [
          { kind: 'image', url: '/static/case_square/photo.png', filename: 'photo.png' },
        ],
      },
      {
        source: 'gallery',
        gallery: [{ kind: 'image', path: 'case_square/photo.png', filename: 'photo.png' }],
      }
    )
    expect(action).toBeNull()
  })

  it('opens .mg and personal-library diagram cases for secondary edit', async () => {
    const { useShowcaseDiagramAction } = await import(
      '@/composables/showcase/useShowcaseDiagramAction'
    )
    const { resolveActionForPost, actionLabel } = useShowcaseDiagramAction()

    const mgAction = resolveActionForPost({
      id: 'post-mg',
      title: 'MG',
      description: null,
      tags: [],
      case_type: 'diagram_case',
      subject: null,
      grade: null,
      diagram_type: 'mind_map',
      thumbnail_url: null,
      source_file_url: '/static/case_square/demo.mg',
      status: 'approved',
      is_expert_recommended: false,
      author: { id: 1, name: 'Author' },
      likes_count: 0,
      views_count: 0,
      created_at: '',
      is_liked: false,
      is_favorited: false,
    })
    expect(mgAction).toBe('import_open')
    expect(actionLabel(mgAction)).toBe('showcase.action.openDiagram')

    const libraryAction = resolveActionForPost(
      {
        id: 'post-lib',
        title: 'Library',
        description: null,
        tags: [],
        case_type: 'diagram_case',
        subject: null,
        grade: null,
        diagram_type: 'mind_map',
        thumbnail_url: null,
        status: 'approved',
        is_expert_recommended: false,
        author: { id: 1, name: 'Author' },
        likes_count: 0,
        views_count: 0,
        created_at: '',
        is_liked: false,
        is_favorited: false,
        gallery_items: [
          {
            kind: 'diagram',
            diagram_id: 'd1',
            title: 'Saved',
            diagram_type: 'mind_map',
            spec: { topic: 'Root', children: [] },
          },
        ],
      },
      {
        source: 'gallery',
        gallery: [
          {
            kind: 'diagram',
            diagram_id: 'd1',
            title: 'Saved',
            diagram_type: 'mind_map',
            spec: { topic: 'Root', children: [] },
          },
        ],
      }
    )
    expect(libraryAction).toBe('import_open')
  })

  it('useShowcaseActionLabel tracks post case type', async () => {
    const { useShowcaseActionLabel } = await import(
      '@/composables/showcase/useShowcaseDiagramAction'
    )
    const post = ref({
      id: 'post-1',
      title: 'T',
      description: null,
      tags: [],
      case_type: 'diagram_template' as const,
      subject: null,
      grade: null,
      diagram_type: 'mind_map',
      thumbnail_url: null,
      status: 'approved' as const,
      is_expert_recommended: false,
      author: { id: 1, name: 'Author' },
      likes_count: 0,
      views_count: 0,
      created_at: '',
      is_liked: false,
      is_favorited: false,
    })
    const label = useShowcaseActionLabel(post)
    expect(label.value).toBe('showcase.action.applyTemplate')
  })
})
