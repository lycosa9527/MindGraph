/**
 * Position snapshots for every auto-laid-out diagram type.
 * Load from spec, recalc with no DOM sizes, then recalc with synthetic measured
 * sizes. A layout refactor must leave these unchanged unless a move is intended.
 * Bilingual cases go through the specIO load path (mirror attach + relayout).
 */
import { describe, expect, it } from 'vitest'

import { attachRemainingSecondary } from '@/diagramBilingual/attachRest'
import {
  loadSpecForDiagramType,
  recalculateBraceMapLayout,
  recalculateBridgeMapLayout,
  recalculateBubbleMapLayout,
  recalculateCircleMapLayout,
  recalculateFlowMapLayout,
  recalculateMultiFlowMapLayout,
  recalculateTreeMapLayout,
} from '@/stores/specLoader'
import { recalculateDoubleBubbleMapLayout } from '@/stores/specLoader/doubleBubbleMapMeasuredLayout'
import { relayoutLoadedSpecNodes } from '@/stores/specLoader/relayoutLoadedSpec'
import type { Connection, DiagramNode, DiagramType } from '@/types'

type Dims = Record<string, { width: number; height: number }>

function round(value: unknown): number | string {
  return typeof value === 'number' ? Math.round(value * 100) / 100 : '-'
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** Minted UUIDs differ per run; alias them by first appearance in the loaded nodes. */
function idAliases(nodes: DiagramNode[]): Map<string, string> {
  const aliases = new Map<string, string>()
  nodes.forEach((node, index) => {
    if (UUID_RE.test(node.id)) aliases.set(node.id, `n${index}`)
  })
  return aliases
}

function serialize(nodes: DiagramNode[], aliases: Map<string, string>): string[] {
  return nodes.map((node) => {
    const id = aliases.get(node.id) ?? (UUID_RE.test(node.id) ? 'unknown-uuid' : node.id)
    const w = round(node.style?.width)
    const h = round(node.style?.height)
    return `${id} ${node.type} @${round(node.position.x)},${round(node.position.y)} ${w}x${h}`
  })
}

/** Deterministic stand-in for ResizeObserver sizes: wider for longer labels, taller every third node. */
function syntheticDims(nodes: DiagramNode[]): Dims {
  const dims: Dims = {}
  nodes.forEach((node, index) => {
    if (node.type === 'boundary') return
    const len = String(node.text ?? '').length
    dims[node.id] = {
      width: 70 + len * 9,
      height: (index % 3 === 0 ? 62 : 42) + (node.textSecondary ? 22 : 0),
    }
  })
  return dims
}

const LONG = 'A considerably longer label that has to wrap onto several lines'

const SPECS: Record<string, { type: DiagramType; spec: Record<string, unknown> }> = {
  circle: {
    type: 'circle_map',
    spec: { topic: 'Water', context: ['Rain', 'Rivers', LONG, 'Oceans', 'Clouds', '冰川'] },
  },
  circleSingle: {
    type: 'circle_map',
    spec: { topic: 'Solo', context: ['Only one'] },
  },
  bubble: {
    type: 'bubble_map',
    spec: { topic: 'Cat', attributes: ['Furry', 'Curious', LONG, '独立', 'Agile'] },
  },
  doubleBubble: {
    type: 'double_bubble_map',
    spec: {
      left: 'Apple',
      right: 'Orange',
      similarities: ['Fruit', LONG],
      left_differences: ['Red', 'Crisp', 'Grows in cold'],
      right_differences: ['Orange', 'Juicy'],
    },
  },
  tree: {
    type: 'tree_map',
    spec: {
      topic: 'Animals',
      dimension: 'Habitat',
      children: [
        { text: 'Land', children: [{ text: 'Lion' }, { text: LONG }, { text: 'Fox' }] },
        { text: 'Sea', children: [{ text: 'Shark' }] },
        { text: 'Air with a longer category', children: [] },
        { text: '天空', children: [{ text: '鹰' }, { text: '燕子' }] },
      ],
    },
  },
  brace: {
    type: 'brace_map',
    spec: {
      whole: 'Car',
      dimension: 'Parts',
      parts: [
        { name: 'Engine', subparts: [{ name: 'Piston' }, { name: LONG }, { name: 'Valve' }] },
        { name: 'Body', subparts: [{ name: 'Door' }] },
        {
          name: 'Wheels with a long name',
          subparts: [{ name: 'Tyre' }, { name: 'Rim' }, { name: 'Hub' }, { name: 'Bolt' }],
        },
      ],
    },
  },
  flowHorizontal: {
    type: 'flow_map',
    spec: {
      title: 'Make tea',
      steps: ['Boil', 'Warm pot', LONG, 'Steep', 'Pour', 'Add milk', 'Serve'],
      substeps: [
        { step: 'Boil', substeps: ['Fill kettle', 'Switch on'] },
        { step: 'Steep', substeps: ['Wait 3 min'] },
      ],
    },
  },
  flowVertical: {
    type: 'flow_map',
    spec: {
      title: 'Bake',
      orientation: 'vertical',
      steps: ['Mix', LONG, 'Bake', 'Cool'],
      substeps: [
        { step: 'Mix', substeps: ['Flour', 'Eggs', 'Sugar'] },
        { step: 'Bake', substeps: ['180C'] },
      ],
    },
  },
  multiFlow: {
    type: 'multi_flow_map',
    spec: {
      event: 'Air Pollution in Cities',
      causes: ['Industry', LONG, '汽车尾气'],
      effects: ['Health', 'Climate'],
    },
  },
  bridge: {
    type: 'bridge_map',
    spec: {
      dimension: 'is to',
      analogies: [
        { left: 'Bird', right: 'Sky' },
        { left: 'Fish', right: 'Water' },
        { left: LONG, right: 'Ground' },
        { left: 'Mole', right: 'Soil' },
        { left: 'Bat', right: 'Cave' },
        { left: 'Frog', right: 'Pond' },
        { left: '鹰', right: '山' },
      ],
    },
  },
}

const ZH_LONG = '选择基础模型并完成对比评估说明文字和记录'
const GLOSS = 'Compare the base models and write down what changed between them'

/** Second language arrives as a `secondary` mirror, like an LLM bilingual spec. */
const BILINGUAL_SPECS: Record<
  string,
  { type: DiagramType; spec: Record<string, unknown>; shape?: string }
> = {
  circle: {
    type: 'circle_map',
    spec: {
      topic: '水',
      context: ['雨', '河流', ZH_LONG, '海洋', '云'],
      secondary: { topic: 'Water', context: ['Rain', 'Rivers', GLOSS, 'Oceans', 'Clouds'] },
    },
  },
  circleUnderline: {
    type: 'circle_map',
    shape: 'underline',
    spec: {
      topic: '水',
      context: ['雨', '河流', ZH_LONG],
      secondary: { topic: 'Water', context: ['Rain', 'Rivers', GLOSS] },
    },
  },
  circleRectangle: {
    type: 'circle_map',
    shape: 'rectangle',
    spec: {
      topic: '水',
      context: ['雨', LONG, '海洋', '云'],
      secondary: { topic: 'Water', context: ['Rain', '长注释', 'Oceans', 'Clouds'] },
    },
  },
  bubble: {
    type: 'bubble_map',
    spec: {
      topic: '猫',
      attributes: ['毛茸茸', '好奇', ZH_LONG, '独立', '敏捷', '安静'],
      secondary: {
        topic: 'Cat',
        attributes: ['Furry', 'Curious', GLOSS, 'Independent', 'Agile', 'Quiet'],
      },
    },
  },
  bubbleRounded: {
    type: 'bubble_map',
    shape: 'rounded',
    spec: {
      topic: '猫',
      attributes: ['毛茸茸', ZH_LONG, '独立'],
      secondary: { topic: 'Cat', attributes: ['Furry', GLOSS, 'Independent'] },
    },
  },
  bubbleUnderline: {
    type: 'bubble_map',
    shape: 'underline',
    spec: {
      topic: '猫',
      attributes: ['毛茸茸', ZH_LONG, '独立', '敏捷'],
      secondary: { topic: 'Cat', attributes: ['Furry', GLOSS, 'Independent', 'Agile'] },
    },
  },
  doubleBubble: {
    type: 'double_bubble_map',
    spec: {
      left: '苹果',
      right: '橙子',
      similarities: ['水果', ZH_LONG],
      left_differences: ['红色', '脆', '生长在寒冷地区的果园里'],
      right_differences: ['橙色', '多汁'],
      secondary: {
        left: 'Apple',
        right: 'Orange',
        similarities: ['Fruit', GLOSS],
        left_differences: ['Red', 'Crisp', 'Grows in cold orchards'],
        right_differences: ['Orange', 'Juicy'],
      },
    },
  },
  tree: {
    type: 'tree_map',
    spec: {
      topic: '动物',
      dimension: '栖息地',
      children: [
        { text: '陆地', children: [{ text: '狮子' }, { text: ZH_LONG }, { text: '狐狸' }] },
        { text: '海洋', children: [{ text: '鲨鱼' }] },
        { text: '天空中的鸟类很多', children: [{ text: '鹰' }, { text: '燕子' }] },
      ],
      secondary: {
        topic: 'Animals',
        dimension: 'Habitat',
        children: [
          { text: 'Land', children: [{ text: 'Lion' }, { text: GLOSS }, { text: 'Fox' }] },
          { text: 'Sea', children: [{ text: 'Shark' }] },
          { text: 'Many birds in the sky', children: [{ text: 'Eagle' }, { text: 'Swallow' }] },
        ],
      },
    },
  },
  brace: {
    type: 'brace_map',
    spec: {
      whole: '汽车',
      dimension: '部件',
      parts: [
        { name: '发动机', subparts: [{ name: '活塞' }, { name: ZH_LONG }, { name: '气门' }] },
        { name: '车身', subparts: [{ name: '车门' }] },
        { name: '轮子', subparts: [{ name: '轮胎' }, { name: '轮毂' }] },
      ],
      secondary: {
        whole: 'Car',
        dimension: 'Parts',
        parts: [
          { name: 'Engine', subparts: [{ name: 'Piston' }, { name: GLOSS }, { name: 'Valve' }] },
          { name: 'Body', subparts: [{ name: 'Door' }] },
          { name: 'Wheels', subparts: [{ name: 'Tyre' }, { name: 'Hub' }] },
        ],
      },
    },
  },
  flowHorizontal: {
    type: 'flow_map',
    spec: {
      title: '炒菜',
      steps: ['买菜', '洗切', '热锅', '翻炒', '调味', '出锅', '装盘'],
      substeps: [
        { step: '洗切', substeps: ['冲洗', '切丝'] },
        { step: '翻炒', substeps: ['先蒜', ZH_LONG] },
      ],
      secondary: {
        title: 'Stir fry',
        steps: ['Shop', 'Wash and cut', 'Heat the pan', GLOSS, 'Season', 'Take it off', 'Plate'],
        substeps: [
          { substeps: [] },
          { substeps: ['Rinse', 'Slice thinly'] },
          { substeps: [] },
          { substeps: ['Garlic first', GLOSS] },
        ],
      },
    },
  },
  flowVertical: {
    type: 'flow_map',
    spec: {
      title: '烘焙一个很长标题的蛋糕',
      orientation: 'vertical',
      steps: ['和面', ZH_LONG, '烘烤', '冷却'],
      substeps: [
        { step: '和面', substeps: ['面粉', '鸡蛋', '糖'] },
        { step: '烘烤', substeps: ['180度'] },
      ],
      secondary: {
        title: 'Bake a cake with a long title',
        steps: ['Mix', GLOSS, 'Bake', 'Cool'],
        substeps: [
          { substeps: ['Flour', 'Eggs', 'Sugar'] },
          { substeps: [] },
          { substeps: ['180C'] },
        ],
      },
    },
  },
  flowVerticalNoSubsteps: {
    type: 'flow_map',
    spec: {
      title: '步骤',
      orientation: 'vertical',
      steps: ['一', ZH_LONG, '三'],
      secondary: { title: 'Steps', steps: ['One', GLOSS, 'Three'] },
    },
  },
  multiFlow: {
    type: 'multi_flow_map',
    spec: {
      event: '城市空气污染',
      causes: ['工业', ZH_LONG, '汽车尾气'],
      effects: ['健康', '气候'],
      secondary: {
        event: 'Air pollution in cities',
        causes: ['Industry', GLOSS, 'Car exhaust'],
        effects: ['Health', 'Climate'],
      },
    },
  },
  bridge: {
    type: 'bridge_map',
    spec: {
      dimension: '类比',
      analogies: [
        { left: '鸟', right: '天空' },
        { left: '鱼', right: '水' },
        { left: ZH_LONG, right: '地面' },
        { left: '鼹鼠', right: '土壤' },
        { left: '蝙蝠', right: '洞穴' },
        { left: '青蛙', right: '池塘' },
      ],
      secondary: {
        dimension: 'is to',
        analogies: [
          { left: 'Bird', right: 'Sky' },
          { left: 'Fish', right: 'Water' },
          { left: GLOSS, right: 'Ground' },
          { left: 'Mole', right: 'Soil' },
          { left: 'Bat', right: 'Cave' },
          { left: 'Frog', right: 'Pond' },
        ],
      },
    },
  },
}

/** specIO.loadFromSpec for a fresh spec: load, attach the mirror, relayout, then any shape restyle. */
function loadBilingual(type: DiagramType, spec: Record<string, unknown>, shape?: string) {
  const result = loadSpecForDiagramType(structuredClone(spec), type)
  attachRemainingSecondary(type, result.nodes, spec)
  const stored = relayoutLoadedSpecNodes(type, result, false)
  const nodes = shape
    ? stored.map((node) => ({ ...node, style: { ...node.style, nodeShape: shape } }) as DiagramNode)
    : stored
  return { nodes, conns: result.connections ?? [] }
}

function recalc(type: DiagramType, nodes: DiagramNode[], conns: Connection[], dims: Dims) {
  switch (type) {
    case 'circle_map':
      return recalculateCircleMapLayout(nodes, dims)
    case 'bubble_map':
      return recalculateBubbleMapLayout(nodes, dims)
    case 'double_bubble_map':
      return recalculateDoubleBubbleMapLayout(nodes, dims)
    case 'tree_map':
      return recalculateTreeMapLayout(nodes, dims)
    case 'brace_map':
      return recalculateBraceMapLayout(nodes, conns, dims)
    case 'flow_map':
      return recalculateFlowMapLayout(nodes, dims)
    case 'multi_flow_map':
      return recalculateMultiFlowMapLayout(nodes, null, dims)
    case 'bridge_map':
      return recalculateBridgeMapLayout(nodes, dims)
    default:
      throw new Error(`no recalc for ${type}`)
  }
}

describe('diagram layout golden positions', () => {
  for (const [name, { type, spec }] of Object.entries(SPECS)) {
    it(`${name}: load, estimate recalc, measured recalc`, () => {
      const loaded = loadSpecForDiagramType(structuredClone(spec), type)
      const conns = loaded.connections ?? []
      const estimated = recalc(type, loaded.nodes, conns, {})
      const measured = recalc(type, loaded.nodes, conns, syntheticDims(loaded.nodes))
      const aliases = idAliases(loaded.nodes)
      expect({
        load: serialize(loaded.nodes, aliases),
        estimated: serialize(estimated, aliases),
        measured: serialize(measured, aliases),
      }).toMatchSnapshot()
    })
  }

  for (const [name, { type, spec }] of Object.entries(SPECS)) {
    it(`${name}: recalc on its own output does not move nodes`, () => {
      const loaded = loadSpecForDiagramType(structuredClone(spec), type)
      const conns = loaded.connections ?? []
      const dims = syntheticDims(loaded.nodes)
      const aliases = idAliases(loaded.nodes)
      const once = recalc(type, loaded.nodes, conns, dims)
      const twice = recalc(type, once, conns, dims)
      expect(serialize(twice, aliases)).toEqual(serialize(once, aliases))
    })
  }

  for (const [name, { type, spec, shape }] of Object.entries(BILINGUAL_SPECS)) {
    it(`bilingual ${name}: load, estimate recalc, measured recalc`, () => {
      const { nodes, conns } = loadBilingual(type, spec, shape)
      expect(nodes.some((node) => node.textSecondary)).toBe(true)
      const aliases = idAliases(nodes)
      expect({
        load: serialize(nodes, aliases),
        estimated: serialize(recalc(type, nodes, conns, {}), aliases),
        measured: serialize(recalc(type, nodes, conns, syntheticDims(nodes)), aliases),
      }).toMatchSnapshot()
    })

    it(`bilingual ${name}: recalc on its own output does not move nodes`, () => {
      const { nodes, conns } = loadBilingual(type, spec, shape)
      const dims = syntheticDims(nodes)
      const aliases = idAliases(nodes)
      const once = recalc(type, nodes, conns, dims)
      expect(serialize(recalc(type, once, conns, dims), aliases)).toEqual(serialize(once, aliases))
    })

    if (!shape) {
      it(`bilingual ${name}: stored load matches the first canvas layout`, () => {
        const { nodes, conns } = loadBilingual(type, spec)
        const aliases = idAliases(nodes)
        expect(serialize(nodes, aliases)).toEqual(
          serialize(recalc(type, nodes, conns, {}), aliases)
        )
      })
    }
  }

  for (const canvasMode of ['v2', 'legacy'] as const) {
    it(`mindmap ${canvasMode}: bilingual load`, () => {
      const loaded = loadSpecForDiagramType(
        {
          topic: '中心',
          children: [
            { text: '分支一', children: [{ text: '叶子' }, { text: ZH_LONG }] },
            { text: '分支二', children: [] },
            { text: '分支三', children: [{ text: '甲' }] },
          ],
          secondary: {
            topic: 'Center',
            children: [
              { text: 'Branch one', children: [{ text: 'Leaf' }, { text: GLOSS }] },
              { text: 'Branch two', children: [] },
              { text: 'Branch three', children: [{ text: 'A' }] },
            ],
          },
        },
        'mindmap',
        { mindMapCanvasMode: canvasMode }
      )
      expect(loaded.nodes.filter((node) => node.textSecondary)).toHaveLength(7)
      expect(serialize(loaded.nodes, idAliases(loaded.nodes))).toMatchSnapshot()
    })

    it(`mindmap ${canvasMode}: load`, () => {
      const loaded = loadSpecForDiagramType(
        {
          topic: 'Central idea',
          children: [
            { text: 'Branch one', children: [{ text: 'Leaf a' }, { text: LONG }] },
            { text: 'Branch two', children: [{ text: 'Leaf b' }] },
            { text: '第三分支', children: [] },
            {
              text: 'Branch four',
              children: [{ text: 'c' }, { text: 'd' }, { text: 'e' }, { text: 'f' }],
            },
            { text: 'Branch five', children: [{ text: 'g' }] },
          ],
        },
        'mindmap',
        { mindMapCanvasMode: canvasMode }
      )
      expect(serialize(loaded.nodes, idAliases(loaded.nodes))).toMatchSnapshot()
    })
  }
})
