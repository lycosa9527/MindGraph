/**

 * Mobile Kitty: pick a saved diagram from the library, sync voice context, queue desktop jump.

 */

import { ref } from 'vue'



import { useLanguage, useNotifications } from '@/composables'

import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'

import { useSavedDiagramsStore, type SavedDiagram } from '@/stores/savedDiagrams'



export function useKittyMobileLibraryDiagramSelect(options: {

  scheduleContextSync: () => void

  refreshBootstrap: (scopeId: string) => Promise<void>

  hydrateFromLibrary: (diagramId: string) => Promise<boolean>

  hydrateStoreFromBootstrap: () => void

  onDebugLine?: (prefix: string, detail: string) => void

}) {

  const savedDiagramsStore = useSavedDiagramsStore()

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



  async function selectDiagram(diagram: SavedDiagram): Promise<void> {

    if (selecting.value) {

      return

    }

    selecting.value = true

    try {

      savedDiagramsStore.setActiveDiagram(diagram.id)

      traceKittyWorkflow('mobile', 'library_select', String(diagram.title).slice(0, 80), {
        scope: diagram.id,
      })

      await options.refreshBootstrap(diagram.id)

      const hydrated = await options.hydrateFromLibrary(diagram.id)

      if (!hydrated) {

        options.hydrateStoreFromBootstrap()

      }



      const res = await fetch('/api/kitty/desktop_action/enqueue', {

        method: 'POST',

        credentials: 'same-origin',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          kind: 'open_library_diagram',

          diagram_library_id: diagram.id,

          title: diagram.title,

        }),

      })



      if (!res.ok) {

        notify.warning(t('mobile.kittyDesktopJumpFailed', '已切换导图，但无法通知电脑端'))

      } else {

        const data = (await res.json()) as { ok?: boolean }

        if (data.ok) {

          notify.success(t('mobile.kittyDiagramSelected', '已选择导图，电脑端将同步打开'))
          traceKittyWorkflow('mobile', 'desktop_enqueue', 'open_library_diagram', {
            scope: diagram.id,
          })

        } else {

          notify.warning(t('mobile.kittyDesktopJumpFailed', '已切换导图，但无法通知电脑端'))

        }

      }



      options.scheduleContextSync()

      options.onDebugLine?.('#lib', String(diagram.title).slice(0, 24))

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

  }

}


