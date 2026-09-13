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
    icon?: Component
    badge?: Component
  }>(),
  { showClose: true, compact: false, ribbon: '', title: '', line1: '', line2: '' }
)

const emit = defineEmits<{ close: [] }>()

const { t } = useLanguage()

const copy = computed(() => {
  if (props.title || props.ribbon || props.line1) {
    return {
      ribbon: props.ribbon,
      title: props.title,
      line1: props.line1,
      line2: props.line2,
    }
  }
  if (props.variant) {
    return {
      ribbon: t(`canvas.ribbon.aiHero.${props.variant}.ribbon`),
      title: t(`canvas.ribbon.aiHero.${props.variant}.title`),
      line1: t(`canvas.ribbon.aiHero.${props.variant}.line1`),
      line2: t(`canvas.ribbon.aiHero.${props.variant}.line2`),
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
const showAudience = computed(
  () => Boolean(props.variant && AUDIENCE_HERO_VARIANTS.has(props.variant))
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
      <span class="ai-glass-hero__ribbon">{{ copy.ribbon }}</span>
      <MindMapSidePanelCloseButton
        v-if="showClose"
        @close="emit('close')"
      />
    </div>

    <h2 class="ai-glass-hero__title">{{ copy.title }}</h2>
    <div class="ai-glass-hero__lines">
      <span class="ai-glass-hero__line">{{ copy.line1 }}</span>
      <span
        v-if="copy.line2"
        class="ai-glass-hero__line"
      >{{ copy.line2 }}</span>
      <ProfessionalContentAudienceBanner
        v-if="showAudience"
        appearance="hero"
      />
    </div>
  </div>
</template>
