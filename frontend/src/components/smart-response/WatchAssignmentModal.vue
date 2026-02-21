<template>
  <el-dialog
    v-model="visible"
    title="Assign Watch to Student"
    width="500px"
    @close="handleClose"
  >
    <el-form :model="form" label-width="100px">
      <el-form-item label="Watch ID">
        <el-input :model-value="watchItem?.watch_id" disabled />
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
      <el-button @click="handleClose">Cancel</el-button>
      <el-button type="primary" @click="handleAssign" :loading="loading">
        Assign
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
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

const visible = ref(false)
const loading = ref(false)
const form = ref({ student_id: null as number | null })
const students = ref<Array<{ id: number; name: string; class: string }>>([])

watch(() => props.modelValue, (val) => {
  visible.value = val
})

watch(() => props.watchItem, () => {
  form.value.student_id = null
})

onMounted(async () => {
  // TODO: Load students from API
  students.value = []
})

function handleClose() {
  visible.value = false
  emit('update:modelValue', false)
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