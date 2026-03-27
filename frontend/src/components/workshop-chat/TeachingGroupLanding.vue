<script setup lang="ts">
/**
 * Center column when a teaching group (教研组) is selected without a lesson channel.
 * Mirrors Zulip’s stream narrow: overview of topics/conversations under the stream.
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { Hash, MessageSquare, MoreVertical } from 'lucide-vue-next'

import ChannelActionsPopover from '@/components/workshop-chat/ChannelActionsPopover.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import type { LocaleCode } from '@/i18n/locales'
import { intlLocaleForUiCode } from '@/i18n/locales'
import { type ChatChannel, useWorkshopChatStore } from '@/stores/workshopChat'
import { formatDeadlineRelative, lessonStudyDeadlineBadge } from '@/utils/lessonStudyDeadline'

const { t, currentLanguage } = useLanguage()
const store = useWorkshopChatStore()
const router = useRouter()

const streamMenuVisible = ref(false)
const activeLessonPopoverId = ref<number | null>(null)

const intlLocale = computed(() => intlLocaleForUiCode(currentLanguage.value as LocaleCode))

const group = computed((): ChatChannel | null => {
  const id = store.teachingGroupLandingId
  if (id == null) {
    return null
  }
  const g = store.findChannelById(id)
  return g ?? null
})

const lessonStudies = computed(() => group.value?.children ?? [])

function topicsForLesson(channelId: number) {
  return store.topics.filter((tp) => tp.channel_id === channelId)
}

function openLesson(channelId: number): void {
  store.selectChannel(channelId)
  void router.push('/workshop-chat')
}

function openTopic(channelId: number, topicId: number): void {
  store.selectChannel(channelId)
  store.selectTopic(topicId)
  void router.push('/workshop-chat')
}

function openGroupSettings(): void {
  const id = store.teachingGroupLandingId
  if (id == null) {
    return
  }
  store.dialogChannelSettingsId = id
  void router.push('/workshop-chat')
}

function openLessonSettings(lessonId: number): void {
  store.dialogChannelSettingsId = lessonId
  void router.push('/workshop-chat')
}

function lessonDeadlineLine(ch: ChatChannel): string | null {
  const badge = lessonStudyDeadlineBadge(ch)
  if (badge.kind === 'inactive' || badge.kind === 'none') {
    return null
  }
  if (badge.kind === 'done') {
    return t('workshop.deadlineBadgeDone')
  }
  if (!ch.deadline) {
    return null
  }
  const rel = formatDeadlineRelative(ch.deadline, intlLocale.value)
  if (badge.kind === 'overdue') {
    return `${t('workshop.lessonStudyDue')}: ${rel} (${t('workshop.deadlineBadgeOverdue')})`
  }
  return `${t('workshop.lessonStudyDue')}: ${rel}`
}
</script>

<template>
  <div
    v-if="group"
    class="tg-landing"
  >
    <header class="tg-landing__header">
      <div class="tg-landing__header-top">
        <div class="tg-landing__title-row">
          <span
            v-if="group.avatar"
            class="tg-landing__avatar"
            >{{ group.avatar }}</span
          >
          <h2 class="tg-landing__title">{{ group.name }}</h2>
        </div>
        <ChannelActionsPopover
          :channel-id="group.id"
          :visible="streamMenuVisible"
          @update:visible="streamMenuVisible = $event"
          @open-settings="openGroupSettings"
          @add-lesson-study="store.openCreateChannel({ parentId: group.id })"
        >
          <button
            type="button"
            class="tg-landing__header-menu"
            :title="t('workshop.streamMenu')"
            @click.stop
          >
            <MoreVertical :size="20" />
          </button>
        </ChannelActionsPopover>
      </div>
      <p
        v-if="group.description"
        class="tg-landing__desc"
      >
        {{ group.description }}
      </p>
      <p class="tg-landing__hint">
        {{ t('workshop.teachingGroupLandingHint') }}
      </p>
    </header>

    <div
      v-if="lessonStudies.length === 0"
      class="tg-landing__empty"
    >
      {{ t('workshop.teachingGroupNoLessons') }}
    </div>

    <section
      v-for="lesson in lessonStudies"
      :key="lesson.id"
      class="tg-landing__block"
    >
      <div class="tg-landing__lesson-row">
        <button
          type="button"
          class="tg-landing__lesson-head"
          @click="openLesson(lesson.id)"
        >
          <Hash
            :size="16"
            class="tg-landing__lesson-icon"
            :style="{ color: lesson.color || undefined }"
          />
          <span class="tg-landing__lesson-name">{{ lesson.name }}</span>
          <span
            v-if="lesson.unread_count > 0"
            class="tg-landing__unread"
            >{{ lesson.unread_count }}</span
          >
        </button>
        <ChannelActionsPopover
          :channel-id="lesson.id"
          :visible="activeLessonPopoverId === lesson.id"
          @update:visible="
            (v: boolean) => {
              activeLessonPopoverId = v ? lesson.id : null
            }
          "
          @open-settings="openLessonSettings(lesson.id)"
          @add-conversation="store.requestNewTopicForChannel(lesson.id)"
        >
          <button
            type="button"
            class="tg-landing__lesson-kebab"
            :title="t('workshop.lessonStudyMenu')"
            @click.stop
          >
            <MoreVertical :size="16" />
          </button>
        </ChannelActionsPopover>
      </div>
      <p
        v-if="lessonDeadlineLine(lesson)"
        class="tg-landing__lesson-meta"
      >
        {{ lessonDeadlineLine(lesson) }}
      </p>

      <ul
        v-if="topicsForLesson(lesson.id).length > 0"
        class="tg-landing__topics"
      >
        <li
          v-for="topic in topicsForLesson(lesson.id)"
          :key="topic.id"
          class="tg-landing__topic"
        >
          <button
            type="button"
            class="tg-landing__topic-btn"
            @click="openTopic(lesson.id, topic.id)"
          >
            <MessageSquare
              :size="14"
              class="tg-landing__topic-icon"
            />
            <span class="tg-landing__topic-title">{{ topic.title }}</span>
            <span
              v-if="(topic.unread_count ?? 0) > 0"
              class="tg-landing__topic-unread"
              >{{ topic.unread_count }}</span
            >
          </button>
        </li>
      </ul>
      <p
        v-else
        class="tg-landing__no-topics"
      >
        {{ t('workshop.noTopicsYet') }}
      </p>
    </section>
  </div>
</template>

<style scoped>
.tg-landing {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 20px 24px;
  max-width: 720px;
  margin: 0 auto;
}

.tg-landing__header {
  border-bottom: 1px solid hsl(0deg 0% 90%);
  padding-bottom: 12px;
}

.tg-landing__header-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.tg-landing__title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.tg-landing__header-menu {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  margin: -4px 0 0;
  padding: 0;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: hsl(0deg 0% 38%);
  cursor: pointer;
  flex-shrink: 0;
  transition:
    background 120ms ease,
    color 120ms ease;
}

.tg-landing__header-menu:hover {
  background: hsl(0deg 0% 0% / 6%);
  color: hsl(0deg 0% 22%);
}

.tg-landing__avatar {
  font-size: 1.5rem;
  line-height: 1;
}

.tg-landing__title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: hsl(0deg 0% 12%);
}

.tg-landing__desc {
  margin: 8px 0 0;
  font-size: 13px;
  color: hsl(0deg 0% 38%);
  line-height: 1.45;
}

.tg-landing__hint {
  margin: 10px 0 0;
  font-size: 12px;
  color: hsl(0deg 0% 48%);
  line-height: 1.4;
}

.tg-landing__empty {
  font-size: 13px;
  color: hsl(0deg 0% 45%);
  padding: 12px 0;
}

.tg-landing__block {
  border: 1px solid hsl(0deg 0% 90%);
  border-radius: 8px;
  padding: 10px 12px 12px;
  background: hsl(0deg 0% 99%);
}

.tg-landing__lesson-row {
  display: flex;
  align-items: flex-start;
  gap: 4px;
}

.tg-landing__lesson-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
  text-align: left;
  font: inherit;
  font-weight: 600;
  font-size: 14px;
  color: hsl(228deg 40% 32%);
}

.tg-landing__lesson-head:hover {
  color: hsl(228deg 50% 28%);
}

.tg-landing__lesson-kebab {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 28px;
  margin: -2px 0 0;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: hsl(0deg 0% 42%);
  cursor: pointer;
  flex-shrink: 0;
  opacity: 0.65;
  transition:
    opacity 120ms ease,
    background 120ms ease;
}

.tg-landing__lesson-kebab:hover {
  opacity: 1;
  background: hsl(0deg 0% 0% / 6%);
}

.tg-landing__lesson-row:hover .tg-landing__lesson-kebab {
  opacity: 0.9;
}

.tg-landing__lesson-icon {
  flex-shrink: 0;
  opacity: 0.85;
}

.tg-landing__lesson-name {
  flex: 1;
  min-width: 0;
}

.tg-landing__unread {
  flex-shrink: 0;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  font-size: 11px;
  font-weight: 700;
  line-height: 18px;
  text-align: center;
  border-radius: 9px;
  background: hsl(217deg 64% 59%);
  color: white;
}

.tg-landing__lesson-meta {
  margin: 4px 0 0 24px;
  font-size: 11px;
  color: hsl(0deg 0% 45%);
}

.tg-landing__topics {
  list-style: none;
  margin: 8px 0 0;
  padding: 0 0 0 8px;
  border-left: 2px solid hsl(228deg 40% 85%);
}

.tg-landing__topic {
  margin: 2px 0;
}

.tg-landing__topic-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 6px 8px;
  border: none;
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font: inherit;
  font-size: 13px;
  color: hsl(0deg 0% 22%);
}

.tg-landing__topic-btn:hover {
  background: hsl(228deg 45% 96%);
}

.tg-landing__topic-icon {
  flex-shrink: 0;
  opacity: 0.55;
}

.tg-landing__topic-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tg-landing__topic-unread {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  color: hsl(217deg 64% 45%);
}

.tg-landing__no-topics {
  margin: 8px 0 0 24px;
  font-size: 12px;
  color: hsl(0deg 0% 50%);
}
</style>
