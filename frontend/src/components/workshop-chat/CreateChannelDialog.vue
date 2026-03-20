<script setup lang="ts">
/**
 * Create org-scoped channels: top-level teaching group (教研组) or lesson study (课例) under a group.
 * Server: POST /api/chat/channels (admin or org manager).
 */
import { computed, ref, watch } from 'vue'

import { ElMessage } from 'element-plus'

import { useLanguage } from '@/composables/useLanguage'
import { useWorkshopChatStore } from '@/stores/workshopChat'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const { t } = useLanguage()
const store = useWorkshopChatStore()

const kind = ref<'group' | 'lesson'>('group')
const name = ref('')
const description = ref('')
const avatar = ref('')
const parentId = ref<number | null>(null)
const saving = ref(false)

const parentOptions = computed(() =>
  store.channels.filter(
    (c) => c.channel_type !== 'announce' && (c.parent_id === null || c.parent_id === undefined)
  )
)

watch(
  () => props.visible,
  (open) => {
    if (open) {
      const prefill = store.createChannelPrefillParentId
      if (prefill != null) {
        kind.value = 'lesson'
        parentId.value = prefill
      } else {
        kind.value = 'group'
        parentId.value = parentOptions.value[0]?.id ?? null
      }
      name.value = ''
      description.value = ''
      avatar.value = ''
    }
  }
)

watch(kind, (k) => {
  if (k === 'lesson' && parentId.value == null) {
    parentId.value = parentOptions.value[0]?.id ?? null
  }
})

async function submit(): Promise<void> {
  const n = name.value.trim()
  if (!n) {
    return
  }
  if (kind.value === 'lesson' && parentId.value == null) {
    ElMessage.warning(t('workshop.createChannelNeedParent'))
    return
  }
  saving.value = true
  const result = await store.createChannel({
    name: n,
    description: description.value.trim() || null,
    avatar: avatar.value.trim() || null,
    parent_id: kind.value === 'lesson' ? parentId.value : null,
  })
  saving.value = false
  if (result.ok) {
    ElMessage.success(t('workshop.createChannelSuccess'))
    emit('update:visible', false)
    return
  }
  ElMessage.error(result.error || t('workshop.createChannelFailed'))
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="t('workshop.addChannelTitle')"
    width="440px"
    :close-on-click-modal="false"
    append-to-body
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="flex flex-col gap-3 text-sm">
      <el-radio-group
        v-model="kind"
        class="flex flex-col items-start gap-2"
      >
        <el-radio label="group">
          {{ t('workshop.channelKindGroup') }}
        </el-radio>
        <el-radio label="lesson">
          {{ t('workshop.channelKindLessonStudy') }}
        </el-radio>
      </el-radio-group>

      <el-form
        label-position="top"
        class="mt-1"
      >
        <el-form-item
          v-if="kind === 'lesson'"
          :label="t('workshop.selectParentGroup')"
        >
          <el-select
            v-model="parentId"
            class="w-full"
            :placeholder="t('workshop.selectParentGroup')"
            filterable
          >
            <el-option
              v-for="g in parentOptions"
              :key="g.id"
              :label="`${g.avatar ?? ''} ${g.name}`.trim()"
              :value="g.id"
            />
          </el-select>
          <p
            v-if="parentOptions.length === 0"
            class="text-xs text-amber-700 mt-1"
          >
            {{ t('workshop.createChannelNoGroupsYet') }}
          </p>
        </el-form-item>

        <el-form-item :label="t('workshop.channelNameLabel')">
          <el-input
            v-model="name"
            maxlength="100"
            show-word-limit
            :placeholder="t('workshop.channelNamePlaceholder')"
          />
        </el-form-item>

        <el-form-item :label="t('workshop.topicDescription')">
          <el-input
            v-model="description"
            type="textarea"
            :rows="2"
            maxlength="500"
            show-word-limit
            :placeholder="t('workshop.topicDescriptionPlaceholder')"
          />
        </el-form-item>

        <el-form-item :label="t('workshop.channelAvatarEmoji')">
          <el-input
            v-model="avatar"
            maxlength="50"
            :placeholder="t('workshop.channelAvatarPlaceholder')"
          />
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="emit('update:visible', false)">
        {{ t('common.cancel') }}
      </el-button>
      <el-button
        type="primary"
        :loading="saving"
        :disabled="!name.trim() || (kind === 'lesson' && parentOptions.length === 0)"
        @click="submit"
      >
        {{ t('workshop.create') }}
      </el-button>
    </template>
  </el-dialog>
</template>
