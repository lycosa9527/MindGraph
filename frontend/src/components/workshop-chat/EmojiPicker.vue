<script setup lang="ts">
/**
 * EmojiPicker - Grid-based emoji picker popover with category tabs.
 * Canvas insert hides search and leads with the objects tab.
 */
import { computed, ref } from 'vue'

import { Search } from '@element-plus/icons-vue'

import {
  EMOJI_PICKER_CATEGORIES,
  orderEmojiCategories,
  type EmojiEntry,
} from '@/config/emojiPickerCategories'

const props = withDefaults(
  defineProps<{
    hideSearch?: boolean
    leadCategory?: string
  }>(),
  {
    hideSearch: false,
    leadCategory: '',
  }
)

const emit = defineEmits<{
  select: [emojiName: string, emojiCode: string]
}>()

const categories = computed(() => orderEmojiCategories(EMOJI_PICKER_CATEGORIES, props.leadCategory))
const activeCategory = ref(props.leadCategory || EMOJI_PICKER_CATEGORIES[0]?.key || 'smileys')
const searchQuery = ref('')

const filteredEmojis = computed(() => {
  const cat = categories.value.find((c) => c.key === activeCategory.value)
  if (!cat) return []
  if (props.hideSearch || !searchQuery.value) return cat.emojis
  const q = searchQuery.value.toLowerCase()
  return cat.emojis.filter((e) => e.name.includes(q) || e.code.includes(q))
})

function handleSelect(emoji: EmojiEntry): void {
  emit('select', emoji.name, emoji.code)
}
</script>

<template>
  <div class="emoji-picker">
    <div class="emoji-picker__tabs">
      <button
        v-for="cat in categories"
        :key="cat.key"
        class="emoji-picker__tab"
        :class="{ 'emoji-picker__tab--active': activeCategory === cat.key }"
        @click="activeCategory = cat.key"
      >
        {{ cat.label }}
      </button>
    </div>

    <div
      v-if="!props.hideSearch"
      class="emoji-picker__search-wrap"
    >
      <el-icon
        class="emoji-picker__search-icon"
        :size="12"
      >
        <Search />
      </el-icon>
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜索..."
        class="emoji-picker__search"
      />
    </div>

    <div class="emoji-picker__grid-wrap">
      <div class="emoji-picker__grid">
        <button
          v-for="emoji in filteredEmojis"
          :key="emoji.name"
          class="emoji-picker__item"
          :title="emoji.name"
          @click="handleSelect(emoji)"
        >
          {{ emoji.code }}
        </button>
      </div>
      <div
        v-if="filteredEmojis.length === 0"
        class="emoji-picker__empty"
      >
        未找到表情
      </div>
    </div>
  </div>
</template>

<style scoped>
.emoji-picker {
  width: 260px;
  background: hsl(0deg 0% 100%);
  border: 1px solid hsl(0deg 0% 0% / 10%);
  border-radius: 8px;
  box-shadow: 0 4px 16px hsl(0deg 0% 0% / 12%);
  overflow: hidden;
}

.emoji-picker__tabs {
  display: flex;
  border-bottom: 1px solid hsl(0deg 0% 0% / 6%);
  padding: 4px 4px 0;
}

.emoji-picker__tab {
  flex: 1;
  padding: 6px 0;
  text-align: center;
  font-size: 16px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  border-radius: 4px 4px 0 0;
  cursor: pointer;
  transition: background 120ms ease;
}

.emoji-picker__tab:hover {
  background: hsl(0deg 0% 0% / 4%);
}

.emoji-picker__tab--active {
  border-bottom-color: hsl(228deg 56% 58%);
  background: hsl(228deg 56% 58% / 6%);
}

.emoji-picker__search-wrap {
  position: relative;
  padding: 6px 8px;
}

.emoji-picker__search-icon {
  position: absolute;
  left: 16px;
  top: 50%;
  transform: translateY(-50%);
  color: hsl(0deg 0% 48%);
  pointer-events: none;
}

.emoji-picker__search {
  width: 100%;
  padding: 5px 8px 5px 26px;
  font-size: 12px;
  border: 1px solid hsl(0deg 0% 84%);
  border-radius: 5px;
  outline: none;
  color: hsl(0deg 0% 15%);
  transition: border-color 150ms ease;
}

.emoji-picker__search:focus {
  border-color: hsl(228deg 40% 68%);
}

.emoji-picker__grid-wrap {
  padding: 4px 8px 8px;
  height: 164px;
  overflow-y: auto;
}

.emoji-picker__grid-wrap::-webkit-scrollbar {
  width: 4px;
}

.emoji-picker__grid-wrap::-webkit-scrollbar-thumb {
  background: hsl(0deg 0% 0% / 12%);
  border-radius: 2px;
}

.emoji-picker__grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 2px;
}

.emoji-picker__item {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  border-radius: 5px;
  border: none;
  background: none;
  cursor: pointer;
  transition:
    background 100ms ease,
    transform 100ms ease;
}

.emoji-picker__item:hover {
  background: hsl(228deg 20% 94%);
  transform: scale(1.15);
}

.emoji-picker__empty {
  text-align: center;
  font-size: 12px;
  color: hsl(0deg 0% 52%);
  padding: 16px 0;
}
</style>
