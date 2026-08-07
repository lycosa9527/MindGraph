<script setup lang="ts">
/**
 * ZhiHui sidebar history — titled generation rows (AskOnce / MindGraph pattern).
 */
import { computed, onMounted, ref } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu, ElScrollbar } from 'element-plus'

import { Image as ImageIcon, MoreHorizontal, Trash2 } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import {
  type ZhihuiConversationItem,
  isZhihuiJobActive,
  useZhihuiHistoryStore,
  zhihuiConversationTitle,
} from '@/stores/zhihuiHistory'

defineProps<{
  isBlurred?: boolean
}>()

const { t } = useLanguage()
const notify = useNotifications()
const store = useZhihuiHistoryStore()

const showAll = ref(false)
const INITIAL_LIMIT = 10

type TimeGroupKey = 'today' | 'yesterday' | 'week' | 'month'

const items = computed(() => store.sortedItems)
const currentId = computed(() => store.currentId)

const visibleItems = computed(() =>
  showAll.value ? items.value : items.value.slice(0, INITIAL_LIMIT)
)

const grouped = computed(() => {
  const groups: Record<TimeGroupKey, ZhihuiConversationItem[]> = {
    today: [],
    yesterday: [],
    week: [],
    month: [],
  }
  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterdayStart = todayStart - 24 * 60 * 60 * 1000
  const weekStart = todayStart - 7 * 24 * 60 * 60 * 1000

  for (const item of visibleItems.value) {
    const ts = item.updated_at
      ? Date.parse(item.updated_at)
      : item.created_at
        ? Date.parse(item.created_at)
        : 0
    if (ts >= todayStart) groups.today.push(item)
    else if (ts >= yesterdayStart) groups.yesterday.push(item)
    else if (ts >= weekStart) groups.week.push(item)
    else groups.month.push(item)
  }
  return groups
})

const groupOrder: TimeGroupKey[] = ['today', 'yesterday', 'week', 'month']

const groupLabels = computed(() => ({
  today: t('common.date.today'),
  yesterday: t('common.date.yesterday'),
  week: t('common.date.pastWeek'),
  month: t('common.date.pastMonth'),
}))

const hasMore = computed(() => items.value.length > INITIAL_LIMIT && !showAll.value)
const remainingCount = computed(() => items.value.length - INITIAL_LIMIT)

function itemTitle(item: ZhihuiConversationItem): string {
  return zhihuiConversationTitle(item) || String(t('sidebar.history.untitled'))
}

function handleSelect(item: ZhihuiConversationItem): void {
  store.selectItem(item.id)
}

async function handleDelete(item: ZhihuiConversationItem): Promise<void> {
  const confirmed = window.confirm(String(t('sidebar.zhihuiHistory.deleteConfirm')))
  if (!confirmed) return
  const ok = await store.deleteItem(item.id)
  if (ok) {
    notify.success(String(t('zhihui.deleted')))
  } else {
    notify.error(String(t('zhihui.deleteFailed')))
  }
}

onMounted(() => {
  void store.fetchHistory()
})
</script>

<template>
  <div class="zhihui-history flex min-h-0 flex-1 flex-col border-t border-stone-200 relative overflow-hidden">
    <div class="px-4 py-3">
      <div class="text-xs font-medium tracking-wider text-stone-400 uppercase">
        {{ t('sidebar.zhihuiHistory.title') }}
      </div>
    </div>

    <ElScrollbar class="min-h-0 flex-1 px-4 pb-4">
      <div :class="isBlurred ? 'blur-sm pointer-events-none select-none' : ''">
        <div
          v-if="store.isLoading"
          class="py-8 text-center text-xs text-stone-400"
        >
          {{ t('common.loading') }}
        </div>
        <div
          v-else-if="store.loadError"
          class="py-8 text-center text-xs text-stone-400"
        >
          {{ t('zhihui.loadFailed') }}
        </div>
        <div
          v-else-if="items.length === 0"
          class="py-8 text-center"
        >
          <ImageIcon class="mx-auto mb-2 h-8 w-8 text-stone-300" />
          <p class="text-xs text-stone-400">
            {{ t('sidebar.zhihuiHistory.empty') }}
          </p>
        </div>
        <template v-else>
          <template
            v-for="key in groupOrder"
            :key="key"
          >
            <div
              v-if="grouped[key].length > 0"
              class="group-section"
            >
            <div class="group-label">{{ groupLabels[key] }}</div>
            <div
              v-for="item in grouped[key]"
              :key="item.id"
              class="history-item"
              :class="{ active: currentId === item.id }"
              @click="handleSelect(item)"
            >
              <span
                class="item-title"
                :title="itemTitle(item)"
              >
                <span
                  v-if="isZhihuiJobActive(item.status)"
                  class="status-dot"
                  :title="String(item.status)"
                />
                <span
                  v-else-if="item.status === 'failed' || item.status === 'partial'"
                  class="status-dot status-dot--warn"
                  :title="String(item.status)"
                />
                {{ itemTitle(item) }}
              </span>
              <ElDropdown
                trigger="click"
                class="more-dropdown"
                @click.stop
              >
                <button
                  type="button"
                  class="more-btn"
                  @click.stop
                >
                  <MoreHorizontal class="h-4 w-4" />
                </button>
                <template #dropdown>
                  <ElDropdownMenu>
                    <ElDropdownItem @click="handleDelete(item)">
                      <span class="delete-option">
                        <Trash2 class="mr-2 h-4 w-4" />
                        {{ t('sidebar.actions.delete') }}
                      </span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
            </div>
          </template>

          <button
            v-if="hasMore"
            type="button"
            class="show-more-btn"
            @click="showAll = true"
          >
            {{ t('sidebar.actions.showMore', { n: remainingCount }) }}
          </button>
          <button
            v-if="showAll && items.length > INITIAL_LIMIT"
            type="button"
            class="show-more-btn"
            @click="showAll = false"
          >
            {{ t('sidebar.actions.showLess') }}
          </button>
        </template>
      </div>
    </ElScrollbar>
  </div>
</template>

<style scoped>
.zhihui-history {
  min-height: 0;
  height: 100%;
}

.group-section {
  margin-bottom: 0.75rem;
}

.group-label {
  margin-bottom: 0.25rem;
  padding: 0 0.25rem;
  font-size: 0.6875rem;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: #a8a29e;
  text-transform: uppercase;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.45rem 0.5rem;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: background 0.12s ease;
}

.history-item:hover {
  background: #f5f5f4;
}

.history-item.active {
  background: #e7e5e4;
}

.item-title {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.8125rem;
  color: #44403c;
}

.status-dot {
  flex-shrink: 0;
  width: 0.4rem;
  height: 0.4rem;
  border-radius: 9999px;
  background: #d97706;
}

.status-dot--warn {
  background: #e11d48;
}

.more-dropdown {
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.12s ease;
}

.history-item:hover .more-dropdown,
.history-item.active .more-dropdown {
  opacity: 1;
}

.more-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.2rem;
  border: none;
  border-radius: 0.375rem;
  background: transparent;
  color: #78716c;
  cursor: pointer;
}

.more-btn:hover {
  background: #e7e5e4;
  color: #1c1917;
}

.delete-option {
  display: inline-flex;
  align-items: center;
  color: #dc2626;
}

.show-more-btn {
  display: block;
  width: 100%;
  margin-top: 0.25rem;
  padding: 0.4rem;
  border: none;
  border-radius: 0.5rem;
  background: transparent;
  font-size: 0.75rem;
  color: #78716c;
  cursor: pointer;
}

.show-more-btn:hover {
  background: #f5f5f4;
  color: #44403c;
}
</style>
