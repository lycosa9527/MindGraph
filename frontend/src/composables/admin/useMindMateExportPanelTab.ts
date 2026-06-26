/**
 * MindMate export panel mode — shared between AdminPage header and export panel body.
 */
import { ref } from 'vue'

export type MindMateExportPanelTab = 'export' | 'dumps'

const panelTab = ref<MindMateExportPanelTab>('export')

export function useMindMateExportPanelTab() {
  return { panelTab }
}
