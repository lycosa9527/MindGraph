/**
 * Rotating Kitty speech lines for mind-map node explain (ephemeral UI copy).
 * Chinese UI → zh pool; everything else → en pool.
 */

export type ExplainBubbleStyle =
  | 'round'
  | 'cloud'
  | 'comic'
  | 'soft'
  | 'ticket'
  | 'whisper'
  | 'tag'
  | 'burst'

export type ExplainBubbleLine = {
  text: string
  style: ExplainBubbleStyle
}

const BUBBLE_STYLES: ExplainBubbleStyle[] = [
  'round',
  'cloud',
  'comic',
  'soft',
  'ticket',
  'whisper',
  'tag',
  'burst',
]

function withStyles(lines: string[]): ExplainBubbleLine[] {
  return lines.map((text, index) => ({
    text,
    style: BUBBLE_STYLES[index % BUBBLE_STYLES.length],
  }))
}

/** Dozens of zh lines — playful, teacherly, curious; rotates while streaming. */
const ZH_LINES: string[] = [
  '我要开始解释这个节点啦',
  '正在看你的导图…',
  '先摸清这个节点在图里站哪儿',
  '喵～三栏马上就来',
  '让我顺着枝桠找找线索',
  '这个节点有故事，我闻见了',
  '别眨眼，灵感在排队',
  '先讲清楚它和主题的关系',
  '认知冲突位，准备就绪',
  '启发提问正在酝酿…',
  '我在对比旁边那些分支',
  '像拼图一样，对上这块了',
  '小声说：这里可能有个误会',
  '等等，我再读一遍层级',
  '好问题马上出炉',
  '主题在这儿，节点在那儿——有意思',
  '给学习者留一点思考缝隙',
  '不是背定义，是看懂位置',
  '张力来了，别怕，挺好玩的',
  '三路并进，我忙得开心',
  '叶子节点也有大宇宙',
  '嘿，兄弟节点好像在抬杠',
  '从中心往外走一步…',
  '再往里挖一点点',
  '解释不是终点，是起点',
  '我在拼一张微型地图',
  '嗯，这句要说得更清楚',
  '好奇模式：已开启',
  '如果换个角度看呢？',
  '喵呜，线索连上了',
  '先稳住含义，再谈冲突',
  '问题要短、要亮、要能追问',
  '图在说话，我只是翻译',
  '这一栏写含义，那一栏写张力',
  '别急，字在路上',
  '我看见它如何撑起主题了',
  '常见误解侦测中…',
  '给课堂留三个小钩子',
  '节点虽小，份量不轻',
  '好，进入深读状态',
  '像聊天一样把道理讲开',
  '再对齐一次祖先路径',
  '兄弟姐妹们也算上',
  '准备好被问倒了吗？',
  '解释进行中，请稍候',
  '喵～马上就好',
]

/** English counterparts for non-Chinese UI locales. */
const EN_LINES: string[] = [
  'Time to explain this node!',
  'Looking at your diagram…',
  'Pinning where this node sits in the map',
  'Three panels incoming — meow',
  'Following the branches for clues',
  'This node has a story; I can smell it',
  'Ideas are lining up — don’t blink',
  'First: how it relates to the topic',
  'Cognitive-conflict lane: ready',
  'Brewing a few spark questions…',
  'Comparing it with nearby branches',
  'Puzzle piece clicked into place',
  'Whisper: there might be a misconception here',
  'One more pass over the hierarchy',
  'Good questions are almost out of the oven',
  'Topic here, node there — interesting',
  'Leaving a little thinking gap for learners',
  'Not a definition dump — a place in the map',
  'Tension rising; that’s the fun part',
  'Three streams at once — happily busy',
  'Even a leaf node can hold a universe',
  'Hey, sibling branches seem to disagree',
  'One step out from the center…',
  'Digging a little deeper',
  'Explanation isn’t the end — it’s a start',
  'Assembling a tiny mental map',
  'Hmm, saying this more clearly…',
  'Curiosity mode: on',
  'What if we look from another angle?',
  'Meow — clues connected',
  'Lock meaning first, then the tension',
  'Questions: short, bright, chase-able',
  'The diagram talks; I’m just translating',
  'This column for meaning, that one for conflict',
  'Hang tight — words are on the way',
  'I see how it props up the topic',
  'Scanning for common misconceptions…',
  'Three little hooks for class discussion',
  'Small node, real weight',
  'Deep-read mode engaged',
  'Unpacking it like a chat, not a lecture',
  'Re-checking the ancestor path',
  'Counting the siblings too',
  'Ready to be stumped by a good question?',
  'Explaining now — one moment',
  'Almost there — meow',
]

export const MIND_MAP_NODE_EXPLAIN_BUBBLES_ZH = withStyles(ZH_LINES)
export const MIND_MAP_NODE_EXPLAIN_BUBBLES_EN = withStyles(EN_LINES)

export function pickExplainBubblePool(isChineseUi: boolean): ExplainBubbleLine[] {
  return isChineseUi ? MIND_MAP_NODE_EXPLAIN_BUBBLES_ZH : MIND_MAP_NODE_EXPLAIN_BUBBLES_EN
}

/**
 * Copy + shuffle for one modal open.
 * Keeps the first line (kickoff) pinned, rotates the rest.
 */
export function shuffleExplainBubbles(pool: ExplainBubbleLine[]): ExplainBubbleLine[] {
  if (pool.length <= 1) return pool.slice()
  const kickoff = pool[0]!
  const rest = pool.slice(1)
  for (let i = rest.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    const tmp = rest[i]
    rest[i] = rest[j]!
    rest[j] = tmp!
  }
  return [kickoff, ...rest]
}
