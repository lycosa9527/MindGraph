/**
 * Mobile Kitty: pick a saved diagram from the library, sync voice context, queue desktop jump.
 * Create-new allocates a durable library draft first (industry standard), then open_library_diagram.
 */
import { ref } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import { reportKittySessionIngress } from '@/composables/kitty/useKittySessionManager'
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import { useDiagramStore } from '@/stores/diagram'
import { type SavedDiagram, useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { useUIStore } from '@/stores/ui'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

export function useKittyMobileLibraryDiagramSelect(options: {
  scheduleContextSync: () => void
  refreshBootstrap: (scopeId: string) => Promise<void>
  hydrateFromLibrary: (diagramId: string) => Promise<boolean>
  hydrateStoreFromBootstrap: () => void
  onDebugLine?: (prefix: string, detail: string) => void
  /** Ignore desktop_focus follow briefly after a mobile picker selection. */
  onUserDiagramOverride?: () => void
  /** Clear ephemeral pin after picking / creating a library diagram. */
  clearForceEphemeralSession?: () => void
}) {
  const savedDiagramsStore = useSavedDiagramsStore()
  const diagramStore = useDiagramStore()
  const uiStore = useUIStore()
  const notify = useNotifications()
  const { t } = useLanguage()
  const showPicker = ref(false)
  const selecting = ref(false)

  async function openPicker(): Promise<void> {
    await savedDiagramsStore.fetchDiagrams()
    showPicker.value = true
  }

  function closePicker(): void {
    showPicker.value = false
  }

  async function enqueueOpenLibraryDiagram(
    diagramId: string,
    title: string
  ): Promise<boolean> {
    const res = await fetch('/api/kitty/desktop_action/enqueue', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kind: 'open_library_diagram',
        diagram_library_id: diagramId,
        title,
      }),
    })
    if (!res.ok) {
      return false
    }
    const data = (await res.json()) as { ok?: boolean }
    return data.ok === true
  }

  async function selectDiagram(diagram: SavedDiagram): Promise<void> {
    if (selecting.value) {
      return
    }

    selecting.value = true

    try {
      options.clearForceEphemeralSession?.()
      options.onUserDiagramOverride?.()
      savedDiagramsStore.setActiveDiagram(diagram.id)

      traceKittyWorkflow('mobile', 'library_select', String(diagram.title).slice(0, 80), {
        scope: diagram.id,
      })

      await options.refreshBootstrap(diagram.id)

      const hydrated = await options.hydrateFromLibrary(diagram.id)

      if (!hydrated) {
        options.hydrateStoreFromBootstrap()
      }

      const ok = await enqueueOpenLibraryDiagram(diagram.id, diagram.title)
      if (ok) {
        notify.success(t('mobile.kittyDiagramSelected', '已选择导图，电脑端将同步打开'))
        traceKittyWorkflow('mobile', 'desktop_enqueue', 'open_library_diagram', {
          scope: diagram.id,
        })
      } else {
        notify.warning(t('mobile.kittyDesktopJumpFailed', '已切换导图，但无法通知电脑端'))
      }

      options.scheduleContextSync()
      options.onDebugLine?.('#lib', String(diagram.title).slice(0, 24))
      showPicker.value = false
    } finally {
      selecting.value = false
    }
  }

  /**
   * Durable create: POST library draft → bind scope → open_library_diagram.
   * No ephemeral UUID / open_canvas / promote dance.
   */
  async function createNewMindmap(): Promise<void> {
    if (selecting.value) {
      return
    }

    selecting.value = true
    try {
      if (!savedDiagramsStore.canSaveMore) {
        notify.warning(
          t('editor.slotsFull', '空间已满，暂无法自动保存。请删除现有图示以释放空间。')
        )
        return
      }

      options.clearForceEphemeralSession?.()
      options.onUserDiagramOverride?.()

      diagramStore.clearHistory()
      diagramStore.setDiagramType('mindmap')
      if (!diagramStore.loadDefaultTemplate('mindmap')) {
        notify.error(t('mobile.kittyNewMindmapCreateFailed', '新建思维导图失败，请重试'))
        return
      }
      const spec = diagramStore.getSpecForSave()
      if (spec == null) {
        notify.error(t('mobile.kittyNewMindmapCreateFailed', '新建思维导图失败，请重试'))
        return
      }

      const title = t('mobile.kittyNewMindmapTitle', '新建思维导图')
      const saved = await savedDiagramsStore.saveDiagram(
        title,
        'mindmap',
        spec,
        uiStore.language || 'zh'
      )
      if (saved == null) {
        notify.error(
          savedDiagramsStore.error ||
            t('mobile.kittyNewMindmapCreateFailed', '新建思维导图失败，请重试')
        )
        return
      }

      savedDiagramsStore.setActiveDiagram(saved.id)
      traceKittyWorkflow('mobile', 'new_mindmap', 'library draft', { scope: saved.id })

      void reportKittySessionIngress(saved.id, {
        requestId: safeRandomUUID(),
        source: 'ui_create',
        text: title,
        lane: 'mobile',
      })

      await options.refreshBootstrap(saved.id)
      const hydrated = await options.hydrateFromLibrary(saved.id)
      if (!hydrated) {
        options.hydrateStoreFromBootstrap()
      }

      const ok = await enqueueOpenLibraryDiagram(saved.id, saved.title || title)
      if (ok) {
        notify.success(
          t('mobile.kittyNewMindmapCreated', '已新建思维导图，电脑端将打开该导图')
        )
        traceKittyWorkflow('mobile', 'desktop_enqueue', 'open_library_diagram', {
          scope: saved.id,
        })
      } else {
        notify.warning(
          t('mobile.kittyNewMindmapDesktopFailed', '已新建导图，但无法通知电脑端打开')
        )
      }

      options.scheduleContextSync()
      options.onDebugLine?.('#new', `draft ${saved.id.slice(0, 8)}`)
      showPicker.value = false
    } finally {
      selecting.value = false
    }
  }

  return {
    showPicker,
    selecting,
    openPicker,
    closePicker,
    selectDiagram,
    createNewMindmap,
  }
}
