/**
 * Cat walk animation for the login modal: walks along the modal card while the user
 * types account and password (restored from legacy static/js/cat-walk.js).
 *
 * Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
 */

export type CatWalkDispose = () => void

export interface CatWalkOptions {
  trackRoot: HTMLElement
  submitButton: HTMLElement
  typingInputs: readonly HTMLInputElement[]
  form: HTMLFormElement
  mountParent?: HTMLElement
}

interface CatWalkState {
  posX: number
  posY: number
  facing: number
  orbiting: boolean
  gaitTime: number
  emerged: boolean
  exited: boolean
  rafId: number | null
}

function createCatElement(): HTMLDivElement {
  const cat = document.createElement('div')
  cat.id = 'mg-cat'
  cat.setAttribute('aria-hidden', 'true')
  cat.style.position = 'fixed'
  cat.style.left = '0'
  cat.style.top = '0'
  cat.style.width = '110px'
  cat.style.height = '78px'
  cat.style.zIndex = '10005'
  cat.style.pointerEvents = 'none'
  cat.style.filter = 'drop-shadow(0 6px 6px rgba(0,0,0,0.25))'
  cat.style.transform = 'translate(-9999px, -9999px)'

  cat.innerHTML =
    '<svg viewBox="0 0 200 140" width="100%" height="100%" overflow="visible" preserveAspectRatio="xMidYMid meet">' +
    '<defs>' +
    '<style>' +
    '#earL, #earR, #legFL, #legFR, #legBL, #legBR, #eyes, #head { transform-box: fill-box; transform-origin: center; }' +
    '#tailFlex { transform-box: fill-box; transform-origin: 0% 50%; }' +
    '#legFL, #legFR, #legBL, #legBR { transform-origin: 50% 10%; }' +
    '</style>' +
    '</defs>' +
    '<g id="cat" fill="#0b0b0f">' +
    '<ellipse cx="120" cy="85" rx="58" ry="34"></ellipse>' +
    '<g id="head">' +
    '<circle cx="65" cy="70" r="26"></circle>' +
    '<polygon id="earL" points="52,56 42,34 64,45" />' +
    '<polygon id="earR" points="78,56 96,34 72,45" />' +
    '<g id="eyes">' +
    '<ellipse id="eyeL" cx="60" cy="70" rx="4" ry="4" fill="#f5f5f5"/>' +
    '<ellipse id="eyeR" cx="72" cy="70" rx="4" ry="4" fill="#f5f5f5"/>' +
    '</g>' +
    '</g>' +
    '<g id="tailMount" transform="translate(170,76)">' +
    '<g id="tailFlex">' +
    '<path id="tailS" fill="none" stroke="#0b0b0f" stroke-width="13" stroke-linecap="round" stroke-linejoin="round" ' +
    'd="M0 0 C10 -16 24 -16 30 0 C36 16 50 16 52 0"/>' +
    '</g>' +
    '</g>' +
    '<g id="legs" fill="#0b0b0f">' +
    '<rect id="legFL" x="88" y="100" width="12" height="28" rx="5"/>' +
    '<rect id="legFR" x="112" y="100" width="12" height="28" rx="5"/>' +
    '<rect id="legBL" x="136" y="100" width="12" height="28" rx="5"/>' +
    '<rect id="legBR" x="160" y="100" width="12" height="28" rx="5"/>' +
    '</g>' +
    '</g>' +
    '</svg>'

  return cat
}

function placeCat(
  cat: HTMLDivElement,
  state: CatWalkState,
  x: number,
  y: number,
  facing?: number
): void {
  state.posX = x
  state.posY = y
  if (typeof facing === 'number') state.facing = facing
  cat.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px) scaleX(${-state.facing})`
}

function animateBlink(cat: HTMLDivElement, state: CatWalkState, blinkTimers: number[]): void {
  const eyesEl = cat.querySelector('#eyes')
  if (!eyesEl) return

  function blink(): void {
    if (state.exited || !eyesEl) return
    eyesEl.animate(
      [{ transform: 'scaleY(1)' }, { transform: 'scaleY(0.1)' }, { transform: 'scaleY(1)' }],
      { duration: 110, easing: 'ease-in-out' }
    )
    blinkTimers.push(window.setTimeout(blink, 1200 + Math.random() * 2500))
  }

  blinkTimers.push(window.setTimeout(blink, 800 + Math.random() * 1200))
}

/**
 * S-curve tail wags around its spine-root attachment.
 * The path is symmetric about y=0, so fill-box 0%/50% lands exactly on local (0,0).
 * Rotation swings the whole S between -13deg and +13deg like a pendulum wag.
 */
function animateTail(cat: HTMLDivElement): Animation[] {
  const flex = cat.querySelector('#tailFlex')
  if (!(flex instanceof SVGGraphicsElement)) {
    return []
  }

  flex.style.transformBox = 'fill-box'
  flex.style.transformOrigin = '0% 50%'

  const anim = flex.animate(
    [
      { transform: 'rotate(-13deg)' },
      { transform: 'rotate(13deg)' },
      { transform: 'rotate(-13deg)' },
    ],
    { duration: 1000, iterations: Infinity, easing: 'ease-in-out' }
  )
  return [anim]
}

/** SVG legs/head are `SVGGraphicsElement`, not `HTMLElement` — stylesheet transforms must reach them. */
function setSvgTransform(el: Element | null, value: string): void {
  if (!(el instanceof SVGGraphicsElement)) return
  el.style.transform = value
}

function animateEars(cat: HTMLDivElement, state: CatWalkState, earIntervals: number[]): void {
  const earL = cat.querySelector('#earL')
  const earR = cat.querySelector('#earR')
  if (!(earL instanceof SVGElement) || !(earR instanceof SVGElement)) return

  function flick(ear: SVGElement, sign: number): void {
    if (state.exited) return
    ear.animate(
      [
        { transform: 'rotate(0deg)' },
        { transform: `rotate(${sign * 10}deg)` },
        { transform: 'rotate(0deg)' },
      ],
      { duration: 260, easing: 'ease-out' }
    )
  }

  earIntervals.push(window.setInterval(() => flick(earL, -1), 3200))
  earIntervals.push(window.setInterval(() => flick(earR, 1), 4100))
}

function startGaitLoop(cat: HTMLDivElement, state: CatWalkState): void {
  const legFL = cat.querySelector('#legFL')
  const legFR = cat.querySelector('#legFR')
  const legBL = cat.querySelector('#legBL')
  const legBR = cat.querySelector('#legBR')
  const head = cat.querySelector('#head')
  let last = performance.now()

  function loop(now: number): void {
    if (state.exited) return
    const dt = Math.min(0.05, (now - last) / 1000)
    last = now
    state.gaitTime += dt
    const speed = state.orbiting ? 1 : 0.6
    const phase = state.gaitTime * 8 * speed
    const a = Math.sin(phase) * 18
    const b = Math.sin(phase + Math.PI) * 18
    setSvgTransform(legFL, `rotate(${a}deg)`)
    setSvgTransform(legBR, `rotate(${a}deg)`)
    setSvgTransform(legFR, `rotate(${b}deg)`)
    setSvgTransform(legBL, `rotate(${b}deg)`)
    if (head instanceof SVGGraphicsElement) {
      const bob = Math.sin(phase * 0.5) * (state.orbiting ? 1.6 : 1.0)
      head.style.transform = `translateY(${bob}px)`
    }
    state.rafId = requestAnimationFrame(loop)
  }

  state.rafId = requestAnimationFrame(loop)
}

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3)
}

function moveCatTo(
  cat: HTMLDivElement,
  state: CatWalkState,
  target: { x: number; y: number },
  durationMs: number
): Promise<void> {
  return new Promise((resolve) => {
    const startX = state.posX
    const startY = state.posY
    const dx = target.x - startX
    const dy = target.y - startY
    state.facing = dx >= 0 ? 1 : -1
    const t0 = performance.now()

    function step(now: number): void {
      const t = Math.min(1, (now - t0) / durationMs)
      const e = easeOutCubic(t)
      placeCat(cat, state, startX + dx * e, startY + dy * e)
      if (t < 1 && !state.exited) requestAnimationFrame(step)
      else resolve()
    }

    requestAnimationFrame(step)
  })
}

function startTrackPatrol(
  cat: HTMLDivElement,
  state: CatWalkState,
  trackRoot: HTMLElement,
  submitButton: HTMLElement
): void {
  if (state.orbiting) return
  state.orbiting = true

  let last = performance.now()
  let progress = 0
  let dir = 1
  let turnUntil = 0
  const speed = 140
  const centerOffsetX = 50
  const centerOffsetY = 36
  const marginPx = 18

  function resolveTrackRect(): { left: number; top: number; width: number } {
    if (document.body.contains(trackRoot)) {
      const r = trackRoot.getBoundingClientRect()
      return {
        left: r.left - marginPx,
        top: r.top - marginPx,
        width: r.width + 2 * marginPx,
      }
    }
    const rFallback = submitButton.getBoundingClientRect()
    return {
      left: rFallback.left - marginPx,
      top: rFallback.top - marginPx,
      width: Math.max(rFallback.width + 2 * marginPx, 260),
    }
  }

  function patrolLoop(now: number): void {
    if (!state.orbiting || state.exited) return
    const dt = Math.min(0.05, (now - last) / 1000)
    last = now
    const rect = resolveTrackRect()
    const w = rect.width
    let nextProgress = progress + dir * speed * dt

    if (nextProgress > w) {
      nextProgress = w
      if (progress !== w) {
        dir = -1
        turnUntil = now + 120
      }
    }
    if (nextProgress < 0) {
      nextProgress = 0
      if (progress !== 0) {
        dir = 1
        turnUntil = now + 120
      }
    }

    if (now < turnUntil) {
      state.facing = dir
      const xPause = rect.left + nextProgress
      const yPause = rect.top
      placeCat(cat, state, xPause - centerOffsetX, yPause - centerOffsetY)
      requestAnimationFrame(patrolLoop)
      return
    }

    progress = nextProgress
    const x = rect.left + progress
    const y = rect.top
    state.facing = dir
    placeCat(cat, state, x - centerOffsetX, y - centerOffsetY)
    requestAnimationFrame(patrolLoop)
  }

  requestAnimationFrame(patrolLoop)
}

export function initCatWalk(options: CatWalkOptions): CatWalkDispose {
  const { trackRoot, submitButton, typingInputs, form } = options
  const mountParent = options.mountParent ?? document.body

  if (window.matchMedia('(hover: none), (pointer: coarse)').matches) {
    return (): void => {}
  }

  if (
    typingInputs.length === 0 ||
    !document.body.contains(trackRoot) ||
    !document.body.contains(submitButton) ||
    !document.body.contains(form)
  ) {
    return (): void => {}
  }

  const state: CatWalkState = {
    posX: 0,
    posY: 0,
    facing: 1,
    orbiting: false,
    gaitTime: 0,
    emerged: false,
    exited: false,
    rafId: null,
  }

  const cat = createCatElement()
  mountParent.appendChild(cat)

  placeCat(cat, state, -9999, -9999, 1)

  const blinkTimers: number[] = []
  const earIntervals: number[] = []
  const tailAnimations = animateTail(cat)

  animateBlink(cat, state, blinkTimers)
  animateEars(cat, state, earIntervals)
  startGaitLoop(cat, state)

  function getButtonSpawnPoint(): { x: number; y: number } {
    const r = submitButton.getBoundingClientRect()
    return { x: r.left + r.width * 0.5, y: r.top + r.height * 0.5 }
  }

  function getApproachPoint(): { x: number; y: number } {
    const r = submitButton.getBoundingClientRect()
    return { x: r.left + r.width * 0.15, y: r.top + r.height + 8 }
  }

  let emerged = false
  let orbitStarted = false

  async function emergeFromButton(): Promise<void> {
    if (emerged || state.exited) return
    emerged = true
    state.emerged = true
    const spawn = getButtonSpawnPoint()
    placeCat(cat, state, spawn.x - 50, spawn.y - 20, 1)
    await moveCatTo(cat, state, getApproachPoint(), 500)
    tryStartOrbit()
  }

  function hasTypedCredential(): boolean {
    return typingInputs.some((el) => el.value.trim().length > 0)
  }

  function tryStartOrbit(): void {
    if (orbitStarted || !state.emerged || state.exited) return
    if (hasTypedCredential()) {
      orbitStarted = true
      startTrackPatrol(cat, state, trackRoot, submitButton)
    }
  }

  function onTypingInput(): void {
    if (hasTypedCredential()) void emergeFromButton()
    tryStartOrbit()
  }

  for (const input of typingInputs) {
    input.addEventListener('input', onTypingInput)
  }

  function onSubmit(): void {
    state.exited = true
    state.orbiting = false
    tailAnimations.forEach((a) => a.cancel())
    const spawn = getButtonSpawnPoint()
    void moveCatTo(cat, state, { x: spawn.x - 50, y: spawn.y - 20 }, 450).then(() => {
      if (!cat.parentNode) return
      cat.animate(
        [
          {
            opacity: 1,
            transform: `translate(${state.posX}px, ${state.posY}px) scaleX(${-state.facing}) scale(1)`,
          },
          {
            opacity: 0,
            transform: `translate(${state.posX}px, ${state.posY}px) scaleX(${-state.facing}) scale(0.6)`,
          },
        ],
        { duration: 220, fill: 'forwards', easing: 'ease-in' }
      )
    })
  }

  form.addEventListener('submit', onSubmit, { once: true })

  return (): void => {
    state.exited = true
    state.orbiting = false
    tailAnimations.forEach((a) => a.cancel())
    blinkTimers.forEach((id) => clearTimeout(id))
    earIntervals.forEach((id) => clearInterval(id))
    if (state.rafId !== null) cancelAnimationFrame(state.rafId)

    for (const input of typingInputs) {
      input.removeEventListener('input', onTypingInput)
    }
    form.removeEventListener('submit', onSubmit)

    cat.remove()
  }
}
