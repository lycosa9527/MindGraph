<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { createClipLesson, deleteClipLesson, listClipLessons } from '@/utils/clipTeachingApi'
import type { ClipLessonSummary } from '@/utils/clipTeachingApi'

const { t } = useLanguage()
const notify = useNotifications()
const router = useRouter()
const items = ref<ClipLessonSummary[]>([])
const loading = ref(true)
const busy = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    items.value = await listClipLessons()
  } catch {
    notify.errorKey('clipTeaching.loadFailed')
  } finally {
    loading.value = false
  }
}

async function create(): Promise<void> {
  busy.value = true
  try {
    const lesson = await createClipLesson(t('clipTeaching.untitled'))
    await router.push(`/clip-teaching/${lesson.id}`)
  } catch {
    notify.errorKey('clipTeaching.saveFailed')
  } finally {
    busy.value = false
  }
}

async function remove(item: ClipLessonSummary): Promise<void> {
  if (!window.confirm(t('clipTeaching.deleteConfirm'))) return
  try {
    await deleteClipLesson(item.id)
    items.value = items.value.filter((row) => row.id !== item.id)
  } catch {
    notify.errorKey('clipTeaching.saveFailed')
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="clip-list">
    <header>
      <h1><I18nText k="clipTeaching.title" /></h1>
      <button
        type="button"
        :disabled="busy"
        @click="create"
      >
        <I18nText k="clipTeaching.create" />
      </button>
    </header>
    <p v-if="loading"><I18nText k="clipTeaching.loading" /></p>
    <p v-else-if="items.length === 0"><I18nText k="clipTeaching.empty" /></p>
    <ul v-else>
      <li
        v-for="item in items"
        :key="item.id"
      >
        <button
          type="button"
          class="clip-list-open"
          @click="router.push(`/clip-teaching/${item.id}`)"
        >
          <strong>{{ item.title }}</strong>
          <span>{{ item.owner_name }}</span>
        </button>
        <button
          v-if="item.is_owner"
          type="button"
          @click="remove(item)"
        >
          <I18nText k="clipTeaching.deleteLesson" />
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.clip-list {
  height: 100%;
  overflow: auto;
  padding: 24px;
  background: #fafaf9;
}

.clip-list header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.clip-list h1 {
  margin: 0;
  font-size: 22px;
}

.clip-list ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.clip-list li,
.clip-list header button,
.clip-list li button {
  border-radius: 10px;
}

.clip-list li {
  display: flex;
  gap: 8px;
  align-items: center;
  background: #fff;
  border: 1px solid #e7e5e4;
  padding: 8px;
}

.clip-list-open {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  border: 0;
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.clip-list button {
  border: 1px solid #d6d3d1;
  background: #fff;
  padding: 8px 12px;
  cursor: pointer;
}
</style>
