import { computed, ref, type Ref } from 'vue'

import { useRouter } from 'vue-router'

import {
  isRenderableShowcaseSpec,
  resolveDiagramAction,
  type ShowcaseDiagramAction,
  type ShowcaseCaseType,
} from '@/components/showcase/showcaseShared'
import { useLanguage, useNotifications } from '@/composables'
import { diagramTypeToChineseMap } from '@/composables/canvasPage/diagramTypeMaps'
import { useAuthStore, useUIStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { ShowcasePost } from '@/utils/apiClient'
import { resolveShowcaseDiagramType } from '@/utils/showcaseDiagramThumbnail'
import { decodeMgFileToJsonText } from '@/utils/mgInterchange'

async function fetchShowcaseSpec(post: ShowcasePost, spec?: unknown): Promise<Record<string, unknown> | null> {
  if (isRenderableShowcaseSpec(spec)) {
    return spec
  }

  if (post.spec_json_url) {
    try {
      const url = post.spec_json_url
      const res = await fetch(`${url}${url.includes('?') ? '&' : '?'}t=${Date.now()}`, {
        credentials: 'include',
        cache: 'no-store',
      })
      if (res.ok) {
        const parsed = (await res.json()) as unknown
        if (isRenderableShowcaseSpec(parsed)) {
          return parsed
        }
      }
    } catch {
      /* fall through to source file */
    }
  }

  const sourceUrl = post.source_file_url ?? ''
  if (/\.mg(\?|$)/i.test(sourceUrl)) {
    try {
      const res = await fetch(`${sourceUrl}${sourceUrl.includes('?') ? '&' : '?'}t=${Date.now()}`, {
        credentials: 'include',
        cache: 'no-store',
      })
      if (!res.ok) return null
      const text = await decodeMgFileToJsonText(await res.arrayBuffer())
      const parsed = JSON.parse(text) as unknown
      return isRenderableShowcaseSpec(parsed) ? parsed : null
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
    return resolveDiagramAction({
      caseType: post.case_type,
      spec,
      specJsonUrl: post.spec_json_url,
      sourceFileUrl: post.source_file_url,
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
      savedDiagramsStore.setActiveDiagram(saved.id)
      notify.success(String(t('community.post.importOk')))
      options?.closeModal?.()
      void router.push({ path: '/canvas', query: { diagramId: saved.id } })
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
