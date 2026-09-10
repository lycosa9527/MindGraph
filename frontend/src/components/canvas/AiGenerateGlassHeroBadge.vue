<script setup lang="ts">
/**
 * Corner badge icon for the Swiss glass hero plate.
 */
import {
  GraduationCap,
  Hammer,
  Lightbulb,
  Link2,
  MessageSquare,
  Mic,
  PenLine,
  Sparkles,
  Upload,
} from '@lucide/vue'

defineProps<{
  variant:
    | 'doc'
    | 'web'
    | 'voice'
    | 'chat'
    | 'classroom'
    | 'learningSheet'
    | 'brainstorm'
    | 'oneSentence'
    | 'link'
}>()
</script>

<template>
  <span class="ai-glass-icon__badge">
    <Upload
      v-if="variant === 'doc'"
      :size="12"
      :stroke-width="2.4"
    />
    <Link2
      v-else-if="variant === 'web'"
      :size="12"
      :stroke-width="2.4"
    />
    <Mic
      v-else-if="variant === 'voice'"
      :size="12"
      :stroke-width="2.4"
    />
    <GraduationCap
      v-else-if="variant === 'classroom'"
      :size="12"
      :stroke-width="2.4"
    />
    <Hammer
      v-else-if="variant === 'learningSheet'"
      :size="12"
      :stroke-width="2.4"
    />
    <Lightbulb
      v-else-if="variant === 'brainstorm'"
      :size="12"
      :stroke-width="2.4"
    />
    <Sparkles
      v-else-if="variant === 'oneSentence'"
      :size="12"
      :stroke-width="2.4"
    />
    <PenLine
      v-else-if="variant === 'link'"
      :size="12"
      :stroke-width="2.4"
    />
    <MessageSquare
      v-else
      :size="12"
      :stroke-width="2.4"
    />
  </span>
</template>
