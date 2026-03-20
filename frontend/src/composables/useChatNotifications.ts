/**
 * Chat Notifications Composable
 *
 * Provides browser Notification API integration, synthesized ding sound,
 * and in-app WeChat-style toast cards for the workshop chat module.
 *
 * Notification rules:
 * - Own messages: never notify
 * - Muted channels: never notify
 * - Actively viewing that exact conversation: silent (no ding, no toast, no popup)
 * - App visible but different conversation:
 *     · Channel message → ding only
 *     · DM or @mention  → ding + in-app toast card
 * - Tab hidden / minimised:
 *     · Channel message → ding + browser OS notification
 *     · DM or @mention  → ding + browser OS notification + in-app toast card
 */
import { useAuthStore } from '@/stores/auth'
import { pushChatToast } from '@/composables/chatToastQueue'
import { useLanguage } from '@/composables/useLanguage'
import type { ChatMessage, DirectMessageItem } from '@/stores/workshopChat'
import { useWorkshopChatStore } from '@/stores/workshopChat'

function playDing(): void {
  try {
    const ctx = new AudioContext()

    const masterGain = ctx.createGain()
    masterGain.gain.value = 0.22
    masterGain.connect(ctx.destination)

    const now = ctx.currentTime

    // Primary tone: A5 (880 Hz) – the bell body
    const osc1 = ctx.createOscillator()
    const gain1 = ctx.createGain()
    osc1.type = 'sine'
    osc1.frequency.value = 880
    gain1.gain.setValueAtTime(1, now)
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.65)
    osc1.connect(gain1)
    gain1.connect(masterGain)
    osc1.start(now)
    osc1.stop(now + 0.65)

    // Overtone: E6 (1320 Hz) – adds brightness
    const osc2 = ctx.createOscillator()
    const gain2 = ctx.createGain()
    osc2.type = 'sine'
    osc2.frequency.value = 1320
    gain2.gain.setValueAtTime(0.35, now)
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.25)
    osc2.connect(gain2)
    gain2.connect(masterGain)
    osc2.start(now)
    osc2.stop(now + 0.25)

    // Close AudioContext once the longer oscillator finishes
    osc1.onended = () => {
      ctx.close().catch(() => undefined)
    }
  } catch {
    // AudioContext unavailable or blocked by autoplay policy – fail silently
  }
}

function showBrowserNotification(title: string, body: string, tag: string): void {
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return
  try {
    const n = new Notification(title, {
      body: body.length > 120 ? `${body.slice(0, 117)}…` : body,
      tag,
      icon: '/favicon.ico',
      silent: true, // we handle sound ourselves
    })
    n.onclick = () => {
      window.focus()
      n.close()
    }
  } catch {
    // Notification constructor may throw in some environments
  }
}

export async function requestNotificationPermission(): Promise<void> {
  if (typeof Notification === 'undefined') return
  if (Notification.permission === 'default') {
    await Notification.requestPermission()
  }
}

export function useChatNotifications() {
  const { t } = useLanguage()
  const store = useWorkshopChatStore()
  const authStore = useAuthStore()

  function myId(): string | undefined {
    return authStore.user?.id
  }

  function myName(): string | undefined {
    return authStore.user?.username
  }

  function isDocumentHidden(): boolean {
    return document.hidden
  }

  function escapeRegExp(s: string): string {
    return s.replace(/[\\^$.*+?()[\]{}|]/g, '\\$&')
  }

  /**
   * True if the current user is mentioned: prefer server `mentioned_user_ids`,
   * else fall back to legacy @firstToken substring match on content.
   */
  function isUserMentionedInMessage(msg: {
    content: string
    mentioned_user_ids?: number[]
  }): boolean {
    const uid = myId()
    if (uid && msg.mentioned_user_ids?.length) {
      return msg.mentioned_user_ids.includes(Number(uid))
    }
    const name = myName()
    if (!name) return false
    const firstName = name.split(/\s+/)[0]
    if (!firstName) return false
    return new RegExp(`@${escapeRegExp(firstName)}`, 'i').test(msg.content)
  }

  function notifyChannelMessage(msg: ChatMessage): void {
    if (String(msg.sender_id) === myId()) return

    const channel = store.channels.find(c => c.id === msg.channel_id)
    if (channel?.is_muted) return

    const isViewing = (
      !isDocumentHidden()
      && msg.channel_id === store.currentChannelId
      && store.currentTopicId === null
      && store.activeTab === 'channels'
    )

    const mentioned = isUserMentionedInMessage(msg)

    if (!isViewing) {
      playDing()
    }

    if (mentioned && !isViewing) {
      const channelName = channel?.name ?? t('workshop.channels')
      pushChatToast({
        type: 'mention',
        senderName: msg.sender_name,
        senderAvatar: msg.sender_avatar,
        context: `#${channelName}`,
        content: msg.content,
        nav: { channelId: msg.channel_id },
      })
    }

    if (isDocumentHidden()) {
      const channelName = channel?.name ?? t('workshop.channels')
      showBrowserNotification(
        mentioned
          ? t('workshop.mentionedInChannel').replace('{0}', channelName)
          : `#${channelName}`,
        `${msg.sender_name}: ${msg.content}`,
        `channel-${msg.channel_id}`,
      )
    }
  }

  function notifyTopicMessage(msg: ChatMessage): void {
    if (String(msg.sender_id) === myId()) return

    const channel = store.channels.find(c => c.id === msg.channel_id)
    if (channel?.is_muted) return

    const isViewing = (
      !isDocumentHidden()
      && msg.topic_id === store.currentTopicId
      && store.activeTab === 'channels'
    )

    const mentioned = isUserMentionedInMessage(msg)

    if (!isViewing) {
      playDing()
    }

    if (mentioned && !isViewing) {
      const matchedTopic = store.topics.find(tp => tp.id === msg.topic_id)
      const channelName = channel?.name ?? t('workshop.channels')
      const topicTitle = matchedTopic?.title ?? t('workshop.topics')
      pushChatToast({
        type: 'mention',
        senderName: msg.sender_name,
        senderAvatar: msg.sender_avatar,
        context: `#${channelName} › ${topicTitle}`,
        content: msg.content,
        nav: { channelId: msg.channel_id, topicId: msg.topic_id ?? undefined },
      })
    }

    if (isDocumentHidden()) {
      const matchedTopic = store.topics.find(tp => tp.id === msg.topic_id)
      const channelName = channel?.name ?? t('workshop.channels')
      const topicTitle = matchedTopic?.title ?? t('workshop.topics')
      showBrowserNotification(
        mentioned
          ? t('workshop.mentionedInTopic').replace('{0}', topicTitle)
          : `#${channelName} › ${topicTitle}`,
        `${msg.sender_name}: ${msg.content}`,
        `topic-${msg.topic_id}`,
      )
    }
  }

  function notifyDM(msg: DirectMessageItem): void {
    if (String(msg.sender_id) === myId()) return

    const isViewing = (
      !isDocumentHidden()
      && msg.sender_id === store.currentDMPartnerId
      && store.activeTab === 'dms'
    )

    if (!isViewing) {
      playDing()

      const conv = store.dmConversations.find(c => c.partner_id === msg.sender_id)
      pushChatToast({
        type: 'dm',
        senderName: conv?.partner_name ?? `User ${msg.sender_id}`,
        senderAvatar: conv?.partner_avatar ?? null,
        context: t('workshop.directMessage'),
        content: msg.content,
        nav: { partnerId: msg.sender_id },
      })
    }

    if (isDocumentHidden()) {
      const conv = store.dmConversations.find(c => c.partner_id === msg.sender_id)
      showBrowserNotification(
        conv?.partner_name ?? `User ${msg.sender_id}`,
        msg.content,
        `dm-${msg.sender_id}`,
      )
    }
  }

  return {
    notifyChannelMessage,
    notifyTopicMessage,
    notifyDM,
  }
}
