<script setup lang="ts">
/**
 * Hover menu that shelves a chat file or diagram into 资源 or 产物.
 */
import { ElPopover } from 'element-plus'

import { Archive } from '@lucide/vue'

import { useLanguage } from '@/composables'

defineProps<{
  busy?: boolean
}>()

const emit = defineEmits<{
  (e: 'pick', destination: 'resource' | 'artifact'): void
}>()

const { t } = useLanguage()

function pick(destination: 'resource' | 'artifact'): void {
  emit('pick', destination)
}
</script>

<template>
  <ElPopover
    trigger="hover"
    placement="top-end"
    :show-arrow="false"
    :width="148"
    :hide-after="160"
    :disabled="busy"
    popper-class="mm-shelf-popper"
  >
    <template #reference>
      <button
        type="button"
        class="mm-shelf__icon"
        :aria-label="t('mindmate.shelf.archive')"
        :disabled="busy"
        @click.stop
      >
        <Archive
          :size="16"
          aria-hidden="true"
        />
      </button>
    </template>
    <div
      class="mm-shelf__menu"
      role="menu"
    >
      <button
        type="button"
        role="menuitem"
        @click.stop="pick('resource')"
      >
        <I18nText k="mindmate.shelf.toResource" />
      </button>
      <button
        type="button"
        role="menuitem"
        @click.stop="pick('artifact')"
      >
        <I18nText k="mindmate.shelf.toArtifact" />
      </button>
    </div>
  </ElPopover>
</template>

<style scoped>
.mm-shelf__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 999px;
  background: #f5f3ff;
  color: #7c3aed;
  cursor: pointer;
}

.mm-shelf__icon:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>

<style>
.mm-shelf-popper.el-popover.el-popper {
  min-width: 148px;
  padding: 4px;
  border: 1px solid #e7e5e4;
  border-radius: 10px;
}

.mm-shelf-popper .mm-shelf__menu {
  display: flex;
  flex-direction: column;
}

.mm-shelf-popper .mm-shelf__menu button {
  height: 32px;
  padding: 0 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #1c1917;
  font-size: 13px;
  text-align: left;
  white-space: nowrap;
  cursor: pointer;
}

.mm-shelf-popper .mm-shelf__menu button:hover {
  background: #f5f3ff;
  color: #5b21b6;
}
</style>
