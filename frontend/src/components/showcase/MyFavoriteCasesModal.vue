<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { Eye, Heart, Star } from '@lucide/vue'

import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import {
  type ShowcaseCaseType,
  caseTypeShortLabel,
  getCoverColor,
} from '@/components/showcase/showcaseShared'
import { useLanguage } from '@/composables'
import { type ShowcasePost, getShowcaseFavoritePosts } from '@/utils/apiClient'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'open', post: ShowcasePost): void
}>()

const { t } = useLanguage()

const open = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
})

const posts = ref<ShowcasePost[]>([])
const isLoading = ref(false)

function caseTypeText(caseType: ShowcaseCaseType): string {
  if (caseType === 'teaching_design') return String(t('showcase.type.teachingDesign'))
  if (caseType === 'diagram_case') return String(t('showcase.type.diagramCase'))
  return String(t('showcase.type.diagramTemplate'))
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('zh-CN')
  } catch {
    return iso
  }
}

async function loadPosts() {
  isLoading.value = true
  try {
    const res = await getShowcaseFavoritePosts({ page: 1, pageSize: 100 })
    posts.value = res.posts.filter((post) => post.is_favorited)
  } catch {
    posts.value = []
  } finally {
    isLoading.value = false
  }
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) void loadPosts()
  }
)

function close() {
  emit('update:visible', false)
}

function openPost(post: ShowcasePost) {
  emit('open', post)
  close()
}
</script>

<template>
  <SwissGlassCard
    v-model="open"
    :ribbon="t('swissGlass.hero.myFavorites.ribbon')"
    :title="t('swissGlass.hero.myFavorites.title')"
    :line1="t('swissGlass.hero.myFavorites.line1')"
    :icon="Star"
    card-class="swiss-glass-card--xl"
    @close="close"
  >
    <div class="max-h-[70vh] overflow-y-auto">
      <div
        v-if="isLoading"
        class="py-12 text-center text-sm text-gray-400"
      >
        …
      </div>
      <div
        v-else-if="posts.length === 0"
        class="py-12 text-center"
      >
        <Star class="mx-auto mb-3 h-12 w-12 text-gray-300" />
        <p class="text-sm text-gray-400">{{ t('showcase.myFavoritesEmpty') }}</p>
        <p class="mt-1 text-xs text-gray-300">{{ t('showcase.myFavoritesEmptyHint') }}</p>
      </div>
      <div
        v-else
        class="divide-y divide-gray-100"
      >
        <button
          v-for="post in posts"
          :key="post.id"
          type="button"
          class="my-favorites-row-btn"
          @click="openPost(post)"
        >
          <div
            :class="[
              'flex h-12 w-12 shrink-0 items-center justify-center rounded-lg text-xs font-bold text-white',
              `bg-gradient-to-br ${getCoverColor(post.id)}`,
            ]"
          >
            {{ caseTypeShortLabel(post.case_type) }}
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="truncate text-sm font-medium text-gray-900">{{ post.title }}</span>
              <Star class="h-3.5 w-3.5 shrink-0 fill-amber-400 text-amber-500" />
            </div>
            <div class="mt-0.5 flex flex-wrap items-center gap-3 text-xs text-gray-400">
              <span>{{ caseTypeText(post.case_type) }}</span>
              <span v-if="post.subject">{{ post.subject }}</span>
              <span>{{ formatDate(post.created_at) }}</span>
              <span class="inline-flex items-center gap-1">
                <Eye class="h-3 w-3" />
                {{ post.views_count }}
              </span>
              <span class="inline-flex items-center gap-1">
                <Heart class="h-3 w-3" />
                {{ post.likes_count }}
              </span>
            </div>
          </div>
        </button>
      </div>
    </div>
  </SwissGlassCard>
</template>

<style scoped>
.my-favorites-row-btn {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem;
  text-align: left;
  border: none;
  outline: none;
  background: transparent;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
  border-radius: 0.75rem;
  transition: background-color 0.15s ease;
}

.my-favorites-row-btn:hover {
  background: #f9fafb;
}

.my-favorites-row-btn:focus,
.my-favorites-row-btn:focus-visible {
  outline: none;
  box-shadow: none;
}
</style>
