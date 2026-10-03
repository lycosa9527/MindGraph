<script setup lang="ts">
/**
 * Person avatar: emoji text, or an image loaded from its stored URL (COS).
 */
import { computed } from 'vue'

import { resolveUserAvatarEmoji, userAvatarImageSrc } from '@/utils/userAvatarEmoji'

const props = withDefaults(
  defineProps<{
    value?: string | null
    fallback?: string
  }>(),
  { fallback: '👤' }
)

const src = computed(() => userAvatarImageSrc(props.value))

const text = computed(() => {
  const raw = props.value?.trim() ?? ''
  if (!raw || src.value || raw.startsWith('avatar_')) {
    return ''
  }
  return resolveUserAvatarEmoji(raw)
})
</script>

<template>
  <img
    v-if="src"
    :src="src"
    alt=""
    class="user-avatar-glyph"
  />
  <template v-else>{{ text || fallback }}</template>
</template>

<style scoped>
.user-avatar-glyph {
  width: 1.75em;
  height: 1.75em;
  object-fit: cover;
  border-radius: 50%;
  display: inline-block;
  vertical-align: middle;
}
</style>
