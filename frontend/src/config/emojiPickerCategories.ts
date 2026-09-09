/**
 * Shared emoji picker categories (workshop chat + canvas insert icon).
 */
export interface EmojiEntry {
  name: string
  code: string
}

export interface EmojiCategory {
  key: string
  label: string
  emojis: EmojiEntry[]
}

export const EMOJI_PICKER_CATEGORIES: EmojiCategory[] = [
  {
    key: 'smileys',
    label: '😊',
    emojis: [
      { name: 'grinning', code: '😀' },
      { name: 'smile', code: '😊' },
      { name: 'laughing', code: '😂' },
      { name: 'joy', code: '🤣' },
      { name: 'wink', code: '😉' },
      { name: 'blush', code: '😊' },
      { name: 'heart_eyes', code: '😍' },
      { name: 'star_struck', code: '🤩' },
      { name: 'thinking', code: '🤔' },
      { name: 'shushing', code: '🤫' },
      { name: 'zipper_mouth', code: '🤐' },
      { name: 'raised_eyebrow', code: '🤨' },
      { name: 'neutral', code: '😐' },
      { name: 'expressionless', code: '😑' },
      { name: 'rolling_eyes', code: '🙄' },
      { name: 'grimacing', code: '😬' },
      { name: 'relieved', code: '😌' },
      { name: 'pensive', code: '😔' },
      { name: 'sleepy', code: '😴' },
      { name: 'drooling', code: '🤤' },
      { name: 'mask', code: '😷' },
      { name: 'nerd', code: '🤓' },
      { name: 'sunglasses', code: '😎' },
      { name: 'clown', code: '🤡' },
    ],
  },
  {
    key: 'gestures',
    label: '👍',
    emojis: [
      { name: 'thumbs_up', code: '👍' },
      { name: 'thumbs_down', code: '👎' },
      { name: 'clap', code: '👏' },
      { name: 'raised_hands', code: '🙌' },
      { name: 'wave', code: '👋' },
      { name: 'ok_hand', code: '👌' },
      { name: 'point_up', code: '☝️' },
      { name: 'point_down', code: '👇' },
      { name: 'point_left', code: '👈' },
      { name: 'point_right', code: '👉' },
      { name: 'pray', code: '🙏' },
      { name: 'handshake', code: '🤝' },
      { name: 'muscle', code: '💪' },
      { name: 'crossed_fingers', code: '🤞' },
      { name: 'v', code: '✌️' },
      { name: 'love_you', code: '🤟' },
      { name: 'fist', code: '✊' },
      { name: 'fist_bump', code: '🤜' },
      { name: 'fire', code: '🔥' },
      { name: 'sparkles', code: '✨' },
    ],
  },
  {
    key: 'hearts',
    label: '❤️',
    emojis: [
      { name: 'heart', code: '❤️' },
      { name: 'orange_heart', code: '🧡' },
      { name: 'yellow_heart', code: '💛' },
      { name: 'green_heart', code: '💚' },
      { name: 'blue_heart', code: '💙' },
      { name: 'purple_heart', code: '💜' },
      { name: 'broken_heart', code: '💔' },
      { name: 'sparkling_heart', code: '💖' },
      { name: 'two_hearts', code: '💕' },
      { name: 'revolving_hearts', code: '💞' },
      { name: 'star', code: '⭐' },
      { name: 'glowing_star', code: '🌟' },
      { name: 'hundred', code: '💯' },
      { name: 'trophy', code: '🏆' },
      { name: 'medal', code: '🏅' },
      { name: 'crown', code: '👑' },
    ],
  },
  {
    key: 'objects',
    label: '📎',
    emojis: [
      { name: 'books', code: '📚' },
      { name: 'open_book', code: '📖' },
      { name: 'notebook', code: '📓' },
      { name: 'graduation', code: '🎓' },
      { name: 'pencil', code: '✏️' },
      { name: 'pen', code: '🖊️' },
      { name: 'ruler', code: '📏' },
      { name: 'triangle_ruler', code: '📐' },
      { name: 'abacus', code: '🧮' },
      { name: 'school', code: '🏫' },
      { name: 'chart', code: '📊' },
      { name: 'chart_up', code: '📈' },
      { name: 'clipboard', code: '📋' },
      { name: 'folder', code: '📁' },
      { name: 'calendar', code: '📅' },
      { name: 'laptop', code: '💻' },
      { name: 'briefcase', code: '💼' },
      { name: 'email', code: '📧' },
      { name: 'target', code: '🎯' },
      { name: 'notepad', code: '🗒️' },
      { name: 'bulb', code: '💡' },
      { name: 'bookmark', code: '🔖' },
      { name: 'memo', code: '📝' },
      { name: 'pin', code: '📌' },
      { name: 'link', code: '🔗' },
      { name: 'paperclip', code: '📎' },
      { name: 'scissors', code: '✂️' },
      { name: 'package', code: '📦' },
      { name: 'bell', code: '🔔' },
      { name: 'megaphone', code: '📣' },
      { name: 'loudspeaker', code: '📢' },
      { name: 'magnifying', code: '🔍' },
      { name: 'key', code: '🔑' },
      { name: 'lock', code: '🔒' },
      { name: 'gear', code: '⚙️' },
      { name: 'hammer', code: '🔨' },
      { name: 'check', code: '✅' },
      { name: 'cross', code: '❌' },
      { name: 'warning', code: '⚠️' },
      { name: 'question', code: '❓' },
    ],
  },
]

export function orderEmojiCategories(
  items: readonly EmojiCategory[],
  leadKey?: string
): EmojiCategory[] {
  if (!leadKey) return [...items]
  const lead = items.find((category) => category.key === leadKey)
  if (!lead) return [...items]
  return [lead, ...items.filter((category) => category.key !== leadKey)]
}
