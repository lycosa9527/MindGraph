<script setup lang="ts">
/**
 * MaitePracticeHistory — recent inquiry sessions in the app sidebar
 * (same accordion pattern as AskOnceHistory / DebateHistory).
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ElScrollbar } from 'element-plus'

import { BookOpen } from '@lucide/vue'
import { storeToRefs } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useMaitePracticeHistory } from '@/composables/maite/useMaitePracticeHistory'
import { useMaiteStore } from '@/stores/maite'

import type { MaitePracticeItem } from '@/types/maite'

defineProps<{
  isBlurred?: boolean
}>()

const { t } = useLanguage()
const router = useRouter()
const store = useMaiteStore()
const { recentPractice, activeSessionId } = storeToRefs(store)
const { loading, loadSessions } = useMaitePracticeHistory()

const showAll = ref(false)
const INITIAL_LIMIT = 10

interface GroupedPractice {
  today: MaitePracticeItem[]
  yesterday: MaitePracticeItem[]
  week: MaitePracticeItem[]
  month: MaitePracticeItem[]
}

function itemTime(item: MaitePracticeItem): number {
  const raw = item.updated_at || item.created_at
  const parsed = Date.parse(raw)
  return Number.isFinite(parsed) ? parsed : 0
}

const sortedPractice = computed(() =>
  [...recentPractice.value].sort((a, b) => itemTime(b) - itemTime(a))
)

const groupedPractice = computed((): GroupedPractice => {
  const groups: GroupedPractice = {
    today: [],
    yesterday: [],
    week: [],
    month: [],
  }
  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterdayStart = todayStart - 24 * 60 * 60 * 1000
  const weekStart = todayStart - 7 * 24 * 60 * 60 * 1000
  const items = showAll.value
    ? sortedPractice.value
    : sortedPractice.value.slice(0, INITIAL_LIMIT)

  for (const item of items) {
    const time = itemTime(item)
    if (time >= todayStart) {
      groups.today.push(item)
    } else if (time >= yesterdayStart) {
      groups.yesterday.push(item)
    } else if (time >= weekStart) {
      groups.week.push(item)
    } else {
      groups.month.push(item)
    }
  }
  return groups
})

const hasMore = computed(
  () => sortedPractice.value.length > INITIAL_LIMIT && !showAll.value
)
const remainingCount = computed(() => sortedPractice.value.length - INITIAL_LIMIT)

const groupLabels = computed(() => ({
  today: t('common.date.today'),
  yesterday: t('common.date.yesterday'),
  week: t('common.date.pastWeek'),
  month: t('common.date.pastMonth'),
}))

onMounted(() => {
  void loadSessions()
})

async function openSession(item: MaitePracticeItem): Promise<void> {
  const mode = item.mode === 'demo' ? 'demo' : 'inquiry'
  store.setActiveSessionId(item.id)
  store.setMode(mode)
  eventBus.emit('maite:mode_changed', { mode })
  eventBus.emit('maite:session_opened', { sessionId: item.id, mode })
  if (!router.currentRoute.value.path.startsWith('/maite')) {
    await router.push('/maite')
  }
}

function toggleShowAll(): void {
  showAll.value = !showAll.value
}

function stageLabel(stage: string): string {
  const key = `maite.stage.${stage}`
  const translated = t(key)
  return translated === key ? stage : translated
}
</script>

<template>
  <div class="maite-practice-history flex flex-col border-t border-stone-200 relative overflow-hidden">
    <div class="px-4 py-3">
      <div class="text-xs font-medium text-stone-400 uppercase tracking-wider">
        {{ t('maite.practice.title') }}
      </div>
    </div>

    <ElScrollbar class="flex-1 px-4 pb-4">
      <div :class="isBlurred ? 'blur-sm pointer-events-none select-none' : ''">
        <div
          v-if="loading && recentPractice.length === 0"
          class="text-center py-8"
        >
          <p class="text-xs text-stone-400">{{ t('maite.practice.loading') }}</p>
        </div>

        <div
          v-else-if="recentPractice.length === 0"
          class="text-center py-8"
        >
          <BookOpen class="w-8 h-8 mx-auto mb-2 text-stone-300" />
          <p class="text-xs text-stone-400">{{ t('maite.practice.empty') }}</p>
        </div>

        <template v-else>
          <div
            v-for="groupKey in (['today', 'yesterday', 'week', 'month'] as const)"
            :key="groupKey"
          >
            <div
              v-if="groupedPractice[groupKey].length > 0"
              class="group-section"
            >
              <div class="group-label">{{ groupLabels[groupKey] }}</div>
              <button
                v-for="item in groupedPractice[groupKey]"
                :key="item.id"
                type="button"
                class="practice-item"
                :class="{ active: activeSessionId === item.id }"
                @click="openSession(item)"
              >
                <span class="practice-name">
                  {{ item.title || t('maite.practice.untitled', { id: item.id }) }}
                </span>
                <span class="practice-stage">{{ stageLabel(item.current_stage) }}</span>
              </button>
            </div>
          </div>

          <button
            v-if="hasMore"
            type="button"
            class="show-more-btn"
            @click="toggleShowAll"
          >
            {{ t('sidebar.actions.showMore', { n: remainingCount }) }}
          </button>
        </template>
      </div>
    </ElScrollbar>
  </div>
</template>

<style scoped>
.maite-practice-history {
  max-height: 320px;
}

.group-section {
  margin-bottom: 12px;
}

.group-label {
  font-size: 11px;
  font-weight: 500;
  color: #a8a29e;
  margin-bottom: 4px;
  padding: 0 4px;
}

.practice-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background-color 0.15s;
}

.practice-item:hover,
.practice-item.active {
  background: #f5f5f4;
}

.practice-name {
  font-size: 13px;
  color: #1c1917;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.practice-stage {
  font-size: 11px;
  color: #78716c;
}

.show-more-btn {
  width: 100%;
  padding: 8px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #78716c;
  font-size: 12px;
  cursor: pointer;
}

.show-more-btn:hover {
  background: #f5f5f4;
  color: #1c1917;
}
</style>
