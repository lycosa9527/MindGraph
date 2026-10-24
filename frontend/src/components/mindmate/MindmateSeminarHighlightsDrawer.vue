<script setup lang="ts">
/**
 * Group highlights, modeled on QQ group essence:
 * whole messages or selected excerpts, with jump-back and host removal.
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import { MapPin, Trash2, X } from '@lucide/vue'

import MindmateSeminarShareDialog, {
  type SeminarShareLine,
} from '@/components/mindmate/MindmateSeminarShareDialog.vue'
import { useLanguage } from '@/composables'
import {
  type SeminarHighlight,
  locateSeminarMessage,
  pushSeminarHighlightNotice,
  removeSeminarHighlight,
  seminarHighlights,
} from '@/composables/mindmate/mindmateSeminarChrome'
import { beijingWallClock, parseApiInstant } from '@/utils/beijingClock'
import type { SeminarBriefRole } from '@/utils/mindmateSeminarBrief'
import type { SeminarGroupMember } from '@/utils/mindmateSeminarGroup'
import { seminarAvatarSurname, seminarAvatarTone } from '@/utils/seminarAvatarSurname'

const props = withDefaults(
  defineProps<{
    sessionId: string
    embedded?: boolean
    members?: SeminarGroupMember[]
    isLeader?: boolean
    selfUserId?: number
  }>(),
  {
    embedded: false,
    members: () => [],
    isLeader: false,
    selfUserId: 0,
  }
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useLanguage()
const filter = ref<'all' | 'mine'>('all')
const overflow = ref<Record<string, boolean>>({})
const preview = ref<SeminarHighlight | null>(null)
const picking = ref(false)
const pickedIds = ref<string[]>([])

const mineCount = computed(
  () => seminarHighlights.value.filter((item) => item.createdByUserId === props.selfUserId).length
)

const visible = computed(() => {
  if (filter.value === 'mine') {
    return seminarHighlights.value.filter((item) => item.createdByUserId === props.selfUserId)
  }
  return seminarHighlights.value
})

function canRemove(item: SeminarHighlight): boolean {
  if (props.isLeader) {
    return true
  }
  return props.selfUserId > 0 && item.createdByUserId === props.selfUserId
}

function remove(item: SeminarHighlight): void {
  if (!canRemove(item)) {
    return
  }
  const self = props.members.find((member) => member.userId === props.selfUserId)
  removeSeminarHighlight(props.sessionId, item.id)
  if (preview.value?.id === item.id) {
    preview.value = null
  }
  pushSeminarHighlightNotice(props.sessionId, {
    kind: 'cancel',
    ownMessage: Boolean(self && self.name.trim() === item.authorName.trim()),
    authorName: item.authorName,
  })
}

function locate(messageId: number | null): void {
  if (messageId == null || messageId <= 0) {
    return
  }
  locateSeminarMessage(messageId)
}

function formatWhen(iso: string): string {
  const date = parseApiInstant(iso)
  if (!date) {
    return ''
  }
  const wall = beijingWallClock(date)
  return `${Number(wall.month)}/${Number(wall.day)} ${wall.hour}:${wall.minute}`
}

function roleForAuthor(name: string): SeminarBriefRole | null {
  const hit = props.members.find((member) => member.name.trim() === name.trim())
  if (!hit) {
    return null
  }
  if (hit.isLeader) {
    return 'leader'
  }
  return hit.role === 'none' ? null : hit.role
}

function roleLabel(name: string): string {
  const role = roleForAuthor(name)
  if (!role) {
    return ''
  }
  return t(`mindmate.home.brief.role.${role}`)
}

function bindText(id: string, el: unknown): void {
  if (!(el instanceof HTMLElement)) {
    return
  }
  const style = getComputedStyle(el)
  const line = Number.parseFloat(style.lineHeight) || 20
  const probe = document.createElement('div')
  probe.textContent = el.textContent
  probe.style.position = 'absolute'
  probe.style.visibility = 'hidden'
  probe.style.pointerEvents = 'none'
  probe.style.boxSizing = 'border-box'
  probe.style.width = `${el.clientWidth}px`
  probe.style.font = style.font
  probe.style.lineHeight = style.lineHeight
  probe.style.whiteSpace = 'pre-wrap'
  probe.style.overflowWrap = 'anywhere'
  document.body.appendChild(probe)
  const clipped = probe.offsetHeight > line * 4 + 1
  probe.remove()
  if (overflow.value[id] === clipped) {
    return
  }
  overflow.value = { ...overflow.value, [id]: clipped }
}

function openPreview(item: SeminarHighlight): void {
  if (!overflow.value[item.id]) {
    return
  }
  preview.value = item
}

function closePreview(): void {
  preview.value = null
}

const shareOpen = ref(false)
const shareLines = ref<SeminarShareLine[]>([])

function linesFromHighlights(items: SeminarHighlight[]): SeminarShareLine[] {
  return items.map((item) => ({
    key: item.id,
    role: 'user',
    authorName: item.authorName,
    content: item.text,
    createdAt: item.messageAt || item.createdAt,
    highlighted: true,
  }))
}

function shareHighlights(items: SeminarHighlight[]): void {
  if (items.length === 0) {
    return
  }
  shareLines.value = linesFromHighlights(items)
  shareOpen.value = true
}

function onExportCommand(command: string): void {
  if (command === 'all') {
    shareHighlights(seminarHighlights.value)
    return
  }
  picking.value = true
  pickedIds.value = []
}

function togglePicked(id: string): void {
  if (pickedIds.value.includes(id)) {
    pickedIds.value = pickedIds.value.filter((item) => item !== id)
    return
  }
  pickedIds.value = [...pickedIds.value, id]
}

function exportPicked(): void {
  const chosen = seminarHighlights.value.filter((item) => pickedIds.value.includes(item.id))
  shareHighlights(chosen)
  picking.value = false
  pickedIds.value = []
}

function cancelPick(): void {
  picking.value = false
  pickedIds.value = []
}

function onPreviewKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    closePreview()
  }
}

watch(preview, (item) => {
  if (item) {
    window.addEventListener('keydown', onPreviewKey)
    return
  }
  window.removeEventListener('keydown', onPreviewKey)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onPreviewKey)
})
</script>

<template>
  <aside
    class="mm-highlight-side"
    :class="{ 'is-embedded': embedded }"
    :aria-label="t('mindmate.highlights.title')"
  >
    <header
      v-if="!embedded"
      class="mm-highlight-side__header"
    >
      <h2 class="mm-highlight-side__title">
        <I18nText k="mindmate.highlights.title" />
      </h2>
      <button
        type="button"
        class="mm-highlight-side__close"
        :aria-label="t('common.close')"
        @click="emit('close')"
      >
        <X
          :size="16"
          aria-hidden="true"
        />
      </button>
    </header>

    <p class="mm-highlight-side__hint">
      <I18nText k="mindmate.highlights.hint" />
    </p>

    <div
      class="mm-highlight-side__filters"
      role="tablist"
    >
      <button
        type="button"
        role="tab"
        class="mm-highlight-side__filter"
        :class="{ 'is-on': filter === 'all' }"
        :aria-selected="filter === 'all'"
        @click="filter = 'all'"
      >
        <I18nText
          k="mindmate.highlights.filterAll"
          :params="{ n: seminarHighlights.length }"
        />
      </button>
      <button
        type="button"
        role="tab"
        class="mm-highlight-side__filter"
        :class="{ 'is-on': filter === 'mine' }"
        :aria-selected="filter === 'mine'"
        @click="filter = 'mine'"
      >
        <I18nText
          k="mindmate.highlights.filterMine"
          :params="{ n: mineCount }"
        />
      </button>
      <ElDropdown
        v-if="!picking"
        trigger="click"
        class="mm-highlight-side__export"
        @command="onExportCommand"
      >
        <button
          type="button"
          class="mm-highlight-side__export-btn"
        >
          <I18nText k="mindmate.highlights.export" />
        </button>
        <template #dropdown>
          <ElDropdownMenu>
            <ElDropdownItem command="all">
              <I18nText k="mindmate.highlights.exportAll" />
            </ElDropdownItem>
            <ElDropdownItem command="pick">
              <I18nText k="mindmate.highlights.exportPick" />
            </ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
      <div
        v-else
        class="mm-highlight-side__export"
      >
        <button
          type="button"
          class="mm-highlight-side__export-btn"
          :disabled="pickedIds.length === 0"
          @click="exportPicked"
        >
          <I18nText
            k="mindmate.highlights.exportSelected"
            :params="{ n: pickedIds.length }"
          />
        </button>
        <button
          type="button"
          class="mm-highlight-side__export-btn"
          @click="cancelPick"
        >
          <I18nText k="common.cancel" />
        </button>
      </div>
    </div>

    <p
      v-if="visible.length === 0"
      class="mm-highlight-side__empty"
    >
      <I18nText k="mindmate.highlights.empty" />
    </p>
    <ul
      v-else
      class="mm-highlight-side__list"
    >
      <li
        v-for="item in visible"
        :key="item.id"
        class="mm-highlight-card"
      >
        <header class="mm-highlight-card__top">
          <button
            v-if="picking"
            type="button"
            class="mm-highlight-card__check"
            :class="{ 'is-on': pickedIds.includes(item.id) }"
            :aria-pressed="pickedIds.includes(item.id)"
            @click="togglePicked(item.id)"
          />
          <span
            class="mm-highlight-card__avatar"
            :style="{
              background: seminarAvatarTone(item.authorName).background,
              color: seminarAvatarTone(item.authorName).color,
            }"
            aria-hidden="true"
          >
            {{ seminarAvatarSurname(item.authorName) }}
          </span>
          <span class="mm-highlight-card__name">{{ item.authorName }}</span>
          <span
            v-if="roleLabel(item.authorName)"
            class="mm-highlight-card__role"
          >
            {{ roleLabel(item.authorName) }}
          </span>
          <time
            v-if="formatWhen(item.messageAt || item.createdAt)"
            class="mm-highlight-card__time"
            :datetime="item.messageAt || item.createdAt"
          >
            {{ formatWhen(item.messageAt || item.createdAt) }}
          </time>
        </header>
        <p
          :ref="(el) => bindText(item.id, el)"
          class="mm-highlight-card__text"
          :class="{ 'is-openable': overflow[item.id] }"
          @click="openPreview(item)"
        >
          {{ item.text }}
        </p>
        <button
          v-if="overflow[item.id]"
          type="button"
          class="mm-highlight-card__expand"
          @click="preview = item"
        >
          <I18nText k="mindmate.highlights.expand" />
        </button>
        <footer class="mm-highlight-card__foot">
          <span
            v-if="item.createdByName"
            class="mm-highlight-card__from"
          >
            <I18nText
              k="mindmate.highlights.createdBy"
              :params="{ name: item.createdByName }"
            />
          </span>
          <span class="mm-highlight-card__actions">
            <button
              v-if="item.messageId"
              type="button"
              class="mm-highlight-card__locate"
              :aria-label="t('mindmate.highlights.locate')"
              :title="t('mindmate.highlights.locate')"
              @click="locate(item.messageId)"
            >
              <MapPin
                :size="14"
                aria-hidden="true"
              />
            </button>
            <button
              v-if="canRemove(item)"
              type="button"
              class="mm-highlight-card__remove"
              :aria-label="t('mindmate.highlights.remove')"
              :title="t('mindmate.highlights.remove')"
              @click="remove(item)"
            >
              <Trash2
                :size="14"
                aria-hidden="true"
              />
            </button>
          </span>
        </footer>
      </li>
    </ul>

    <Teleport to="body">
      <div
        v-if="preview"
        class="mm-highlight-zoom"
        @click.self="closePreview"
      >
        <article
          class="mm-highlight-zoom__card"
          role="dialog"
          aria-modal="true"
          :aria-label="t('mindmate.highlights.title')"
        >
          <header class="mm-highlight-zoom__top">
            <span
              class="mm-highlight-card__avatar"
              :style="{
                background: seminarAvatarTone(preview.authorName).background,
                color: seminarAvatarTone(preview.authorName).color,
              }"
              aria-hidden="true"
            >
              {{ seminarAvatarSurname(preview.authorName) }}
            </span>
            <span class="mm-highlight-zoom__name">{{ preview.authorName }}</span>
            <span
              v-if="roleLabel(preview.authorName)"
              class="mm-highlight-card__role"
            >
              {{ roleLabel(preview.authorName) }}
            </span>
            <time
              v-if="formatWhen(preview.messageAt || preview.createdAt)"
              class="mm-highlight-card__time"
              :datetime="preview.messageAt || preview.createdAt"
            >
              {{ formatWhen(preview.messageAt || preview.createdAt) }}
            </time>
            <button
              type="button"
              class="mm-highlight-zoom__close"
              :aria-label="t('common.close')"
              @click="closePreview"
            >
              <X
                :size="16"
                aria-hidden="true"
              />
            </button>
          </header>
          <p class="mm-highlight-zoom__text">{{ preview.text }}</p>
          <footer class="mm-highlight-card__foot">
            <span
              v-if="preview.createdByName"
              class="mm-highlight-card__from"
            >
              <I18nText
                k="mindmate.highlights.createdBy"
                :params="{ name: preview.createdByName }"
              />
            </span>
            <span class="mm-highlight-card__actions">
              <button
                v-if="preview.messageId"
                type="button"
                class="mm-highlight-card__locate"
                :aria-label="t('mindmate.highlights.locate')"
                :title="t('mindmate.highlights.locate')"
                @click="locate(preview.messageId)"
              >
                <MapPin
                  :size="14"
                  aria-hidden="true"
                />
              </button>
              <button
                v-if="canRemove(preview)"
                type="button"
                class="mm-highlight-card__remove"
                :aria-label="t('mindmate.highlights.remove')"
                :title="t('mindmate.highlights.remove')"
                @click="remove(preview)"
              >
                <Trash2
                  :size="14"
                  aria-hidden="true"
                />
              </button>
            </span>
          </footer>
        </article>
      </div>
    </Teleport>
    <MindmateSeminarShareDialog
      :open="shareOpen"
      :title="t('mindmate.highlights.title')"
      :lines="shareLines"
      :member-count="members.length"
      @close="shareOpen = false"
    />
  </aside>
</template>

<style scoped>
.mm-highlight-side {
  display: flex;
  flex-direction: column;
  width: 300px;
  max-width: 38vw;
  min-width: 0;
  min-height: 0;
  height: 100%;
  border-left: 1px solid #ececf1;
  background: #f7f7f8;
  overflow: hidden;
  color: #18191c;
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.mm-highlight-side.is-embedded {
  width: 100%;
  max-width: none;
  height: auto;
  flex: 1 1 auto;
  border-left: none;
}

.mm-highlight-side__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 16px 16px 0;
  background: #fff;
}

.mm-highlight-side__title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #18191c;
}

.mm-highlight-side__close {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 999px;
  background: #f4f4f5;
  color: #6b6b76;
  cursor: pointer;
}

.mm-highlight-side__hint {
  margin: 0;
  padding: 8px 14px 0;
  font-size: 11px;
  line-height: 1.45;
  color: #9c9aa8;
  white-space: pre-line;
}

.mm-highlight-side__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 8px 14px 0;
}

.mm-highlight-side__export {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}

.mm-highlight-side__export-btn {
  border: 1px solid #e6e6ec;
  border-radius: 999px;
  padding: 2px 9px;
  background: #fff;
  color: #5046e5;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
  cursor: pointer;
}

.mm-highlight-side__export-btn:disabled {
  opacity: 0.45;
  cursor: default;
}

.mm-highlight-card__check {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  border: 1.5px solid #d6d3d1;
  border-radius: 999px;
  background: #fff;
  cursor: pointer;
}

.mm-highlight-card__check.is-on {
  border-color: #5046e5;
  background: #5046e5;
  box-shadow: inset 0 0 0 3px #fff;
}

.mm-highlight-side__filter {
  border: 1px solid #e6e6ec;
  border-radius: 999px;
  padding: 2px 9px;
  background: #fff;
  color: #6b6b76;
  font: inherit;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
  cursor: pointer;
}

.mm-highlight-side__filter.is-on {
  border-color: #5046e5;
  background: #5046e5;
  color: #fff;
}

.mm-highlight-side__empty {
  margin: 0;
  padding: 10px 14px 0;
  font-size: 12px;
  line-height: 1.4;
  color: #9c9aa8;
}

.mm-highlight-side__list {
  list-style: none;
  margin: 0;
  padding: 12px 12px 8px;
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  overflow: auto;
}

.mm-highlight-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 10px 8px;
  border: 1px solid #ececf1;
  border-radius: 14px;
  background: #fff;
  box-shadow:
    0 1px 2px rgba(24, 25, 28, 0.04),
    0 4px 12px rgba(24, 25, 28, 0.04);
}

.mm-highlight-card__top {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.mm-highlight-card__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
}

.mm-highlight-card__name {
  min-width: 0;
  overflow: hidden;
  color: #18191c;
  font-size: 13px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-highlight-card__role {
  flex: 0 0 auto;
  padding: 0 6px;
  border-radius: 999px;
  background: #efeafe;
  color: #7c6fe8;
  font-size: 11px;
  font-weight: 600;
}

.mm-highlight-card__time {
  margin-left: auto;
  flex: 0 0 auto;
  color: #9c9aa8;
  font-size: 11px;
}

.mm-highlight-card__text {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: #18191c;
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 4;
}

.mm-highlight-card__text.is-openable {
  cursor: pointer;
}

.mm-highlight-card__expand {
  align-self: flex-start;
  padding: 0;
  border: none;
  background: none;
  color: #5046e5;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.mm-highlight-zoom {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(24, 25, 28, 0.36);
}

.mm-highlight-zoom__card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: min(520px, 100%);
  max-height: min(72vh, 640px);
  padding: 18px 18px 14px;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 16px 48px rgba(24, 25, 28, 0.18);
}

.mm-highlight-zoom__top {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.mm-highlight-zoom__name {
  min-width: 0;
  overflow: hidden;
  color: #18191c;
  font-size: 15px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-highlight-zoom__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  margin-left: 4px;
  border: none;
  border-radius: 999px;
  background: #f4f4f6;
  color: #6b6b76;
  cursor: pointer;
}

.mm-highlight-zoom__text {
  margin: 0;
  overflow: auto;
  color: #18191c;
  font-size: 16px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.mm-highlight-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  flex-wrap: nowrap;
  min-width: 0;
}

.mm-highlight-card__from {
  min-width: 0;
  overflow: hidden;
  color: #9c9aa8;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-highlight-card__actions {
  display: inline-flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 4px;
  margin-left: auto;
}

.mm-highlight-card__locate,
.mm-highlight-card__remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  border-radius: 999px;
  cursor: pointer;
}

.mm-highlight-card__locate {
  background: #f4f4f6;
  color: #6b6b76;
}

.mm-highlight-card__locate:hover {
  background: #ececf1;
}

.mm-highlight-card__remove {
  background: #fdecef;
  color: #d6455d;
}

.mm-highlight-card__remove:hover {
  background: #f8dbe1;
}
</style>
