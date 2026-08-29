/** Template catalog row used by TemplatePage (market SKU or mock). */
export interface TemplateResource {
  id: string
  listingId: number | null
  priceMinor: number | null
  title: string
  thumbnail: string
  type: 'MindMate' | 'MindGraph'
  scene: string
  subject: string
  views: number
  downloads: number
}

export interface MarketListingRow {
  id: number
  title: string
  product_type: string | null
  scene: string | null
  subject: string | null
  price_minor: number
}

export function listingRowToTemplate(row: MarketListingRow): TemplateResource {
  return {
    id: String(row.id),
    listingId: row.id,
    priceMinor: row.price_minor,
    title: row.title,
    thumbnail: '',
    type: row.product_type === 'MindMate' ? 'MindMate' : 'MindGraph',
    scene: row.scene ?? '',
    subject: row.subject ?? '',
    views: 0,
    downloads: 0,
  }
}

function mockRow(
  id: string,
  title: string,
  type: 'MindMate' | 'MindGraph',
  scene: string,
  subject: string,
  views: number,
  downloads: number
): TemplateResource {
  return {
    id,
    listingId: null,
    priceMinor: null,
    title,
    thumbnail: '',
    type,
    scene,
    subject,
    views,
    downloads,
  }
}

export const MOCK_TEMPLATE_LISTINGS: TemplateResource[] = [
  mockRow('1', '小学语文课文思维导图模板', 'MindGraph', '教学通用', '语文', 1234, 567),
  mockRow('2', '初中数学公式整理思维导图', 'MindGraph', '总结汇报', '数学', 2345, 890),
  mockRow('3', '英语语法知识点总结', 'MindMate', '教学通用', '英语', 1567, 432),
  mockRow('4', '高中化学元素周期表思维导图', 'MindGraph', '教学通用', '化学', 3456, 1234),
  mockRow('5', '班级文化建设主题班会', 'MindMate', '主题班会', '综合实践', 987, 321),
  mockRow('6', '物理力学知识框架', 'MindGraph', '总结汇报', '物理', 2134, 765),
  mockRow('7', '历史朝代年表思维导图', 'MindGraph', '教学通用', '历史', 4567, 1890),
  mockRow('8', '地理气候类型总结', 'MindMate', '总结汇报', '地理', 1789, 654),
  mockRow('9', '生物细胞结构图解', 'MindGraph', '教学通用', '生物', 2890, 987),
  mockRow('10', '政治考点梳理思维导图', 'MindMate', '总结汇报', '政治', 1234, 456),
  mockRow('11', '音乐乐理知识框架', 'MindMate', '教学通用', '音乐', 876, 234),
  mockRow('12', '美术色彩理论思维导图', 'MindGraph', '教学通用', '美术', 1567, 543),
]
