/**
 * Kitty — MindGraph mascot and VoiceAgent character (SVG, legacy `static/js/editor/black-cat.js`).
 * Voice integration deferred; retained for reuse.
 *
 * Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
 * All Rights Reserved
 *
 * @author WANG CUNCHI
 */

declare global {
  interface Window {
    logger?: Pick<Console, 'info'>
  }
}

export type KittyState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'celebrating' | 'error'

/** SVG-based mascot; wire to VoiceAgent flows when integrating. */
export class BlackCat {
  container: HTMLDivElement | null = null

  svgElement: SVGSVGElement | null = null

  state: KittyState = 'idle'

  onClick: (() => void) | null = null

  private readonly logger: Pick<Console, 'info'> = window.logger ?? console

  init(parentElement: HTMLElement = document.body): void {
    this.container = document.createElement('div')
    this.container.className = 'black-cat-container'
    this.container.title = '点我开始对话'

    this.container.innerHTML = this.getSvgMarkup()
    this.svgElement = this.container.querySelector('svg')

    this.container.addEventListener('click', () => {
      this.onClick?.()
    })

    parentElement.appendChild(this.container)

    this.logger.info('BlackCat', 'Kitty mascot initialized')
  }

  private getSvgMarkup(): string {
    return `
        <svg class="kitty-svg" width="100%" height="100%" viewBox="0 0 200 300" preserveAspectRatio="xMidYMax meet" fill="none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <style>
              .fur-dark { fill: #1f1f24; }
              .fur-leg { fill: #26262e; }
              .ear-inner { fill: #454552; }
              .sclera { fill: #fcfcfc; }
              .iris-left { fill: #89e289; }
              .iris-right { fill: #eecf68; }
              .pupil { fill: #111111; }
              .highlight { fill: #ffffff; opacity: 0.9; }
              .bow-main { fill: #d93636; }
              .bow-knot { fill: #b52828; }
              .bow-highlight { fill: #e85555; opacity: 0.5; }
              .tail-wrapper {
                transform-origin: 100px 240px;
                animation: tailSway 5s ease-in-out infinite alternate;
              }
              .pupils-group {
                animation: lookAround 8s ease-in-out infinite;
              }
              .eyelids {
                fill: #1f1f24;
                transform-origin: center;
                transform: scaleY(0);
                animation: blink 6s linear infinite;
              }
              @keyframes tailSway {
                0% { transform: rotate(-10deg); }
                100% { transform: rotate(10deg); }
              }
              @keyframes lookAround {
                0%, 15% { transform: translate(0, 0); }
                20%, 40% { transform: translate(-5px, 2px); }
                45%, 65% { transform: translate(5px, -2px); }
                70%, 100% { transform: translate(0, 0); }
              }
              @keyframes blink {
                0%, 96% { transform: scaleY(0); }
                98% { transform: scaleY(1); }
                100% { transform: scaleY(0); }
              }
              @keyframes pulse-glow {
                0%, 100% { filter: drop-shadow(0 0 8px rgba(102, 126, 234, 0.6)); }
                50% { filter: drop-shadow(0 0 20px rgba(102, 126, 234, 0.9)); }
              }
              @keyframes bounce {
                0%, 100% { transform: translateY(0); }
                50% { transform: translateY(-8px); }
              }
              @keyframes shake {
                0%, 100% { transform: translateX(0); }
                25% { transform: translateX(-3px); }
                75% { transform: translateX(3px); }
              }
              .kitty-svg.listening {
                animation: pulse-glow 1.5s ease-in-out infinite;
              }
              .kitty-svg.thinking {
                animation: pulse-glow 2s ease-in-out infinite;
              }
              .kitty-svg.speaking .tail-wrapper {
                animation: tailSway 1s ease-in-out infinite alternate !important;
              }
              .kitty-svg.celebrating {
                animation: bounce 0.5s ease-in-out infinite;
              }
              .kitty-svg.error {
                animation: shake 0.3s ease-in-out;
                filter: drop-shadow(0 0 10px rgba(255, 80, 80, 0.6));
              }
            </style>
            <radialGradient id="listening-glow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stop-color="rgba(102, 126, 234, 0.3)" />
              <stop offset="100%" stop-color="rgba(102, 126, 234, 0)" />
            </radialGradient>
          </defs>

          <g class="tail-wrapper">
            <path d="M100 240 Q 160 250 160 190 Q 160 140 180 130 C 190 125 195 135 185 150 Q 180 180 180 200 Q 185 260 100 250 Z" class="fur-dark"/>
          </g>

          <path d="M60 250 C 45 250 50 200 55 180 C 68 145 85 135 100 135 C 115 135 132 145 145 180 C 150 200 155 250 140 250 L 60 250 Z" class="fur-dark"/>

          <g class="bow-group" transform="translate(100, 138)">
            <ellipse cx="-15" cy="0" rx="12" ry="7" class="bow-main" transform="rotate(-10)"/>
            <ellipse cx="15" cy="0" rx="12" ry="7" class="bow-main" transform="rotate(10)"/>
            <ellipse cx="0" cy="0" rx="5" ry="4" class="bow-knot"/>
            <ellipse cx="-17" cy="-2" rx="3" ry="1.5" class="bow-highlight" transform="rotate(-10)"/>
            <ellipse cx="17" cy="-2" rx="3" ry="1.5" class="bow-highlight" transform="rotate(10)"/>
          </g>

          <path d="M72 255 L 75 210 C 75 195 85 195 85 210 L 88 255 L 72 255 Z" class="fur-leg"/>
          <path d="M112 255 L 115 210 C 115 195 125 195 125 210 L 128 255 L 112 255 Z" class="fur-leg"/>

          <ellipse cx="80" cy="255" rx="10" ry="6" class="fur-dark"/>
          <ellipse cx="120" cy="255" rx="10" ry="6" class="fur-dark"/>

          <g class="head-group" transform="translate(0, -10)">
            <path d="M55 90 L 30 15 L 95 68" class="fur-dark"/>
            <path d="M145 90 L 170 15 L 105 68" class="fur-dark"/>
            <path d="M42 38 L 55 78 L 75 72" class="ear-inner"/>
            <path d="M158 38 L 145 78 L 125 72" class="ear-inner"/>

            <ellipse cx="100" cy="100" rx="55" ry="45" class="fur-dark"/>

            <g class="whiskers" stroke="#888" stroke-width="1.5" fill="none" opacity="0.9" stroke-linecap="round">
              <path d="M58 108 L 10 98"/>
              <path d="M58 116 L 12 118"/>
              <path d="M58 124 L 15 135"/>
              <path d="M142 108 L 190 98"/>
              <path d="M142 116 L 188 118"/>
              <path d="M142 124 L 185 135"/>
            </g>

            <path d="M96 118 L 104 118 L 100 124 Z" fill="#000"/>

            <clipPath id="clip-left"><ellipse cx="72" cy="95" rx="15" ry="18"/></clipPath>
            <clipPath id="clip-right"><ellipse cx="128" cy="95" rx="15" ry="18"/></clipPath>

            <g clip-path="url(#clip-left)">
              <rect x="50" y="70" width="50" height="50" class="sclera"/>
              <circle cx="72" cy="95" r="13" class="iris-left"/>
              <g class="pupils-group"><ellipse cx="72" cy="95" rx="4" ry="11" class="pupil"/></g>
              <rect x="50" y="70" width="50" height="50" class="eyelids"/>
            </g>

            <g clip-path="url(#clip-right)">
              <rect x="100" y="70" width="50" height="50" class="sclera"/>
              <circle cx="128" cy="95" r="13" class="iris-right"/>
              <g class="pupils-group"><ellipse cx="128" cy="95" rx="4" ry="11" class="pupil"/></g>
              <rect x="100" y="70" width="50" height="50" class="eyelids"/>
            </g>

            <circle cx="76" cy="88" r="3.5" class="highlight"/>
            <circle cx="132" cy="88" r="3.5" class="highlight"/>
          </g>

          <g class="state-indicator thinking-indicator" style="display: none;">
            <text x="165" y="30" font-size="28" fill="#667eea">?</text>
          </g>

          <g class="state-indicator speaking-waves" style="display: none;">
            <circle cx="175" cy="80" r="8" stroke="#667eea" stroke-width="2" fill="none" opacity="0.8">
              <animate attributeName="r" values="8;18;8" dur="1s" repeatCount="indefinite"/>
              <animate attributeName="opacity" values="0.8;0.2;0.8" dur="1s" repeatCount="indefinite"/>
            </circle>
            <circle cx="175" cy="80" r="12" stroke="#667eea" stroke-width="2" fill="none" opacity="0.5">
              <animate attributeName="r" values="12;22;12" dur="1s" repeatCount="indefinite" begin="0.3s"/>
              <animate attributeName="opacity" values="0.5;0.1;0.5" dur="1s" repeatCount="indefinite" begin="0.3s"/>
            </circle>
          </g>

          <g class="state-indicator celebrating-sparkles" style="display: none;">
            <circle cx="40" cy="40" r="4" fill="#FFD700">
              <animate attributeName="opacity" values="1;0.3;1" dur="0.5s" repeatCount="indefinite"/>
            </circle>
            <circle cx="160" cy="50" r="3" fill="#FFD700">
              <animate attributeName="opacity" values="0.3;1;0.3" dur="0.5s" repeatCount="indefinite"/>
            </circle>
            <circle cx="30" cy="100" r="3" fill="#FFD700">
              <animate attributeName="opacity" values="1;0.5;1" dur="0.4s" repeatCount="indefinite"/>
            </circle>
            <circle cx="170" cy="120" r="4" fill="#FFD700">
              <animate attributeName="opacity" values="0.5;1;0.5" dur="0.6s" repeatCount="indefinite"/>
            </circle>
          </g>
        </svg>
        `
  }

  setState(newState: KittyState): void {
    if (this.state === newState || !this.svgElement || !this.container) return

    this.logger.info('BlackCat', 'State:', this.state, '->', newState)
    this.state = newState

    this.svgElement.setAttribute('class', `kitty-svg ${newState}`)

    const thinkingIndicator = this.svgElement.querySelector('.thinking-indicator')
    const speakingWaves = this.svgElement.querySelector('.speaking-waves')
    const celebratingSparkles = this.svgElement.querySelector('.celebrating-sparkles')

    if (thinkingIndicator instanceof HTMLElement) thinkingIndicator.style.display = 'none'
    if (speakingWaves instanceof HTMLElement) speakingWaves.style.display = 'none'
    if (celebratingSparkles instanceof HTMLElement) celebratingSparkles.style.display = 'none'

    switch (newState) {
      case 'thinking':
        if (thinkingIndicator instanceof HTMLElement) thinkingIndicator.style.display = 'block'
        break
      case 'speaking':
        if (speakingWaves instanceof HTMLElement) speakingWaves.style.display = 'block'
        break
      case 'celebrating':
        if (celebratingSparkles instanceof HTMLElement) celebratingSparkles.style.display = 'block'
        break
      default:
        break
    }

    const tooltips: Record<KittyState, string> = {
      idle: '点我开始对话',
      listening: '正在听…',
      thinking: '思考中…',
      speaking: '说话中…',
      celebrating: '完成！',
      error: '出错了',
    }
    this.container.title = tooltips[newState]
  }

  destroy(): void {
    if (this.container?.parentElement) {
      this.container.parentElement.removeChild(this.container)
      this.container = null
      this.svgElement = null
    }
  }
}
