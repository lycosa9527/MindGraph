<script setup lang="ts">
/**
 * Swiss stone header for canvas dialogs — title block plus the small top-right menu.
 * Existing variants keep i18n lookup. Custom copy + Lucide icons skip that path.
 */
import { type Component, computed } from 'vue'

import { MessageSquare, Sparkles } from '@lucide/vue'

import AiGenerateGlassHeroBadge from '@/components/canvas/AiGenerateGlassHeroBadge.vue'
import AiGenerateGlassHeroGlyphs from '@/components/canvas/AiGenerateGlassHeroGlyphs.vue'
import MindMapSidePanelCloseButton from '@/components/canvas/MindMapSidePanelCloseButton.vue'
import ProfessionalContentAudienceBanner from '@/components/canvas/ProfessionalContentAudienceBanner.vue'
import '@/components/canvas/aiGenerateGlass.css'
import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables/core/useLanguage'

export type AiGlassHeroVariant =
  | 'doc'
  | 'web'
  | 'voice'
  | 'chat'
  | 'classroom'
  | 'learningSheet'
  | 'brainstorm'
  | 'oneSentence'
  | 'link'

const AUDIENCE_HERO_VARIANTS: ReadonlySet<AiGlassHeroVariant> = new Set([
  'doc',
  'web',
  'voice',
  'chat',
  'brainstorm',
  'oneSentence',
])

const props = withDefaults(
  defineProps<{
    variant?: AiGlassHeroVariant
    showClose?: boolean
    compact?: boolean
    ribbon?: string
    title?: string
    line1?: string
    line2?: string
    ribbonKey?: string
    titleKey?: string
    line1Key?: string
    line2Key?: string
    icon?: Component
    badge?: Component
  }>(),
  {
    showClose: true,
    compact: false,
    ribbon: '',
    title: '',
    line1: '',
    line2: '',
    ribbonKey: '',
    titleKey: '',
    line1Key: '',
    line2Key: '',
  }
)

const emit = defineEmits<{ close: [] }>()

const { t } = useLanguage()

const hasCustomCopy = computed(() => Boolean(props.title || props.ribbon || props.line1))

function variantMessageKey(part: 'ribbon' | 'title' | 'line1' | 'line2'): string {
  if (!props.variant) {
    return ''
  }
  return `canvas.ribbon.aiHero.${props.variant}.${part}`
}

function resolvedKey(explicitKey: string, part: 'ribbon' | 'title' | 'line1' | 'line2'): string {
  if (explicitKey) {
    return explicitKey
  }
  if (!hasCustomCopy.value && props.variant) {
    return variantMessageKey(part)
  }
  return ''
}

const ribbonMessageKey = computed(() => resolvedKey(props.ribbonKey, 'ribbon'))
const titleMessageKey = computed(() => resolvedKey(props.titleKey, 'title'))
const line1MessageKey = computed(() => resolvedKey(props.line1Key, 'line1'))
const line2MessageKey = computed(() => resolvedKey(props.line2Key, 'line2'))

const copy = computed(() => {
  if (hasCustomCopy.value) {
    return {
      ribbon: props.ribbon,
      title: props.title,
      line1: props.line1,
      line2: props.line2,
    }
  }
  if (props.variant) {
    return {
      ribbon: t(variantMessageKey('ribbon')),
      title: t(variantMessageKey('title')),
      line1: t(variantMessageKey('line1')),
      line2: t(variantMessageKey('line2')),
    }
  }
  return { ribbon: '', title: '', line1: '', line2: '' }
})

const heroClass = computed(() => {
  const classes = ['ai-glass-hero']
  if (props.variant) {
    classes.push(`ai-glass-hero--${props.variant}`)
  }
  if (props.compact) {
    classes.push('ai-glass-hero--compact')
  }
  return classes
})

const plateIcon = computed(() => props.icon ?? Sparkles)
const badgeIcon = computed(() => props.badge ?? MessageSquare)
const showAudience = computed(() =>
  Boolean(props.variant && AUDIENCE_HERO_VARIANTS.has(props.variant))
)
</script>

<template>
  <div :class="heroClass">
    <div
      class="ai-glass-hero__icon"
      aria-hidden="true"
    >
      <div class="ai-glass-icon__plate">
        <AiGenerateGlassHeroGlyphs
          v-if="variant && !icon"
          :variant="variant"
        />
        <component
          :is="plateIcon"
          v-else
          class="ai-glass-icon__glyph"
          :size="32"
          :stroke-width="2"
        />
      </div>
      <AiGenerateGlassHeroBadge
        v-if="variant && !badge"
        :variant="variant"
      />
      <span
        v-else
        class="ai-glass-icon__badge"
      >
        <component
          :is="badgeIcon"
          :size="12"
          :stroke-width="2.4"
        />
      </span>
    </div>

    <div class="ai-glass-hero__corner">
      <span class="ai-glass-hero__ribbon">
        <I18nText
          v-if="ribbonMessageKey"
          :k="ribbonMessageKey"
        />
        <template v-else>{{ copy.ribbon }}</template>
      </span>
      <MindMapSidePanelCloseButton
        v-if="showClose"
        @close="emit('close')"
      />
    </div>

    <h2 class="ai-glass-hero__title">
      <I18nText
        v-if="titleMessageKey"
        :k="titleMessageKey"
      />
      <template v-else>{{ copy.title }}</template>
    </h2>
    <div class="ai-glass-hero__lines">
      <span class="ai-glass-hero__line">
        <I18nText
          v-if="line1MessageKey"
          :k="line1MessageKey"
        />
        <template v-else>{{ copy.line1 }}</template>
      </span>
      <span
        v-if="line2MessageKey || copy.line2"
        class="ai-glass-hero__line"
      >
        <I18nText
          v-if="line2MessageKey"
          :k="line2MessageKey"
        />
        <template v-else>{{ copy.line2 }}</template>
      </span>
      <ProfessionalContentAudienceBanner
        v-if="showAudience"
        appearance="hero"
      />
    </div>
  </div>
</template>
