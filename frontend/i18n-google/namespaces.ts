export const NS_FILES = [
  'common',
  'mindmate',
  'canvas',
  'clipTeaching',
  'workshop',
  'training',
  'admin',
  'knowledge',
  'learningSpace',
  'community',
  'showcase',
  'zhihui',
  'sidebar',
  'auth',
  'notification',
  'thinkingCoins',
] as const

export type Namespace = (typeof NS_FILES)[number]
