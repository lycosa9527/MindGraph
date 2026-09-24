<script setup lang="ts">
/**
 * Full-width read-only strip for someone who opened a shared diagram after the editor.
 */
import { useLanguage } from '@/composables'

defineProps<{
  editorName: string
}>()

const { t } = useLanguage()
</script>

<template>
  <div
    data-collab-session-banner
    class="w-full shrink-0 flex items-center justify-center gap-2 border-b border-slate-600/60 px-3 py-1.5 text-xs text-white bg-slate-700/95 pointer-events-none select-none"
    role="status"
  >
    <span>{{ t('canvas.share.readOnlyBar', { name: editorName || '…' }) }}</span>
    <span class="opacity-40">·</span>
    <span>{{ t('canvas.topBar.viewOnly') }}</span>
  </div>
</template>
