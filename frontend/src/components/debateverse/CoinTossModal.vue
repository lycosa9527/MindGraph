<script setup lang="ts">
/**
 * CoinTossModal - Modal explaining the coin toss stage
 */
import { ElDialog, ElButton } from 'element-plus'
import { useLanguage } from '@/composables/useLanguage'
import { Coins } from 'lucide-vue-next'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
}>()

const { isZh } = useLanguage()

function handleClose() {
  emit('update:visible', false)
  emit('close')
}
</script>

<template>
  <ElDialog
    :model-value="visible"
    :title="isZh ? '掷硬币阶段' : 'Coin Toss Stage'"
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
        {{ isZh ? '赛前通过掷硬币决定发言顺序或选择正反方立场' : 'Before the debate, determine speaking order or choose affirmative/negative positions through coin toss' }}
      </p>
      
      <div class="flex justify-center">
        <ElButton
          type="primary"
          @click="handleClose"
        >
          {{ isZh ? '知道了' : 'Got it' }}
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
