<script setup lang="ts">
/**
 * Bottom Mind Classroom entry — mint blob tutor holding chalk mind-map board (QQ edge dock).
 */
import { computed, ref } from 'vue'

import { storeToRefs } from 'pinia'

import { ElDialog } from 'element-plus'

import { ChevronDown } from '@lucide/vue'

import MindClassroomLaunchContent from '@/components/canvas/MindClassroomLaunchContent.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useDiagramStore, useMindClassroomStore } from '@/stores'

const { t } = useLanguage()
const diagramStore = useDiagramStore()
const classroomStore = useMindClassroomStore()
const { modalOpen } = storeToRefs(classroomStore)

/** Session-only tuck; hover bottom edge to reveal again. */
const docked = ref(false)
const bubbleVisible = ref(true)
const peekHover = ref(false)

const showEntry = computed(() => Boolean(diagramStore.data?.nodes?.length))

const isPeeking = computed(() => docked.value && !peekHover.value)

function handleSpriteClick(): void {
  if (docked.value && isPeeking.value) {
    docked.value = false
    peekHover.value = false
    return
  }
  if (docked.value) {
    docked.value = false
    peekHover.value = false
  }
  classroomStore.openModal()
}

function handleDock(event: Event): void {
  event.stopPropagation()
  docked.value = true
  peekHover.value = false
  bubbleVisible.value = false
}

function handleHotzoneEnter(): void {
  if (docked.value) peekHover.value = true
}

function handleHotzoneLeave(): void {
  peekHover.value = false
}

function handleHotzoneReveal(event: PointerEvent): void {
  if (!docked.value) return
  event.preventDefault()
  peekHover.value = true
}

function handleRootEnter(): void {
  if (docked.value) peekHover.value = true
}

function handleRootLeave(event: MouseEvent): void {
  const related = event.relatedTarget as Node | null
  const root = event.currentTarget as HTMLElement
  if (related && root.contains(related)) return
  peekHover.value = false
}

function handleModalClose(): void {
  classroomStore.closeModal()
}

function handleStarted(): void {
  classroomStore.closeModal()
}
</script>

<template>
  <div
    v-if="showEntry"
    class="mc-sprite-root pointer-events-none"
    :class="{
      'is-docked': docked,
      'is-peeking': isPeeking,
      'is-revealed': docked && peekHover,
    }"
    @mouseenter="handleRootEnter"
    @mouseleave="handleRootLeave"
  >
    <div
      class="mc-sprite-hotzone pointer-events-auto"
      aria-hidden="true"
      @mouseenter="handleHotzoneEnter"
      @mouseleave="handleHotzoneLeave"
      @pointerdown="handleHotzoneReveal"
    />

    <div class="mc-sprite-stack pointer-events-auto">
      <Transition name="mc-bubble">
        <div
          v-if="bubbleVisible && !docked"
          class="mc-sprite__bubble"
        >
          {{ t('canvas.mindClassroom.mascotBubble') }}
        </div>
      </Transition>

      <button
        type="button"
        class="mc-sprite"
        :aria-label="t('canvas.mindClassroom.title')"
        aria-haspopup="dialog"
        :aria-expanded="modalOpen"
        @click="handleSpriteClick"
      >
        <svg
          class="mc-sprite__art"
          viewBox="0 0 160 150"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <defs>
            <radialGradient
              id="mcIpBody"
              cx="36%"
              cy="30%"
              r="70%"
            >
              <stop
                offset="0%"
                stop-color="#f0fdfa"
              />
              <stop
                offset="40%"
                stop-color="#99f6e4"
              />
              <stop
                offset="78%"
                stop-color="#5eead4"
              />
              <stop
                offset="100%"
                stop-color="#2dd4bf"
              />
            </radialGradient>
            <radialGradient
              id="mcIpInner"
              cx="42%"
              cy="36%"
              r="52%"
            >
              <stop
                offset="0%"
                stop-color="#ffffff"
                stop-opacity="0.55"
              />
              <stop
                offset="100%"
                stop-color="#ffffff"
                stop-opacity="0"
              />
            </radialGradient>
            <linearGradient
              id="mcIpHorn"
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop
                offset="0%"
                stop-color="#5eead4"
              />
              <stop
                offset="100%"
                stop-color="#0d9488"
              />
            </linearGradient>
            <linearGradient
              id="mcIpWood"
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop
                offset="0%"
                stop-color="#fde68a"
              />
              <stop
                offset="55%"
                stop-color="#fbbf24"
              />
              <stop
                offset="100%"
                stop-color="#d97706"
              />
            </linearGradient>
            <linearGradient
              id="mcIpSlate"
              x1="0"
              y1="0"
              x2="1"
              y2="1"
            >
              <stop
                offset="0%"
                stop-color="#334155"
              />
              <stop
                offset="100%"
                stop-color="#0f172a"
              />
            </linearGradient>
            <radialGradient
              id="mcIpFloor"
              cx="50%"
              cy="50%"
              r="50%"
            >
              <stop
                offset="0%"
                stop-color="#99f6e4"
                stop-opacity="0.5"
              />
              <stop
                offset="100%"
                stop-color="#67e8f9"
                stop-opacity="0"
              />
            </radialGradient>
          </defs>

          <!-- soft ambience -->
          <ellipse
            class="mc-art__glow"
            cx="80"
            cy="138"
            rx="54"
            ry="8"
            fill="url(#mcIpFloor)"
          />
          <circle
            class="mc-art__bubble mc-art__bubble--a"
            cx="22"
            cy="48"
            r="5"
            fill="#bae6fd"
            opacity="0.35"
          />
          <circle
            class="mc-art__bubble mc-art__bubble--b"
            cx="142"
            cy="36"
            r="7"
            fill="#a5f3fc"
            opacity="0.32"
          />
          <circle
            class="mc-art__bubble mc-art__bubble--c"
            cx="148"
            cy="78"
            r="4"
            fill="#fde68a"
            opacity="0.4"
          />

          <!-- blob body (behind board) -->
          <g class="mc-art__body">
            <!-- horn -->
            <path
              d="M80 8l7 18H73Z"
              fill="url(#mcIpHorn)"
            />
            <circle
              cx="80"
              cy="48"
              r="38"
              fill="url(#mcIpBody)"
            />
            <circle
              cx="80"
              cy="48"
              r="38"
              fill="url(#mcIpInner)"
            />
            <circle
              cx="80"
              cy="48"
              r="37"
              fill="none"
              stroke="#ffffff"
              stroke-width="1.2"
              opacity="0.3"
            />

            <!-- face -->
            <g class="mc-art__face">
              <g class="mc-art__eye mc-art__eye--left">
                <ellipse
                  cx="68"
                  cy="44"
                  rx="2.4"
                  ry="4.2"
                  fill="#0f172a"
                />
              </g>
              <g class="mc-art__eye mc-art__eye--right">
                <ellipse
                  cx="92"
                  cy="44"
                  rx="2.4"
                  ry="4.2"
                  fill="#0f172a"
                />
              </g>
              <path
                d="M76 56h8"
                stroke="#0f172a"
                stroke-width="2.2"
                stroke-linecap="round"
              />
            </g>

            <!-- feet peeking under board -->
            <ellipse
              cx="64"
              cy="98"
              rx="8"
              ry="5"
              fill="#14b8a6"
            />
            <ellipse
              cx="96"
              cy="98"
              rx="8"
              ry="5"
              fill="#14b8a6"
            />
          </g>

          <!-- easel legs -->
          <g class="mc-art__easel">
            <path
              d="M54 118l7-16"
              stroke="#f59e0b"
              stroke-width="3.2"
              stroke-linecap="round"
            />
            <path
              d="M106 118l-7-16"
              stroke="#f59e0b"
              stroke-width="3.2"
              stroke-linecap="round"
            />
            <path
              d="M61 112h38"
              stroke="#fbbf24"
              stroke-width="2.2"
              stroke-linecap="round"
              opacity="0.85"
            />
          </g>

          <!-- chalk board (narrower, closer to body width) -->
          <g class="mc-art__board">
            <rect
              x="38"
              y="62"
              width="84"
              height="50"
              rx="6"
              fill="url(#mcIpWood)"
            />
            <rect
              x="43"
              y="67"
              width="74"
              height="40"
              rx="4"
              fill="url(#mcIpSlate)"
            />
            <!-- chalk mind map -->
            <g class="mc-art__chalkmap">
              <!-- center topic -->
              <rect
                x="48"
                y="82"
                width="8"
                height="8"
                rx="1.5"
                fill="#f9a8d4"
                opacity="0.95"
              />
              <!-- upper branch (orange) -->
              <path
                d="M56 84c8-1 14-5 22-7"
                fill="none"
                stroke="#fb923c"
                stroke-width="1.6"
                stroke-linecap="round"
                opacity="0.95"
              />
              <ellipse
                cx="80"
                cy="75"
                rx="4.5"
                ry="2.8"
                fill="#fdba74"
              />
              <ellipse
                cx="94"
                cy="74"
                rx="4"
                ry="2.5"
                fill="#fed7aa"
              />
              <path
                d="M84.5 74.5h6"
                fill="none"
                stroke="#fb923c"
                stroke-width="1.2"
                stroke-linecap="round"
              />
              <!-- middle branch (violet) -->
              <path
                d="M56 86h24"
                fill="none"
                stroke="#a78bfa"
                stroke-width="1.6"
                stroke-linecap="round"
              />
              <ellipse
                cx="86"
                cy="86"
                rx="4.5"
                ry="2.8"
                fill="#c4b5fd"
              />
              <ellipse
                cx="100"
                cy="86"
                rx="4"
                ry="2.5"
                fill="#ddd6fe"
              />
              <path
                d="M90.5 86h5.5"
                fill="none"
                stroke="#a78bfa"
                stroke-width="1.2"
                stroke-linecap="round"
              />
              <!-- lower branch (teal) -->
              <path
                d="M56 88c9 2 16 7 24 9"
                fill="none"
                stroke="#2dd4bf"
                stroke-width="1.6"
                stroke-linecap="round"
              />
              <ellipse
                cx="82"
                cy="99"
                rx="4.5"
                ry="2.8"
                fill="#5eead4"
              />
              <ellipse
                cx="96"
                cy="100"
                rx="4"
                ry="2.5"
                fill="#99f6e4"
              />
              <path
                d="M86.5 99.5h6"
                fill="none"
                stroke="#2dd4bf"
                stroke-width="1.2"
                stroke-linecap="round"
              />
            </g>
          </g>

          <!-- flipper hands holding board -->
          <g class="mc-art__hands">
            <ellipse
              class="mc-art__hand mc-art__hand--left"
              cx="40"
              cy="88"
              rx="6.5"
              ry="8.5"
              fill="#14b8a6"
            />
            <ellipse
              class="mc-art__hand mc-art__hand--right"
              cx="120"
              cy="88"
              rx="6.5"
              ry="8.5"
              fill="#14b8a6"
            />
          </g>
        </svg>
      </button>

      <button
        v-if="!docked"
        type="button"
        class="mc-sprite__dock"
        :aria-label="t('canvas.mindClassroom.mascotDismiss')"
        :title="t('canvas.mindClassroom.mascotDismiss')"
        @click="handleDock"
      >
        <ChevronDown
          class="h-3.5 w-3.5"
          :stroke-width="2.5"
        />
      </button>
    </div>
  </div>

  <ElDialog
    v-model="modalOpen"
    :title="t('canvas.mindClassroom.title')"
    width="600px"
    align-center
    append-to-body
    destroy-on-close
    class="mc-classroom-dialog"
    @close="handleModalClose"
  >
    <MindClassroomLaunchContent
      variant="modal"
      @started="handleStarted"
    />
  </ElDialog>
</template>

<style scoped src="./mindClassroomMascot.css"></style>

<style>
.mc-classroom-dialog.el-dialog {
  border-radius: 18px;
  overflow: hidden;
}

.mc-classroom-dialog .el-dialog__header {
  padding: 18px 22px 8px;
  margin: 0;
}

.mc-classroom-dialog .el-dialog__title {
  font-size: 18px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: 0.01em;
}

.mc-classroom-dialog .el-dialog__headerbtn {
  top: 16px;
  right: 16px;
  width: 32px;
  height: 32px;
}

.mc-classroom-dialog .el-dialog__body {
  padding: 4px 22px 20px;
}

@media (max-width: 640px) {
  .mc-classroom-dialog.el-dialog {
    width: calc(100vw - 24px) !important;
  }
}
</style>
