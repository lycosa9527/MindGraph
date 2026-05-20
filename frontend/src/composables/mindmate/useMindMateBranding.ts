/**
 * Per-school MindMate branding (sidebar label + avatar).
 * When no school agent name is set, uses the default MindMate label.
 * When no school avatar is uploaded, uses bundled MindMate default assets.
 */
import { computed } from 'vue'

import mindmateAvatarLg from '@/assets/mindmate-avatar-lg.png'
import mindmateAvatarMd from '@/assets/mindmate-avatar-md.png'
import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores'

export function resolveSchoolMindmateAgentName(
  raw: string | null | undefined
): string | null {
  const trimmed = (raw ?? '').trim()
  return trimmed || null
}

export function resolveSchoolMindmateAvatarUrl(
  raw: string | null | undefined
): string | null {
  const trimmed = (raw ?? '').trim()
  return trimmed || null
}

export function useMindMateBranding(size: 'md' | 'lg' = 'md') {
  const { t } = useLanguage()
  const authStore = useAuthStore()
  const defaultAvatar = size === 'lg' ? mindmateAvatarLg : mindmateAvatarMd
  const defaultDisplayName = computed(() => t('sidebar.mindMate') as string)

  const customAgentName = computed(() =>
    resolveSchoolMindmateAgentName(authStore.user?.mindmateAgentName)
  )
  const hasCustomAgentName = computed(() => customAgentName.value !== null)
  const displayName = computed(() => {
    if (customAgentName.value) {
      return customAgentName.value
    }
    return defaultDisplayName.value
  })
  const customAvatarUrl = computed(() =>
    resolveSchoolMindmateAvatarUrl(authStore.user?.mindmateAgentAvatarUrl)
  )
  const hasCustomAvatar = computed(() => customAvatarUrl.value !== null)
  const avatarUrl = computed(() => customAvatarUrl.value ?? defaultAvatar)

  return {
    customAgentName,
    hasCustomAgentName,
    displayName,
    defaultDisplayName,
    customAvatarUrl,
    hasCustomAvatar,
    avatarUrl,
    defaultAvatar,
  }
}
