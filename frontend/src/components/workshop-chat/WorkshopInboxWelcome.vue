<script setup lang="ts">
/**
 * Default Workshop landing: welcome copy and a lightweight inbox summary.
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { Hash, Inbox, MessageSquare } from 'lucide-vue-next'

import { useLanguage } from '@/composables/core/useLanguage'
import { useWorkshopChatStore } from '@/stores/workshopChat'

const { t } = useLanguage()
const store = useWorkshopChatStore()
const router = useRouter()

const unreadChannels = computed(() => store.totalUnreadChannels)
const unreadDms = computed(() => store.totalUnreadDMs)

const recentDmThreads = computed(() =>
  [...store.dmConversations]
    .filter((c) => c.last_message?.created_at)
    .sort((a, b) => {
      const da = a.last_message?.created_at
      const db = b.last_message?.created_at
      if (!da || !db) return 0
      return new Date(db).getTime() - new Date(da).getTime()
    })
    .slice(0, 8)
)

function openRecentDm(partnerId: number): void {
  store.leaveWorkshopHomeView()
  store.selectDMPartner(partnerId)
  store.selectChannel(null)
  store.activeTab = 'dms'
  void router.push('/workshop-chat')
}
</script>

<template>
  <div class="wi-welcome">
    <header class="wi-welcome__hero">
      <h1 class="wi-welcome__title">{{ t('workshop.welcomeTitle') }}</h1>
      <p class="wi-welcome__subtitle">{{ t('workshop.welcomeSubtitle') }}</p>
      <p class="wi-welcome__intro">{{ t('workshop.welcomeIntro') }}</p>
    </header>

    <section
      class="wi-welcome__inbox"
      aria-labelledby="wi-inbox-heading"
    >
      <h2
        id="wi-inbox-heading"
        class="wi-welcome__section-title"
      >
        <Inbox
          :size="18"
          class="wi-welcome__section-icon"
        />
        {{ t('workshop.inboxSummaryTitle') }}
      </h2>
      <div class="wi-welcome__stats">
        <div class="wi-welcome__stat">
          <Hash
            :size="16"
            class="wi-welcome__stat-icon"
          />
          <span class="wi-welcome__stat-label">{{ t('workshop.inboxUnreadChannels') }}</span>
          <span class="wi-welcome__stat-value">{{ unreadChannels }}</span>
        </div>
        <div class="wi-welcome__stat">
          <MessageSquare
            :size="16"
            class="wi-welcome__stat-icon"
          />
          <span class="wi-welcome__stat-label">{{ t('workshop.inboxUnreadDms') }}</span>
          <span class="wi-welcome__stat-value">{{ unreadDms }}</span>
        </div>
      </div>
      <p class="wi-welcome__hint">{{ t('workshop.inboxHintPickChannel') }}</p>
    </section>

    <section
      v-if="recentDmThreads.length > 0"
      class="wi-welcome__recent"
      aria-labelledby="wi-recent-heading"
    >
      <h2
        id="wi-recent-heading"
        class="wi-welcome__section-title"
      >
        {{ t('workshop.recentDmActivity') }}
      </h2>
      <ul class="wi-welcome__recent-list">
        <li
          v-for="conv in recentDmThreads"
          :key="conv.partner_id"
          class="wi-welcome__recent-item"
        >
          <button
            type="button"
            class="wi-welcome__recent-btn"
            @click="openRecentDm(conv.partner_id)"
          >
            <span class="wi-welcome__recent-name">{{ conv.partner_name }}</span>
            <span
              v-if="conv.unread_count > 0"
              class="wi-welcome__recent-unread"
              >{{ conv.unread_count }}</span
            >
          </button>
        </li>
      </ul>
    </section>

    <section
      class="wi-welcome__explain"
      aria-labelledby="wi-how-heading"
    >
      <h2
        id="wi-how-heading"
        class="wi-welcome__section-title"
      >
        {{ t('workshop.welcomeHowTitle') }}
      </h2>

      <div class="wi-welcome__cards">
        <article class="wi-card">
          <h3 class="wi-card__title">{{ t('workshop.welcomeChannelsTitle') }}</h3>
          <p class="wi-card__body">{{ t('workshop.welcomeChannelsBody') }}</p>
        </article>
        <article class="wi-card">
          <h3 class="wi-card__title">{{ t('workshop.welcomeLessonStudyTitle') }}</h3>
          <p class="wi-card__body">{{ t('workshop.welcomeLessonStudyBody') }}</p>
        </article>
        <article class="wi-card">
          <h3 class="wi-card__title">{{ t('workshop.welcomeConversationsTitle') }}</h3>
          <p class="wi-card__body">{{ t('workshop.welcomeConversationsBody') }}</p>
        </article>
        <article class="wi-card">
          <h3 class="wi-card__title">{{ t('workshop.welcomeMessagesTitle') }}</h3>
          <p class="wi-card__body">{{ t('workshop.welcomeMessagesBody') }}</p>
        </article>
      </div>

      <figure
        class="wi-example"
        aria-label="Workshop structure example"
      >
        <figcaption class="wi-example__caption">
          {{ t('workshop.welcomeExampleCaption') }}
        </figcaption>
        <div class="wi-example__body">
          <div class="wi-example__org">{{ t('workshop.welcomeExampleOrg') }}</div>

          <div class="wi-example__groups">
            <div class="wi-example__group">
              <div class="wi-example__group-title">{{ t('workshop.welcomeExampleGroupMath') }}</div>

              <div class="wi-example__ls">
                <div class="wi-example__ls-title">{{ t('workshop.welcomeExampleLSMath1') }}</div>
                <div class="wi-example__conv-head">{{ t('workshop.welcomeExampleConvLabel') }}</div>
                <ul class="wi-example__conv-list">
                  <li>{{ t('workshop.welcomeExampleLSMath1C1') }}</li>
                  <li>{{ t('workshop.welcomeExampleLSMath1C2') }}</li>
                  <li>{{ t('workshop.welcomeExampleLSMath1C3') }}</li>
                </ul>
              </div>

              <div class="wi-example__ls">
                <div class="wi-example__ls-title">{{ t('workshop.welcomeExampleLSMath2') }}</div>
                <div class="wi-example__conv-head">{{ t('workshop.welcomeExampleConvLabel') }}</div>
                <ul class="wi-example__conv-list">
                  <li>{{ t('workshop.welcomeExampleLSMath2C1') }}</li>
                </ul>
              </div>
            </div>

            <div class="wi-example__group">
              <div class="wi-example__group-title">
                {{ t('workshop.welcomeExampleGroupEnglish') }}
              </div>

              <div class="wi-example__ls">
                <div class="wi-example__ls-title">{{ t('workshop.welcomeExampleLSEng1') }}</div>
                <div class="wi-example__conv-head">{{ t('workshop.welcomeExampleConvLabel') }}</div>
                <ul class="wi-example__conv-list">
                  <li>{{ t('workshop.welcomeExampleLSEng1C1') }}</li>
                  <li>{{ t('workshop.welcomeExampleLSEng1C2') }}</li>
                  <li>{{ t('workshop.welcomeExampleLSEng1C3') }}</li>
                </ul>
              </div>

              <div class="wi-example__ls">
                <div class="wi-example__ls-title">{{ t('workshop.welcomeExampleLSEng2') }}</div>
                <div class="wi-example__conv-head">{{ t('workshop.welcomeExampleConvLabel') }}</div>
                <ul class="wi-example__conv-list">
                  <li>{{ t('workshop.welcomeExampleLSEng2C1') }}</li>
                </ul>
              </div>
            </div>
          </div>

          <p class="wi-example__msg-foot">{{ t('workshop.welcomeExampleMsgLabel') }}</p>
        </div>
      </figure>
    </section>
  </div>
</template>

<style scoped>
.wi-welcome {
  box-sizing: border-box;
  width: 100%;
  flex: 1;
  min-height: 0;
  padding: 28px 20px 40px;
  overflow-y: auto;
  overflow-x: hidden;
  color: hsl(0deg 0% 15%);
}

.wi-welcome__hero {
  margin-bottom: 28px;
}

.wi-welcome__title {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: hsl(210deg 36% 22%);
}

.wi-welcome__subtitle {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
  color: hsl(228deg 35% 38%);
}

.wi-welcome__intro {
  margin: 0;
  font-size: 14px;
  line-height: 1.55;
  color: hsl(0deg 0% 38%);
}

.wi-welcome__section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: hsl(0deg 0% 40%);
}

.wi-welcome__section-icon {
  opacity: 0.65;
}

.wi-welcome__inbox {
  padding: 16px 18px;
  margin-bottom: 28px;
  background: hsl(0deg 0% 100%);
  border: 1px solid hsl(0deg 0% 0% / 12%);
  border-radius: 10px;
  box-shadow: 0 1px 3px hsl(0deg 0% 0% / 5%);
}

.wi-welcome__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.wi-welcome__stat {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: hsl(228deg 56% 58% / 8%);
  border-radius: 8px;
  font-size: 13px;
}

.wi-welcome__stat-icon {
  color: hsl(228deg 45% 48%);
  opacity: 0.85;
}

.wi-welcome__stat-label {
  color: hsl(0deg 0% 35%);
}

.wi-welcome__stat-value {
  font-weight: 700;
  color: hsl(228deg 40% 38%);
  min-width: 1.25em;
}

.wi-welcome__hint {
  margin: 14px 0 0;
  font-size: 13px;
  line-height: 1.45;
  color: hsl(0deg 0% 45%);
}

.wi-welcome__recent {
  margin: 24px 0;
  padding: 16px;
  background: hsl(0deg 0% 100%);
  border: 1px solid hsl(0deg 0% 0% / 10%);
  border-radius: 8px;
}

.wi-welcome__recent-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.wi-welcome__recent-item {
  margin: 0;
}

.wi-welcome__recent-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 6px;
  background: hsl(228deg 56% 58% / 6%);
  font-size: 13px;
  color: hsl(210deg 36% 22%);
  cursor: pointer;
  text-align: left;
  transition: background 120ms ease;
}

.wi-welcome__recent-btn:hover {
  background: hsl(228deg 56% 58% / 12%);
}

.wi-welcome__recent-name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wi-welcome__recent-unread {
  flex-shrink: 0;
  margin-left: 8px;
  min-width: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: hsl(217deg 64% 59%);
  color: hsl(0deg 0% 100%);
  font-size: 11px;
  font-weight: 700;
  text-align: center;
}

.wi-welcome__cards {
  display: grid;
  gap: 12px;
  margin-bottom: 24px;
}

@media (width >= 560px) {
  .wi-welcome__cards {
    grid-template-columns: 1fr 1fr;
  }
}

.wi-card {
  padding: 14px 16px;
  background: hsl(0deg 0% 100%);
  border: 1px solid hsl(0deg 0% 0% / 10%);
  border-radius: 8px;
}

.wi-card__title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 700;
  color: hsl(210deg 28% 28%);
}

.wi-card__body {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: hsl(0deg 0% 38%);
}

.wi-example {
  margin: 0;
  padding: 16px 18px;
  background: hsl(228deg 30% 97%);
  border: 1px solid hsl(228deg 20% 88%);
  border-radius: 10px;
}

.wi-example__caption {
  margin: 0 0 14px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.45;
  color: hsl(0deg 0% 42%);
}

.wi-example__body {
  width: 100%;
}

.wi-example__org {
  margin-bottom: 14px;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 700;
  text-align: center;
  color: hsl(210deg 30% 24%);
  background: hsl(228deg 56% 58% / 14%);
  border: 1px solid hsl(228deg 40% 70% / 45%);
  border-radius: 8px;
}

.wi-example__groups {
  display: grid;
  gap: 14px;
}

@media (width >= 640px) {
  .wi-example__groups {
    grid-template-columns: 1fr 1fr;
    align-items: start;
  }
}

.wi-example__group {
  padding: 12px 12px 10px;
  background: hsl(0deg 0% 100%);
  border: 1px solid hsl(0deg 0% 0% / 10%);
  border-radius: 8px;
}

.wi-example__group-title {
  margin: 0 0 10px;
  padding-bottom: 8px;
  font-size: 13px;
  font-weight: 700;
  color: hsl(228deg 38% 32%);
  border-bottom: 1px solid hsl(0deg 0% 0% / 8%);
}

.wi-example__ls {
  margin-bottom: 12px;
}

.wi-example__ls:last-child {
  margin-bottom: 0;
}

.wi-example__ls-title {
  margin: 0 0 6px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
  color: hsl(210deg 22% 28%);
}

.wi-example__conv-head {
  margin: 0 0 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: hsl(0deg 0% 48%);
}

.wi-example__conv-list {
  margin: 0;
  padding: 0 0 0 16px;
  font-size: 11px;
  line-height: 1.45;
  color: hsl(0deg 0% 38%);
}

.wi-example__conv-list li {
  margin-bottom: 3px;
}

.wi-example__conv-list li:last-child {
  margin-bottom: 0;
}

.wi-example__msg-foot {
  margin: 14px 0 0;
  padding-top: 12px;
  border-top: 1px dashed hsl(0deg 0% 0% / 12%);
  font-size: 11px;
  line-height: 1.4;
  color: hsl(0deg 0% 45%);
  text-align: center;
}
</style>
