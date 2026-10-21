<script setup lang="ts">
/**
 * One-item menu shown when a seminar avatar is right-clicked.
 */
import { computed, onMounted, onUnmounted } from 'vue'

const props = defineProps<{
  x: number
  y: number
  name: string
}>()

const emit = defineEmits<{
  (e: 'choose'): void
  (e: 'close'): void
}>()

const point = computed(() => {
  const width = 220
  const height = 44
  return {
    x: Math.max(8, Math.min(props.x, window.innerWidth - width - 8)),
    y: Math.max(8, Math.min(props.y, window.innerHeight - height - 8)),
  }
})

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    emit('close')
  }
}

function onScroll(): void {
  emit('close')
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
  window.addEventListener('scroll', onScroll, true)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('scroll', onScroll, true)
})
</script>

<template>
  <Teleport to="body">
    <div
      class="mm-mention-menu__backdrop"
      @mousedown="emit('close')"
      @contextmenu.prevent="emit('close')"
    >
      <button
        type="button"
        class="mm-mention-menu"
        :style="{ left: `${point.x}px`, top: `${point.y}px` }"
        @mousedown.stop
        @click.stop="emit('choose')"
      >
        @{{ name }}
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
.mm-mention-menu__backdrop {
  position: fixed;
  inset: 0;
  z-index: 4000;
}

.mm-mention-menu {
  position: fixed;
  z-index: 4001;
  max-width: 220px;
  margin: 0;
  padding: 8px 14px;
  border: 1px solid #ece9f5;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(40, 24, 72, 0.12);
  color: #5b4cdb;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.3;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.mm-mention-menu:hover {
  background: #f6f4ff;
}
</style>
