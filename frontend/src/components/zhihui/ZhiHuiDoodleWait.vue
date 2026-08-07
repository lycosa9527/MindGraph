<script setup lang="ts">
/**
 * Light doodle / sketch wait animation while DashScope generates an image.
 */
defineProps<{
  label?: string
}>()
</script>

<template>
  <div
    class="zhihui-doodle"
    role="status"
    aria-live="polite"
  >
    <svg
      class="zhihui-doodle__canvas"
      viewBox="0 0 160 96"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <!-- Soft paper frame -->
      <rect
        class="zhihui-doodle__frame"
        x="10"
        y="8"
        width="140"
        height="80"
        rx="10"
      />
      <!-- Squiggle strokes (drawn in sequence) -->
      <path
        class="zhihui-doodle__stroke zhihui-doodle__stroke--1"
        d="M28 36 C42 22, 58 50, 74 34 S102 20, 118 38"
      />
      <path
        class="zhihui-doodle__stroke zhihui-doodle__stroke--2"
        d="M32 58 C48 48, 62 70, 84 56 S112 44, 128 60"
      />
      <path
        class="zhihui-doodle__stroke zhihui-doodle__stroke--3"
        d="M40 74 C56 68, 70 78, 90 70 S118 66, 130 72"
      />
      <!-- Tiny star accents -->
      <path
        class="zhihui-doodle__spark zhihui-doodle__spark--a"
        d="M122 24 l2.2 5.4 5.8.4-4.4 3.6 1.4 5.6-4.9-3.2-4.9 3.2 1.4-5.6-4.4-3.6 5.8-.4z"
      />
      <path
        class="zhihui-doodle__spark zhihui-doodle__spark--b"
        d="M26 22 l1.4 3.4 3.6.2-2.8 2.2.8 3.5-3-2-3 2 .8-3.5-2.8-2.2 3.6-.2z"
      />
      <!-- Pencil tip -->
      <g class="zhihui-doodle__pencil">
        <path
          d="M118 70 L132 56 L138 62 L124 76 Z"
          fill="#d6d3d1"
          stroke="#78716c"
          stroke-width="1.2"
        />
        <path
          d="M132 56 L138 50 L144 56 L138 62 Z"
          fill="#fbbf24"
          stroke="#b45309"
          stroke-width="1.1"
        />
        <path
          d="M138 50 L142 46 L146 50 L142 54 Z"
          fill="#1c1917"
        />
      </g>
    </svg>
    <p
      v-if="label"
      class="zhihui-doodle__label"
    >
      {{ label }}
    </p>
  </div>
</template>

<style scoped>
.zhihui-doodle {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.65rem;
  padding: 0.25rem 0;
}

.zhihui-doodle__canvas {
  width: min(100%, 200px);
  height: auto;
}

.zhihui-doodle__frame {
  fill: #fafaf9;
  stroke: #e7e5e4;
  stroke-width: 1.5;
}

.zhihui-doodle__stroke {
  fill: none;
  stroke: #78716c;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 180;
  stroke-dashoffset: 180;
  animation: zhihuiDoodleDraw 2.8s ease-in-out infinite;
}

.zhihui-doodle__stroke--1 {
  animation-delay: 0s;
}

.zhihui-doodle__stroke--2 {
  animation-delay: 0.35s;
  stroke: #a8a29e;
}

.zhihui-doodle__stroke--3 {
  animation-delay: 0.7s;
  stroke: #d6d3d1;
}

.zhihui-doodle__spark {
  fill: #f59e0b;
  opacity: 0;
  transform-origin: center;
  animation: zhihuiDoodleSpark 2.8s ease-in-out infinite;
}

.zhihui-doodle__spark--a {
  animation-delay: 0.9s;
}

.zhihui-doodle__spark--b {
  animation-delay: 1.3s;
}

.zhihui-doodle__pencil {
  transform-origin: 130px 60px;
  animation: zhihuiDoodlePencil 2.8s ease-in-out infinite;
}

.zhihui-doodle__label {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: #78716c;
}

@keyframes zhihuiDoodleDraw {
  0% {
    stroke-dashoffset: 180;
    opacity: 0.35;
  }
  35% {
    stroke-dashoffset: 0;
    opacity: 1;
  }
  70% {
    stroke-dashoffset: 0;
    opacity: 1;
  }
  100% {
    stroke-dashoffset: 180;
    opacity: 0.35;
  }
}

@keyframes zhihuiDoodleSpark {
  0%,
  40% {
    opacity: 0;
    transform: scale(0.6);
  }
  55% {
    opacity: 1;
    transform: scale(1);
  }
  75%,
  100% {
    opacity: 0;
    transform: scale(0.7);
  }
}

@keyframes zhihuiDoodlePencil {
  0% {
    transform: translate(0, 0) rotate(-8deg);
  }
  25% {
    transform: translate(-18px, -10px) rotate(6deg);
  }
  50% {
    transform: translate(8px, 6px) rotate(-4deg);
  }
  75% {
    transform: translate(-10px, 4px) rotate(5deg);
  }
  100% {
    transform: translate(0, 0) rotate(-8deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .zhihui-doodle__stroke,
  .zhihui-doodle__spark,
  .zhihui-doodle__pencil {
    animation: none;
  }

  .zhihui-doodle__stroke {
    stroke-dashoffset: 0;
    opacity: 1;
  }

  .zhihui-doodle__spark {
    opacity: 0.7;
  }
}
</style>
