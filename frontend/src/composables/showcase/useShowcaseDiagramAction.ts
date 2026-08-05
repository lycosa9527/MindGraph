import { computed, ref, type Ref } from 'vue'

import { useRouter } from 'vue-router'

import { firstGalleryDiagramSpec } from '@/components/showcase/showcaseGallery'
import {
  isRenderableShowcaseSpec,
  resolveDiagramAction,
  type ShowcaseDiagramAction,
} from '@/components/showcase/showcaseShared'
import { useLanguage, useNotifications } from '@/composables'
import { diagramTypeToChineseMap } from '@/composables/canvasPage/diagramTypeMaps'
import { useAuthStore, useUIStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { ShowcasePost } from '@/utils/apiClient'
import { fetchShowcaseAsset } from '@/utils/fetchShowcaseAsset'
import { decodeMgFileToJsonText } from '@/utils/mgInterchange'
import {
  cloneShowcaseDiagramSpec,
  resolveShowcaseDiagramType,
} from '@/utils/showcaseDiagramThumbnail'

async function fetchShowcaseSpec(post: ShowcasePost, spec?: unknown): Promise<Record<string, unknown> | null> {
  if (isRenderableShowcaseSpec(spec)) {
    return cloneShowcaseDiagramSpec(spec)
  }

  const fromGallery = firstGalleryDiagramSpec(spec, post.gallery_items)
  if (fromGallery && isRenderableShowcaseSpec(fromGallery)) {
    return cloneShowcaseDiagramSpec(fromGallery)
  }

  if (post.spec_json_url) {
    try {
      const res = await fetchShowcaseAsset(post.spec_json_url)
      if (res.ok) {
        const parsed = (await res.json()) as unknown
        if (isRenderableShowcaseSpec(parsed)) {
          return cloneShowcaseDiagramSpec(parsed)
        }
      }
    } catch {
      /* fall through to source file */
    }
  }

  const sourceUrl = post.source_file_url ?? ''
  if (/\.mg(\?|$)/i.test(sourceUrl)) {
    try {
      const res = await fetchShowcaseAsset(sourceUrl)
      if (!res.ok) return null
      const text = await decodeMgFileToJsonText(await res.arrayBuffer())
      const parsed = JSON.parse(text) as unknown
      return isRenderableShowcaseSpec(parsed) ? cloneShowcaseDiagramSpec(parsed) : null
    } catch {
      return null
    }
  }

  return null
}

export function useShowcaseDiagramAction() {
  const router = useRouter()
  const authStore = useAuthStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const notify = useNotifications()
  const { t } = useLanguage()
  const isImporting = ref(false)

  function actionLabel(action: ShowcaseDiagramAction | null): string {
    if (action === 'go_draw') return String(t('showcase.action.goDraw'))
    if (action === 'apply_template') return String(t('showcase.action.applyTemplate'))
    if (action === 'import_open') return String(t('showcase.action.openDiagram'))
    return ''
  }

  function resolveActionForPost(post: ShowcasePost, spec?: unknown): ShowcaseDiagramAction | null {
    const hasGalleryDiagram = Boolean(
      post.gallery_items?.some(
        (item) => item.kind === 'diagram' && item.spec && typeof item.spec === 'object'
      ) || firstGalleryDiagramSpec(spec, post.gallery_items)
    )
    return resolveDiagramAction({
      caseType: post.case_type,
      spec,
      specJsonUrl: post.spec_json_url,
      sourceFileUrl: post.source_file_url,
      hasGalleryDiagram,
    })
  }

  function navigateToBlankCanvas(diagramType: string | null | undefined): void {
    const normalized = resolveShowcaseDiagramType(undefined, diagramType || 'mind_map')
    const zhName = diagramTypeToChineseMap[normalized]
    if (zhName) {
      useUIStore().setSelectedChartType(zhName)
    }
    void router.push({ path: '/canvas', query: { type: normalized } })
  }

  async function handleDiagramAction(
    post: ShowcasePost,
    spec?: unknown,
    options?: { closeModal?: () => void }
  ): Promise<void> {
    if (!authStore.isAuthenticated) {
      notify.warning(String(t('community.post.loginFirst')))
      return
    }

    const action = resolveActionForPost(post, spec)
    if (!action) return

    if (action === 'go_draw') {
      options?.closeModal?.()
      navigateToBlankCanvas(post.diagram_type)
      return
    }

    isImporting.value = true
    try {
      const specObj = await fetchShowcaseSpec(post, spec)
      if (!specObj) {
        notify.error(String(t('community.post.diagramLoadFailed')))
        return
      }

      const diagramType = resolveShowcaseDiagramType(specObj, post.diagram_type || 'mind_map')
      const saved = await savedDiagramsStore.saveDiagram(post.title, diagramType, specObj, 'zh', null)
      if (!saved) {
        notify.error(savedDiagramsStore.error || String(t('community.post.importFail')))
        return
      }

      // Clear sticky active id so CanvasPage always loads the freshly saved diagram.
      savedDiagramsStore.clearActiveDiagram()
      notify.success(String(t('community.post.importOk')))
      options?.closeModal?.()
      await router.push({ path: '/canvas', query: { diagramId: saved.id } })
    } catch (e) {
      notify.error(e instanceof Error ? e.message : String(t('community.post.importFail')))
    } finally {
      isImporting.value = false
    }
  }

  return {
    actionLabel,
    resolveActionForPost,
    handleDiagramAction,
    isImporting,
  }
}

/** Reactive action label for a loaded post + optional spec. */
export function useShowcaseActionLabel(
  post: Ref<ShowcasePost | null>,
  spec?: Ref<unknown>
) {
  const { actionLabel, resolveActionForPost } = useShowcaseDiagramAction()
  return computed(() => {
    const p = post.value
    if (!p) return ''
    const action = resolveActionForPost(p, spec?.value)
    return actionLabel(action)
  })
}
