<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useWorkshopChatStore } from '@/stores/workshopChat'
import { useLanguage } from '@/composables/useLanguage'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  channelId: number
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const store = useWorkshopChatStore()
const authStore = useAuthStore()
const { t } = useLanguage()

const channel = computed(() =>
  store.channels.find(c => c.id === props.channelId),
)

const isManagerOrAdmin = computed(() =>
  authStore.isAdmin || authStore.isManager,
)

const localColor = ref('#c2c2c2')
const localDesktopNotif = ref(true)
const localEmailNotif = ref(false)
const localChannelType = ref('public')
const localPostingPolicy = ref('everyone')
const localIsDefault = ref(false)
const saving = ref(false)

watch(
  () => props.visible,
  (val) => {
    if (val && channel.value) {
      localColor.value = channel.value.color || '#c2c2c2'
      localChannelType.value = channel.value.channel_type
      localPostingPolicy.value = channel.value.posting_policy
      localIsDefault.value = channel.value.is_default
    }
  },
)

const channelTypeOptions = [
  { value: 'announce', label: 'workshop.channelTypeAnnounce' },
  { value: 'public', label: 'workshop.channelTypePublic' },
  { value: 'private', label: 'workshop.channelTypePrivate' },
]

const postingPolicyOptions = [
  { value: 'everyone', label: 'workshop.policyEveryone' },
  { value: 'managers', label: 'workshop.policyManagers' },
  { value: 'members_only', label: 'workshop.policyMembersOnly' },
]

async function savePrefs(): Promise<void> {
  saving.value = true
  await store.updateChannelPrefs(props.channelId, {
    color: localColor.value,
    desktop_notifications: localDesktopNotif.value,
    email_notifications: localEmailNotif.value,
  })
  saving.value = false
}

async function savePermissions(): Promise<void> {
  saving.value = true
  await store.updateChannelPermissions(props.channelId, {
    channel_type: localChannelType.value,
    posting_policy: localPostingPolicy.value,
    is_default: localIsDefault.value,
  })
  saving.value = false
  emit('update:visible', false)
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="t('workshop.channelSettings')"
    width="420px"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="flex flex-col gap-4">
      <div v-if="channel" class="flex items-center gap-2 text-sm text-stone-600">
        <span class="text-lg">{{ channel.avatar || '#' }}</span>
        <span class="font-medium">{{ channel.name }}</span>
        <span
          v-if="channel.channel_type !== 'public'"
          class="text-[10px] px-1.5 py-0.5 rounded bg-stone-100 text-stone-500"
        >
          {{ t(`workshop.channelType${channel.channel_type.charAt(0).toUpperCase() + channel.channel_type.slice(1)}`) }}
        </span>
      </div>

      <!-- User preferences section -->
      <div v-if="channel?.is_joined" class="border-t border-stone-100 pt-3">
        <h4 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">
          {{ t('workshop.preferences') }}
        </h4>

        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-stone-600">{{ t('workshop.channelColor') }}</span>
          <el-color-picker v-model="localColor" size="small" @change="savePrefs" />
        </div>

        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-stone-600">{{ t('workshop.desktopNotifications') }}</span>
          <el-switch v-model="localDesktopNotif" size="small" @change="savePrefs" />
        </div>

        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-stone-600">{{ t('workshop.emailNotifications') }}</span>
          <el-switch v-model="localEmailNotif" size="small" @change="savePrefs" />
        </div>
      </div>

      <!-- Admin permissions section -->
      <div v-if="isManagerOrAdmin" class="border-t border-stone-100 pt-3">
        <h4 class="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">
          {{ t('workshop.permissions') }}
        </h4>

        <div class="mb-3">
          <label class="text-xs text-stone-600 mb-1 block">{{ t('workshop.channelType') }}</label>
          <el-select v-model="localChannelType" size="small" class="w-full">
            <el-option
              v-for="opt in channelTypeOptions"
              :key="opt.value"
              :value="opt.value"
              :label="t(opt.label)"
            />
          </el-select>
        </div>

        <div class="mb-3">
          <label class="text-xs text-stone-600 mb-1 block">{{ t('workshop.postingPolicy') }}</label>
          <el-select v-model="localPostingPolicy" size="small" class="w-full">
            <el-option
              v-for="opt in postingPolicyOptions"
              :key="opt.value"
              :value="opt.value"
              :label="t(opt.label)"
            />
          </el-select>
        </div>

        <div class="flex items-center justify-between mb-3">
          <span class="text-xs text-stone-600">{{ t('workshop.defaultChannel') }}</span>
          <el-switch v-model="localIsDefault" size="small" />
        </div>

        <el-button
          type="primary"
          size="small"
          :loading="saving"
          class="w-full"
          @click="savePermissions"
        >
          {{ t('workshop.create') }}
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>
