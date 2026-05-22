<script setup lang="ts">
/**
 * Compact diagram pairing summary for Mobile Kitty bottom bar (camera · card · mic).
 * Tap opens the saved-diagram picker dropdown.
 */
import { ChevronDown } from 'lucide-vue-next'

defineProps<{
  /** First line e.g. "Current diagram: My topic" */
  primaryLine: string
  /** Optional second line type · scope id */
  metaLine?: string | null
  /** Hub bootstrap source badge (localized short label) */
  sourceBadge?: string | null
  /** Accessible label summarizing pairing state */
  ariaLabel: string
  /** Dropdown open — rotates chevron */
  expanded?: boolean
  disabled?: boolean
}>()
</script>

<template>
  <div
    class="kitty-mobile-diag-card"
    :class="{
      'kitty-mobile-diag-card--open': expanded,
      'kitty-mobile-diag-card--disabled': disabled,
    }"
    role="button"
    tabindex="0"
    :aria-label="ariaLabel"
    :aria-expanded="expanded ?? false"
  >
    <div class="kitty-mobile-diag-card__body">
      <div
        class="kitty-mobile-diag-card__primary"
        :title="primaryLine"
      >
        {{ primaryLine }}
      </div>
      <div
        v-if="metaLine || sourceBadge"
        class="kitty-mobile-diag-card__meta-row"
      >
        <span
          v-if="metaLine"
          class="kitty-mobile-diag-card__meta"
          :title="metaLine"
        >
          {{ metaLine }}
        </span>
        <span
          v-if="sourceBadge"
          class="kitty-mobile-diag-card__badge"
          :title="sourceBadge"
        >
          {{ sourceBadge }}
        </span>
      </div>
    </div>
    <ChevronDown
      class="kitty-mobile-diag-card__chevron"
      :class="{ 'kitty-mobile-diag-card__chevron--open': expanded }"
      aria-hidden="true"
    />
  </div>
</template>

<style scoped>
.kitty-mobile-diag-card {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 0.25rem;
  width: 100%;
  height: 100%;
  min-height: 0;
  padding: 0.375rem 0.5rem;
  border: 1px solid #e7e5e4;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
  text-align: left;
  touch-action: manipulation;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}

.kitty-mobile-diag-card:active:not(.kitty-mobile-diag-card--disabled) {
  background: #fafaf9;
}

.kitty-mobile-diag-card--open {
  border-color: #d6d3d1;
  background: #fafaf9;
}

.kitty-mobile-diag-card--disabled {
  opacity: 0.45;
  pointer-events: none;
}

.kitty-mobile-diag-card__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.125rem;
}

.kitty-mobile-diag-card__primary {
  font-size: clamp(0.625rem, 2.8vw, 0.6875rem);
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: 0.01em;
  color: #1c1917;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kitty-mobile-diag-card__meta-row {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  min-width: 0;
}

.kitty-mobile-diag-card__meta {
  flex: 1;
  min-width: 0;
  font-size: clamp(0.5625rem, 2.4vw, 0.625rem);
  font-weight: 500;
  line-height: 1.2;
  letter-spacing: 0.02em;
  color: #78716c;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kitty-mobile-diag-card__badge {
  flex-shrink: 0;
  max-width: 42%;
  padding: 0.0625rem 0.25rem;
  border-radius: 4px;
  background: #f5f5f4;
  color: #57534e;
  font-size: clamp(0.5rem, 2.2vw, 0.5625rem);
  font-weight: 600;
  letter-spacing: 0.03em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kitty-mobile-diag-card__chevron {
  width: clamp(0.875rem, 3.8vw, 1rem);
  height: clamp(0.875rem, 3.8vw, 1rem);
  flex-shrink: 0;
  color: #a8a29e;
  transition: transform 0.2s ease;
}

.kitty-mobile-diag-card__chevron--open {
  transform: rotate(180deg);
}
</style>
