/**
 * Canonical message shape for typed `t()` keys (derived from the zh bundle).
 * `useLanguage().t` overloads use `keyof MessageSchema` for compile-time checks.
 */
import zhMessages from '@/locales/messages/zh'

export type MessageSchema = typeof zhMessages
