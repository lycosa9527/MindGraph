<script setup lang="ts">
/**
 * MindMate collab — org contacts or session participants sidebar.
 */
import OrgContactsPanel from '@/components/social/OrgContactsPanel.vue'

defineProps<{
  sessionId: string
  roomCode: string
  roomTitle: string
  visibility?: string
}>()

const emit = defineEmits<{
  (e: 'message', partnerId: number): void
}>()
</script>

<template>
  <OrgContactsPanel
    source="mindmate-collab"
    variant="compact"
    zulip-presence
    :session-id="sessionId"
    :collab-room-code="roomCode"
    :collab-visibility="visibility || 'organization'"
    @message="emit('message', $event)"
  />
</template>
