export const NS_FILES = [
  'common',
  'mindmate',
  'maite',
  'canvas',
  'workshop',
  'training',
  'admin',
  'knowledge',
  'community',
  'showcase',
  'zhihui',
  'sidebar',
  'auth',
  'notification',
  'thinkingCoins',
] as const

export type Namespace = (typeof NS_FILES)[number]
