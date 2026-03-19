<script setup lang="ts">
import { ref } from 'vue'
import { Settings } from 'lucide-vue-next'
import { useLanguage } from '@/composables/useLanguage'

const emit = defineEmits<{
  (e: 'navigate', page: string): void
}>()

const { t } = useLanguage()

const visible = ref(false)

function go(page: string): void {
  visible.value = false
  emit('navigate', page)
}
</script>

<template>
  <el-popover
    v-model:visible="visible"
    placement="bottom-end"
    :width="180"
    trigger="click"
  >
    <template #reference>
      <button
        class="p-1.5 rounded-md hover:bg-stone-200/70 transition-colors text-stone-500"
        :title="t('workshop.gearMenu')"
      >
        <Settings class="w-4 h-4" />
      </button>
    </template>

    <div class="ws-popover-menu">
      <button class="ws-popover-item" @click="go('notifications')">
        {{ t('workshop.notifications') }}
      </button>
      <button class="ws-popover-item" @click="go('preferences')">
        {{ t('workshop.preferences') }}
      </button>
    </div>
  </el-popover>
</template>

<style scoped>
.ws-popover-menu {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: -4px;
}

.ws-popover-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  font-size: 13px;
  color: hsl(0deg 0% 30%);
  background: none;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  width: 100%;
  text-align: left;
  transition: background 120ms ease;
}

.ws-popover-item:hover {
  background: hsl(0deg 0% 0% / 5%);
}
</style>
