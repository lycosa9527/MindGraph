<script setup lang="ts">
/**
 * Overlapping avatar circles for people currently in the seminar.
 */
import { computed } from 'vue'

import { ElTooltip } from 'element-plus'

import { useLanguage } from '@/composables'
import { useMindmateSeminarFaces } from '@/composables/mindmate/useMindmateSeminarFaces'
import { lockRingColorForUser } from '@/shared/collabPalette'
import { useAuthStore } from '@/stores/auth'
import { orderSeminarFaces, splitSeminarFaces } from '@/utils/mindmateSeminarFaces'
import { resolveUserAvatarEmoji } from '@/utils/userAvatarEmoji'

const { t } = useLanguage()
const authStore = useAuthStore()
const { faces } = useMindmateSeminarFaces()

const selfId = computed(() => Number(authStore.user?.id) || 0)

const ordered = computed(() => orderSeminarFaces(faces.value, selfId.value))

const split = computed(() => splitSeminarFaces(ordered.value))

const overflowLabel = computed(() => split.value.overflow.map((face) => face.name).join(', '))
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
          class="seminar-faces__avatar mg-user-avatar-emoji"
          :style="{ boxShadow: `0 0 0 2px ${lockRingColorForUser(face.userId)}` }"
        >
          {{ resolveUserAvatarEmoji(face.avatar) }}
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
</template>

<style scoped>
.seminar-faces {
  display: flex;
  align-items: center;
  margin-right: 4px;
}

.seminar-faces__item {
  display: inline-flex;
  margin-left: -8px;
}

.seminar-faces__item:first-child {
  margin-left: 0;
}

.seminar-faces__avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid #fff;
  background: #fafaf9;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  line-height: 1;
  cursor: default;
  user-select: none;
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
