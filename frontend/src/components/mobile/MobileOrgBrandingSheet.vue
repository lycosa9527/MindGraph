<script setup lang="ts">
/**
 * Phone editor for a school's public MindMate identity.
 * Text fields save together. The avatar uploads or clears on its own.
 */
import { onMounted, onUnmounted, shallowRef, useTemplateRef, watch } from 'vue'

import { Loader2 } from '@lucide/vue'

import mindmateAvatarMd from '@/assets/mindmate-avatar-md.png'
import { useLanguage, useNotifications } from '@/composables'
import { resolveSchoolMindmateAvatarUrl } from '@/composables/mindmate/useMindMateBranding'
import {
  useUpdateMobileOrganizationBranding,
  useUploadMobileOrganizationMindmateAvatar,
} from '@/composables/queries'
import { useAuthStore } from '@/stores'
import {
  mindmateAvatarFileErrorKey,
  mindmateAvatarUploadErrorKey,
} from '@/utils/mindmateAvatarFile'

const AGENT_NAME_MAX = 10
const DISPLAY_NAME_MAX = 200

const props = defineProps<{
  org: {
    id: number
    name: string
    displayName: string
    agentName: string
    agentAlias: string
    avatarUrl: string
  } | null
}>()

const emit = defineEmits<{
  close: []
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const updateBranding = useUpdateMobileOrganizationBranding()
const uploadAvatar = useUploadMobileOrganizationMindmateAvatar()

const agentName = shallowRef('')
const agentAlias = shallowRef('')
const displayName = shallowRef('')
const avatarUrl = shallowRef('')
const saving = shallowRef(false)
const avatarUploading = shallowRef(false)
const sheetMaxHeight = shallowRef('')
const sheetBottom = shallowRef('0px')
const avatarInput = useTemplateRef<HTMLInputElement>('avatarInput')

const fieldClass =
  'w-full h-11 px-3 rounded-md border border-gray-200 bg-white text-base text-gray-800 placeholder-gray-400 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100'

function previewSrc(): string {
  return resolveSchoolMindmateAvatarUrl(avatarUrl.value) ?? mindmateAvatarMd
}

function requestClose(): void {
  if (saving.value || avatarUploading.value) {
    return
  }
  emit('close')
}

let bodyLocked = false
let viewportBound = false

function lockBody(): void {
  if (bodyLocked) {
    return
  }
  document.body.style.overflow = 'hidden'
  bodyLocked = true
}

function unlockBody(): void {
  if (!bodyLocked) {
    return
  }
  document.body.style.overflow = ''
  bodyLocked = false
}

function syncSheetToViewport(): void {
  const viewport = window.visualViewport
  const visibleHeight = viewport?.height ?? window.innerHeight
  const keyboardInset = viewport
    ? Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop)
    : 0
  sheetBottom.value = `${Math.round(keyboardInset)}px`
  sheetMaxHeight.value = `${Math.round(Math.min(visibleHeight * 0.92, 44 * 16))}px`
}

function bindViewport(): void {
  syncSheetToViewport()
  if (viewportBound) {
    return
  }
  window.visualViewport?.addEventListener('resize', syncSheetToViewport)
  window.visualViewport?.addEventListener('scroll', syncSheetToViewport)
  viewportBound = true
}

function unbindViewport(): void {
  if (!viewportBound) {
    return
  }
  window.visualViewport?.removeEventListener('resize', syncSheetToViewport)
  window.visualViewport?.removeEventListener('scroll', syncSheetToViewport)
  viewportBound = false
}

function onKeydown(event: KeyboardEvent): void {
  if (props.org && event.key === 'Escape') {
    requestClose()
  }
}

function onFieldFocus(event: FocusEvent): void {
  const target = event.target
  if (!(target instanceof HTMLElement)) {
    return
  }
  window.setTimeout(() => {
    target.scrollIntoView({ block: 'nearest' })
  }, 280)
}

function fillFromOrg(): void {
  const org = props.org
  if (!org) {
    return
  }
  agentName.value = org.agentName
  agentAlias.value = org.agentAlias
  displayName.value = org.displayName
  avatarUrl.value = org.avatarUrl
}

watch(
  () => props.org?.id ?? null,
  (id) => {
    if (id == null) {
      unlockBody()
      unbindViewport()
      return
    }
    fillFromOrg()
    lockBody()
    bindViewport()
  },
  { immediate: true }
)

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  unlockBody()
  unbindViewport()
  window.removeEventListener('keydown', onKeydown)
})

async function refreshSignedInProfile(orgId: number): Promise<void> {
  const schoolId = authStore.user?.schoolId
  if (!schoolId || Number(schoolId) !== orgId) {
    return
  }
  await authStore.refreshUserProfile({ bypassThrottle: true })
}

function notifyRequestError(message: string, fallbackKey: string): void {
  if (message === 'NETWORK_ERROR') {
    notify.errorKey('notification.networkError')
    return
  }
  const key = message.trim() ? mindmateAvatarUploadErrorKey(message) : ''
  if (key) {
    notify.errorKey(key)
    return
  }
  notify.error(message || String(t(fallbackKey)))
}

async function save(): Promise<void> {
  const org = props.org
  if (!org || saving.value || avatarUploading.value) {
    return
  }
  saving.value = true
  try {
    await updateBranding.mutateAsync({
      orgId: org.id,
      body: {
        mindmate_agent_name: agentName.value.trim() || null,
        mindmate_agent_alias: agentAlias.value.trim() || null,
        display_name: displayName.value.trim() || null,
      },
    })
    await refreshSignedInProfile(org.id)
    notify.successKey('notification.saved')
    emit('close')
  } catch (err) {
    const message = err instanceof Error ? err.message : ''
    notifyRequestError(message, 'admin.trendChartErrors.saveFailed')
  } finally {
    saving.value = false
  }
}

function openAvatarPicker(): void {
  avatarInput.value?.click()
}

async function onAvatarSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  const org = props.org
  if (!file || !org || saving.value || avatarUploading.value) {
    return
  }
  const validationKey = mindmateAvatarFileErrorKey(file)
  if (validationKey) {
    notify.warningKey(validationKey)
    return
  }
  avatarUploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const data = await uploadAvatar.mutateAsync({ orgId: org.id, formData })
    const nextUrl = data.mindmate_agent_avatar_url
    avatarUrl.value = typeof nextUrl === 'string' ? nextUrl : ''
    await refreshSignedInProfile(org.id)
    notify.successKey('admin.schoolMindmateAvatarUploaded')
  } catch (err) {
    const message = err instanceof Error ? err.message : ''
    notifyRequestError(message, 'admin.schoolMindmateAvatarUploadFailed')
  } finally {
    avatarUploading.value = false
  }
}

async function removeAvatar(): Promise<void> {
  const org = props.org
  if (!org || !avatarUrl.value || saving.value || avatarUploading.value) {
    return
  }
  avatarUploading.value = true
  try {
    await updateBranding.mutateAsync({
      orgId: org.id,
      body: { mindmate_agent_avatar_url: null },
    })
    avatarUrl.value = ''
    await refreshSignedInProfile(org.id)
    notify.successKey('admin.schoolMindmateAvatarRemoved')
  } catch (err) {
    const message = err instanceof Error ? err.message : ''
    notifyRequestError(message, 'admin.schoolMindmateAvatarRemoveFailed')
  } finally {
    avatarUploading.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="org"
      class="branding-sheet-overlay"
      @click.self="requestClose"
    >
      <form
        class="branding-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mobile-org-branding-title"
        :style="{ maxHeight: sheetMaxHeight, bottom: sheetBottom }"
        @submit.prevent="save"
      >
        <div
          class="branding-sheet-handle"
          aria-hidden="true"
        />
        <div class="px-4 pt-3 pb-2">
          <h2
            id="mobile-org-branding-title"
            class="text-base font-semibold text-gray-900"
          >
            <I18nText k="admin.editSchool" />
          </h2>
          <p class="text-xs text-gray-500 truncate mt-0.5">
            {{ org.name }}
          </p>
        </div>

        <div class="branding-sheet-body px-4 pb-4 space-y-4">
          <label class="block">
            <span class="flex items-baseline justify-between gap-2 mb-1">
              <span class="text-sm font-semibold text-gray-800">
                <I18nText k="admin.schoolMindmateAgentName" />
              </span>
              <span class="text-xs text-gray-400">{{ agentName.length }}/{{ AGENT_NAME_MAX }}</span>
            </span>
            <input
              v-model="agentName"
              type="text"
              autocomplete="off"
              :maxlength="AGENT_NAME_MAX"
              :class="fieldClass"
              @focus="onFieldFocus"
            />
            <p class="text-xs text-gray-500 leading-relaxed mt-1">
              <I18nText k="admin.schoolMindmateAgentNameHint" />
            </p>
          </label>

          <label class="block">
            <span class="flex items-baseline justify-between gap-2 mb-1">
              <span class="text-sm font-semibold text-gray-800">
                <I18nText k="admin.schoolMindmateAgentAlias" />
              </span>
              <span class="text-xs text-gray-400"
                >{{ agentAlias.length }}/{{ AGENT_NAME_MAX }}</span
              >
            </span>
            <input
              v-model="agentAlias"
              type="text"
              autocomplete="off"
              :maxlength="AGENT_NAME_MAX"
              :class="fieldClass"
              @focus="onFieldFocus"
            />
            <p class="text-xs text-gray-500 leading-relaxed mt-1">
              <I18nText k="admin.schoolMindmateAgentAliasHint" />
            </p>
          </label>

          <label class="block">
            <span class="block text-sm font-semibold text-gray-800 mb-1">
              <I18nText k="admin.schoolMindmateSchoolName" />
            </span>
            <input
              v-model="displayName"
              type="text"
              autocomplete="organization"
              :maxlength="DISPLAY_NAME_MAX"
              :placeholder="org.name"
              :class="fieldClass"
              @focus="onFieldFocus"
            />
            <p class="text-xs text-gray-500 leading-relaxed mt-1">
              <I18nText k="admin.schoolMindmateSchoolNameHint" />
            </p>
          </label>

          <div>
            <div class="text-sm font-semibold text-gray-800 mb-2">
              <I18nText k="admin.schoolMindmateAgentAvatar" />
            </div>
            <div class="flex items-center gap-3">
              <img
                :src="previewSrc()"
                alt=""
                class="h-16 w-16 rounded-full object-cover border border-gray-200 bg-white shrink-0"
              />
              <div class="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  class="org-pill org-pill--quiet"
                  :disabled="avatarUploading || saving"
                  @click="openAvatarPicker"
                >
                  <Loader2
                    v-if="avatarUploading"
                    :size="16"
                    class="animate-spin"
                  />
                  <I18nText k="admin.schoolMindmateAgentAvatarUpload" />
                </button>
                <button
                  v-if="avatarUrl"
                  type="button"
                  class="org-pill org-pill--quiet"
                  :disabled="avatarUploading || saving"
                  @click="removeAvatar"
                >
                  <I18nText k="admin.schoolMindmateAgentAvatarRemove" />
                </button>
              </div>
            </div>
            <input
              ref="avatarInput"
              type="file"
              accept="image/png,image/jpeg,image/jpg,image/gif,image/webp"
              class="hidden"
              @change="onAvatarSelected"
            />
            <p class="text-xs text-gray-500 leading-relaxed mt-2">
              <I18nText k="admin.schoolMindmateAgentAvatarHint" />
            </p>
          </div>
        </div>

        <div class="branding-sheet-actions">
          <button
            type="button"
            class="org-pill org-pill--quiet"
            :disabled="saving || avatarUploading"
            @click="requestClose"
          >
            <I18nText k="common.cancel" />
          </button>
          <button
            type="submit"
            class="org-pill org-pill--primary"
            :disabled="saving || avatarUploading"
          >
            <Loader2
              v-if="saving"
              :size="16"
              class="animate-spin"
            />
            <I18nText k="common.save" />
          </button>
        </div>
      </form>
    </div>
  </Teleport>
</template>

<style scoped>
.branding-sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(0, 0, 0, 0.4);
  overscroll-behavior: none;
}

.branding-sheet {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100%;
  max-height: min(92vh, 44rem);
  max-height: min(92dvh, 44rem);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 16px 16px 0 0;
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
  padding-bottom: max(12px, env(safe-area-inset-bottom));
}

.branding-sheet-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.branding-sheet-handle {
  width: 36px;
  height: 4px;
  background: #d1d5db;
  border-radius: 2px;
  margin: 10px auto 0;
}

.branding-sheet-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 8px 16px 4px;
  border-top: 1px solid #f3f4f6;
  background: #fff;
}

.org-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 40px;
  flex: 0 0 auto;
  width: fit-content;
  max-width: 100%;
  padding: 0 18px;
  border: 0;
  border-radius: 9999px;
  font-size: 14px;
  font-weight: 500;
  line-height: 1;
}

.org-pill:disabled {
  opacity: 0.5;
}

.org-pill--primary {
  background: #4f46e5;
  color: #fff;
}

.org-pill--primary:active:not(:disabled) {
  background: #4338ca;
}

.org-pill--quiet {
  background: #fff;
  color: #1f2937;
  border: 1px solid #e5e7eb;
}

.org-pill--quiet:active:not(:disabled) {
  background: #f9fafb;
}
</style>
