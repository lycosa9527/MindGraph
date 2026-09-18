<script setup lang="ts">
/**
 * Showcase-style diagram case card for Learning Space lists.
 */
defineProps<{
  title: string
  description?: string
  coverUrl?: string | null
  meta?: string
  badge?: string
  active?: boolean
}>()

defineEmits<{
  click: []
}>()
</script>

<template>
  <article
    role="button"
    tabindex="0"
    class="ls-case-card"
    :class="{ 'ls-case-card--active': active }"
    @click="$emit('click')"
    @keydown.enter.prevent="$emit('click')"
    @keydown.space.prevent="$emit('click')"
  >
    <div
      class="ls-case-card__cover"
      :class="coverUrl ? 'ls-case-card__cover--media' : 'ls-case-card__cover--fallback'"
    >
      <img
        v-if="coverUrl"
        :src="coverUrl"
        :alt="title"
        loading="lazy"
        class="ls-case-card__img"
      />
      <span
        v-if="badge"
        class="ls-case-card__badge"
      >{{ badge }}</span>
    </div>
    <div class="ls-case-card__body">
      <h3 class="ls-case-card__title">{{ title }}</h3>
      <p
        v-if="description"
        class="ls-case-card__desc"
      >
        {{ description }}
      </p>
      <p
        v-if="meta"
        class="ls-case-card__meta"
      >
        {{ meta }}
      </p>
    </div>
  </article>
</template>

<style scoped>
.ls-case-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 0.75rem;
  border: 1px solid #f3f4f6;
  background: #fff;
  text-align: left;
  cursor: pointer;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.04);
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;
}
.ls-case-card:hover,
.ls-case-card:focus-visible {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgb(0 0 0 / 0.08);
  outline: none;
}
.ls-case-card--active {
  border-color: #a8a29e;
  box-shadow: 0 0 0 2px #e7e5e4;
}
.ls-case-card__cover {
  position: relative;
  aspect-ratio: 5 / 3;
  width: 100%;
  overflow: hidden;
}
.ls-case-card__cover--media {
  background: #f3f4f6;
}
.ls-case-card__cover--fallback {
  background: linear-gradient(135deg, #e7e5e4 0%, #fafaf9 55%, #d6d3d1 100%);
}
.ls-case-card__img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
}
.ls-case-card__badge {
  position: absolute;
  top: 0.5rem;
  left: 0.5rem;
  z-index: 1;
  border-radius: 999px;
  background: rgb(28 25 23 / 0.82);
  color: #fff;
  font-size: 0.625rem;
  font-weight: 700;
  padding: 0.2rem 0.5rem;
}
.ls-case-card__body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 0.2rem;
  padding: 0.55rem 0.65rem 0.75rem;
}
.ls-case-card__title {
  margin: 0;
  font-size: 0.8125rem;
  font-weight: 650;
  line-height: 1.25;
  color: #111827;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ls-case-card__desc,
.ls-case-card__meta {
  margin: 0;
  font-size: 0.6875rem;
  line-height: 1.35;
  color: #6b7280;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ls-case-card__meta {
  margin-top: auto;
  -webkit-line-clamp: 1;
  color: #78716c;
}
</style>
