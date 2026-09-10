<template>
  <SwissGlassDialog
    v-model="visible"
    :ribbon="t('swissGlass.hero.watchAssign.ribbon')"
    :title="t('swissGlass.hero.watchAssign.title')"
    :line1="t('swissGlass.hero.watchAssign.line1')"
    :icon="Eye"
    width="min(500px, 92vw)"
    @close="handleClose"
  >
    <el-form
      :model="form"
      label-width="100px"
    >
      <el-form-item label="Watch ID">
        <el-input
          :model-value="watchItem?.watch_id"
          disabled
        />
      </el-form-item>
      <el-form-item label="Student">
        <el-select
          v-model="form.student_id"
          placeholder="Select student"
          filterable
          style="width: 100%"
        >
          <el-option
            v-for="student in students"
            :key="student.id"
            :label="`${student.name} (${student.class})`"
            :value="student.id"
          />
        </el-select>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="handleClose"
        >
          Cancel
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          :disabled="loading"
          @click="handleAssign"
        >
          Assign
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { Eye } from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import type { Watch } from '@/stores/smartResponse'

interface Props {
  modelValue: boolean
  watchItem: Watch | null
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'assigned', watchId: string, studentId: number): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const { t } = useLanguage()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const loading = ref(false)
const form = ref({ student_id: null as number | null })
const students = ref<Array<{ id: number; name: string; class: string }>>([])

watch(
  () => props.watchItem,
  () => {
    form.value.student_id = null
  }
)

onMounted(async () => {
  // TODO: Load students from API
  students.value = []
})

function handleClose() {
  visible.value = false
}

async function handleAssign() {
  if (!props.watchItem || !form.value.student_id) return

  loading.value = true
  try {
    emit('assigned', props.watchItem.watch_id, form.value.student_id)
  } finally {
    loading.value = false
  }
}
</script>
