<script setup lang="ts">
/**
 * ChannelSidebarItem - Renders a single channel row with Zulip-style
 * nested topic list and bracket indent. Emits navigation and action events.
 */
import { computed } from 'vue'
import {
  Hash, Lock, Globe, Pin, ChevronRight, ChevronDown,
  MoreVertical,
} from 'lucide-vue-next'

import ChannelActionsPopover from '@/components/workshop-chat/ChannelActionsPopover.vue'
import TopicActionsPopover from '@/components/workshop-chat/TopicActionsPopover.vue'
import { useLanguage } from '@/composables/useLanguage'
import type { ChatChannel, ChatTopic } from '@/stores/workshopChat'

const MAX_VISIBLE_TOPICS = 5

const props = defineProps<{
  channel: ChatChannel
  topics: ChatTopic[]
  isExpanded: boolean
  isActiveChannel: boolean
  activeTopicId: number | null
  channelPopoverVisible: boolean
  topicPopoverId: number | null
  showPin?: boolean
  indentLevel?: number
}>()

const emit = defineEmits<{
  navigate: [channelId: number]
  toggleExpand: [channelId: number]
  navigateToTopic: [channelId: number, topicId: number]
  navigateToAllTopics: [channelId: number]
  openSettings: [channelId: number]
  updateChannelPopover: [visible: boolean]
  updateTopicPopover: [topicId: number | null]
  renameTopic: [topicId: number, channelId: number]
  moveTopic: [topicId: number, channelId: number]
}>()

const { t } = useLanguage()

const channelIcon = computed(() => {
  if (props.channel.channel_type === 'private') return Lock
  if (props.channel.channel_type === 'announce') return Globe
  return Hash
})

const visibleTopics = computed(() =>
  props.topics.slice(0, MAX_VISIBLE_TOPICS),
)

const hasMoreTopics = computed(() =>
  props.topics.length > MAX_VISIBLE_TOPICS,
)

const remainingCount = computed(() =>
  Math.max(0, props.topics.length - MAX_VISIBLE_TOPICS),
)

const hasTopics = computed(() => props.topics.length > 0)
</script>

<template>
  <li
    class="channel-item"
    :class="{ 'channel-item--expanded': isExpanded }"
  >
    <!-- Channel header row -->
    <div
      class="channel-row"
      :class="{
        'channel-row--active': isActiveChannel,
        'channel-row--muted': channel.is_muted,
      }"
      :style="indentLevel ? { paddingLeft: `${6 + indentLevel * 12}px` } : undefined"
      @click="emit('navigate', channel.id)"
    >
      <button
        class="channel-expand-btn"
        :class="{ 'channel-expand-btn--visible': hasTopics }"
        @click.stop="emit('toggleExpand', channel.id)"
      >
        <component
          :is="isExpanded ? ChevronDown : ChevronRight"
          :size="12"
        />
      </button>
      <component
        :is="channelIcon"
        :size="14"
        class="channel-icon"
        :style="{ color: channel.color || undefined }"
      />
      <span class="channel-name">{{ channel.name }}</span>
      <Pin v-if="showPin" :size="10" class="pin-indicator" />
      <span v-if="channel.unread_count > 0" class="unread-badge">
        {{ channel.unread_count }}
      </span>
      <ChannelActionsPopover
        :channel-id="channel.id"
        :visible="channelPopoverVisible"
        @update:visible="(v: boolean) => emit('updateChannelPopover', v)"
        @open-settings="emit('openSettings', channel.id)"
      >
        <button class="channel-kebab" @click.stop>
          <MoreVertical :size="12" />
        </button>
      </ChannelActionsPopover>
    </div>

    <!-- Topic list (nested inside channel, Zulip-style) -->
    <ul
      v-if="isExpanded && hasTopics"
      class="topic-list"
      :class="{ 'topic-list--has-more': hasMoreTopics }"
    >
      <li
        v-for="topic in visibleTopics"
        :key="topic.id"
        class="topic-row"
        :class="{
          'topic-row--active': activeTopicId === topic.id,
          'topic-row--muted': topic.visibility_policy === 'muted',
        }"
        @click.stop="emit('navigateToTopic', channel.id, topic.id)"
      >
        <span class="topic-name">
          <span class="topic-name-inner">{{ topic.title }}</span>
        </span>
        <div class="topic-markers">
          <span
            v-if="topic.message_count > 0"
            class="unread-badge unread-badge--topic"
          >
            {{ topic.message_count }}
          </span>
        </div>
        <TopicActionsPopover
          :topic="topic"
          :channel-id="channel.id"
          :visible="topicPopoverId === topic.id"
          @update:visible="(v: boolean) => emit('updateTopicPopover', v ? topic.id : null)"
          @rename="(id: number) => emit('renameTopic', id, channel.id)"
          @move="(id: number) => emit('moveTopic', id, channel.id)"
        >
          <button class="topic-kebab" @click.stop>
            <MoreVertical :size="12" />
          </button>
        </TopicActionsPopover>
      </li>

      <li
        v-if="hasMoreTopics"
        class="topic-row topic-row--show-all"
        @click.stop="emit('navigateToAllTopics', channel.id)"
      >
        <span class="show-all-label">
          {{ t('workshop.showAllTopics') }}
          ({{ remainingCount }} {{ t('workshop.more') }})
        </span>
      </li>
    </ul>

    <!-- Empty topics state -->
    <ul v-if="isExpanded && !hasTopics" class="topic-list">
      <li class="topic-row topic-row--empty">
        <span class="topic-empty-text">{{ t('workshop.noTopicsYet') }}</span>
      </li>
    </ul>
  </li>
</template>

<style scoped>
/* Channel item: wraps both the channel-row header and nested topic-list */
.channel-item {
  position: relative;
}

/* Channel header row */
.channel-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border-radius: 4px;
  cursor: pointer;
  color: hsl(0deg 0% 20%);
  transition: background 120ms ease, box-shadow 120ms ease;
  line-height: 24px;
  font-size: 13px;
}

.channel-row:hover {
  background: hsl(0deg 0% 0% / 5%);
  box-shadow: inset 0 0 0 1px hsl(0deg 0% 0% / 8%);
}

.channel-row--active {
  background: hsl(228deg 56% 58% / 10%);
  box-shadow: inset 0 0 0 1px hsl(228deg 56% 58% / 18%);
}

.channel-row--active:hover {
  background: hsl(228deg 56% 58% / 14%);
}

.channel-row--muted { opacity: 0.45; }

/* Expand toggle for topics */
.channel-expand-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  background: none;
  border: none;
  cursor: pointer;
  color: hsl(0deg 0% 50%);
  border-radius: 2px;
  padding: 0;
  opacity: 0;
  transition: opacity 120ms ease;
}

.channel-row:hover .channel-expand-btn,
.channel-expand-btn--visible {
  opacity: 0.6;
}

.channel-item--expanded .channel-expand-btn { opacity: 1; }

.channel-icon { flex-shrink: 0; }

.channel-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.pin-indicator {
  flex-shrink: 0;
  color: hsl(45deg 90% 50%);
  opacity: 0.55;
}

/* Unread badge */
.unread-badge {
  flex-shrink: 0;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  text-align: center;
  border-radius: 8px;
  background: hsl(217deg 64% 59%);
  color: white;
  font-variant-numeric: tabular-nums;
}

.unread-badge--topic {
  background: hsl(0deg 0% 0% / 12%);
  color: hsl(0deg 0% 40%);
  font-weight: 600;
  min-width: auto;
  height: 15px;
  line-height: 15px;
  font-size: 10px;
}

/* Kebab menu buttons */
.channel-kebab,
.topic-kebab {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  background: none;
  border: none;
  cursor: pointer;
  color: hsl(0deg 0% 50%);
  border-radius: 3px;
  padding: 0;
  opacity: 0;
  transition: all 120ms ease;
}

.channel-row:hover .channel-kebab,
.topic-row:hover .topic-kebab {
  opacity: 0.5;
}

.channel-kebab:hover,
.topic-kebab:hover {
  opacity: 1 !important;
  background: hsl(0deg 0% 0% / 10%);
}

/* ===== Topic list (Zulip-style bracket) ===== */
.topic-list {
  list-style: none;
  margin: 0;
  padding: 1px 0 2px;
  position: relative;
  font-weight: normal;
}

/* Vertical bracket line (left side) */
.topic-list::before {
  content: '';
  display: block;
  position: absolute;
  top: 4px;
  bottom: 6px;
  left: 10px;
  border: 1px solid hsl(0deg 0% 0% / 14%);
  border-right: 0;
  border-radius: 6px 0 0 6px;
  width: 5px;
  pointer-events: none;
}

/* Horizontal bracket line (bottom) */
.topic-list::after {
  content: '';
  display: block;
  position: absolute;
  top: -2px;
  bottom: 6px;
  left: 16px;
  width: 10px;
  border-bottom: 1px solid hsl(0deg 0% 0% / 14%);
  pointer-events: none;
}

.topic-list--has-more::after { width: 16px; }

/* Topic row */
.topic-row {
  position: relative;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px 2px 28px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  line-height: 22px;
  color: hsl(0deg 0% 25%);
  transition: background 120ms ease, box-shadow 120ms ease;
}

.topic-row:hover {
  background: hsl(0deg 0% 0% / 5%);
  box-shadow: inset 0 0 0 1px hsl(0deg 0% 0% / 8%);
}

.topic-row--active {
  background: hsl(228deg 56% 58% / 10%);
  font-weight: 600;
  box-shadow: inset 0 0 0 1px hsl(228deg 56% 58% / 18%);
}

.topic-row--active:hover {
  background: hsl(228deg 56% 58% / 14%);
}

.topic-row--active .topic-name-inner {
  color: hsl(228deg 44% 36%);
}

.topic-row--muted { opacity: 0.4; }
.topic-row--empty { cursor: default; }
.topic-row--empty:hover { background: none; box-shadow: none; }

/* Topic name (supports multi-line like Zulip) */
.topic-name {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.topic-name-inner {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  overflow-wrap: break-word;
  line-height: 1.35;
}

.topic-markers {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

/* "Show all topics" row */
.topic-row--show-all { padding-left: 28px; cursor: pointer; }

.topic-row--show-all:hover {
  background: hsl(228deg 20% 96%);
  box-shadow: none;
}

.show-all-label {
  font-size: 11px;
  font-weight: 600;
  color: hsl(228deg 40% 48%);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  cursor: pointer;
}

.show-all-label:hover { color: hsl(228deg 50% 38%); }

.topic-empty-text {
  color: hsl(0deg 0% 52%);
  font-style: italic;
  font-size: 11px;
  padding-left: 20px;
}
</style>
