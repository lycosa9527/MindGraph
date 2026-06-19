<script setup lang="ts">
/**
 * Combined Terms of Use & Privacy Policy — opened from /auth footer link.
 */
import { computed } from 'vue'

import { ElDialog, ElScrollbar } from 'element-plus'

import { useLanguage } from '@/composables'
import { softwareAgreementForUiCode } from '@/content/authSoftwareAgreement'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const { t, currentLanguage } = useLanguage()

const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const agreement = computed(() => softwareAgreementForUiCode(currentLanguage.value))
</script>

<template>
  <ElDialog
    v-model="isVisible"
    width="min(640px, 94vw)"
    append-to-body
    destroy-on-close
    class="software-agreement-dialog"
    modal-class="software-agreement-modal-backdrop"
    :show-close="true"
    align-center
  >
    <template #header>
      <div class="sa-header">
        <h2 class="sa-header__title">
          {{ agreement.title }}
        </h2>
        <p class="sa-header__updated">
          {{ t('auth.softwareAgreementUpdated', { date: agreement.updated }) }}
        </p>
      </div>
    </template>

    <ElScrollbar
      class="sa-scrollbar"
      max-height="70vh"
    >
      <div class="sa-body">
        <p class="sa-preamble">
          {{ agreement.preamble }}
        </p>

        <section
          v-for="(section, idx) in agreement.sections"
          :key="idx"
          class="sa-section"
        >
          <h3 class="sa-section__title">
            {{ section.title }}
          </h3>
          <p
            v-for="(paragraph, pIdx) in section.paragraphs"
            :key="pIdx"
            class="sa-section__paragraph"
          >
            {{ paragraph }}
          </p>
        </section>
      </div>
    </ElScrollbar>
  </ElDialog>
</template>

<style scoped>
.sa-header {
  padding-right: 1.5rem;
}

.sa-header__title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  line-height: 1.4;
  color: rgb(28 25 23);
  letter-spacing: 0.01em;
}

.sa-header__updated {
  margin: 0.35rem 0 0;
  font-size: 0.75rem;
  color: rgb(120 113 108);
}

.sa-body {
  padding: 0.25rem 0.5rem 0.75rem 0;
  color: rgb(41 37 36);
}

.sa-preamble {
  margin: 0 0 1.25rem;
  font-size: 0.875rem;
  line-height: 1.65;
  color: rgb(68 64 60);
}

.sa-section + .sa-section {
  margin-top: 1.1rem;
}

.sa-section__title {
  margin: 0 0 0.45rem;
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.45;
  color: rgb(28 25 23);
}

.sa-section__paragraph {
  margin: 0 0 0.5rem;
  font-size: 0.8125rem;
  line-height: 1.7;
  color: rgb(68 64 60);
}

.sa-section__paragraph:last-child {
  margin-bottom: 0;
}
</style>

<style>
.software-agreement-dialog.el-dialog {
  border-radius: 1rem;
  border: 1px solid rgb(231 229 228);
  box-shadow:
    0 20px 45px rgba(28, 25, 23, 0.12),
    0 4px 12px rgba(28, 25, 23, 0.06);
}

.software-agreement-dialog .el-dialog__header {
  margin-right: 0;
  padding: 1.25rem 1.25rem 0.5rem;
}

.software-agreement-dialog .el-dialog__body {
  padding: 0.5rem 1.25rem 1.25rem;
}

.software-agreement-modal-backdrop {
  backdrop-filter: blur(2px);
}
</style>
