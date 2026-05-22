/**

 * Mobile Kitty: pick a saved diagram from the library, sync voice context, queue desktop jump.

 */

import { ref } from 'vue'



import { diagramTypeMap } from '@/composables/canvasPage/diagramTypeMaps'

import { useLanguage, useNotifications } from '@/composables'

import { eventBus } from '@/composables/core/useEventBus'

import { useDiagramStore, useUIStore } from '@/stores'

import { useSavedDiagramsStore, type SavedDiagram } from '@/stores/savedDiagrams'

import type { DiagramType } from '@/types'



async function loadKittyLibraryDiagramIntoStore(diagramId: string): Promise<boolean> {

  const savedDiagramsStore = useSavedDiagramsStore()

  const diagramStore = useDiagramStore()

  const uiStore = useUIStore()

  const diagram = await savedDiagramsStore.getDiagram(diagramId)

  if (!diagram) {

    return false

  }



  savedDiagramsStore.setActiveDiagram(diagramId)

  diagramStore.clearHistory()



  const spec = diagram.spec as Record<string, unknown>

  const loaded = diagramStore.loadFromSpec(spec, diagram.diagram_type as DiagramType)

  if (!loaded) {

    return false

  }



  uiStore.setSelectedChartType(

    Object.entries(diagramTypeMap).find(([, value]) => value === diagram.diagram_type)?.[0] ||

      diagram.diagram_type

  )

  eventBus.emit('diagram:loaded_from_library', {

    diagramId,

    diagramType: diagram.diagram_type,

  })

  return true

}



export function useKittyMobileLibraryDiagramSelect(options: {

  scheduleContextSync: () => void

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

      const loaded = await loadKittyLibraryDiagramIntoStore(diagram.id)

      if (!loaded) {

        notify.warning(

          t('mobile.kittyDiagramPickFailed', '无法加载该导图，请稍后重试')

        )

        return

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

        notify.warning(

          t('mobile.kittyDesktopJumpFailed', '已切换导图，但无法通知电脑端')

        )

      } else {

        const data = (await res.json()) as { ok?: boolean }

        if (data.ok) {

          notify.success(

            t('mobile.kittyDiagramSelected', '已选择导图，电脑端将同步打开')

          )

        } else {

          notify.warning(

            t('mobile.kittyDesktopJumpFailed', '已切换导图，但无法通知电脑端')

          )

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


