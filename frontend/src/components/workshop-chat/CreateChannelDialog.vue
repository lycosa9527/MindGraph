<script setup lang="ts">
/**
 * Create org-scoped channels: top-level teaching group (教研组) or lesson study (课例) under a group.
 * Server: POST /api/chat/channels (admin or org manager).
 */
import { computed, ref, watch } from 'vue'

import { ElMessage } from 'element-plus'

import { MessagesSquare } from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useWorkshopChatStore } from '@/stores/workshopChat'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const open = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
})

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
  <SwissGlassDialog
    v-model="open"
    :ribbon="t('swissGlass.hero.createChannel.ribbon')"
    :title="t('swissGlass.hero.createChannel.title')"
    :line1="t('swissGlass.hero.createChannel.line1')"
    :icon="MessagesSquare"
    width="min(440px, 92vw)"
    :close-on-click-modal="false"
  >
    <div class="flex flex-col gap-3 text-sm">
      <el-radio-group
        v-model="kind"
        class="flex flex-col items-start gap-2"
      >
        <el-radio value="group">
          {{ t('workshop.channelKindGroup') }}
        </el-radio>
        <el-radio value="lesson">
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
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="open = false"
        >
          {{ t('common.cancel') }}
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          :disabled="saving || !name.trim() || (kind === 'lesson' && parentOptions.length === 0)"
          @click="submit"
        >
          {{ t('workshop.create') }}
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>
