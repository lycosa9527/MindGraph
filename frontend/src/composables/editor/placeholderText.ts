/**
 * Default canvas labels that should not be treated as real topic text.
 * Leaf module: stores and palette helpers import this without loading auto-complete.
 */

const CHINESE_PLACEHOLDERS = [
  /^分支\s*\d+$/, // 分支1, 分支2
  /^子项\s*[\d.]+$/, // 子项1.1, 子项2.3
  /^子节点\s*[\d.]+$/, // 子节点1.1
  /^子\s*[\d.]+$/, // 子1.1
  /^新.*$/, // 新节点, 新属性, 新步骤, 新原因, 新结果, etc.
  /^属性\s*\d+$/, // 属性1, 属性2
  /^步骤\s*\d+$/, // 步骤1, 步骤2
  /^子步骤\s*[\d.]+$/, // 子步骤1.1, 子步骤2.2 (Flow Map)
  /^原因\s*\d+$/, // 原因1
  /^结果\s*\d+$/, // 结果1
  /^联想\s*\d+$/, // 联想1, 联想2 (Circle Map context nodes)
  /^事件流程$/, // 事件流程 (Flow Map title)
  /^事件$/, // 事件 (Multi-Flow Map event)
  /^主题\s*\d+$/, // 主题1
  /^主题$/, // 主题 (Circle Map default)
  /^主题[A-Z]$/, // 主题A, 主题B (Double Bubble Map)
  /^相似点\s*\d+$/, // 相似点1, 相似点2 (Double Bubble Map)
  /^不同点[A-Z]\d+$/, // 不同点A1, 不同点B2 (Double Bubble Map)
  /^如同$/, // 如同 (Bridge Map relating factor)
  /^事物[A-Z]\d+$/, // 事物A1, 事物B1 (Bridge Map)
  /^项目[\d.]+$/, // 项目1.1, 项目2.3 (Tree Map)
  /^根主题$/, // 根主题 (Tree Map)
  /^类别\s*\d+$/, // 类别1, 类别2 (Tree Map)
  /^分类\s*\d+$/, // 分类1
  /^叶子\s*\d+$/, // 叶子1
  /^部分\s*\d+$/, // 部分1, 部分2 (Brace Map)
  /^子部分\s*[\d.]+$/, // 子部分1.1, 子部分1.2 (Brace Map)
  /^新子部分\s*[\d.]+$/, // 新子部分 1, 新子部分 2 (Brace Map default subparts)
  /^左\s*\d+$/, // 左1
  /^右\s*\d+$/, // 右1
  /^中心主题$/, // 中心主题
  /^主要主题$/, // 主要主题
  /^要点\s*\d+$/, // 要点1
  /^概念\s*\d+$/, // 概念1
  /^关联$/, // 关联
  /^整体$/, // 整体 (Brace Map)
  /^特征\s*\d+$/, // 特征1 (Bubble Map)
  /^请输入/, // 请输入主题
  /^焦点问题:请输入$/, // Concept map focus question default (zh)
  /^点击编辑/, // 点击编辑
  /^\[点击设置\]$/, // Bridge map dimension placeholder
]

const EN_DEFAULT_CANVAS_PLACEHOLDERS = [
  /^Focus question:\s*Enter$/i,
  /^Root concept$/i,
  /^'s root concept$/i,
  /^\[Click to set\]$/i,
]

const ENGLISH_PLACEHOLDERS = [
  /^Branch\s+\d+$/i, // Branch 1, Branch 2
  /^Child\s+[\d.]+$/i, // Child 1.1, Child 2.3
  /^New\s+.*$/i, // New Node, New Attribute, New Step, etc.
  /^Attribute\s+\d+$/i, // Attribute 1, Attribute 2
  /^Step\s+\d+$/i, // Step 1, Step 2
  /^Substep\s+[\d.]+$/i, // Substep 1.1, Substep 2.2 (Flow Map)
  /^Cause\s+\d+$/i, // Cause 1
  /^Effect\s+\d+$/i, // Effect 1
  /^Context\s+\d+$/i, // Context 1, Context 2 (Circle Map context nodes)
  /^Process$/i, // Process (Flow Map title)
  /^Main\s+Event$/i, // Main Event (Multi-Flow Map event)
  /^Topic\s*\d*$/i, // Topic, Topic 1
  /^Topic\s+[A-Z]$/i, // Topic A, Topic B (Double Bubble Map)
  /^Similarity\s+\d+$/i, // Similarity 1, 2 (Double Bubble Map)
  /^Difference\s+[A-Z]\d+$/i, // Difference A1, B2 (Double Bubble Map)
  /^as$/i, // as (Bridge Map relating factor)
  /^Item\s+\d+$/i, // Item 1, Item 2 (Bridge Map)
  /^Item\s+[A-Z]$/i, // Item A, Item B (Bridge Map)
  /^Item\s+[\d.]+$/i, // Item 1.1, Item 2.3 (Tree Map)
  /^Root\s+Topic$/i, // Root Topic (Tree Map)
  /^Category\s+\d+$/i, // Category 1 (Tree Map)
  /^Leaf\s+\d+$/i, // Leaf 1
  /^Part\s+\d+$/i, // Part 1 (Brace Map)
  /^Subpart\s+[\d.]+$/i, // Subpart 1.1, Subpart 1.2 (Brace Map)
  /^New\s+Subpart\s+\d+$/i, // New Subpart 1, New Subpart 2 (Brace Map default subparts)
  /^Left\s+\d+$/i, // Left 1
  /^Right\s+\d+$/i, // Right 1
  /^Main\s+Topic$/i, // Main Topic
  /^Central\s+Topic$/i, // Central Topic
  /^Point\s+\d+$/i, // Point 1
  /^Concept\s+\d+$/i, // Concept 1
  /^Relation(ship)?$/i, // Relation, Relationship
  /^Whole$/i, // Whole (Brace Map)
  /^Event$/i, // Event (Multi-Flow Map)
  /^Enter\s+/i, // Enter topic
  /^Click\s+to\s+edit/i, // Click to edit
  /^Association\s*\d*$/i, // Association 1 (Circle Map)
  /^Property\s+\d+$/i, // Property 1 (Bubble Map)
]

const PLACEHOLDER_PATTERNS = [
  ...CHINESE_PLACEHOLDERS,
  ...ENGLISH_PLACEHOLDERS,
  ...EN_DEFAULT_CANVAS_PLACEHOLDERS,
]

/** True when text is empty or a default canvas label, not a real topic. */
export function isPlaceholderText(text: string | undefined | null): boolean {
  if (!text || !text.trim()) return true
  return PLACEHOLDER_PATTERNS.some((pattern) => pattern.test(text.trim()))
}
