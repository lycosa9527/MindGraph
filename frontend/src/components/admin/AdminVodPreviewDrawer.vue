<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { ElDrawer } from 'element-plus'

import { useLanguage, useNotifications } from '@/composables'
import { type VodMediaItem, playVodMedia } from '@/utils/vodApi'

const props = defineProps<{
  modelValue: boolean
  media: VodMediaItem | null
  organizationId?: number | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const { t, isZh } = useLanguage()
const notify = useNotifications()
const playerId = 'admin-vod-player'
const loading = ref(false)
const playerSlot = ref(0)
let player: { dispose: () => void } | null = null
let loadGen = 0

async function destroyPlayer(): Promise<void> {
  if (player) {
    player.dispose()
    player = null
  }
  playerSlot.value = 0
  await nextTick()
}

async function loadPlayer(): Promise<void> {
  const gen = ++loadGen
  await destroyPlayer()
  if (!props.modelValue || !props.media || gen !== loadGen) {
    return
  }
  loading.value = true
  try {
    const token = await playVodMedia(props.media.id, props.organizationId)
    if (gen !== loadGen || !props.modelValue) {
      return
    }
    playerSlot.value = gen
    await nextTick()
    if (gen !== loadGen) {
      return
    }
    const [TCPlayer] = await Promise.all([
      import('tcplayer.js').then((mod) => mod.default),
      import('tcplayer.js/dist/tcplayer.min.css'),
    ])
    if (gen !== loadGen) {
      return
    }
    player = TCPlayer(playerId, {
      fileID: token.fileId,
      appID: token.appId,
      psign: token.psign,
      licenseUrl: token.licenseUrl,
      licenseKey: token.licenseKey,
      language: isZh.value ? 'zh-CN' : 'en',
    })
  } catch {
    if (gen === loadGen) {
      notify.error(t('admin.vod.playFailed'))
    }
  } finally {
    if (gen === loadGen) {
      loading.value = false
    }
  }
}

watch(
  () => [props.modelValue, props.media?.id],
  async ([visible]) => {
    if (visible && props.media) {
      await loadPlayer()
      return
    }
    await destroyPlayer()
  }
)

onBeforeUnmount(() => {
  void destroyPlayer()
})
</script>

<template>
  <ElDrawer
    :model-value="modelValue"
    :title="media?.title || t('admin.vod.preview')"
    size="36rem"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p
      v-if="loading"
      class="text-sm text-stone-500"
    >
      {{ t('common.loading') }}
    </p>
    <video
      v-if="playerSlot"
      :id="playerId"
      :key="playerSlot"
      class="vod-preview-player"
      preload="auto"
      playsinline
    />
  </ElDrawer>
</template>

<style scoped>
.vod-preview-player {
  width: 100%;
  min-height: 12rem;
  background: #111;
}
</style>
