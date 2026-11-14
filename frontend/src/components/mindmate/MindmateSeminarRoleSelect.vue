<script setup lang="ts">
/**
 * Compact role picker: presets plus an explicit “+ custom role” entry.
 * Created custom labels stay in the shared dropdown pool for later selection.
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { PenLine, Plus } from '@lucide/vue'

import { useLanguage } from '@/composables'
import {
  SEMINAR_BRIEF_ROLE_OPTIONS,
  SEMINAR_CUSTOM_ROLE_MAX,
  type SeminarBriefRole,
  isSeminarBuiltinRole,
  isSeminarCustomRole,
  normalizeSeminarBriefRole,
} from '@/utils/mindmateSeminarBrief'
import { rememberSeminarCustomRole, seminarCustomRoles } from '@/utils/seminarCustomRoles'

const props = withDefaults(
  defineProps<{
    modelValue: SeminarBriefRole
    disabled?: boolean
    /** Wider field for the brief selected-list column. */
    wide?: boolean
  }>(),
  {
    disabled: false,
    wide: false,
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: SeminarBriefRole): void
}>()

const { t } = useLanguage()
const rootRef = ref<HTMLElement | null>(null)
const triggerRef = ref<HTMLButtonElement | null>(null)
const menuRef = ref<HTMLElement | null>(null)
const open = ref(false)
const customEditing = ref(false)
const customDraft = ref('')
const customInput = ref<HTMLInputElement | null>(null)
const menuStyle = ref<Record<string, string>>({})

/** Rough menu height used to decide whether to flip above the trigger. */
const MENU_ESTIMATE = 280

const displayValue = computed(() => {
  const role = props.modelValue === 'none' ? 'observer' : props.modelValue
  return role || 'observer'
})

const isCustom = computed(() => !isSeminarBuiltinRole(displayValue.value))

const customOptions = computed(() => {
  const rows = new Set(seminarCustomRoles.value)
  if (isSeminarCustomRole(displayValue.value)) {
    rows.add(displayValue.value)
  }
  return [...rows]
})

const triggerLabel = computed(() => optionLabel(displayValue.value))

watch(
  () => props.modelValue,
  (value) => {
    if (isSeminarCustomRole(value)) {
      rememberSeminarCustomRole(value)
    }
    if (!customEditing.value) {
      customDraft.value = isCustom.value ? displayValue.value : ''
    }
  },
  { immediate: true }
)

function optionLabel(role: string): string {
  if (isSeminarBuiltinRole(role) || role === 'none') {
    return t(`mindmate.home.brief.role.${role === 'none' ? 'observer' : role}`)
  }
  return role
}

function closeMenu(): void {
  open.value = false
  customEditing.value = false
  customDraft.value = isCustom.value ? displayValue.value : ''
}

function positionMenu(): void {
  const rect = triggerRef.value?.getBoundingClientRect()
  if (!rect) {
    return
  }
  const style: Record<string, string> = {
    left: `${Math.round(rect.left)}px`,
    minWidth: `${Math.max(Math.round(rect.width), 156)}px`,
  }
  const spaceBelow = window.innerHeight - rect.bottom
  if (spaceBelow < MENU_ESTIMATE && rect.top > spaceBelow) {
    style.bottom = `${Math.round(window.innerHeight - rect.top + 4)}px`
  } else {
    style.top = `${Math.round(rect.bottom + 4)}px`
  }
  menuStyle.value = style
}

function toggleMenu(): void {
  if (props.disabled) {
    return
  }
  if (open.value) {
    closeMenu()
    return
  }
  positionMenu()
  open.value = true
  customEditing.value = false
  customDraft.value = isCustom.value ? displayValue.value : ''
}

function pickRole(role: string): void {
  const next = normalizeSeminarBriefRole(role)
  if (isSeminarCustomRole(next)) {
    rememberSeminarCustomRole(next)
  }
  if (next !== displayValue.value) {
    emit('update:modelValue', next)
  }
  closeMenu()
}

async function startCustom(): Promise<void> {
  customEditing.value = true
  customDraft.value = isCustom.value ? displayValue.value : ''
  await nextTick()
  customInput.value?.focus()
  customInput.value?.select()
}

function commitCustom(): void {
  const cleaned = customDraft.value.trim().slice(0, SEMINAR_CUSTOM_ROLE_MAX)
  if (!cleaned) {
    customEditing.value = false
    return
  }
  const next = normalizeSeminarBriefRole(cleaned)
  if (!isSeminarCustomRole(next) && !isSeminarBuiltinRole(next)) {
    return
  }
  if (isSeminarCustomRole(next)) {
    rememberSeminarCustomRole(next)
  }
  if (next !== displayValue.value) {
    emit('update:modelValue', next)
  }
  closeMenu()
}

function onDocumentPointerDown(event: PointerEvent): void {
  if (!open.value) {
    return
  }
  const target = event.target as Node | null
  if (!target) {
    return
  }
  if (rootRef.value?.contains(target) || menuRef.value?.contains(target)) {
    return
  }
  closeMenu()
}

function onDocumentKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && open.value) {
    closeMenu()
  }
}

function onWindowScroll(event: Event): void {
  if (!open.value) {
    return
  }
  const target = event.target as Node | null
  if (target && menuRef.value?.contains(target)) {
    return
  }
  closeMenu()
}

function onWindowResize(): void {
  if (open.value) {
    closeMenu()
  }
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown, true)
  document.addEventListener('keydown', onDocumentKeydown)
  window.addEventListener('scroll', onWindowScroll, true)
  window.addEventListener('resize', onWindowResize)
})

onUnmounted(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown, true)
  document.removeEventListener('keydown', onDocumentKeydown)
  window.removeEventListener('scroll', onWindowScroll, true)
  window.removeEventListener('resize', onWindowResize)
})
</script>

<template>
  <div
    ref="rootRef"
    class="mm-role-select"
    :class="{ 'is-wide': wide, 'is-custom': isCustom, 'is-open': open, 'is-disabled': disabled }"
  >
    <button
      ref="triggerRef"
      type="button"
      class="mm-role-select__trigger"
      :disabled="disabled"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click="toggleMenu"
    >
      <PenLine
        v-if="isCustom"
        class="mm-role-select__pen"
        :size="12"
        aria-hidden="true"
      />
      <span class="mm-role-select__label">{{ triggerLabel }}</span>
      <span
        class="mm-role-select__caret"
        aria-hidden="true"
      />
    </button>

    <Teleport to="body">
      <div
        v-if="open"
        ref="menuRef"
        class="mm-role-select__menu"
        :style="menuStyle"
        role="listbox"
        @pointerdown.stop
        @mousedown.stop
      >
        <button
          v-for="role in SEMINAR_BRIEF_ROLE_OPTIONS"
          :key="role"
          type="button"
          class="mm-role-select__option"
          :class="{ 'is-selected': displayValue === role }"
          role="option"
          :aria-selected="displayValue === role"
          @click="pickRole(role)"
        >
          {{ optionLabel(role) }}
        </button>
        <button
          v-for="role in customOptions"
          :key="`custom-${role}`"
          type="button"
          class="mm-role-select__option is-custom-opt"
          :class="{ 'is-selected': displayValue === role }"
          role="option"
          :aria-selected="displayValue === role"
          @click="pickRole(role)"
        >
          <PenLine
            :size="12"
            aria-hidden="true"
          />
          <span>{{ role }}</span>
        </button>
        <div class="mm-role-select__footer">
          <button
            v-if="!customEditing"
            type="button"
            class="mm-role-select__add"
            @click.stop="startCustom"
          >
            <Plus
              :size="14"
              aria-hidden="true"
            />
            <span><I18nText k="mindmate.home.brief.role.customAdd" /></span>
          </button>
          <div
            v-else
            class="mm-role-select__edit"
          >
            <input
              ref="customInput"
              v-model="customDraft"
              class="mm-role-select__edit-input"
              type="text"
              :maxlength="SEMINAR_CUSTOM_ROLE_MAX"
              :placeholder="t('mindmate.home.brief.role.customPlaceholder')"
              @keydown.enter.prevent="commitCustom"
              @keydown.escape.prevent="customEditing = false"
            />
            <button
              type="button"
              class="mm-role-select__edit-ok"
              @click.stop="commitCustom"
            >
              <I18nText k="common.confirm" />
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.mm-role-select {
  position: relative;
  width: 92px;
  max-width: 100%;
}

.mm-role-select.is-wide {
  width: 100%;
  min-width: 0;
}

.mm-role-select__trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  min-height: 30px;
  padding: 0 8px;
  border: 1px solid #e7e5e4;
  border-radius: 999px;
  background: #fafaf9;
  color: #1c1917;
  font: inherit;
  font-size: 12px;
  line-height: 20px;
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s,
    box-shadow 0.15s;
}

.mm-role-select.is-wide .mm-role-select__trigger {
  border-radius: 8px;
  background: #fff;
}

.mm-role-select.is-custom .mm-role-select__trigger {
  border-color: #c4b5fd;
  background: #f5f3ff;
}

.mm-role-select__trigger:hover {
  border-color: #d6d3d1;
  background: #fff;
}

.mm-role-select.is-custom .mm-role-select__trigger:hover {
  border-color: #a78bfa;
  background: #ede9fe;
}

.mm-role-select.is-open .mm-role-select__trigger,
.mm-role-select__trigger:focus-visible {
  border-color: #c4b5fd;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.12);
  outline: none;
}

.mm-role-select.is-disabled .mm-role-select__trigger {
  opacity: 0.6;
  cursor: not-allowed;
}

.mm-role-select__pen {
  display: block;
  flex-shrink: 0;
  color: #7c3aed;
}

.mm-role-select__label {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}

.mm-role-select__caret {
  flex-shrink: 0;
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 5px solid #a8a29e;
}

.mm-role-select__menu {
  position: fixed;
  z-index: 4000;
  min-width: 156px;
  max-width: 260px;
  max-height: 260px;
  overflow: auto;
  padding: 4px 0 0;
  border: 1px solid #e7e5e4;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(28, 25, 23, 0.12);
}

.mm-role-select__option {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  min-height: 32px;
  padding: 0 12px;
  border: 0;
  background: transparent;
  color: #1c1917;
  font: inherit;
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}

.mm-role-select__option:hover {
  background: #f5f5f4;
}

.mm-role-select__option.is-selected {
  color: #5b21b6;
  font-weight: 600;
  background: #f5f3ff;
}

.mm-role-select__option.is-custom-opt {
  color: #5b21b6;
}

.mm-role-select__footer {
  position: sticky;
  bottom: 0;
  padding: 6px 8px 8px;
  border-top: 1px solid #f5f5f4;
  background: #fff;
}

.mm-role-select__add {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  min-height: 32px;
  padding: 0 10px;
  border: 1px dashed #ddd6fe;
  border-radius: 8px;
  background: #faf8ff;
  color: #5b21b6;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.mm-role-select__add:hover {
  background: #f5f3ff;
  border-color: #c4b5fd;
}

.mm-role-select__edit {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mm-role-select__edit-input {
  flex: 1 1 auto;
  min-width: 0;
  height: 32px;
  padding: 0 10px;
  border: 1px solid #c4b5fd;
  border-radius: 8px;
  background: #fff;
  color: #1c1917;
  font: inherit;
  font-size: 12px;
  outline: none;
  box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.12);
}

.mm-role-select__edit-ok {
  flex-shrink: 0;
  height: 32px;
  padding: 0 10px;
  border: 0;
  border-radius: 8px;
  background: #ede9fe;
  color: #5b21b6;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.mm-role-select__edit-ok:hover {
  background: #ddd6fe;
}
</style>
