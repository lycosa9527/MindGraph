<script setup lang="ts">
/**
 * MathLive dialog for inserting LaTeX into a node label (inline $...$ for KaTeX + mhchem).
 * Extends the global virtual keyboard with K-12 math, K-12 equations, chemistry, and K-12 chem formulas tabs; restores on close.
 */
import { nextTick, onUnmounted, ref, watch } from 'vue'

import { ElButton, ElDialog } from 'element-plus'

import {
  buildChemistryVirtualKeyboardLayout,
  buildK12ChemFormulasVirtualKeyboardLayout,
  buildK12EquationsVirtualKeyboardLayout,
  buildK12MathVirtualKeyboardLayout,
  MATHLIVE_BASE_LAYOUTS_BEFORE_CUSTOM,
} from '@/composables/canvas/mathLiveCustomKeyboardLayouts'
import { buildK12ChemFormulasKeyLabels, buildK12EquationsKeyLabels } from '@/composables/canvas/mathLiveKeyboardI18n'
import { mapUiLocaleToMathLiveLocale } from '@/composables/canvas/mathLiveLocale'
import { useLanguage } from '@/composables/core/useLanguage'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: [latex: string]
}>()

const { t, currentLanguage } = useLanguage()

const mathFieldEl = ref<HTMLElement | null>(null)
const mathLoadError = ref<string | null>(null)
const mathliveReady = ref(false)

/** Snapshot of window.mathVirtualKeyboard.layouts before we add MindGraph tabs. */
let savedVirtualKeyboardLayouts: ReadonlyArray<string | object> | null = null

type MathfieldElementCtor = { locale: string }

async function syncMathLiveLocale(): Promise<void> {
  const ml = (await import('mathlive')) as unknown as { MathfieldElement?: MathfieldElementCtor }
  if (ml.MathfieldElement) {
    ml.MathfieldElement.locale = mapUiLocaleToMathLiveLocale(String(currentLanguage.value))
  }
}

async function ensureMathlive(): Promise<void> {
  if (!mathliveReady.value) {
    try {
      await import('mathlive')
      await import('mathlive/fonts.css')
      mathliveReady.value = true
    } catch (err) {
      mathLoadError.value = err instanceof Error ? err.message : 'MathLive load failed'
      return
    }
  }
  await syncMathLiveLocale()
}

function mindgraphKeyboardLayouts() {
  return {
    k12: buildK12MathVirtualKeyboardLayout(t('canvas.toolbar.mathKeyboardTabK12'), {
      p1: t('canvas.toolbar.mathKeyboardK12Page1'),
      p2: t('canvas.toolbar.mathKeyboardK12Page2'),
      p3: t('canvas.toolbar.mathKeyboardK12Page3'),
      p4: t('canvas.toolbar.mathKeyboardK12Page4'),
    }),
    k12Eq: buildK12EquationsVirtualKeyboardLayout(
      t('canvas.toolbar.mathKeyboardTabK12Equations'),
      {
        p1: t('canvas.toolbar.mathKeyboardK12EqPage1'),
        p2: t('canvas.toolbar.mathKeyboardK12EqPage2'),
        p3: t('canvas.toolbar.mathKeyboardK12EqPage3'),
        p4: t('canvas.toolbar.mathKeyboardK12EqPage4'),
      },
      buildK12EquationsKeyLabels(t)
    ),
    chem: buildChemistryVirtualKeyboardLayout(t('canvas.toolbar.mathKeyboardTabChemistry'), {
      p1: t('canvas.toolbar.mathKeyboardChemPage1'),
      p2: t('canvas.toolbar.mathKeyboardChemPage2'),
    }),
    k12ChemForm: buildK12ChemFormulasVirtualKeyboardLayout(
      t('canvas.toolbar.mathKeyboardTabK12ChemFormulas'),
      {
        p1: t('canvas.toolbar.mathKeyboardK12ChemFormPage1'),
        p2: t('canvas.toolbar.mathKeyboardK12ChemFormPage2'),
        p3: t('canvas.toolbar.mathKeyboardK12ChemFormPage3'),
      },
      buildK12ChemFormulasKeyLabels(t)
    ),
  }
}

function snapshotLayoutsBeforeMindGraph(
  vk: NonNullable<typeof window.mathVirtualKeyboard>
): void {
  const raw = vk.layouts as unknown
  savedVirtualKeyboardLayouts = Array.isArray(raw) ? [...raw] : null
}

function captureAndApplyKeyboardLayouts(): void {
  const vk = typeof window !== 'undefined' ? window.mathVirtualKeyboard : undefined
  if (!vk) return
  const { k12, k12Eq, chem, k12ChemForm } = mindgraphKeyboardLayouts()
  const next = [...MATHLIVE_BASE_LAYOUTS_BEFORE_CUSTOM, k12, k12Eq, chem, k12ChemForm]
  snapshotLayoutsBeforeMindGraph(vk)
  vk.layouts = next as typeof vk.layouts
}

function restoreKeyboardLayouts(): void {
  const vk = typeof window !== 'undefined' ? window.mathVirtualKeyboard : undefined
  if (!vk) {
    savedVirtualKeyboardLayouts = null
    return
  }
  if (savedVirtualKeyboardLayouts == null) {
    vk.layouts = ['default'] as typeof vk.layouts
  } else {
    vk.layouts = [...savedVirtualKeyboardLayouts] as typeof vk.layouts
  }
  savedVirtualKeyboardLayouts = null
}

watch(currentLanguage, () => {
  if (!props.modelValue || !mathliveReady.value) return
  void syncMathLiveLocale()
  const vk = typeof window !== 'undefined' ? window.mathVirtualKeyboard : undefined
  if (!vk) return
  const { k12, k12Eq, chem, k12ChemForm } = mindgraphKeyboardLayouts()
  vk.layouts = [...MATHLIVE_BASE_LAYOUTS_BEFORE_CUSTOM, k12, k12Eq, chem, k12ChemForm]
})

function showVirtualKeyboard(): void {
  const vk = typeof window !== 'undefined' ? window.mathVirtualKeyboard : undefined
  if (vk && !vk.visible) vk.show({ animate: true })
}

function hideVirtualKeyboard(): void {
  const vk = typeof window !== 'undefined' ? window.mathVirtualKeyboard : undefined
  if (vk && vk.visible) vk.hide({ animate: false })
}

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) {
      hideVirtualKeyboard()
      restoreKeyboardLayouts()
      return
    }
    mathLoadError.value = null
    await ensureMathlive()
    if (mathLoadError.value) return
    captureAndApplyKeyboardLayouts()
    await nextTick()
    const el = mathFieldEl.value as unknown as { value?: string } | undefined
    if (el && 'value' in el) {
      el.value = ''
    }
    await nextTick()
    showVirtualKeyboard()
  }
)

onUnmounted(() => {
  hideVirtualKeyboard()
  restoreKeyboardLayouts()
})

function handleConfirm(): void {
  const el = mathFieldEl.value as unknown as
    | { value?: string; getValue?: (format: string) => string }
    | undefined
  if (!el) {
    emit('update:modelValue', false)
    return
  }
  let latex = ''
  if (typeof el.getValue === 'function') {
    latex = el.getValue('latex').trim()
  } else if (typeof el.value === 'string') {
    latex = el.value.trim()
  }
  if (latex) {
    emit('confirm', latex)
  }
  emit('update:modelValue', false)
}

function handleCancel(): void {
  emit('update:modelValue', false)
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    :title="t('canvas.toolbar.insertEquationDialogTitle')"
    width="min(520px, 92vw)"
    append-to-body
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div
      v-if="mathLoadError"
      class="text-red-600 text-sm"
    >
      {{ mathLoadError }}
    </div>
    <template v-else-if="mathliveReady">
      <math-field
        ref="mathFieldEl"
        math-virtual-keyboard-policy="manual"
        class="math-insert-field w-full min-h-12 min-w-0 rounded border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-900"
      />
    </template>
    <div
      v-else
      class="text-sm text-gray-500 dark:text-gray-400 py-4"
    >
      {{ t('canvas.toolbar.insertEquationLoading') }}
    </div>
    <template #footer>
      <ElButton @click="handleCancel">
        {{ t('canvas.toolbar.insertEquationCancel') }}
      </ElButton>
      <ElButton
        type="primary"
        @click="handleConfirm"
      >
        {{ t('canvas.toolbar.insertEquationConfirm') }}
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.math-insert-field {
  font-size: 1.1rem;
}
</style>
