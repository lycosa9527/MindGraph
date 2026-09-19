<script setup lang="ts">
/**
 * Assignment submission roster modal — green submitted / red pending chips.
 */
import { computed } from 'vue'
import { X } from '@lucide/vue'

import { useLanguage } from '@/composables'
import type { LearningStudentRow } from '@/utils/learningSpaceApi'

const visible = defineModel<boolean>({ required: true })

const props = defineProps<{
  className: string
  students: LearningStudentRow[]
  submittedIds: number[]
}>()

const { t } = useLanguage()

const submittedSet = computed(() => new Set(props.submittedIds))

const rows = computed(() =>
  props.students.map((s) => ({
    ...s,
    submitted: submittedSet.value.has(s.id),
  }))
)

const submittedCount = computed(() => rows.value.filter((r) => r.submitted).length)
const pendingCount = computed(() => rows.value.length - submittedCount.value)

function avatarLabel(name: string): string {
  const trimmed = name.trim()
  if (!trimmed) return '?'
  return trimmed.length <= 2 ? trimmed : trimmed.slice(0, 2)
}

function onClose(): void {
  visible.value = false
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="ls-modal-overlay"
      @click.self="onClose"
    >
      <div
        class="ls-modal ls-modal--status"
        role="dialog"
        aria-modal="true"
        :aria-label="t('learningSpace.submissionStatus')"
      >
        <header class="ls-modal__head">
          <div class="ls-modal__head-text">
            <p class="ls-modal__eyebrow">{{ className }}</p>
            <h2 class="ls-modal__title">{{ t('learningSpace.submissionStatus') }}</h2>
          </div>
          <button
            type="button"
            class="ls-modal__close"
            :aria-label="t('common.close')"
            @click="onClose"
          >
            <X :size="18" />
          </button>
        </header>

        <div class="ls-modal__body">
          <div class="ls-status-card">
            <div class="ls-status-card__head">
              <h3>
                {{ t('learningSpace.unsubmittedZone', { n: pendingCount }) }}
              </h3>
            </div>
            <div class="ls-status-chips">
              <span
                v-for="s in rows.filter((r) => !r.submitted)"
                :key="`p-${s.id}`"
                class="ls-status-chip ls-status-chip--pending"
              >
                <span class="ls-status-chip__avatar ls-status-chip__avatar--pending">
                  {{ avatarLabel(s.name) }}
                </span>
                <span class="ls-status-chip__name">{{ s.name }}</span>
              </span>
              <span
                v-if="pendingCount > 0"
                class="ls-status-chips__more"
              >
                {{ t('learningSpace.statusTotalEtc', { n: pendingCount }) }}
              </span>
              <p
                v-else
                class="ls-muted"
              >
                {{ t('learningSpace.allSubmitted') }}
              </p>
            </div>
          </div>

          <div class="ls-status-card">
            <div class="ls-status-card__head">
              <h3>
                {{ t('learningSpace.submittedZone', { n: submittedCount }) }}
              </h3>
            </div>
            <div class="ls-status-chips">
              <span
                v-for="s in rows.filter((r) => r.submitted)"
                :key="`s-${s.id}`"
                class="ls-status-chip ls-status-chip--done"
              >
                <span class="ls-status-chip__avatar ls-status-chip__avatar--done">
                  {{ avatarLabel(s.name) }}
                </span>
                <span class="ls-status-chip__name">{{ s.name }}</span>
              </span>
              <p
                v-if="!submittedCount"
                class="ls-muted"
              >
                {{ t('learningSpace.noSubmissionsYet') }}
              </p>
            </div>
          </div>
        </div>

        <footer class="ls-modal__foot">
          <button
            type="button"
            class="ls-btn ls-btn--ghost"
            @click="onClose"
          >
            {{ t('common.close') }}
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
