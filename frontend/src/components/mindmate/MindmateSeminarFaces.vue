<script setup lang="ts">
/**
 * Overlapping avatar circles for people currently in the seminar.
 */
import { computed, ref } from 'vue'

import { ElTooltip } from 'element-plus'

import MindmateMentionMenu from '@/components/mindmate/MindmateMentionMenu.vue'
import { useLanguage } from '@/composables'
import {
  requestSeminarMention,
  seminarSpectator,
} from '@/composables/mindmate/mindmateSeminarChrome'
import { useMindmateSeminarFaces } from '@/composables/mindmate/useMindmateSeminarFaces'
import { lockRingColorForUser } from '@/shared/collabPalette'
import { useAuthStore } from '@/stores/auth'
import {
  type SeminarFace,
  orderSeminarFaces,
  splitSeminarFaces,
} from '@/utils/mindmateSeminarFaces'
import { seminarAvatarSurname, seminarAvatarTone } from '@/utils/seminarAvatarSurname'

const { t } = useLanguage()
const authStore = useAuthStore()
const { faces } = useMindmateSeminarFaces()

const selfId = computed(() => Number(authStore.user?.id) || 0)

/** Roster pin only keeps online members; leave events remove faces. */
const ordered = computed(() => orderSeminarFaces(faces.value, selfId.value))

const split = computed(() => splitSeminarFaces(ordered.value))

const overflowLabel = computed(() => split.value.overflow.map((face) => face.name).join(', '))

const mentionMenu = ref<{ x: number; y: number; name: string } | null>(null)

function canMentionFace(face: SeminarFace): boolean {
  if (!face.name.trim() || seminarSpectator.value) {
    return false
  }
  return selfId.value <= 0 || face.userId !== selfId.value
}

function onFaceMenu(event: MouseEvent, face: SeminarFace): void {
  if (!canMentionFace(face)) {
    return
  }
  event.preventDefault()
  event.stopPropagation()
  mentionMenu.value = {
    x: event.clientX,
    y: event.clientY,
    name: face.name.trim(),
  }
}

function chooseMention(): void {
  const name = mentionMenu.value?.name || ''
  mentionMenu.value = null
  if (name) {
    requestSeminarMention(name)
  }
}
</script>

<template>
  <div
    v-if="ordered.length > 0"
    class="seminar-faces"
    role="list"
    :aria-label="t('mindmate.collabSessionFaces')"
  >
    <span
      v-for="face in split.visible"
      :key="face.userId"
      class="seminar-faces__item"
      role="listitem"
    >
      <ElTooltip
        :content="face.name"
        placement="bottom"
        :show-after="300"
      >
        <span
          class="seminar-faces__avatar"
          :class="{ 'is-mentionable': canMentionFace(face) }"
          :style="{
            background: seminarAvatarTone(face.userId).background,
            color: seminarAvatarTone(face.userId).color,
            boxShadow: `0 0 0 2px ${
              face.userId === selfId ? '#8b7cf7' : lockRingColorForUser(face.userId)
            }`,
          }"
          @contextmenu="onFaceMenu($event, face)"
        >
          {{ seminarAvatarSurname(face.name) }}
        </span>
      </ElTooltip>
    </span>
    <span
      v-if="split.overflow.length > 0"
      class="seminar-faces__item"
      role="listitem"
    >
      <ElTooltip
        :content="overflowLabel"
        placement="bottom"
        :show-after="300"
      >
        <span class="seminar-faces__avatar seminar-faces__avatar--more">
          +{{ split.overflow.length }}
        </span>
      </ElTooltip>
    </span>
  </div>
  <MindmateMentionMenu
    v-if="mentionMenu"
    :x="mentionMenu.x"
    :y="mentionMenu.y"
    :name="mentionMenu.name"
    @choose="chooseMention"
    @close="mentionMenu = null"
  />
</template>

<style scoped>
.seminar-faces {
  display: flex;
  align-items: center;
  margin-right: 4px;
}

.seminar-faces__item {
  display: inline-flex;
  margin-left: -10px;
}

.seminar-faces__item:first-child {
  margin-left: 0;
}

.seminar-faces__avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 2px solid #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 650;
  line-height: 1;
  cursor: default;
  user-select: none;
}

.seminar-faces__avatar.is-mentionable {
  cursor: context-menu;
}

:global(.dark) .seminar-faces__avatar {
  border-color: #1f2937;
}

.seminar-faces__item:hover {
  position: relative;
  z-index: 1;
}

.seminar-faces__avatar--more {
  border-color: #e7e5e4;
  background: #f5f5f4;
  color: #57534e;
  font-size: 11px;
  font-weight: 600;
}

:global(.dark) .seminar-faces__avatar--more {
  border-color: #4b5563;
  background: #374151;
  color: #e7e5e4;
}
</style>
