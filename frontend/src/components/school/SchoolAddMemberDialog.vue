<script setup lang="ts">
/**
 * School dashboard — add member dialog (light Swiss stone, Excel paste batch import).
 */
import { computed, nextTick, ref, watch } from 'vue'

import { Close, DocumentCopy } from '@element-plus/icons-vue'
import { Loader2 } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import {
  useCreateAdminSchoolUser,
  useCreateAdminSchoolUsersBatch,
} from '@/composables/queries'
import { useAdminOrgScope } from '@/composables/admin/useAdminOrgScope'
import { useAuthStore } from '@/stores'
import { httpErrorDetail } from '@/utils/httpErrorDetail'
import {
  dedupeMemberRows,
  isValidMemberName,
  isValidMemberPhone,
  normalizeMemberPhone,
  parseExcelMemberPaste,
} from '@/utils/parseBatchMemberPaste'

const visible = defineModel<boolean>('visible', { required: true })

const props = withDefaults(
  defineProps<{
    orgId: number
    schoolName?: string
  }>(),
  { schoolName: '' }
)

const emit = defineEmits<{
  created: []
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const { effectiveOrgName } = useAdminOrgScope()
const createSchoolUser = useCreateAdminSchoolUser()
const createSchoolUsersBatch = useCreateAdminSchoolUsersBatch()

const modalTitle = computed(() => {
  const school = (
    props.schoolName ||
    effectiveOrgName.value ||
    authStore.user?.schoolName ||
    ''
  ).trim()
  if (!school) {
    return t('admin.schoolAddMemberTitle')
  }
  return t('admin.schoolAddMemberModalTitle', { school })
})

const nameEdit = ref('')
const phoneEdit = ref('')
const batchPasteText = ref('')
const batchExpanded = ref(false)
const batchPasteFocused = ref(false)
const pasteTextareaRef = ref<HTMLTextAreaElement | null>(null)
const submitting = ref(false)

const canSubmitSingle = computed(
  () => isValidMemberPhone(phoneEdit.value.trim()) && isValidMemberName(nameEdit.value)
)

const batchParseResult = computed(() => parseExcelMemberPaste(batchPasteText.value))

const batchRows = computed(() => dedupeMemberRows(batchParseResult.value.rows))

const batchDuplicateCount = computed(() => {
  const parsedCount = batchParseResult.value.rows.length
  return parsedCount > batchRows.value.length ? parsedCount - batchRows.value.length : 0
})

const batchPreviewRows = computed(() => batchRows.value.slice(0, 8))

const batchPreviewCount = computed(() => batchRows.value.length)

const batchParseErrorKey = computed(() => batchParseResult.value.errorKey)

const batchSkippedInvalidCount = computed(() => batchParseResult.value.skippedInvalidCount ?? 0)

const canSubmitBatch = computed(
  () =>
    batchExpanded.value &&
    batchPreviewCount.value > 0 &&
    !batchParseErrorKey.value &&
    !submitting.value
)

const canSubmit = computed(() => {
  if (batchExpanded.value) {
    return canSubmitBatch.value
  }
  return canSubmitSingle.value
})

const submitLabel = computed(() =>
  batchExpanded.value && batchPreviewCount.value >= 1
    ? t('admin.schoolAddMemberSubmitBatch', { count: batchPreviewCount.value })
    : t('admin.schoolAddMemberSubmit')
)

function resetForm(): void {
  nameEdit.value = ''
  phoneEdit.value = ''
  batchPasteText.value = ''
  batchExpanded.value = false
  batchPasteFocused.value = false
}

function closeModal(): void {
  visible.value = false
}

function orgQueryString(): string {
  return new URLSearchParams({ organization_id: String(props.orgId) }).toString()
}

async function openBatchPaste(): Promise<void> {
  batchExpanded.value = true
  await nextTick()
  pasteTextareaRef.value?.focus()
}

function focusPasteArea(): void {
  pasteTextareaRef.value?.focus()
}

function onPasteFromClipboard(event: ClipboardEvent): void {
  const text = event.clipboardData?.getData('text/plain') ?? ''
  if (!text.trim()) {
    return
  }
  event.preventDefault()
  batchExpanded.value = true
  batchPasteText.value = text
}

async function submitSingle(): Promise<boolean> {
  try {
    await createSchoolUser.mutateAsync({
      organizationId: props.orgId,
      body: {
        name: nameEdit.value.trim(),
        phone: normalizeMemberPhone(phoneEdit.value),
        role: 'teacher',
      },
    })
    notify.success(t('admin.schoolAddMemberSuccess'))
    return true
  } catch (err) {
    const message = err instanceof Error ? err.message : t('admin.schoolAddMemberCreateError')
    notify.error(message)
    return false
  }
}

async function submitBatch(): Promise<boolean> {
  const parseError = batchParseErrorKey.value
  if (parseError) {
    notify.error(t(parseError, batchParseResult.value.errorParams ?? {}))
    return false
  }

  const members = batchRows.value.map((row) => ({
    phone: row.phone,
    name: row.name,
    role: 'teacher',
  }))

  try {
    const data = (await createSchoolUsersBatch.mutateAsync({
      organizationId: props.orgId,
      body: { members },
    })) as {
      message?: string
      created_count?: number
      failed_count?: number
    }
    const created = data.created_count ?? 0
    const failed = data.failed_count ?? 0
    if (failed > 0 && created > 0) {
      notify.warning(t('admin.schoolAddMemberBatchPartial', { created, failed }))
    } else if (failed > 0) {
      notify.error(data.message || t('admin.schoolAddMemberCreateError'))
      return false
    } else {
      notify.success(t('admin.schoolAddMemberBatchSuccess', { created }))
    }
    return true
  } catch (err) {
    const message = err instanceof Error ? err.message : t('admin.schoolAddMemberCreateError')
    notify.error(message)
    return false
  }
}

async function handleSubmit(): Promise<void> {
  if (submitting.value) {
    return
  }
  submitting.value = true
  try {
    let ok = false
    if (batchExpanded.value && batchPreviewCount.value > 0) {
      ok = await submitBatch()
    } else if (canSubmitSingle.value) {
      ok = await submitSingle()
    } else if (batchExpanded.value) {
      notify.error(t('admin.schoolAddMemberBatchEmpty'))
    } else {
      notify.error(t('admin.schoolAddMemberRequired'))
    }
    if (ok) {
      visible.value = false
      emit('created')
    }
  } finally {
    submitting.value = false
  }
}

watch(visible, (open) => {
  if (!open) {
    resetForm()
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="admin-school-modal">
      <div
        v-if="visible"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div
          class="absolute inset-0 bg-stone-900/60 backdrop-blur-[2px]"
          aria-hidden="true"
          @click="closeModal"
        />

        <div
          class="relative w-full max-w-lg max-h-[90vh] flex flex-col"
          role="dialog"
          aria-modal="true"
          :aria-label="modalTitle"
          @click.stop
        >
          <div class="bg-white rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div class="px-8 pt-8 pb-4 text-center border-b border-stone-100 relative shrink-0">
              <el-button
                :icon="Close"
                circle
                text
                class="admin-school-modal__close"
                :aria-label="t('common.cancel')"
                @click="closeModal"
              />
              <h2 class="text-lg font-semibold text-stone-900 tracking-tight px-6">
                {{ modalTitle }}
              </h2>
            </div>

            <form
              class="p-8 space-y-5 overflow-y-auto"
              @submit.prevent="handleSubmit"
            >
              <template v-if="!batchExpanded">
                <div>
                  <label
                    class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                    for="add-member-name"
                  >
                    {{ t('admin.schoolAddMemberName') }}
                    <span class="text-stone-400">*</span>
                  </label>
                  <input
                    id="add-member-name"
                    v-model="nameEdit"
                    type="text"
                    autocomplete="name"
                    :placeholder="t('admin.schoolAddMemberNamePlaceholder')"
                    class="school-add-member-input"
                  />
                </div>

                <div>
                  <label
                    class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                    for="add-member-phone"
                  >
                    {{ t('admin.schoolAddMemberPhone') }}
                    <span class="text-stone-400">*</span>
                  </label>
                  <input
                    id="add-member-phone"
                    v-model="phoneEdit"
                    type="tel"
                    inputmode="tel"
                    autocomplete="tel"
                    :placeholder="t('admin.schoolAddMemberPhonePlaceholder')"
                    class="school-add-member-input"
                  />
                </div>
              </template>

              <button
                type="button"
                class="school-add-member-batch-trigger"
                :class="{ 'school-add-member-batch-trigger--open': batchExpanded }"
                @click="batchExpanded ? (batchExpanded = false) : void openBatchPaste()"
              >
                <span class="school-add-member-batch-trigger__icon">
                  <el-icon><DocumentCopy /></el-icon>
                </span>
                <span class="min-w-0 text-left">
                  <span class="block text-sm font-medium text-stone-800">
                    {{ t('admin.schoolAddMemberBatchTitle') }}
                  </span>
                  <span class="block text-xs text-stone-500 leading-relaxed mt-1">
                    {{ t('admin.schoolAddMemberBatchHint') }}
                  </span>
                </span>
              </button>

              <div
                v-show="batchExpanded"
                class="school-add-member-paste-panel"
                :class="{ 'school-add-member-paste-panel--focused': batchPasteFocused }"
                @click="focusPasteArea"
                @paste="onPasteFromClipboard"
              >
                <textarea
                  ref="pasteTextareaRef"
                  v-model="batchPasteText"
                  class="school-add-member-paste-input"
                  rows="6"
                  :placeholder="t('admin.schoolAddMemberBatchPastePlaceholder')"
                  @focus="batchPasteFocused = true"
                  @blur="batchPasteFocused = false"
                  @click.stop
                  @paste="onPasteFromClipboard"
                />

                <p
                  v-if="batchParseErrorKey"
                  class="school-add-member-meta school-add-member-meta--error"
                >
                  {{ t(batchParseErrorKey, batchParseResult.errorParams ?? {}) }}
                </p>
          <p
            v-else-if="batchPreviewCount > 0"
            class="school-add-member-meta"
          >
            {{ t('admin.schoolAddMemberBatchPreview', { count: batchPreviewCount }) }}
            <template v-if="batchDuplicateCount > 0">
              {{ ' ' }}
              {{ t('admin.schoolAddMemberBatchDuplicatesRemoved', { count: batchDuplicateCount }) }}
            </template>
            <template v-if="batchSkippedInvalidCount > 0">
              {{ ' ' }}
              {{ t('admin.schoolAddMemberBatchSkippedRows', { count: batchSkippedInvalidCount }) }}
            </template>
          </p>
                <p
                  v-else
                  class="school-add-member-meta school-add-member-meta--hint"
                >
                  {{ t('admin.schoolAddMemberBatchPasteHint') }}
                </p>

                <div
                  v-if="batchPreviewCount > 0"
                  class="school-add-member-preview"
                >
                  <div class="school-add-member-preview__head">
                    <span>{{ t('admin.schoolAddMemberPhone') }}</span>
                    <span>{{ t('admin.schoolAddMemberName') }}</span>
                  </div>
                  <div
                    v-for="row in batchPreviewRows"
                    :key="`${row.line}-${row.phone}`"
                    class="school-add-member-preview__row"
                  >
                    <span>{{ row.phone }}</span>
                    <span>{{ row.name }}</span>
                  </div>
                  <p
                    v-if="batchPreviewCount > batchPreviewRows.length"
                    class="school-add-member-preview__more"
                  >
                    {{
                      t('admin.schoolAddMemberBatchPreviewMore', {
                        count: batchPreviewCount - batchPreviewRows.length,
                      })
                    }}
                  </p>
                </div>
              </div>

              <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end pt-1">
                <button
                  type="button"
                  class="school-add-member-btn school-add-member-btn--ghost"
                  @click="closeModal"
                >
                  {{ t('common.cancel') }}
                </button>
                <button
                  type="submit"
                  :disabled="submitting || !canSubmit"
                  class="school-add-member-btn school-add-member-btn--primary"
                >
                  <Loader2
                    v-if="submitting"
                    class="w-4 h-4 animate-spin"
                  />
                  {{ submitLabel }}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.admin-school-modal-enter-active,
.admin-school-modal-leave-active {
  transition: opacity 0.2s ease;
}

.admin-school-modal-enter-active .relative,
.admin-school-modal-leave-active .relative {
  transition: transform 0.2s ease;
}

.admin-school-modal-enter-from,
.admin-school-modal-leave-to {
  opacity: 0;
}

.admin-school-modal-enter-from .relative,
.admin-school-modal-leave-to .relative {
  transform: scale(0.97);
}

.admin-school-modal__close {
  position: absolute;
  top: 16px;
  inset-inline-end: 16px;
  --el-button-text-color: #a8a29e;
  --el-button-hover-text-color: #57534e;
  --el-button-hover-bg-color: #f5f5f4;
}

.school-add-member-input {
  width: 100%;
  padding: 0.75rem 1rem;
  border: 0;
  border-radius: 0.5rem;
  background: #fafaf9;
  color: #1c1917;
  font-size: 0.9375rem;
  transition:
    background-color 0.15s ease,
    box-shadow 0.15s ease;
}

.school-add-member-input::placeholder {
  color: #a8a29e;
}

.school-add-member-input:focus {
  outline: none;
  background: #fff;
  box-shadow: 0 0 0 2px #1c1917;
}

.school-add-member-batch-trigger {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  width: 100%;
  padding: 0.875rem 1rem;
  text-align: left;
  cursor: pointer;
  border: 1px dashed #d6d3d1;
  border-radius: 0.75rem;
  background: #fafaf9;
  transition:
    border-color 0.15s ease,
    background-color 0.15s ease;
}

.school-add-member-batch-trigger:hover,
.school-add-member-batch-trigger--open {
  border-color: #a8a29e;
  background: #f5f5f4;
}

.school-add-member-batch-trigger__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 9999px;
  background: #e7e5e4;
  color: #57534e;
  flex-shrink: 0;
}

.school-add-member-paste-panel {
  padding: 0.875rem;
  border: 1px solid #e7e5e4;
  border-radius: 0.75rem;
  background: #fff;
  cursor: text;
}

.school-add-member-paste-panel--focused {
  border-color: #a8a29e;
  box-shadow: 0 0 0 1px #d6d3d1;
}

.school-add-member-paste-input {
  display: block;
  width: 100%;
  min-height: 6.5rem;
  padding: 0.75rem 1rem;
  resize: vertical;
  border: 0;
  border-radius: 0.5rem;
  background: #fafaf9;
  color: #1c1917;
  font-size: 0.8125rem;
  line-height: 1.5;
}

.school-add-member-paste-input:focus {
  outline: none;
  background: #fff;
  box-shadow: 0 0 0 2px #1c1917;
}

.school-add-member-paste-input::placeholder {
  color: #a8a29e;
}

.school-add-member-meta {
  margin: 0.625rem 0 0;
  font-size: 0.75rem;
  color: #57534e;
}

.school-add-member-meta--error {
  color: #b91c1c;
}

.school-add-member-meta--hint {
  color: #78716c;
}

.school-add-member-preview {
  margin-top: 0.75rem;
  border: 1px solid #e7e5e4;
  border-radius: 0.5rem;
  overflow: hidden;
}

.school-add-member-preview__head,
.school-add-member-preview__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.75rem;
}

.school-add-member-preview__head {
  background: #fafaf9;
  color: #78716c;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.school-add-member-preview__row {
  border-top: 1px solid #f5f5f4;
  color: #44403c;
}

.school-add-member-preview__row span:first-child {
  font-variant-numeric: tabular-nums;
}

.school-add-member-preview__more {
  margin: 0;
  padding: 0.5rem 0.75rem;
  border-top: 1px solid #f5f5f4;
  font-size: 0.75rem;
  color: #78716c;
}

.school-add-member-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.625rem 1.25rem;
  border: 0;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    color 0.15s ease,
    opacity 0.15s ease;
}

@media (min-width: 640px) {
  .school-add-member-btn {
    width: auto;
  }
}

.school-add-member-btn--ghost {
  color: #57534e;
  background: #f5f5f4;
}

.school-add-member-btn--ghost:hover {
  background: #e7e5e4;
}

.school-add-member-btn--primary {
  color: #fff;
  background: #1c1917;
}

.school-add-member-btn--primary:hover:not(:disabled) {
  background: #292524;
}

.school-add-member-btn--primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
