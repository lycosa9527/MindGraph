<script setup lang="ts">
/**
 * Zulip-style DM drawer for MindMate collab — optimistic send via /api/chat/dm.
 */
import { computed, ref, watch } from 'vue'

import { ElButton, ElDrawer, ElInput } from 'element-plus'

import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { useWorkshopChatStore } from '@/stores/workshopChat'
import { authFetch } from '@/utils/api'

const props = defineProps<{
  visible: boolean
  partnerId: number | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const store = useWorkshopChatStore()

const draft = ref('')
const sending = ref(false)
const localMessages = ref<
  Array<{ id: number; content: string; sender_id: number; optimistic?: boolean }>
>([])

const partnerName = computed(() => {
  if (!props.partnerId) return ''
  const fromMembers = store.orgMembers.find((m) => m.id === props.partnerId)
  if (fromMembers) return fromMembers.name
  const fromDm = store.dmConversations.find((c) => c.partner_id === props.partnerId)
  return fromDm?.partner_name || `#${props.partnerId}`
})

watch(
  () => [props.visible, props.partnerId] as const,
  async ([open, partnerId]) => {
    if (!open || !partnerId) {
      localMessages.value = []
      draft.value = ''
      return
    }
    const rows = await store.fetchDMMessages(partnerId)
    localMessages.value = rows.map((m) => ({
      id: m.id,
      content: m.content,
      sender_id: m.sender_id,
    }))
  },
  { immediate: true }
)

async function sendMessage(): Promise<void> {
  const trimmed = draft.value.trim()
  const partnerId = props.partnerId
  const selfId = Number(authStore.user?.id)
  if (!trimmed || !partnerId || !selfId || sending.value) {
    return
  }

  const tempId = -Date.now()
  localMessages.value = [
    ...localMessages.value,
    { id: tempId, content: trimmed, sender_id: selfId, optimistic: true },
  ]
  draft.value = ''
  sending.value = true

  try {
    const response = await authFetch(`/api/chat/dm/${partnerId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: trimmed, message_type: 'text' }),
    })
    if (!response.ok) {
      localMessages.value = localMessages.value.filter((m) => m.id !== tempId)
      notify.error(t('mindmate.dmSendFailed'))
      return
    }
    const saved = (await response.json()) as { id: number; content: string; sender_id: number }
    localMessages.value = localMessages.value.map((m) =>
      m.id === tempId ? { id: saved.id, content: saved.content, sender_id: saved.sender_id } : m
    )
  } catch {
    localMessages.value = localMessages.value.filter((m) => m.id !== tempId)
    notify.error(t('mindmate.dmSendFailed'))
  } finally {
    sending.value = false
  }
}

function closeDrawer(): void {
  emit('update:visible', false)
}
</script>

<template>
  <ElDrawer
    :model-value="visible"
    :title="partnerName || t('mindmate.dmDrawerTitle')"
    size="360px"
    append-to-body
    @update:model-value="emit('update:visible', $event)"
    @close="closeDrawer"
  >
    <div class="flex flex-col h-full min-h-0">
      <div class="flex-1 overflow-y-auto space-y-2 pb-4">
        <div
          v-for="msg in localMessages"
          :key="msg.id"
          class="text-sm rounded-lg px-3 py-2 max-w-[90%]"
          :class="
            msg.sender_id === Number(authStore.user?.id)
              ? 'ml-auto bg-primary-100 text-stone-800'
              : 'mr-auto bg-stone-100 text-stone-700'
          "
        >
          <div
            class="whitespace-pre-wrap"
            :class="{ 'opacity-70': msg.optimistic }"
          >
            {{ msg.content }}
          </div>
        </div>
      </div>
      <div class="border-t border-stone-200 pt-3 flex gap-2">
        <ElInput
          v-model="draft"
          :placeholder="t('mindmate.dmDrawerPlaceholder')"
          @keyup.enter="sendMessage"
        />
        <ElButton
          type="primary"
          :loading="sending"
          @click="sendMessage"
        >
          Send
        </ElButton>
      </div>
    </div>
  </ElDrawer>
</template>
