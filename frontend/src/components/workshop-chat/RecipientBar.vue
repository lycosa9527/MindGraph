<script setup lang="ts">
import { ChevronRight, Globe, Hash, Lock, User } from 'lucide-vue-next'

defineProps<{
  type: 'channel' | 'dm'
  channelName?: string
  channelType?: 'announce' | 'public' | 'private'
  channelColor?: string
  topicName?: string
  dmPartnerName?: string
  date?: string
  isSticky?: boolean
}>()

function channelTypeIcon(ct?: string) {
  if (ct === 'private') return Lock
  if (ct === 'announce') return Globe
  return Hash
}
</script>

<template>
  <div
    class="recipient-bar"
    :class="{
      'recipient-bar--sticky': isSticky,
      'recipient-bar--dm': type === 'dm',
    }"
  >
    <div
      class="recipient-bar__inner"
      :style="type === 'channel' && channelColor
        ? { background: `linear-gradient(90deg, ${channelColor}22 0%, hsl(0deg 0% 100%) 50%)` }
        : undefined"
    >
      <!-- Channel header -->
      <template v-if="type === 'channel'">
        <span class="recipient-bar__stream">
          <component
            :is="channelTypeIcon(channelType)"
            :size="13"
            class="recipient-bar__stream-icon"
            :style="{ color: channelColor || undefined }"
          />
          <span
            class="recipient-bar__stream-name"
            :style="{ color: channelColor || undefined }"
          >
            {{ channelName }}
          </span>
        </span>
        <span v-if="topicName" class="recipient-bar__chevron">
          <ChevronRight :size="12" />
        </span>
        <span v-if="topicName" class="recipient-bar__topic">
          {{ topicName }}
        </span>
      </template>

      <!-- DM header -->
      <template v-else>
        <span class="recipient-bar__dm">
          <User :size="13" class="recipient-bar__dm-icon" />
          <span class="recipient-bar__dm-name">{{ dmPartnerName }}</span>
        </span>
      </template>

      <!-- Date on the right -->
      <span v-if="date" class="recipient-bar__date">
        {{ date }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.recipient-bar {
  position: relative;
  z-index: 3;
}

.recipient-bar--sticky {
  position: sticky;
  top: 0;
  z-index: 4;
}

.recipient-bar__inner {
  display: flex;
  align-items: center;
  gap: 3px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid hsl(0deg 0% 0% / 10%);
  border-bottom: 1px solid hsl(0deg 0% 0% / 14%);
  border-radius: 6px 6px 0 0;
  background: hsl(0deg 0% 100%);
  font-size: 13px;
  line-height: 28px;
}

.recipient-bar--dm .recipient-bar__inner {
  background: hsl(40deg 18% 96%);
  border-color: hsl(40deg 15% 82%);
}

/* Stream / channel label */
.recipient-bar__stream {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  padding: 2px 4px 2px 0;
  border-radius: 3px;
  transition: background 100ms ease;
}

.recipient-bar__stream:hover {
  background: hsl(0deg 0% 0% / 5%);
}

.recipient-bar__stream:hover .recipient-bar__stream-name {
  text-decoration: underline;
}

.recipient-bar__stream-icon { flex-shrink: 0; }

.recipient-bar__stream-name {
  font-weight: 700;
  font-size: 13px;
  letter-spacing: -0.005em;
}

/* Chevron separator */
.recipient-bar__chevron {
  display: inline-flex;
  align-items: center;
  color: hsl(0deg 0% 68%);
  margin: 0 1px;
}

/* Topic */
.recipient-bar__topic {
  font-weight: 600;
  color: hsl(0deg 0% 22%);
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 3px;
  transition: background 100ms ease;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recipient-bar__topic:hover {
  text-decoration: underline;
  background: hsl(0deg 0% 0% / 4%);
}

/* DM */
.recipient-bar__dm {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.recipient-bar__dm-icon { color: hsl(0deg 0% 42%); }

.recipient-bar__dm-name {
  font-weight: 700;
  color: hsl(0deg 0% 22%);
  letter-spacing: -0.005em;
}

/* Date */
.recipient-bar__date {
  margin-left: auto;
  font-size: 11px;
  font-weight: 700;
  color: hsl(0deg 0% 15% / 45%);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}
</style>
