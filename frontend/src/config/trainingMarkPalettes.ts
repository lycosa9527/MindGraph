export type TrainingArrowColor = 'red' | 'amber' | 'green' | 'blue' | 'violet' | 'stone'
export type TrainingArrowLine = 'solid' | 'dashed' | 'thick'

export interface TrainingEmojiPage {
  id: string
  labelKey: string
  glyphs: readonly string[]
}

export interface TrainingArrowColorDef {
  key: TrainingArrowColor
  hex: string
}

export const TRAINING_EMOJI_PAGES: TrainingEmojiPage[] = [
  {
    id: 'common',
    labelKey: 'training.builder.emojiPageCommon',
    glyphs: ['⭐', '💡', '✅', '❗', '👍', '🎯', '📌', '✨', '❤️', '🔥', '👀', '🎉', '⚠️', '👏', '💯', '➡️'],
  },
  {
    id: 'faces',
    labelKey: 'training.builder.emojiPageFaces',
    glyphs: ['😀', '😃', '😄', '😁', '😊', '😍', '🤩', '😎', '🤔', '😅', '😭', '😇', '🙃', '😉', '😴', '🤯'],
  },
  {
    id: 'hands',
    labelKey: 'training.builder.emojiPageHands',
    glyphs: ['👍', '👎', '👌', '✌️', '🤞', '👋', '🙏', '💪', '👆', '👉', '👈', '👇', '✊', '✋', '🤝', '🫶'],
  },
  {
    id: 'marks',
    labelKey: 'training.builder.emojiPageMarks',
    glyphs: ['✅', '❌', '❗', '❓', '➕', '➖', '✔️', '⭕', '🚫', '➡️', '⬅️', '⬆️', '⬇️', '⭐', '📌', '📝'],
  },
]

export const TRAINING_ARROW_COLORS: TrainingArrowColorDef[] = [
  { key: 'red', hex: '#e30613' },
  { key: 'amber', hex: '#d97706' },
  { key: 'green', hex: '#15803d' },
  { key: 'blue', hex: '#2563eb' },
  { key: 'violet', hex: '#7c3aed' },
  { key: 'stone', hex: '#1c1917' },
]

export const TRAINING_ARROW_LINES: TrainingArrowLine[] = ['solid', 'dashed', 'thick']

const COLOR_HEX = new Map(TRAINING_ARROW_COLORS.map((item) => [item.key, item.hex]))

export function trainingArrowHex(color: string | undefined): string {
  return COLOR_HEX.get(color as TrainingArrowColor) || '#e30613'
}

export function trainingArrowColorKey(color: string | undefined): TrainingArrowColor {
  return COLOR_HEX.has(color as TrainingArrowColor) ? (color as TrainingArrowColor) : 'red'
}

export function trainingArrowLine(line: string | undefined): TrainingArrowLine {
  if (line === 'dashed' || line === 'thick') return line
  return 'solid'
}
