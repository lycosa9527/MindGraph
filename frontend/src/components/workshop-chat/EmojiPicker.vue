<script setup lang="ts">
/**
 * EmojiPicker - Grid-based emoji picker popover with category tabs and search.
 */
import { computed, ref } from 'vue'

import { Search } from '@element-plus/icons-vue'

const emit = defineEmits<{
  select: [emojiName: string, emojiCode: string]
}>()

interface EmojiEntry {
  name: string
  code: string
}

interface EmojiCategory {
  key: string
  label: string
  emojis: EmojiEntry[]
}

const categories: EmojiCategory[] = [
  {
    key: 'smileys',
    label: '😊',
    emojis: [
      { name: 'grinning', code: '😀' },
      { name: 'smile', code: '😊' },
      { name: 'laughing', code: '😂' },
      { name: 'joy', code: '🤣' },
      { name: 'wink', code: '😉' },
      { name: 'blush', code: '😊' },
      { name: 'heart_eyes', code: '😍' },
      { name: 'star_struck', code: '🤩' },
      { name: 'thinking', code: '🤔' },
      { name: 'shushing', code: '🤫' },
      { name: 'zipper_mouth', code: '🤐' },
      { name: 'raised_eyebrow', code: '🤨' },
      { name: 'neutral', code: '😐' },
      { name: 'expressionless', code: '😑' },
      { name: 'rolling_eyes', code: '🙄' },
      { name: 'grimacing', code: '😬' },
      { name: 'relieved', code: '😌' },
      { name: 'pensive', code: '😔' },
      { name: 'sleepy', code: '😴' },
      { name: 'drooling', code: '🤤' },
      { name: 'mask', code: '😷' },
      { name: 'nerd', code: '🤓' },
      { name: 'sunglasses', code: '😎' },
      { name: 'clown', code: '🤡' },
    ],
  },
  {
    key: 'gestures',
    label: '👍',
    emojis: [
      { name: 'thumbs_up', code: '👍' },
      { name: 'thumbs_down', code: '👎' },
      { name: 'clap', code: '👏' },
      { name: 'raised_hands', code: '🙌' },
      { name: 'wave', code: '👋' },
      { name: 'ok_hand', code: '👌' },
      { name: 'point_up', code: '☝️' },
      { name: 'point_down', code: '👇' },
      { name: 'point_left', code: '👈' },
      { name: 'point_right', code: '👉' },
      { name: 'pray', code: '🙏' },
      { name: 'handshake', code: '🤝' },
      { name: 'muscle', code: '💪' },
      { name: 'crossed_fingers', code: '🤞' },
      { name: 'v', code: '✌️' },
      { name: 'love_you', code: '🤟' },
      { name: 'fist', code: '✊' },
      { name: 'fist_bump', code: '🤜' },
      { name: 'fire', code: '🔥' },
      { name: 'sparkles', code: '✨' },
    ],
  },
  {
    key: 'hearts',
    label: '❤️',
    emojis: [
      { name: 'heart', code: '❤️' },
      { name: 'orange_heart', code: '🧡' },
      { name: 'yellow_heart', code: '💛' },
      { name: 'green_heart', code: '💚' },
      { name: 'blue_heart', code: '💙' },
      { name: 'purple_heart', code: '💜' },
      { name: 'broken_heart', code: '💔' },
      { name: 'sparkling_heart', code: '💖' },
      { name: 'two_hearts', code: '💕' },
      { name: 'revolving_hearts', code: '💞' },
      { name: 'star', code: '⭐' },
      { name: 'glowing_star', code: '🌟' },
      { name: 'hundred', code: '💯' },
      { name: 'trophy', code: '🏆' },
      { name: 'medal', code: '🏅' },
      { name: 'crown', code: '👑' },
    ],
  },
  {
    key: 'objects',
    label: '📎',
    emojis: [
      { name: 'bulb', code: '💡' },
      { name: 'bookmark', code: '🔖' },
      { name: 'memo', code: '📝' },
      { name: 'pin', code: '📌' },
      { name: 'link', code: '🔗' },
      { name: 'paperclip', code: '📎' },
      { name: 'scissors', code: '✂️' },
      { name: 'package', code: '📦' },
      { name: 'bell', code: '🔔' },
      { name: 'megaphone', code: '📣' },
      { name: 'loudspeaker', code: '📢' },
      { name: 'magnifying', code: '🔍' },
      { name: 'key', code: '🔑' },
      { name: 'lock', code: '🔒' },
      { name: 'gear', code: '⚙️' },
      { name: 'hammer', code: '🔨' },
      { name: 'check', code: '✅' },
      { name: 'cross', code: '❌' },
      { name: 'warning', code: '⚠️' },
      { name: 'question', code: '❓' },
    ],
  },
]

const activeCategory = ref('smileys')
const searchQuery = ref('')

const filteredEmojis = computed(() => {
  const cat = categories.find((c) => c.key === activeCategory.value)
  if (!cat) return []
  if (!searchQuery.value) return cat.emojis
  const q = searchQuery.value.toLowerCase()
  return cat.emojis.filter((e) => e.name.includes(q) || e.code.includes(q))
})

function handleSelect(emoji: EmojiEntry): void {
  emit('select', emoji.name, emoji.code)
}
</script>

<template>
  <div class="emoji-picker">
    <!-- Category tabs -->
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

    <!-- Search -->
    <div class="emoji-picker__search-wrap">
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

    <!-- Emoji grid -->
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
