<script setup lang="ts">
/**
 * ZhiHui conversation thread — user prompt + assistant image / doodle wait.
 */
import { nextTick, ref, watch } from 'vue'

import { ElScrollbar } from 'element-plus'

import { useLanguage } from '@/composables'

import ZhiHuiDoodleWait from './ZhiHuiDoodleWait.vue'

export type ZhihuiSessionTurn = {
  localId: string
  prompt: string
  status: 'waiting' | 'done' | 'error'
  imageUrl: string | null
  error: string | null
  historyId: string | null
  referencePreviews?: string[]
}

const props = defineProps<{
  turns: ZhihuiSessionTurn[]
}>()

const { t } = useLanguage()
const scrollbarRef = ref<InstanceType<typeof ElScrollbar> | null>(null)

async function scrollToBottom(): Promise<void> {
  await nextTick()
  const wrap = scrollbarRef.value?.$el?.querySelector('.el-scrollbar__wrap') as HTMLElement | null
  if (wrap) {
    wrap.scrollTop = wrap.scrollHeight
  }
}

watch(
  () => props.turns.map((row) => `${row.localId}:${row.status}:${row.imageUrl ?? ''}`).join('|'),
  () => {
    void scrollToBottom()
  },
  { flush: 'post' }
)
</script>

<template>
  <ElScrollbar
    ref="scrollbarRef"
    class="zhihui-messages"
  >
    <div class="zhihui-messages__inner">
      <div
        v-for="turn in turns"
        :key="turn.localId"
        class="zhihui-messages__turn"
      >
        <div class="zhihui-messages__row zhihui-messages__row--user">
          <div class="zhihui-messages__bubble zhihui-messages__bubble--user">
            <div
              v-if="turn.referencePreviews?.length"
              class="zhihui-messages__refs"
            >
              <img
                v-for="(src, refIndex) in turn.referencePreviews"
                :key="`${turn.localId}-ref-${refIndex}`"
                :src="src"
                alt=""
                class="zhihui-messages__ref-img"
              />
            </div>
            <p class="zhihui-messages__prompt">
              {{ turn.prompt }}
            </p>
          </div>
        </div>

        <div class="zhihui-messages__row zhihui-messages__row--assistant">
          <div
            v-if="turn.status === 'waiting'"
            class="zhihui-messages__bubble zhihui-messages__bubble--assistant"
          >
            <ZhiHuiDoodleWait :label="String(t('zhihui.doodleWaiting'))" />
          </div>

          <div
            v-else-if="turn.status === 'error'"
            class="zhihui-messages__bubble zhihui-messages__bubble--assistant zhihui-messages__bubble--error"
          >
            {{ turn.error || t('zhihui.generateFailed') }}
          </div>

          <div
            v-else-if="turn.imageUrl"
            class="zhihui-messages__result"
          >
            <a
              :href="turn.imageUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="zhihui-messages__image-link"
              :title="String(t('zhihui.openImage'))"
            >
              <img
                :src="turn.imageUrl"
                :alt="turn.prompt"
                class="zhihui-messages__image"
              />
            </a>
          </div>
        </div>
      </div>
    </div>
  </ElScrollbar>
</template>

<style scoped>
.zhihui-messages {
  flex: 1 1 0;
  min-height: 0;
  width: 100%;
}

.zhihui-messages__inner {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  width: 100%;
  max-width: 48rem;
  margin: 0 auto;
  padding: 1.25rem 1rem 1.5rem;
}

.zhihui-messages__turn {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.zhihui-messages__row {
  display: flex;
  width: 100%;
}

.zhihui-messages__row--user {
  justify-content: flex-end;
}

.zhihui-messages__row--assistant {
  justify-content: flex-start;
}

.zhihui-messages__bubble {
  max-width: min(100%, 36rem);
  padding: 0.75rem 1rem;
  border-radius: 1rem;
  font-size: 0.9375rem;
  line-height: 1.55;
  letter-spacing: 0.01em;
  word-break: break-word;
}

.zhihui-messages__bubble--user {
  border-bottom-right-radius: 0.35rem;
  background: #57534e;
  color: #fafaf9;
  font-weight: 500;
}

.zhihui-messages__prompt {
  margin: 0;
}

.zhihui-messages__refs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.55rem;
}

.zhihui-messages__ref-img {
  width: 3.25rem;
  height: 3.25rem;
  object-fit: cover;
  border-radius: 0.45rem;
  border: 1px solid rgb(255 255 255 / 0.25);
  background: rgb(28 25 23 / 0.25);
}

.zhihui-messages__bubble--assistant {
  border-bottom-left-radius: 0.35rem;
  border: 1px solid #e7e5e4;
  background: rgb(255 255 255 / 0.92);
  color: #44403c;
  box-shadow: 0 8px 24px -20px rgb(28 25 23 / 0.35);
}

.zhihui-messages__bubble--error {
  color: #b91c1c;
  border-color: #fecaca;
  background: #fef2f2;
}

.zhihui-messages__result {
  max-width: min(100%, 36rem);
  overflow: hidden;
  border: 1px solid #e7e5e4;
  border-radius: 1rem;
  background: rgb(255 255 255 / 0.92);
  box-shadow: 0 8px 24px -20px rgb(28 25 23 / 0.35);
}

.zhihui-messages__image-link {
  display: block;
  background: #f5f5f4;
}

.zhihui-messages__image {
  display: block;
  width: 100%;
  max-height: 28rem;
  object-fit: contain;
}
</style>
