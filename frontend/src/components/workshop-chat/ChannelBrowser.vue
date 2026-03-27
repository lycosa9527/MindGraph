<script setup lang="ts">
/**
 * ChannelBrowser - Browse and join channels in the user's organization.
 * Groups channels by type: Announce, Public, Private.
 */
import { computed } from 'vue'

import { OfficeBuilding } from '@element-plus/icons-vue'

import { Globe, Lock, Megaphone, Pin } from 'lucide-vue-next'

import { useLanguage } from '@/composables/core/useLanguage'
import type { ChatChannel } from '@/stores/workshopChat'

const { t } = useLanguage()

const props = defineProps<{
  channels: ChatChannel[]
  loading?: boolean
}>()

const emit = defineEmits<{
  select: [channelId: number]
  join: [channelId: number]
  leave: [channelId: number]
}>()

interface ChannelSection {
  key: string
  labelKey: string
  icon: typeof Globe
  channels: ChatChannel[]
}

const sections = computed<ChannelSection[]>(() => {
  const announce = props.channels.filter((c) => c.channel_type === 'announce')
  const pub = props.channels.filter((c) => c.channel_type === 'public')
  const priv = props.channels.filter((c) => c.channel_type === 'private')

  const result: ChannelSection[] = []
  if (announce.length > 0) {
    result.push({
      key: 'announce',
      labelKey: 'workshop.announceChannels',
      icon: Megaphone,
      channels: announce,
    })
  }
  if (pub.length > 0) {
    result.push({
      key: 'public',
      labelKey: 'workshop.publicChannels',
      icon: Globe,
      channels: pub,
    })
  }
  if (priv.length > 0) {
    result.push({
      key: 'private',
      labelKey: 'workshop.privateChannels',
      icon: Lock,
      channels: priv,
    })
  }
  return result
})

function typeColor(ct: string): string {
  if (ct === 'announce') return 'text-amber-500'
  if (ct === 'private') return 'text-rose-400'
  return 'text-emerald-500'
}
</script>

<template>
  <div class="cb">
    <div
      v-if="loading"
      class="cb__loading"
    >
      <div class="cb__spinner" />
    </div>

    <div
      v-else-if="channels.length === 0"
      class="cb__empty"
    >
      {{ t('workshop.noChannelsAvailable') }}
    </div>

    <div
      v-else
      class="cb__body"
    >
      <div
        v-for="section in sections"
        :key="section.key"
        class="cb__section"
      >
        <!-- Section header -->
        <div class="cb__section-header">
          <component
            :is="section.icon"
            class="cb__section-icon"
            :class="typeColor(section.key)"
          />
          <h2 class="cb__section-title">{{ t(section.labelKey) }}</h2>
          <span class="cb__section-count">{{ section.channels.length }}</span>
        </div>

        <!-- Channel cards grid -->
        <div class="cb__grid">
          <div
            v-for="channel in section.channels"
            :key="channel.id"
            class="cb__card"
            :class="{
              'cb__card--muted': channel.is_muted,
              'cb__card--joined': channel.is_joined,
            }"
            :style="
              channel.is_joined && channel.color
                ? { borderLeftColor: channel.color, borderLeftWidth: '3px' }
                : {}
            "
            @click="channel.is_joined ? emit('select', channel.id) : undefined"
          >
            <div class="cb__card-top">
              <div class="cb__card-avatar">
                {{ channel.avatar || '📢' }}
              </div>
              <div class="cb__card-info">
                <div class="cb__card-name-row">
                  <h3 class="cb__card-name">{{ channel.name }}</h3>
                  <Pin
                    v-if="channel.pin_to_top"
                    class="cb__card-pin"
                  />
                  <el-badge
                    v-if="channel.unread_count > 0"
                    :value="channel.unread_count"
                    type="danger"
                    class="shrink-0"
                  />
                </div>
                <p
                  v-if="channel.description"
                  class="cb__card-desc"
                >
                  {{ channel.description }}
                </p>
                <div class="cb__card-meta">
                  <span class="cb__card-meta-item">
                    <el-icon :size="12"><OfficeBuilding /></el-icon>
                    {{ channel.member_count }} {{ t('workshop.members') }}
                  </span>
                  <span class="cb__card-meta-item">
                    {{ channel.topic_count }} {{ t('workshop.topicCount') }}
                  </span>
                  <span
                    v-if="channel.is_default"
                    class="cb__card-default-badge"
                  >
                    {{ t('workshop.defaultChannel') }}
                  </span>
                </div>
              </div>
            </div>

            <div class="cb__card-actions">
              <el-button
                v-if="!channel.is_joined"
                size="small"
                type="primary"
                @click.stop="emit('join', channel.id)"
              >
                {{ t('workshop.join') }}
              </el-button>
              <el-button
                v-else-if="channel.channel_type !== 'announce'"
                size="small"
                plain
                @click.stop="emit('leave', channel.id)"
              >
                {{ t('workshop.leave') }}
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cb__loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}

.cb__spinner {
  width: 22px;
  height: 22px;
  border: 2px solid hsl(0deg 0% 84%);
  border-top-color: hsl(228deg 56% 58%);
  border-radius: 50%;
  animation: cb-spin 0.65s linear infinite;
}

@keyframes cb-spin {
  to {
    transform: rotate(360deg);
  }
}

.cb__empty {
  text-align: center;
  padding: 40px 16px;
  color: hsl(0deg 0% 52%);
  font-size: 14px;
}

.cb__body {
  padding: 16px;
}

.cb__section {
  margin-bottom: 24px;
}

.cb__section:last-child {
  margin-bottom: 0;
}

.cb__section-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}

.cb__section-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.cb__section-title {
  font-size: 11px;
  font-weight: 700;
  color: hsl(0deg 0% 40%);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0;
}

.cb__section-count {
  font-size: 10px;
  color: hsl(0deg 0% 52%);
}

.cb__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.cb__card {
  border: 1px solid hsl(0deg 0% 0% / 10%);
  border-radius: 8px;
  padding: 14px 16px;
  background: hsl(0deg 0% 100%);
  cursor: pointer;
  transition:
    border-color 150ms ease,
    box-shadow 150ms ease;
}

.cb__card:hover {
  border-color: hsl(0deg 0% 0% / 16%);
  box-shadow: 0 2px 8px hsl(0deg 0% 0% / 6%);
}

.cb__card--muted {
  opacity: 0.55;
}

.cb__card-top {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.cb__card-avatar {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: hsl(0deg 0% 96%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.cb__card-info {
  flex: 1;
  min-width: 0;
}

.cb__card-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.cb__card-name {
  font-size: 14px;
  font-weight: 600;
  color: hsl(0deg 0% 12%);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin: 0;
}

.cb__card-pin {
  width: 12px;
  height: 12px;
  color: hsl(45deg 90% 50%);
  flex-shrink: 0;
}

.cb__card-desc {
  font-size: 12px;
  color: hsl(0deg 0% 42%);
  margin-top: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
}

.cb__card-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  font-size: 12px;
}

.cb__card-meta-item {
  display: flex;
  align-items: center;
  gap: 3px;
  color: hsl(0deg 0% 48%);
}

.cb__card-default-badge {
  font-size: 10px;
  background: hsl(0deg 0% 96%);
  padding: 1px 6px;
  border-radius: 4px;
  color: hsl(0deg 0% 42%);
}

.cb__card-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
