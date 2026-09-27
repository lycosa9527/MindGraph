<script setup lang="ts">
/**
 * Session-expired re-login: same white card form as `/auth`.
 */
import AuthLegalFooter from '@/components/auth/AuthLegalFooter.vue'
import LoginModal from '@/components/auth/LoginModal.vue'
import '@/styles/authPageCard.css'

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'success'): void
}>()
</script>

<template>
  <div
    v-if="visible"
    class="session-auth-overlay"
  >
    <section
      class="auth-page-card session-auth-overlay__card"
      data-tsec-anchor
    >
      <div class="auth-page-card__form">
        <LoginModal
          :visible="true"
          auth-page
          light-backdrop
          persistent
          @success="emit('success')"
        />
        <AuthLegalFooter />
      </div>
    </section>
  </div>
</template>

<style scoped>
.session-auth-overlay {
  position: fixed;
  inset: 0;
  z-index: 4100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: max(1.25rem, env(safe-area-inset-top, 0px))
    max(1rem, env(safe-area-inset-right, 0px)) max(1.5rem, env(safe-area-inset-bottom, 0px))
    max(1rem, env(safe-area-inset-left, 0px));
  background: rgb(15 23 42 / 0.45);
  backdrop-filter: blur(10px);
}

.session-auth-overlay__card {
  max-height: min(calc(100dvh - 2.5rem), 52rem);
}
</style>
