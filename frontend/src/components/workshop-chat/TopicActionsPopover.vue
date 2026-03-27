<script setup lang="ts">
import { computed } from 'vue'

import { ElMessageBox } from 'element-plus'

import { ArrowRightLeft, Bell, BellOff, BookCheck, Eye, Pencil, Trash2 } from 'lucide-vue-next'

import { useLanguage } from '@/composables/core/useLanguage'
import { useAuthStore } from '@/stores/auth'
import type { ChatTopic } from '@/stores/workshopChat'
import { useWorkshopChatStore } from '@/stores/workshopChat'

const props = defineProps<{
  topic: ChatTopic
  channelId: number
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'rename', topicId: number): void
  (e: 'move', topicId: number): void
}>()

const store = useWorkshopChatStore()
const authStore = useAuthStore()
const { t } = useLanguage()

const canManage = computed(
  () =>
    authStore.isAdmin ||
    authStore.isManager ||
    props.topic.created_by === Number(authStore.user?.id)
)

async function handleMarkRead(): Promise<void> {
  await store.markTopicRead(props.channelId, props.topic.id)
  emit('update:visible', false)
}

async function handleToggleMute(): Promise<void> {
  const newPolicy = props.topic.visibility_policy === 'muted' ? 'inherit' : 'muted'
  await store.setTopicVisibility(props.channelId, props.topic.id, newPolicy)
  emit('update:visible', false)
}

async function handleToggleFollow(): Promise<void> {
  const newPolicy = props.topic.visibility_policy === 'followed' ? 'inherit' : 'followed'
  await store.setTopicVisibility(props.channelId, props.topic.id, newPolicy)
  emit('update:visible', false)
}

function handleRename(): void {
  emit('rename', props.topic.id)
  emit('update:visible', false)
}

function handleMove(): void {
  emit('move', props.topic.id)
  emit('update:visible', false)
}

async function handleDelete(): Promise<void> {
  try {
    await ElMessageBox.confirm(t('workshop.deleteTopicConfirm'), t('workshop.deleteTopic'), {
      confirmButtonText: t('workshop.deleteTopic'),
      type: 'warning',
    })
    await store.deleteTopic(props.channelId, props.topic.id)
    emit('update:visible', false)
  } catch {
    /* user cancelled */
  }
}
</script>

<template>
  <el-popover
    :visible="visible"
    placement="bottom-start"
    :width="220"
    trigger="click"
    @update:visible="emit('update:visible', $event)"
  >
    <template #reference>
      <slot />
    </template>

    <div class="ws-popover-menu">
      <button
        class="ws-popover-item"
        @click="handleMarkRead"
      >
        <BookCheck class="ws-popover-icon" />
        {{ t('workshop.markAsRead') }}
      </button>

      <button
        class="ws-popover-item"
        @click="handleToggleMute"
      >
        <component
          :is="topic.visibility_policy === 'muted' ? Bell : BellOff"
          class="ws-popover-icon"
        />
        {{
          topic.visibility_policy === 'muted' ? t('workshop.unmuteTopic') : t('workshop.muteTopic')
        }}
      </button>

      <button
        class="ws-popover-item"
        @click="handleToggleFollow"
      >
        <Eye class="ws-popover-icon" />
        {{
          topic.visibility_policy === 'followed'
            ? t('workshop.unfollowTopic')
            : t('workshop.followTopic')
        }}
      </button>

      <template v-if="canManage">
        <div class="ws-popover-divider" />

        <button
          class="ws-popover-item"
          @click="handleRename"
        >
          <Pencil class="ws-popover-icon" />
          {{ t('workshop.renameTopic') }}
        </button>

        <button
          class="ws-popover-item"
          @click="handleMove"
        >
          <ArrowRightLeft class="ws-popover-icon" />
          {{ t('workshop.moveTopic') }}
        </button>

        <button
          class="ws-popover-item ws-popover-item--danger"
          @click="handleDelete"
        >
          <Trash2 class="ws-popover-icon" />
          {{ t('workshop.deleteTopic') }}
        </button>
      </template>
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

.ws-popover-item--danger {
  color: hsl(0deg 60% 48%);
}

.ws-popover-item--danger:hover {
  background: hsl(0deg 70% 97%);
}

.ws-popover-icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
  opacity: 0.7;
}

.ws-popover-divider {
  height: 1px;
  background: hsl(0deg 0% 0% / 8%);
  margin: 2px 0;
}
</style>
