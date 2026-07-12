/** Desktop Kitty voice-command guide rows (display-only reference panel). */

export type KittyVoiceCommandGuideRow = {
  id: string
  /** Action id for ``kitty.voiceCommand.*`` label (empty detail). */
  action: string
  /** Example phrase locale key under ``canvas.voiceCommandGuide.example.*``. */
  exampleKey: string
}

export const KITTY_VOICE_COMMAND_GUIDE_ROWS: KittyVoiceCommandGuideRow[] = [
  {
    id: 'add_node',
    action: 'add_node',
    exampleKey: 'canvas.voiceCommandGuide.example.add_node',
  },
  {
    id: 'auto_complete_branch',
    action: 'auto_complete_branch',
    exampleKey: 'canvas.voiceCommandGuide.example.auto_complete_branch',
  },
  {
    id: 'auto_complete',
    action: 'auto_complete',
    exampleKey: 'canvas.voiceCommandGuide.example.auto_complete',
  },
  {
    id: 'select_node',
    action: 'select_node',
    exampleKey: 'canvas.voiceCommandGuide.example.select_node',
  },
  {
    id: 'update_center',
    action: 'update_center',
    exampleKey: 'canvas.voiceCommandGuide.example.update_center',
  },
  {
    id: 'delete_node',
    action: 'delete_node',
    exampleKey: 'canvas.voiceCommandGuide.example.delete_node',
  },
  {
    id: 'explain_node',
    action: 'explain_node',
    exampleKey: 'canvas.voiceCommandGuide.example.explain_node',
  },
  {
    id: 'start_inline_recommendations',
    action: 'start_inline_recommendations',
    exampleKey: 'canvas.voiceCommandGuide.example.start_inline_recommendations',
  },
]
