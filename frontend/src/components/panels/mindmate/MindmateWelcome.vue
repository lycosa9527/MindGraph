<script setup lang="ts">
import { computed } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import MindmateHomeModeSwitch from '@/components/mindmate/MindmateHomeModeSwitch.vue'
import { useLanguage } from '@/composables'
import { greetHourLabel } from '@/composables/learningSpace/lsHelpers'
import { useMindMateBranding } from '@/composables/mindmate/useMindMateBranding'
import { resolveBilingual } from '@/i18n/resolveBilingual'
import { useAuthStore } from '@/stores/auth'

import MindmateAgentAvatar from './MindmateAgentAvatar.vue'

const props = withDefaults(
  defineProps<{
    mode?: 'panel' | 'fullpage'
    showModeSwitch?: boolean
    homeMode?: 'dialogue' | 'seminar'
  }>(),
  {
    mode: 'panel',
    showModeSwitch: false,
    homeMode: 'dialogue',
  }
)

const emit = defineEmits<{
  (e: 'update:homeMode', mode: 'dialogue' | 'seminar'): void
}>()

const authStore = useAuthStore()
const { t } = useLanguage()
const isFullpageMode = computed(() => props.mode === 'fullpage')
const { displayName } = useMindMateBranding('md')
const username = computed(() => authStore.user?.username || '')
const welcomeParams = computed(() => ({
  username: username.value,
  agentName: displayName.value,
}))
const greetKey = computed(() => {
  const label = greetHourLabel(new Date().getHours())
  if (label === 'morning') return 'mindmate.greetMorning'
  if (label === 'afternoon') return 'mindmate.greetAfternoon'
  return 'mindmate.greetEvening'
})
const greetText = computed(() => t(greetKey.value, { name: username.value }))

function splitAroundName(
  text: string,
  name: string
): { before: string; name: string; after: string } {
  const index = name ? text.indexOf(name) : -1
  if (index < 0) {
    return { before: text, name: '', after: '' }
  }
  return {
    before: text.slice(0, index),
    name,
    after: text.slice(index + name.length),
  }
}

const welcomeLead = computed(() => resolveBilingual('mindmate.welcomeLead', welcomeParams.value))
const leadPrimary = computed(() => splitAroundName(welcomeLead.value.primary, displayName.value))
const leadSecondary = computed(() =>
  welcomeLead.value.secondary
    ? splitAroundName(welcomeLead.value.secondary, displayName.value)
    : null
)
</script>

<template>
  <div
    v-if="isFullpageMode"
    class="welcome-fullpage"
  >
    <div class="welcome-hero">
      <MindmateAgentAvatar
        :size="96"
        branding-size="lg"
        avatar-class="mm-welcome-avatar"
      />
      <div class="welcome-copy">
        <div class="welcome-title">{{ greetText }}</div>
        <div class="welcome-subtitle">
          <span>{{ leadPrimary.before }}</span
          ><span
            v-if="leadPrimary.name"
            class="welcome-agent"
            >{{ leadPrimary.name }}</span
          ><span>{{ leadPrimary.after }}</span>
        </div>
        <div
          v-if="leadSecondary"
          class="welcome-subtitle-alt"
        >
          <span>{{ leadSecondary.before }}</span
          ><span
            v-if="leadSecondary.name"
            class="welcome-agent"
            >{{ leadSecondary.name }}</span
          ><span>{{ leadSecondary.after }}</span>
        </div>
      </div>
    </div>
    <div
      v-if="showModeSwitch"
      class="welcome-mode-row"
    >
      <MindmateHomeModeSwitch
        :mode="homeMode"
        @update:mode="emit('update:homeMode', $event)"
      />
    </div>
  </div>

  <div
    v-else
    class="welcome-panel"
  >
    <div
      class="welcome-card bg-gradient-to-br from-primary-50 to-purple-50 dark:from-gray-700 dark:to-gray-600 rounded-xl p-6 text-center"
    >
      <MindmateAgentAvatar
        :size="64"
        branding-size="md"
        avatar-class="mindmate-avatar mx-auto mb-3"
      />
      <p class="text-sm font-medium text-gray-800 dark:text-gray-200 mb-1">
        {{ displayName }}
      </p>
      <p class="text-sm text-gray-600 dark:text-gray-300">
        <I18nText
          k="mindmate.welcome"
          :params="welcomeParams"
          align="center"
        />
      </p>
      <MindmateHomeModeSwitch
        v-if="showModeSwitch"
        :mode="homeMode"
        @update:mode="emit('update:homeMode', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
@import './mindmate.css';

.welcome-fullpage {
  align-items: flex-start;
}

.welcome-mode-row {
  display: flex;
  justify-content: center;
  width: 100%;
}

.welcome-hero {
  display: flex;
  align-items: flex-start;
  gap: 20px;
  width: 100%;
  text-align: left;
}

.welcome-copy {
  min-width: 0;
  padding-top: 6px;
}

.welcome-title,
.welcome-subtitle {
  font-size: 1.75rem;
  letter-spacing: -0.02em;
  line-height: 1.4;
  color: #1c1917;
}

.welcome-title {
  font-weight: 400;
}

.welcome-subtitle {
  margin-top: 6px;
  font-weight: 400;
}

.welcome-agent {
  font-weight: 400;
  background-image: linear-gradient(90deg, #9333ea 0%, #6366f1 48%, #2563eb 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.welcome-mode-row :deep(.mm-home-mode) {
  margin-top: 0;
  padding: 5px;
  gap: 6px;
}

.welcome-mode-row :deep(.mm-home-mode__btn) {
  gap: 8px;
  padding: 10px 20px;
  font-size: 16px;
}

.welcome-mode-row :deep(.mm-home-mode__icon) {
  width: 18px;
  height: 18px;
}

.welcome-subtitle-alt {
  margin-top: 2px;
  font-size: 0.875rem;
  line-height: 1.4;
  color: #a8a29e;
}

:global(.dark) .welcome-title,
:global(.dark) .welcome-subtitle {
  color: #f5f5f4;
}
</style>
