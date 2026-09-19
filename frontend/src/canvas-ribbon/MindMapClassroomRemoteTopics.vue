<script setup lang="ts">
/**
 * Preloaded classroom topics on the Topics tab. Tap applies the center topic;
 * teachers can rewrite the list for the ClassIn demo.
 */
import { computed } from 'vue'

import { Plus, RotateCcw, Trash2 } from '@lucide/vue'

import {
  applyClassroomRemoteTopic,
  readDiagramCenterTopic,
} from '@/canvas-ribbon/classroomRemoteTopics'
import I18nText from '@/components/common/I18nText.vue'
import { useClassroomRemoteTopics } from '@/composables/canvas/useClassroomRemoteTopics'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramStore } from '@/stores'

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const topicList = useClassroomRemoteTopics()
const currentTopic = computed(() => readDiagramCenterTopic(diagramStore))

function applyTopic(topic: string): void {
  if (topicList.editing.value) {
    return
  }
  if (!applyClassroomRemoteTopic(diagramStore, topic)) {
    notify.warning(t('canvas.toolbar.createDiagramFirst'))
    return
  }
  notify.success(t('canvas.classroomRemote.topicsApplied', { topic }))
}

function onDraftEnter(): void {
  topicList.addTopic()
}
</script>

<template>
  <section
    class="mm-remote-topics"
    data-testid="mindmap-classroom-remote-topics"
  >
    <div class="mm-remote-topics__head">
      <span class="mm-remote-topics__title">
        <I18nText
          k="canvas.classroomRemote.topicsTitle"
          dense
        />
      </span>
      <button
        type="button"
        class="mm-remote-topics__text-btn"
        data-testid="mindmap-classroom-remote-topics-edit"
        @click="topicList.setEditing(!topicList.editing.value)"
      >
        <I18nText
          :k="
            topicList.editing.value
              ? 'canvas.classroomRemote.topicsDone'
              : 'canvas.classroomRemote.topicsEdit'
          "
          dense
        />
      </button>
    </div>

    <p
      v-if="topicList.topics.value.length === 0 && !topicList.editing.value"
      class="mm-remote-topics__empty"
    >
      <I18nText k="canvas.classroomRemote.topicsEmpty" />
    </p>

    <ul class="mm-remote-topics__list">
      <li
        v-for="(topic, index) in topicList.topics.value"
        :key="`${index}-${topic}`"
        class="mm-remote-topics__row"
      >
        <input
          v-if="topicList.editing.value"
          class="mm-remote-topics__input"
          :value="topic"
          :aria-label="t('canvas.classroomRemote.topicsEdit')"
          :data-testid="`mindmap-classroom-remote-topic-edit-${index}`"
          @change="topicList.updateTopic(index, ($event.target as HTMLInputElement).value)"
        />
        <button
          v-else
          type="button"
          class="mm-remote-topics__chip"
          :class="{ 'is-current': currentTopic === topic }"
          :data-testid="`mindmap-classroom-remote-topic-${index}`"
          :aria-label="t('canvas.classroomRemote.topicsApply')"
          @click="applyTopic(topic)"
        >
          {{ topic }}
        </button>
        <button
          v-if="topicList.editing.value"
          type="button"
          class="mm-remote__icon-btn mm-remote-topics__remove"
          :aria-label="t('canvas.classroomRemote.topicsRemove')"
          :data-testid="`mindmap-classroom-remote-topic-remove-${index}`"
          @click="topicList.removeTopic(index)"
        >
          <Trash2
            class="h-3.5 w-3.5"
            :stroke-width="2.2"
          />
        </button>
      </li>
    </ul>

    <div
      v-if="topicList.editing.value"
      class="mm-remote-topics__add"
    >
      <input
        v-model="topicList.draft.value"
        class="mm-remote-topics__input"
        :placeholder="t('canvas.classroomRemote.topicsAddPlaceholder')"
        data-testid="mindmap-classroom-remote-topic-draft"
        @keydown.enter.prevent="onDraftEnter"
      />
      <button
        type="button"
        class="mm-remote__icon-btn"
        :aria-label="t('canvas.classroomRemote.topicsAdd')"
        data-testid="mindmap-classroom-remote-topic-add"
        @click="topicList.addTopic()"
      >
        <Plus
          class="h-4 w-4"
          :stroke-width="2.2"
        />
      </button>
    </div>

    <button
      v-if="topicList.editing.value"
      type="button"
      class="mm-remote-topics__reset"
      data-testid="mindmap-classroom-remote-topics-reset"
      @click="topicList.resetDefaults()"
    >
      <RotateCcw
        class="h-3 w-3"
        :stroke-width="2.2"
      />
      <I18nText
        k="canvas.classroomRemote.topicsReset"
        dense
      />
    </button>
  </section>
</template>
