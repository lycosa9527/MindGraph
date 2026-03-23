<script setup lang="ts">
/**
 * CoinTossModal - Modal explaining the coin toss stage
 */
import { ElButton, ElDialog } from 'element-plus'

import { Coins } from 'lucide-vue-next'

import { useLanguage } from '@/composables/useLanguage'

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
}>()

const { t } = useLanguage()

function handleClose() {
  emit('update:visible', false)
  emit('close')
}
</script>

<template>
  <ElDialog
    :model-value="visible"
    :title="t('debateverse.coinTossStageTitle')"
    width="500px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    @update:model-value="handleClose"
  >
    <div class="coin-toss-modal-content">
      <div class="flex items-center justify-center mb-4">
        <div class="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center">
          <Coins
            :size="32"
            class="text-blue-600"
          />
        </div>
      </div>

      <p class="text-center text-gray-700 mb-6">
        {{ t('debateverse.coinTossModalBody') }}
      </p>

      <div class="flex justify-center">
        <ElButton
          type="primary"
          @click="handleClose"
        >
          {{ t('debateverse.coinTossGotIt') }}
        </ElButton>
      </div>
    </div>
  </ElDialog>
</template>

<style scoped>
.coin-toss-modal-content {
  padding: 20px 0;
}
</style>
