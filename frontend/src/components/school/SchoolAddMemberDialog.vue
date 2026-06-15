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
import type { SchoolMemberBatchFailureItem } from '@/types/api'
import { httpErrorDetail } from '@/utils/httpErrorDetail'
import {
  dedupeMemberRows,
  formatMemberContact,
  isValidMemberContact,
  isValidMemberEmail,
  isValidMemberName,
  looksLikeEmail,
  normalizeMemberEmail,
  normalizeMemberPhone,
  parseExcelMemberPaste,
  type ParsedMemberInvalidRow,
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

interface BatchImportResultView {
  createdCount: number
  failedCount: number
  failedItems: SchoolMemberBatchFailureItem[]
}

type BatchSubmitOutcome = 'success' | 'partial' | 'all_failed' | 'error'

interface BatchSubmitResult {
  outcome: BatchSubmitOutcome
  createdCount: number
}

const batchImportResult = ref<BatchImportResultView | null>(null)

const showingBatchResult = computed(() => batchImportResult.value !== null)

const modalTitle = computed(() => {
  if (showingBatchResult.value) {
    return t('admin.schoolAddMemberBatchResultTitle')
  }
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
const contactEdit = ref('')
const batchPasteText = ref('')
const batchExpanded = ref(false)
const batchPasteFocused = ref(false)
const pasteTextareaRef = ref<HTMLTextAreaElement | null>(null)
const submitting = ref(false)

const canSubmitSingle = computed(
  () => isValidMemberContact(contactEdit.value) && isValidMemberName(nameEdit.value)
)

const batchInvalidRows = computed(() => batchParseResult.value.invalidRows ?? [])

const batchInvalidPreviewRows = computed(() => batchInvalidRows.value.slice(0, 8))

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

const batchResultSummaryKey = computed(() => {
  const result = batchImportResult.value
  if (!result) {
    return null
  }
  if (result.failedCount === 0) {
    return 'admin.schoolAddMemberBatchResultSuccess'
  }
  if (result.createdCount > 0) {
    return 'admin.schoolAddMemberBatchResultPartial'
  }
  return 'admin.schoolAddMemberBatchResultAllFailed'
})

const batchResultSummaryTone = computed(() => {
  const result = batchImportResult.value
  if (!result) {
    return 'neutral'
  }
  if (result.failedCount === 0) {
    return 'success'
  }
  if (result.createdCount > 0) {
    return 'warning'
  }
  return 'error'
})

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
  contactEdit.value = ''
  batchPasteText.value = ''
  batchExpanded.value = false
  batchPasteFocused.value = false
  batchImportResult.value = null
}

function buildMemberBody(name: string, contact: string): Record<string, unknown> {
  const trimmedContact = contact.trim()
  if (isValidMemberEmail(trimmedContact)) {
    return {
      name: name.trim(),
      email: normalizeMemberEmail(trimmedContact),
      role: 'teacher',
    }
  }
  return {
    name: name.trim(),
    phone: normalizeMemberPhone(trimmedContact),
    role: 'teacher',
  }
}

function formatFailureContact(item: SchoolMemberBatchFailureItem): string {
  return item.email ?? item.phone ?? ''
}

function notifyInvalidContact(name: string, contact: string): void {
  const displayName = name.trim() || contact.trim()
  if (looksLikeEmail(contact)) {
    notify.error(t('admin.schoolAddMemberInvalidEmailForName', { name: displayName }))
    return
  }
  notify.error(t('admin.schoolAddMemberInvalidPhoneForName', { name: displayName }))
}

function notifyInvalidRow(row: ParsedMemberInvalidRow): void {
  notify.error(t(row.errorKey, row.errorParams ?? {}))
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
  const name = nameEdit.value.trim()
  const contact = contactEdit.value.trim()
  if (!isValidMemberName(name)) {
    notify.error(t('admin.schoolAddMemberInvalidNameForName', { name: name || '—' }))
    return false
  }
  if (!isValidMemberContact(contact)) {
    notifyInvalidContact(name, contact)
    return false
  }

  try {
    await createSchoolUser.mutateAsync({
      organizationId: props.orgId,
      body: buildMemberBody(name, contact),
    })
    notify.success(t('admin.schoolAddMemberSuccess'))
    return true
  } catch (err) {
    const message = err instanceof Error ? err.message : t('admin.schoolAddMemberCreateError')
    notify.error(message)
    return false
  }
}

async function submitBatch(): Promise<BatchSubmitResult> {
  const parseError = batchParseErrorKey.value
  if (parseError) {
    notify.error(t(parseError, batchParseResult.value.errorParams ?? {}))
    return { outcome: 'error', createdCount: 0 }
  }

  const members = batchRows.value.map((row) => {
    const base = { name: row.name, role: 'teacher' as const }
    if (row.contactType === 'email' && row.email) {
      return { ...base, email: row.email }
    }
    return { ...base, phone: row.phone }
  })

  try {
    const data = await createSchoolUsersBatch.mutateAsync({
      organizationId: props.orgId,
      body: { members },
    })
    const created = data.created_count ?? 0
    const failed = data.failed_count ?? 0
    const skipped = data.skipped_count ?? 0
    const failedItems = data.failed ?? []

    if (failed > 0) {
      batchImportResult.value = {
        createdCount: created,
        failedCount: failed,
        failedItems,
      }
      return {
        outcome: created > 0 ? 'partial' : 'all_failed',
        createdCount: created,
      }
    }

    if (created > 0 && skipped > 0) {
      notify.success(t('admin.schoolAddMemberBatchSuccessWithSkipped', { created, skipped }))
    } else if (created > 0) {
      notify.success(t('admin.schoolAddMemberBatchSuccess', { created }))
    } else if (skipped > 0) {
      notify.success(t('admin.schoolAddMemberBatchAllSkipped', { skipped }))
    } else {
      notify.success(t('admin.schoolAddMemberBatchSuccess', { created: 0 }))
    }
    return { outcome: 'success', createdCount: created }
  } catch (err) {
    const message = err instanceof Error ? err.message : t('admin.schoolAddMemberCreateError')
    notify.error(message)
    return { outcome: 'error', createdCount: 0 }
  }
}

async function handleSubmit(): Promise<void> {
  if (submitting.value) {
    return
  }
  submitting.value = true
  try {
    if (batchExpanded.value && batchPreviewCount.value > 0) {
      if (batchInvalidRows.value.length > 0) {
        notifyInvalidRow(batchInvalidRows.value[0]!)
      }
      const { outcome, createdCount } = await submitBatch()
      if (outcome === 'success') {
        visible.value = false
        if (createdCount > 0) {
          emit('created')
        }
      } else if (outcome === 'partial') {
        emit('created')
      }
      return
    }

    if (canSubmitSingle.value) {
      const ok = await submitSingle()
      if (ok) {
        visible.value = false
        emit('created')
      }
      return
    }

    if (batchExpanded.value) {
      const invalid = batchInvalidRows.value[0]
      if (invalid) {
        notifyInvalidRow(invalid)
      } else {
        notify.error(t('admin.schoolAddMemberBatchEmpty'))
      }
    } else if (!canSubmitSingle.value && contactEdit.value.trim() && nameEdit.value.trim()) {
      notifyInvalidContact(nameEdit.value, contactEdit.value)
    } else if (!canSubmitSingle.value && nameEdit.value.trim()) {
      notify.error(t('admin.schoolAddMemberInvalidNameForName', { name: nameEdit.value.trim() }))
    } else {
      notify.error(t('admin.schoolAddMemberRequired'))
    }
  } finally {
    submitting.value = false
  }
}

function closeBatchResult(): void {
  visible.value = false
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
              v-if="!showingBatchResult"
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
                    for="add-member-contact"
                  >
                    {{ t('admin.schoolAddMemberContact') }}
                    <span class="text-stone-400">*</span>
                  </label>
                  <input
                    id="add-member-contact"
                    v-model="contactEdit"
                    type="text"
                    inputmode="email"
                    autocomplete="username"
                    :placeholder="t('admin.schoolAddMemberContactPlaceholder')"
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
                    <span>{{ t('admin.schoolAddMemberContact') }}</span>
                    <span>{{ t('admin.schoolAddMemberName') }}</span>
                  </div>
                  <div
                    v-for="row in batchPreviewRows"
                    :key="`${row.line}-${formatMemberContact(row)}`"
                    class="school-add-member-preview__row"
                  >
                    <span>{{ formatMemberContact(row) }}</span>
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

                <div
                  v-if="batchInvalidRows.length > 0"
                  class="school-add-member-invalid-panel"
                >
                  <p class="school-add-member-invalid-panel__title">
                    {{
                      t('admin.schoolAddMemberBatchInvalidRowsTitle', {
                        count: batchInvalidRows.length,
                      })
                    }}
                  </p>
                  <div class="school-add-member-preview school-add-member-preview--invalid">
                    <div
                      class="school-add-member-preview__head school-add-member-preview__head--invalid"
                    >
                      <span>{{ t('admin.schoolAddMemberContact') }}</span>
                      <span>{{ t('admin.schoolAddMemberName') }}</span>
                      <span>{{ t('admin.schoolAddMemberBatchFailedReason') }}</span>
                    </div>
                    <div class="school-add-member-invalid-panel__list">
                      <div
                        v-for="row in batchInvalidPreviewRows"
                        :key="`invalid-${row.line}-${row.contactRaw}`"
                        class="school-add-member-preview__row school-add-member-preview__row--invalid"
                      >
                        <span>{{ row.contactRaw || '—' }}</span>
                        <span>{{ row.name || '—' }}</span>
                        <span class="school-add-member-preview__reason">
                          {{ t(row.errorKey, row.errorParams ?? {}) }}
                        </span>
                      </div>
                    </div>
                  </div>
                  <p
                    v-if="batchInvalidRows.length > batchInvalidPreviewRows.length"
                    class="school-add-member-preview__more"
                  >
                    {{
                      t('admin.schoolAddMemberBatchPreviewMore', {
                        count: batchInvalidRows.length - batchInvalidPreviewRows.length,
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

            <div
              v-else-if="batchImportResult"
              class="p-8 space-y-5 overflow-y-auto"
            >
              <p
                class="school-add-member-result-summary"
                :class="`school-add-member-result-summary--${batchResultSummaryTone}`"
              >
                {{
                  t(batchResultSummaryKey ?? 'admin.schoolAddMemberBatchResultSuccess', {
                    created: batchImportResult.createdCount,
                    failed: batchImportResult.failedCount,
                  })
                }}
              </p>

              <div
                v-if="batchImportResult.failedCount > 0"
                class="school-add-member-failed-panel"
              >
                <p class="school-add-member-failed-panel__title">
                  {{
                    t('admin.schoolAddMemberBatchFailedListTitle', {
                      count: batchImportResult.failedCount,
                    })
                  }}
                </p>
                <div class="school-add-member-preview school-add-member-preview--failed">
                  <div class="school-add-member-preview__head school-add-member-preview__head--failed">
                    <span>{{ t('admin.schoolAddMemberContact') }}</span>
                    <span>{{ t('admin.schoolAddMemberName') }}</span>
                    <span>{{ t('admin.schoolAddMemberBatchFailedReason') }}</span>
                  </div>
                  <div class="school-add-member-failed-panel__list">
                    <div
                      v-for="item in batchImportResult.failedItems"
                      :key="`${item.index}-${formatFailureContact(item)}`"
                      class="school-add-member-preview__row school-add-member-preview__row--failed"
                    >
                      <span>{{ formatFailureContact(item) }}</span>
                      <span>{{ item.name }}</span>
                      <span class="school-add-member-preview__reason">{{ item.detail }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end pt-1">
                <button
                  type="button"
                  class="school-add-member-btn school-add-member-btn--primary"
                  @click="closeBatchResult"
                >
                  {{ t('admin.schoolAddMemberBatchResultDone') }}
                </button>
              </div>
            </div>
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

.school-add-member-result-summary {
  margin: 0;
  padding: 0.875rem 1rem;
  border-radius: 0.75rem;
  font-size: 0.875rem;
  line-height: 1.5;
}

.school-add-member-result-summary--success {
  background: #ecfdf5;
  color: #047857;
}

.school-add-member-result-summary--warning {
  background: #fffbeb;
  color: #b45309;
}

.school-add-member-result-summary--error {
  background: #fef2f2;
  color: #b91c1c;
}

.school-add-member-failed-panel__title {
  margin: 0 0 0.625rem;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #44403c;
}

.school-add-member-failed-panel__list {
  max-height: 16rem;
  overflow-y: auto;
}

.school-add-member-invalid-panel {
  margin-top: 0.75rem;
}

.school-add-member-invalid-panel__title {
  margin: 0 0 0.625rem;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #b45309;
}

.school-add-member-invalid-panel__list {
  max-height: 12rem;
  overflow-y: auto;
}

.school-add-member-preview--invalid {
  border-color: #fed7aa;
}

.school-add-member-preview__head--invalid,
.school-add-member-preview__row--invalid {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.25fr);
}

.school-add-member-preview__head--invalid {
  background: #fffbeb;
  color: #b45309;
}

.school-add-member-preview__row--invalid {
  align-items: start;
}

.school-add-member-preview--failed {
  border-color: #fecaca;
}

.school-add-member-preview__head--failed,
.school-add-member-preview__row--failed {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.25fr);
}

.school-add-member-preview__head--failed {
  background: #fef2f2;
  color: #991b1b;
}

.school-add-member-preview__row--failed {
  align-items: start;
}

.school-add-member-preview__reason {
  color: #b91c1c;
  line-height: 1.4;
  word-break: break-word;
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
