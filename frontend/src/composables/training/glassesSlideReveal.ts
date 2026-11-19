/**
 * Plays a slide's glasses reveal on the open canvas. The topic expands first,
 * then each surrounding node swooshes in clockwise with the line that joins it.
 * A double bubble names itself, enlarges the two topics, then the shared nodes, then the differences.
 */
import { builderDiagramSession } from '@/composables/training/builderDiagramBridge'
import {
  type ClockPoint,
  type ShownLink,
  clockwiseFromTop,
  doubleBubbleRevealOrder,
  linesBetweenShown,
} from '@/composables/training/glassesPlay'
import { i18n } from '@/i18n'
import { useDiagramStore } from '@/stores/diagram'
import type { Connection, DiagramNode } from '@/types'
import { readDoubleBubbleIndex, readDoubleBubbleRole } from '@/utils/doubleBubbleMapIdentity'

const SWOOSH_MS = 520
const TOPIC_SCALE = '1.3'
const BUBBLE_SCALE = '1.12'

function roleOf(node: DiagramNode): string {
  const data = node.data
  if (!data || typeof data !== 'object') return ''
  const role = (data as { doubleBubbleRole?: unknown }).doubleBubbleRole
  return typeof role === 'string' ? role : ''
}

function nodeElement(root: HTMLElement, id: string): HTMLElement | null {
  const node = root.querySelector(`.vue-flow__node[data-id="${CSS.escape(id)}"]`)
  return node instanceof HTMLElement ? node : null
}

function centerOf(node: HTMLElement): ClockPoint {
  const rect = node.getBoundingClientRect()
  return { id: '', x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

type DrawnSession = {
  nodes: DiagramNode[]
  links: ShownLink[]
}

function linksOf(connections: Connection[] | undefined): ShownLink[] {
  if (!Array.isArray(connections)) return []
  return connections.flatMap((link) => {
    if (!link?.id || !link.source || !link.target) return []
    return [{ id: link.id, source: link.source, target: link.target }]
  })
}

function sessionDrawn(
  session: { data?: { nodes?: DiagramNode[]; connections?: Connection[] } | null } | null,
  root: HTMLElement
): DrawnSession | null {
  const nodes = session?.data?.nodes
  if (!Array.isArray(nodes)) return null
  if (!nodes.some((node) => node.id && nodeElement(root, node.id))) return null
  return { nodes, links: linksOf(session?.data?.connections) }
}

function drawnSession(root: HTMLElement): DrawnSession {
  const bound = sessionDrawn(builderDiagramSession.value, root)
  if (bound) return bound
  return sessionDrawn(useDiagramStore(), root) ?? { nodes: [], links: [] }
}

async function whenDiagramReady(root: HTMLElement): Promise<DrawnSession> {
  for (let attempt = 0; attempt < 15; attempt += 1) {
    const drawn = drawnSession(root)
    const bubbles = drawn.nodes.filter((node) => node.type === 'bubble')
    if (bubbles.some((node) => nodeElement(root, node.id))) return drawn
    await wait(200)
  }
  return drawnSession(root)
}

function clearMotion(node: HTMLElement): void {
  node.style.removeProperty('transition')
  node.style.removeProperty('opacity')
  node.style.removeProperty('translate')
  node.style.removeProperty('scale')
  node.style.removeProperty('transform-origin')
  node.style.removeProperty('outline')
  node.style.removeProperty('outline-offset')
}

const LINE_STYLE_ID = 'glasses-reveal-lines-style'

function ensureLineStyle(): void {
  if (document.getElementById(LINE_STYLE_ID)) return
  const style = document.createElement('style')
  style.id = LINE_STYLE_ID
  style.textContent = [
    '.vue-flow.glasses-reveal-lines .vue-flow__edge:not([data-glasses-line="in"]){opacity:0 !important}',
    '.vue-flow.glasses-reveal-lines .vue-flow__edge[data-glasses-line="in"]{opacity:1 !important}',
    '.vue-flow.glasses-reveal-lines .vue-flow__edge:not([data-glasses-line="in"]) .vue-flow__edge-path{stroke-dasharray:1 !important;stroke-dashoffset:1 !important}',
    `.vue-flow.glasses-reveal-lines .vue-flow__edge[data-glasses-line="in"] .vue-flow__edge-path{stroke-dasharray:1 !important;stroke-dashoffset:0 !important;transition:stroke-dashoffset ${SWOOSH_MS}ms ease !important}`,
  ].join('')
  document.head.appendChild(style)
}

function flowSurface(root: HTMLElement): HTMLElement {
  if (root.classList.contains('vue-flow')) return root
  const nested = root.querySelector('.vue-flow')
  return nested instanceof HTMLElement ? nested : root
}

function stampLines(surface: HTMLElement, visible: ReadonlySet<string>): void {
  surface.querySelectorAll('.vue-flow__edge').forEach((edge) => {
    const id = edge.getAttribute('data-id') || ''
    if (visible.has(id)) edge.setAttribute('data-glasses-line', 'in')
    else edge.removeAttribute('data-glasses-line')
    const path = edge.querySelector('.vue-flow__edge-path')
    if (path instanceof SVGPathElement && path.getAttribute('pathLength') !== '1') {
      path.setAttribute('pathLength', '1')
    }
  })
}

function releaseLines(surface: HTMLElement): void {
  surface.classList.remove('glasses-reveal-lines')
  surface.querySelectorAll('.vue-flow__edge').forEach((edge) => {
    edge.removeAttribute('data-glasses-line')
    const path = edge.querySelector('.vue-flow__edge-path')
    if (path instanceof SVGPathElement) path.removeAttribute('pathLength')
  })
}

function prepareExpand(node: HTMLElement): void {
  node.style.transition = 'none'
  node.style.opacity = '0'
  node.style.scale = '0.2'
}

function expandNode(node: HTMLElement): void {
  node.style.transition = `opacity ${SWOOSH_MS}ms ease, scale ${SWOOSH_MS}ms cubic-bezier(0.16, 1, 0.3, 1)`
  node.style.opacity = '1'
  node.style.scale = '1'
}

function prepareSwoosh(node: HTMLElement, toward: ClockPoint): void {
  const here = centerOf(node)
  const dx = (toward.x - here.x) * 0.55
  const dy = (toward.y - here.y) * 0.55
  node.style.transition = 'none'
  node.style.opacity = '0'
  node.style.translate = `${dx}px ${dy}px`
  node.style.scale = '0.15'
}

function releaseSwoosh(node: HTMLElement): void {
  node.style.transition = `opacity ${SWOOSH_MS}ms ease, translate ${SWOOSH_MS}ms cubic-bezier(0.16, 1, 0.3, 1), scale ${SWOOSH_MS}ms cubic-bezier(0.16, 1, 0.3, 1)`
  node.style.opacity = '1'
  node.style.translate = '0px 0px'
  node.style.scale = '1'
}

function drawReadyLines(links: ShownLink[], shown: ReadonlySet<string>, drawn: Set<string>): void {
  for (const id of linesBetweenShown(links, shown)) drawn.add(id)
}

async function playClockwise(
  root: HTMLElement,
  nodes: DiagramNode[],
  links: ShownLink[],
  pace: number
): Promise<void> {
  const topics = nodes.filter((node) => node.type === 'topic')
  const bubbles = nodes.filter((node) => node.type === 'bubble')
  const topicEls = topics
    .map((node) => nodeElement(root, node.id))
    .filter((node): node is HTMLElement => node instanceof HTMLElement)
  const bubbleEls = bubbles
    .map((node) => nodeElement(root, node.id))
    .filter((node): node is HTMLElement => node instanceof HTMLElement)
  if (!bubbleEls.length) return
  const origin = topicEls.length
    ? {
        id: 'topic',
        x: topicEls.reduce((sum, node) => sum + centerOf(node).x, 0) / topicEls.length,
        y: topicEls.reduce((sum, node) => sum + centerOf(node).y, 0) / topicEls.length,
      }
    : { id: 'topic', x: 0, y: 0 }
  const points = bubbleEls.map((node) => ({ ...centerOf(node), id: node.dataset.id || '' }))
  const order = clockwiseFromTop(points, origin)
  const shown = new Set(topics.map((node) => node.id))
  const drawn = new Set<string>()
  const surface = flowSurface(root)
  ensureLineStyle()
  surface.classList.add('glasses-reveal-lines')
  let frame = window.requestAnimationFrame(function tick() {
    stampLines(surface, drawn)
    frame = window.requestAnimationFrame(tick)
  })
  try {
    for (const node of topicEls) prepareExpand(node)
    for (const node of bubbleEls) prepareSwoosh(node, origin)
    await wait(40)
    for (const node of topicEls) expandNode(node)
    if (topicEls.length) await wait(SWOOSH_MS)
    drawReadyLines(links, shown, drawn)
    for (const id of order) {
      const node = bubbleEls.find((item) => item.dataset.id === id)
      if (!node) continue
      shown.add(id)
      releaseSwoosh(node)
      drawReadyLines(links, shown, drawn)
      await wait(pace)
    }
    await wait(SWOOSH_MS)
    for (const node of [...topicEls, ...bubbleEls]) clearMotion(node)
  } finally {
    window.cancelAnimationFrame(frame)
    releaseLines(surface)
  }
}

function pinMotion(node: HTMLElement, opacity: string, scale: string, transition: string): void {
  node.style.setProperty('transform-origin', 'center', 'important')
  node.style.setProperty('transition', transition, 'important')
  node.style.setProperty('opacity', opacity, 'important')
  node.style.setProperty('scale', scale, 'important')
}

function hideForStage(node: HTMLElement): void {
  pinMotion(node, '0', '0.82', 'none')
}

function enlarge(node: HTMLElement, scale: string): void {
  const ease = `opacity ${SWOOSH_MS}ms ease, scale ${SWOOSH_MS}ms cubic-bezier(0.16, 1, 0.3, 1)`
  pinMotion(node, '1', scale, ease)
}

function mountStageLines(): SVGSVGElement {
  // Vue Flow owns the canvas element and drops children appended there.
  document.querySelector('[data-glasses-stage-lines]')?.remove()
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.setAttribute('data-glasses-stage-lines', '1')
  svg.style.position = 'fixed'
  svg.style.left = '0'
  svg.style.top = '0'
  svg.style.overflow = 'visible'
  svg.style.pointerEvents = 'none'
  svg.style.zIndex = '90'
  document.body.appendChild(svg)
  return svg
}

function sizeStageLines(svg: SVGSVGElement): void {
  const width = document.documentElement.clientWidth
  const height = document.documentElement.clientHeight
  svg.setAttribute('width', String(width))
  svg.setAttribute('height', String(height))
  svg.style.width = `${width}px`
  svg.style.height = `${height}px`
}

function rimPoint(rect: DOMRect, towardX: number, towardY: number): { x: number; y: number } {
  const cx = rect.left + rect.width / 2
  const cy = rect.top + rect.height / 2
  const rx = Math.max(rect.width / 2, 1)
  const ry = Math.max(rect.height / 2, 1)
  const dx = towardX - cx
  const dy = towardY - cy
  const length = Math.hypot(dx, dy) || 1
  const ux = dx / length
  const uy = dy / length
  const reach = 1 / Math.sqrt((ux / rx) ** 2 + (uy / ry) ** 2)
  return { x: cx + ux * reach, y: cy + uy * reach }
}

function stageCurve(from: { x: number; y: number }, to: { x: number; y: number }): string {
  const mx = (from.x + to.x) / 2
  const my = (from.y + to.y) / 2
  const dx = to.x - from.x
  const dy = to.y - from.y
  const length = Math.hypot(dx, dy) || 1
  const bend = length * 0.16
  return `M ${from.x} ${from.y} Q ${mx + (-dy / length) * bend} ${my + (dx / length) * bend} ${to.x} ${to.y}`
}

function paintStageLines(
  svg: SVGSVGElement,
  root: HTMLElement,
  links: ShownLink[],
  shown: ReadonlySet<string>,
  born: Map<string, SVGPathElement>
): void {
  sizeStageLines(svg)
  const visible = new Set(linesBetweenShown(links, shown))
  for (const link of links) {
    const path = born.get(link.id)
    if (!visible.has(link.id)) {
      path?.remove()
      born.delete(link.id)
      continue
    }
    const source = nodeElement(root, link.source)
    const target = nodeElement(root, link.target)
    if (!source || !target) continue
    const sourceBox = source.getBoundingClientRect()
    const targetBox = target.getBoundingClientRect()
    const sourceCenterX = sourceBox.left + sourceBox.width / 2
    const sourceCenterY = sourceBox.top + sourceBox.height / 2
    const targetCenterX = targetBox.left + targetBox.width / 2
    const targetCenterY = targetBox.top + targetBox.height / 2
    const from = rimPoint(sourceBox, targetCenterX, targetCenterY)
    const to = rimPoint(targetBox, sourceCenterX, sourceCenterY)
    const line = path ?? document.createElementNS('http://www.w3.org/2000/svg', 'path')
    if (!path) {
      const real = edgeStroke(root, link.id)
      line.setAttribute('fill', 'none')
      line.setAttribute('stroke', real.stroke)
      line.setAttribute('stroke-width', real.width)
      line.setAttribute('stroke-linecap', 'round')
      line.setAttribute('pathLength', '1')
      line.style.strokeDasharray = '1'
      line.style.strokeDashoffset = '1'
      line.style.transition = `stroke-dashoffset ${SWOOSH_MS}ms ease`
      svg.appendChild(line)
      born.set(link.id, line)
      window.requestAnimationFrame(() => {
        line.style.strokeDashoffset = '0'
      })
    }
    line.setAttribute('d', stageCurve(from, to))
  }
}

function edgeStroke(root: HTMLElement, id: string): { stroke: string; width: string } {
  const edge = root.querySelector(
    `.vue-flow__edge[data-id="${CSS.escape(id)}"] .vue-flow__edge-path`
  )
  if (!(edge instanceof Element)) return { stroke: '#64748b', width: '2' }
  const style = window.getComputedStyle(edge)
  return { stroke: style.stroke || '#64748b', width: style.strokeWidth || '2' }
}

function mountMapTitle(): HTMLElement {
  document.querySelector('[data-glasses-map-title]')?.remove()
  const title = document.createElement('div')
  title.textContent = String(i18n.global.t('sidebar.diagramType.double_bubble_map'))
  title.setAttribute('data-glasses-map-title', 'double-bubble')
  title.style.position = 'fixed'
  title.style.zIndex = '91'
  title.style.transform = 'translate(-50%, -50%) scale(0.9)'
  title.style.pointerEvents = 'none'
  title.style.color = '#14532d'
  title.style.fontSize = '40px'
  title.style.fontWeight = '600'
  title.style.letterSpacing = '0.2em'
  title.style.opacity = '0'
  title.style.textShadow = '0 0 18px rgba(61, 220, 132, 0.9)'
  title.style.transition = 'opacity 420ms ease, transform 420ms cubic-bezier(0.16, 1, 0.3, 1)'
  document.body.appendChild(title)
  return title
}

function placeTitle(title: HTMLElement, surface: HTMLElement): void {
  const box = surface.getBoundingClientRect()
  title.style.left = `${box.left + box.width / 2}px`
  title.style.top = `${box.top + box.height * 0.16}px`
}

async function revealIds(
  ids: string[],
  nodes: DiagramNode[],
  root: HTMLElement,
  links: ShownLink[],
  shown: Set<string>,
  drawn: Set<string> | null,
  scale: string,
  stagger: number
): Promise<void> {
  for (const id of ids) {
    const source = nodes.find((node) => node.id === id)
    const element = source ? nodeElement(root, source.id) : null
    if (!element) continue
    shown.add(id)
    enlarge(element, scale)
    if (drawn) drawReadyLines(links, shown, drawn)
    await wait(stagger)
  }
}

async function playDoubleBubble(
  root: HTMLElement,
  nodes: DiagramNode[],
  links: ShownLink[],
  pace: number
): Promise<void> {
  const topics = nodes.filter((node) => node.type === 'topic')
  const topicEls = topics
    .map((node) => nodeElement(root, node.id))
    .filter((node): node is HTMLElement => node instanceof HTMLElement)
  const staged = nodes.flatMap((node) => {
    const role = readDoubleBubbleRole(node)
    if (!role) return []
    return [{ id: node.id, role, index: readDoubleBubbleIndex(node) }]
  })
  const order = doubleBubbleRevealOrder(staged)
  const roleEls = staged
    .map((node) => nodeElement(root, node.id))
    .filter((node): node is HTMLElement => node instanceof HTMLElement)
  if (!topicEls.length && !roleEls.length) return
  const shown = new Set<string>()
  const surface = flowSurface(root)
  const title = mountMapTitle()
  const lines = mountStageLines()
  const born = new Map<string, SVGPathElement>()
  ensureLineStyle()
  surface.classList.add('glasses-reveal-lines')
  let frame = window.requestAnimationFrame(function tick() {
    placeTitle(title, surface)
    paintStageLines(lines, root, links, shown, born)
    frame = window.requestAnimationFrame(tick)
  })
  const stagger = Math.min(220, Math.max(120, pace))
  try {
    for (const node of [...topicEls, ...roleEls]) hideForStage(node)
    await wait(40)
    title.style.opacity = '1'
    title.style.transform = 'translate(-50%, -50%) scale(1)'
    await wait(980)
    title.style.opacity = '0'
    title.style.transform = 'translate(-50%, -50%) scale(1.04)'
    await wait(280)
    for (const node of topicEls) enlarge(node, TOPIC_SCALE)
    for (const node of topics) shown.add(node.id)
    await wait(SWOOSH_MS + 240)
    await revealIds(order.similarities, nodes, root, links, shown, null, BUBBLE_SCALE, stagger)
    await wait(180)
    await revealIds(order.differences, nodes, root, links, shown, null, BUBBLE_SCALE, stagger)
    await wait(SWOOSH_MS)
    for (const node of [...topicEls, ...roleEls]) enlarge(node, '1')
    await wait(SWOOSH_MS)
  } finally {
    window.cancelAnimationFrame(frame)
    title.remove()
    lines.remove()
    releaseLines(surface)
    for (const node of [...topicEls, ...roleEls]) clearMotion(node)
  }
}

async function playHighlight(root: HTMLElement, nodes: DiagramNode[], pace: number): Promise<void> {
  const chosen = nodes.filter((node) => roleOf(node) === 'similarity')
  const bubbles = chosen.length ? chosen : nodes.filter((node) => node.type === 'bubble')
  const elements = bubbles
    .map((node) => nodeElement(root, node.id))
    .filter((node): node is HTMLElement => node instanceof HTMLElement)
  for (const node of elements) {
    node.style.transition = 'scale 280ms ease, outline-color 280ms ease'
    node.style.outline = '3px solid #16a34a'
    node.style.outlineOffset = '6px'
    node.style.scale = '1.08'
  }
  await wait(Math.round(pace * 1.2))
  for (const node of elements) node.style.scale = '1'
  await wait(pace * 3)
  for (const node of elements) clearMotion(node)
}

export async function playGlassesReveal(
  root: HTMLElement,
  reveal: string,
  pace = 280
): Promise<void> {
  if (reveal !== 'clockwise' && reveal !== 'highlight' && reveal !== 'stages') return
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const drawn = await whenDiagramReady(root)
  const gap = Math.min(800, Math.max(160, pace))
  if (reveal === 'stages') {
    await playDoubleBubble(root, drawn.nodes, drawn.links, gap)
    return
  }
  if (reveal === 'clockwise') {
    await playClockwise(root, drawn.nodes, drawn.links, gap)
    return
  }
  await playHighlight(root, drawn.nodes, gap)
}
