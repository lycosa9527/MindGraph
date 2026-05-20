<script setup lang="ts">
/**
 * MindMate assistant avatar: school upload when set, else bundled default; falls back on load error.
 */
import { ref, watch } from 'vue'

import { ElAvatar } from 'element-plus'

import { useMindMateBranding } from '@/composables/mindmate/useMindMateBranding'

const props = withDefaults(
  defineProps<{
    size?: number
    avatarClass?: string
    brandingSize?: 'md' | 'lg'
  }>(),
  {
    size: 40,
    avatarClass: '',
    brandingSize: 'md',
  }
)

const { avatarUrl, defaultAvatar, displayName } = useMindMateBranding(props.brandingSize)
const displaySrc = ref(avatarUrl.value)

watch(avatarUrl, (url) => {
  displaySrc.value = url
})

function onAvatarError() {
  if (displaySrc.value !== defaultAvatar) {
    displaySrc.value = defaultAvatar
  }
}
</script>

<template>
  <ElAvatar
    :src="displaySrc"
    :alt="displayName"
    :size="size"
    :class="avatarClass"
    @error="onAvatarError"
  />
</template>
