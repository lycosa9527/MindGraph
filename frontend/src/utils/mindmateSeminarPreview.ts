/**
 * Local-only seminar transcript so the room can show every message shape.
 * These rows are not sent to the server.
 */
import heroUrl from '@/assets/seminar/face-chat-hero.jpg'
import type { MindmateCollabMessage } from '@/composables/mindmate/useMindmateCollab'
import { seminarSummaryMessage } from '@/utils/mindmateSeminarCards'
import { seminarMessageFileToken } from '@/utils/mindmateSeminarFolder'

const REVIEW_FILE = seminarMessageFileToken(
  '00000000-0000-4000-8000-0000000000aa',
  '中小学课程思政评价指标研究综述.docx'
)
const VOICE_FILE = seminarMessageFileToken('00000000-0000-4000-8000-0000000000bb', '课堂片段.webm')

function at(minute: number): string {
  return new Date(Date.UTC(2026, 9, 15, 6, minute, 0)).toISOString()
}

export function seminarPreviewMessages(self: {
  selfId: number
  selfName: string
}): MindmateCollabMessage[] {
  const selfId = self.selfId > 0 ? self.selfId : 91000
  return [
    {
      clientKey: 'seminar-preview-wang',
      role: 'user',
      sender_user_id: 91001,
      username: '王雅萱',
      created_at: at(1),
      content:
        '第一个目标写得太满了。我建议收成一句：把评价指标怎么进课堂说清楚。综述可以当我们的共同文本。\n\n📎 中小学课程思政评价指标研究综述.docx',
    },
    {
      clientKey: 'seminar-preview-li',
      role: 'user',
      sender_user_id: 91002,
      username: '李思琦',
      created_at: at(4),
      content: `我把综述里和「一体化」有关的两页摘出来了，大家先看这一份。\n\n${REVIEW_FILE}`,
    },
    {
      clientKey: 'seminar-preview-own',
      role: 'user',
      sender_user_id: selfId,
      username: self.selfName || '我',
      created_at: at(7),
      content: '@MindMate 请按刚才两位的意见，把目标收短，并对比「指标进课堂」和「一体化评价」。',
    },
    {
      clientKey: 'seminar-preview-mate',
      role: 'assistant',
      sender_user_id: null,
      username: 'MindMate',
      created_at: at(8),
      content: [
        '可以收成两句，供组长定稿：',
        '',
        '1. 说清思政评价指标如何进入一节课的目标和活动。',
        '2. 用一体化评价看这节课和学生后续学习的衔接。',
        '',
        '两边的差别：左边问「这节课怎么看见指标」，右边问「这节课放进学段链条里还成不成立」。',
        '',
        `![研讨现场](${heroUrl})`,
        '',
        '<!-- mg-reply-kind:teaching_instruction -->',
        '<!-- mg-diagram-id:11111111-1111-4111-8111-111111111111 -->',
      ].join('\n'),
    },
    {
      clientKey: 'seminar-preview-liu',
      role: 'user',
      sender_user_id: 91003,
      username: '刘璨',
      created_at: at(12),
      content: `我补一段课堂上学生的原话，后面评课可以对照。\n\n${VOICE_FILE}`,
    },
    {
      clientKey: 'seminar-preview-summary',
      role: 'user',
      sender_user_id: selfId,
      username: self.selfName || '我',
      created_at: at(16),
      content: seminarSummaryMessage(
        '全部消息',
        [
          '结论',
          '目标收成两句：指标如何进课堂，以及这节课如何放进一体化评价。',
          '',
          '分歧',
          '综述是作为共同文本细读，还是只摘「一体化」相关页，还没定。',
          '',
          '待办',
          '1. 王雅萱改一版目标表述。',
          '2. 李思琦标出综述里要共读的页码。',
          '3. 刘璨把课堂原话整理进评课记录。',
        ].join('\n')
      ),
    },
  ]
}
