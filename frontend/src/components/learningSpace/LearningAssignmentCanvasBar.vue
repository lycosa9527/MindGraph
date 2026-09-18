<script setup lang="ts">
/**
 * Lightweight homework chrome on the MindGraph canvas.
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ArrowLeft, FileText, Send } from '@lucide/vue'

import LearningSpaceRequirementsModal from '@/components/learningSpace/LearningSpaceRequirementsModal.vue'
import { swissGlassConfirm, useLanguage, useNotifications } from '@/composables'
import { useLearningAssignmentCanvasStore } from '@/stores/learningAssignmentCanvas'
import { submitStudentAssignment } from '@/utils/learningSpaceApi'
import '@/styles/learning-space.css'

const { t } = useLanguage()
const notify = useNotifications()
const router = useRouter()
const lsCanvas = useLearningAssignmentCanvasStore()

const showRequirements = ref(false)
const submitting = ref(false)

const title = computed(() => lsCanvas.assignment?.title || t('learningSpace.title'))
const submitted = computed(() => lsCanvas.assignment?.submission?.status === 'submitted')

async function onSubmit(): Promise<void> {
  const id = lsCanvas.assignmentId
  if (id == null || submitting.value) return
  try {
    await swissGlassConfirm(
      t('learningSpace.submitConfirm'),
      t('learningSpace.submit'),
      {
        confirmButtonText: t('learningSpace.submit'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
  } catch {
    return
  }
  submitting.value = true
  try {
    await submitStudentAssignment(id)
    notify.success(t('learningSpace.submitSuccess'))
    await router.push('/learning-space')
    if (router.currentRoute.value.path.startsWith('/learning-space')) {
      lsCanvas.clear()
    }
  } catch {
    notify.error(t('learningSpace.submitFailed'))
  } finally {
    submitting.value = false
  }
}

function onBack(): void {
  void router.push('/learning-space').finally(() => {
    if (!router.currentRoute.value.path.startsWith('/learning-space')) return
    lsCanvas.clear()
  })
}
</script>

<template>
  <div
    v-if="lsCanvas.isActive"
    class="ls-canvas-strip"
  >
    <button
      type="button"
      class="ls-canvas-strip__back"
      @click="onBack"
    >
      <ArrowLeft :size="14" />
      {{ t('learningSpace.backToLearningSpace') }}
    </button>
    <div class="ls-canvas-strip__title">{{ title }}</div>
    <div class="ls-canvas-strip__actions">
      <button
        type="button"
        class="ls-btn ls-btn--ghost ls-btn--sm"
        @click="showRequirements = true"
      >
        <FileText :size="14" />
        {{ t('learningSpace.viewRequirements') }}
      </button>
      <button
        type="button"
        class="ls-btn ls-btn--primary ls-btn--sm"
        :disabled="submitted || submitting"
        @click="onSubmit"
      >
        <Send :size="14" />
        {{ submitted ? t('learningSpace.statusSubmitted') : t('learningSpace.submit') }}
      </button>
    </div>
    <LearningSpaceRequirementsModal
      v-model="showRequirements"
      :assignment="lsCanvas.assignment"
      :class-name="t('learningSpace.class')"
      audience="student"
    />
  </div>
</template>

<style scoped>
.ls-canvas-strip {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.35rem 0.9rem 0.4rem;
  border-top: 1px solid #e8eaef;
  background: #fafbfc;
}

.ls-canvas-strip__back {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: #5b5ce2;
  font-size: 0.78rem;
  font-weight: 650;
  cursor: pointer;
  padding: 0.15rem 0;
}

.ls-canvas-strip__title {
  min-width: 0;
  flex: 1;
  font-size: 0.82rem;
  font-weight: 650;
  color: #374151;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ls-canvas-strip__actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 0.4rem;
}

.ls-canvas-strip__actions .ls-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

@media (max-width: 640px) {
  .ls-canvas-strip {
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  .ls-canvas-strip__title {
    flex-basis: 100%;
  }

  .ls-canvas-strip__actions {
    margin-left: auto;
  }
}
</style>
