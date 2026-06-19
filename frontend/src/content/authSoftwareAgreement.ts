/**
 * MindGraph combined Terms of Use + Privacy Policy — shown from /auth footer.
 * Draft for review; not legal advice.
 */
import { isChineseUiLocale } from '@/types/sidebar-quotes'

const COMPANY_ZH = '北京思源智教科技有限公司'
const COMPANY_EN = 'Beijing Siyuan Zhijiao Technology Co., Ltd.'

export interface SoftwareAgreementSection {
  title: string
  paragraphs: string[]
}

export interface SoftwareAgreementContent {
  title: string
  updated: string
  preamble: string
  sections: SoftwareAgreementSection[]
}

export const SOFTWARE_AGREEMENT_ZH: SoftwareAgreementContent = {
  title: 'MindGraph 用户协议与隐私政策',
  updated: '2026年6月19日',
  preamble: `MindGraph 是由${COMPANY_ZH}（以下简称「本公司」或「我们」）开发并运营的教育教学产品（以下简称「本平台」）。本文件同时构成《用户协议》与《隐私政策》。在您注册、登录或使用本平台任何功能前，请仔细阅读。您使用本平台，即视为您已阅读、理解并同意本文件全部内容。`,
  sections: [
    {
      title: '一、协议接受与适用范围',
      paragraphs: [
        `本文件是您与${COMPANY_ZH}之间关于使用 MindGraph 及相关服务所订立的法律协议，并说明我们如何处理您的个人信息及其他相关数据。`,
        '若您不同意本文件任何条款，请停止使用本平台。若您代表学校或机构使用本平台，您声明并保证已获得该组织授权，并有权使该组织受本文件约束。',
        '如您的学校或机构与本公司另行签署了书面服务协议，该书面协议与本文件不一致的，以书面协议为准；未约定事项适用本文件。',
      ],
    },
    {
      title: '二、服务说明',
      paragraphs: [
        '本平台面向教育教学场景，提供 AI 辅助思维导图生成、知识整理、智能对话（MindMate）、协作、第三方集成及相关工具服务。具体功能以平台实际提供为准。',
        '本平台按「现状」提供服务。我们将尽力保障服务稳定与安全，但不保证服务在任何情况下均不间断、无错误或完全满足您的特定教学需求。',
        'AI 生成内容仅供参考，不构成专业意见。您应在教育教学实践中自行判断并核实其准确性与适用性。',
      ],
    },
    {
      title: '三、用户义务与账号管理',
      paragraphs: [
        '您应保证注册信息真实、准确，并妥善保管账户与密码。您对账户下的操作行为承担责任。',
        '您不得利用本平台制作、传播违法、侵权、虚假、骚扰性或其他违反公序良俗的内容，不得干扰平台正常运行或侵害他人合法权益。',
        '若您上传、输入或生成的内容涉及学生或其他个人的个人信息，您应确保已获得学校、监护人或相关权利人的必要授权，并仅上传实现教学目的所必需的信息。',
      ],
    },
    {
      title: '四、知识产权与专有许可',
      paragraphs: [
        `MindGraph 及其软件、界面设计、商标、文档、算法与相关技术成果的知识产权归${COMPANY_ZH}或相应权利人所有。`,
        'MindGraph 受专有许可证（Proprietary License）保护，并非开源软件。未经授权，您不得运行、修改、复制、分发、商业利用或创建衍生作品。',
        '除本文件项下经本公司明确授权、通过本平台提供的登录使用外，任何对软件及相关资料的使用（包括但不限于自行部署、二次开发、转授权、在校内外独立运行或用于竞赛、培训、出版等场景）均须事先取得本公司的书面许可。',
        '您通过本平台上传或生成的教学内容，其依法享有的著作权等权利仍归您或相应权利人所有；您授予本公司在提供服务、履行本文件及开展统计分析所必需的范围内使用该等内容的非独占许可。未经授权，您不得将平台数据用于与本平台竞争、批量爬取或损害平台安全与稳定的行为。',
      ],
    },
    {
      title: '五、我们收集的信息',
      paragraphs: [
        '为向您提供、维护和改进服务，并履行法定义务，我们可能收集以下信息：',
        '（1）账户与身份信息：手机号码、姓名、所属学校或组织、角色、头像、邀请码及账户状态等；',
        '（2）教学与创作内容：思维导图、笔记、上传的文件与图片、知识库文档、协作内容等；',
        '（3）交互与生成内容：您在 MindMate 等模块中的输入、生成结果及相关会话标识（具体存储范围以产品实际功能为准）；',
        '（4）使用与日志信息：登录时间、功能使用记录、操作日志、设备类型、浏览器信息、IP 地址、错误日志等；',
        '（5）第三方绑定信息：如您绑定钉钉等第三方账号，我们可能保存相应的绑定标识及平台返回的必要信息；',
        '（6）安全与合规信息：验证码校验记录、异常登录检测、审计日志等。',
      ],
    },
    {
      title: '六、我们如何使用信息',
      paragraphs: [
        '我们基于以下目的处理上述信息：',
        '（1）提供核心服务：账户注册与登录、导图生成与保存、协作、智能对话、导出、学校与组织管理等；',
        '（2）保障安全与稳定：身份验证、故障排查、防范欺诈与滥用、系统维护；',
        '（3）改进产品体验：统计分析、功能优化、模型效果评估（优先使用去标识化或聚合数据）；',
        '（4）履行法律法规要求、响应监管或司法机关依法提出的要求；',
        '（5）经您另行明确同意的其他用途。',
        '我们仅在实现上述目的所必需的范围内处理信息，并采取合理措施降低识别特定个人的风险。',
      ],
    },
    {
      title: '七、教育研究用途',
      paragraphs: [
        '为改进教学质量、优化学习体验、开展教育科学研究及产品迭代，在符合法律法规的前提下，我们可对平台数据进行统计、分析与研究使用，包括：',
        '（1）汇总使用情况与功能效果，用于教学研究与产品改进；',
        '（2）在去除或无法识别特定个人身份的前提下，将数据用于教育领域学术研究、论文撰写或行业报告；',
        '（3）基于匿名化或聚合数据评估 AI 辅助教学效果。',
        '若研究活动需要使用可识别到特定个人的信息，我们将另行征得您的明示同意，或确保已由学校等合法主体依法取得并向我们提供必要授权。',
      ],
    },
    {
      title: '八、第三方服务与委托处理',
      paragraphs: [
        '为实现本平台功能，我们可能委托或接入第三方服务，并在必要范围内向其提供相关信息，例如：',
        '（1）大模型及 AI 推理服务提供方（用于内容生成、理解与分析）；',
        '（2）协作与消息平台（如钉钉等）；',
        '（3）云基础设施、数据库、缓存、搜索与对象存储服务；',
        '（4）短信验证、安全检测及其他技术服务提供方。',
        '我们会要求第三方在委托范围内处理信息，并采取合理安全措施。第三方具体名称与处理范围可能随业务调整，我们将在合理范围内更新本文件或通过产品界面提示重要变化。',
      ],
    },
    {
      title: '九、信息共享、转让与公开披露',
      paragraphs: [
        '我们不会向无关第三方出售可识别您个人身份的信息。除以下情形外，我们不会向第三方共享您的个人信息：',
        '（1）事先获得您的明示同意；',
        '（2）根据法律法规规定、诉讼/仲裁需要，或应行政机关、司法机关依法提出的要求；',
        '（3）为履行本文件或向您提供服务所必需，向本文件第八条所列第三方提供；',
        '（4）在学校或机构部署模式下，向您所属组织的授权管理员提供与其管理职责相关的必要信息。',
        '如发生合并、收购、资产转让等情形，我们将要求继受方继续受本文件约束，或重新征得您的同意。',
      ],
    },
    {
      title: '十、信息存储与保留',
      paragraphs: [
        '您的信息原则上存储于中华人民共和国境内。我们将在实现本文件所述目的所必需的期限内保留信息，法律法规另有规定或您另行同意的除外。',
        '账户注销、学校解约或处理目的已实现后，我们将依法删除或匿名化处理相关信息；法律要求留存的除外。备份系统中的数据可能延迟删除，但我们会停止除存储与安全防护以外的其他处理。',
      ],
    },
    {
      title: '十一、您的权利',
      paragraphs: [
        '根据适用法律法规，您对个人信息享有以下权利：',
        '（1）查阅、复制：您可通过账户设置或联系平台管理员了解我们持有的与您相关的信息；',
        '（2）更正、补充：发现信息有误时，可申请更正或补充；',
        '（3）删除：在符合法定条件时，可申请删除相关信息；',
        '（4）撤回同意：您可撤回此前就特定处理活动给予的同意，但不影响撤回前基于同意已进行的处理；',
        '（5）注销账户：您可申请注销账户，我们将按法律规定处理相关数据。',
        '您可通过平台内反馈或学校管理员联系我们行使上述权利。我们将在合理期限内答复。为保障安全，我们可能先验证您的身份。',
      ],
    },
    {
      title: '十二、未成年人与学生个人信息',
      paragraphs: [
        '本平台主要面向教师及学校工作人员。若学生直接或间接使用本平台，学校及教师应确保已取得监护人或学校的合法授权，并避免上传超出教学必要范围的学生个人信息。',
        '我们不会在明知的情况下主动收集未满十四周岁未成年人的个人信息，除非已获得监护人的明示同意或学校依法提供的有效授权。如发现不当收集，请联系我们删除。',
      ],
    },
    {
      title: '十三、信息安全',
      paragraphs: [
        '我们采取访问控制、传输加密、日志审计、权限分级等合理可行的安全措施保护您的信息，并持续改进安全防护能力。',
        '尽管已采取合理措施，互联网环境并非绝对安全。请您妥善保管账户凭证，并及时告知我们可疑的安全事件。',
        '如发生个人信息安全事件，我们将按照法律法规要求启动应急预案，并以合理方式告知您事件概况、可能影响和已采取的措施。',
      ],
    },
    {
      title: '十四、服务变更、暂停与终止',
      paragraphs: [
        '我们可因维护、升级、合规或不可抗力等原因暂停或终止部分或全部服务，并将尽可能提前通知。',
        '若您严重违反本文件或相关法律法规，我们有权限制、暂停或终止向您提供服务，并依法保留相关记录。',
      ],
    },
    {
      title: '十五、免责声明',
      paragraphs: [
        '在法律允许的最大范围内，因不可抗力、第三方服务故障、网络中断或您自身原因导致的损失，我们不承担超出法律规定范围的责任。',
        '对于您自行上传、发布或依赖 AI 生成内容所引发的内容纠纷、侵权争议或教学决策后果，您应自行承担相应责任，法律法规另有规定的除外。',
      ],
    },
    {
      title: '十六、协议修订',
      paragraphs: [
        '我们可根据业务与法律变化修订本文件，修订后的版本将在平台公布。若您继续使用本平台，即视为接受修订后的内容。涉及您重大权益变更时，我们将通过弹窗、站内通知或其他合理方式提醒您注意。',
      ],
    },
    {
      title: '十七、适用法律与争议解决',
      paragraphs: [
        '本文件的订立、生效、解释、履行及争议解决适用中华人民共和国大陆地区法律（不含冲突法）。',
        '因本文件引起的或与本文件有关的争议，双方应先友好协商；协商不成的，任何一方可向本公司住所地有管辖权的人民法院提起诉讼。',
      ],
    },
    {
      title: '十八、联系我们',
      paragraphs: [
        `如对本文件、个人信息处理或软件授权许可有疑问、投诉或建议，请通过平台内反馈渠道或您所在学校的平台管理员与我们联系。`,
        `涉及自行部署、二次开发或其他超出本平台登录使用的需求，须向${COMPANY_ZH}申请书面许可。`,
      ],
    },
  ],
}

export const SOFTWARE_AGREEMENT_EN: SoftwareAgreementContent = {
  title: 'MindGraph Terms of Use & Privacy Policy',
  updated: '19 June 2026',
  preamble: `MindGraph is an educational product developed and operated by ${COMPANY_EN} (${COMPANY_ZH}) ("we", "us", "the Company"). This document combines our Terms of Use and Privacy Policy. Please read it before you register, sign in, or use any feature. By using the Platform, you acknowledge that you have read, understood, and agree to this document in full.`,
  sections: [
    {
      title: '1. Acceptance and scope',
      paragraphs: [
        `This document is a legal agreement between you and ${COMPANY_EN} (${COMPANY_ZH}) regarding your use of MindGraph and related services, and explains how we process your personal information and related data.`,
        'If you do not agree, do not use the Platform. If you use the Platform on behalf of a school or organization, you represent that you are authorized to bind that organization to this document.',
        'If your school or organization has signed a separate written service agreement with us, that agreement prevails where it conflicts with this document; otherwise this document applies.',
      ],
    },
    {
      title: '2. Services',
      paragraphs: [
        'The Platform provides AI-assisted diagram generation, knowledge organization, MindMate conversations, collaboration, third-party integrations, and related educational tools. Available features may change over time.',
        'The Platform is provided "as is". We work to keep it stable and secure but do not guarantee uninterrupted, error-free service or that it will meet every specific teaching need.',
        'AI-generated content is for reference only and is not professional advice. You should independently verify accuracy and suitability in your teaching practice.',
      ],
    },
    {
      title: '3. Your responsibilities and accounts',
      paragraphs: [
        'Provide accurate registration information and keep your account credentials secure. You are responsible for activity under your account.',
        "Do not use the Platform to create or distribute unlawful, infringing, false, harassing, or otherwise harmful content, or to disrupt the Platform or others' rights.",
        'If you upload, input, or generate content involving student or other personal information, ensure you have required authorization from the school, guardians, or other rights holders, and upload only what is necessary for teaching purposes.',
      ],
    },
    {
      title: '4. Intellectual property and proprietary license',
      paragraphs: [
        `MindGraph and its software, interface design, trademarks, documentation, algorithms, and related technology are owned by ${COMPANY_EN} (${COMPANY_ZH}) or respective rights holders.`,
        'MindGraph is protected by a Proprietary License and is not open-source software. Without authorization, you may not run, modify, copy, distribute, commercially exploit, or create derivative works.',
        'Except for sign-in use expressly authorized through this Platform under this document, any use of the software or related materials (including self-hosting, modification, sublicensing, independent operation inside or outside schools, or use in competitions, training, or publications) requires prior written permission from the Company.',
        'Copyright and other lawful rights in teaching content you upload or generate remain yours or belong to respective rights holders. You grant us a non-exclusive license to use such content as reasonably necessary to provide services, perform this document, and conduct statistical analysis. Without our permission, you may not use Platform data to compete with the Platform, bulk-scrape, or harm Platform security or stability.',
      ],
    },
    {
      title: '5. Information we collect',
      paragraphs: [
        'To provide, maintain, and improve services and meet legal obligations, we may collect:',
        '(1) Account and identity information: phone number, name, school or organization, role, avatar, invitation code, and account status;',
        '(2) Teaching and creative content: diagrams, notes, uploaded files and images, knowledge-base documents, and collaboration content;',
        '(3) Interaction and generated content: inputs, outputs, and session identifiers in MindMate and similar modules (exact scope depends on product features);',
        '(4) Usage and log data: sign-in times, feature usage, operation logs, device type, browser information, IP address, and error logs;',
        '(5) Third-party binding data: if you bind DingTalk or similar accounts, we may store binding identifiers and necessary data returned by those platforms;',
        '(6) Security and compliance data: captcha verification, abnormal sign-in detection, and audit logs.',
      ],
    },
    {
      title: '6. How we use information',
      paragraphs: [
        'We process information for the following purposes:',
        '(1) Core services: registration and sign-in, diagram generation and storage, collaboration, AI conversations, export, and school or organization management;',
        '(2) Security and stability: authentication, troubleshooting, fraud and abuse prevention, and system maintenance;',
        '(3) Product improvement: statistical analysis, feature optimization, and model evaluation (preferably using de-identified or aggregated data);',
        '(4) Compliance with applicable laws and lawful requests from regulators or judicial authorities;',
        '(5) Other purposes with your separate explicit consent.',
        'We process information only as necessary for these purposes and take reasonable steps to reduce the risk of identifying specific individuals.',
      ],
    },
    {
      title: '7. Educational research use',
      paragraphs: [
        'To improve teaching quality, learning experience, educational research, and product development, we may analyze Platform data in compliance with applicable law, including to:',
        '(1) aggregate usage and feature outcomes for teaching research and product improvement;',
        '(2) use de-identified or non-personally identifiable data for academic research, publications, or industry reports in education;',
        '(3) evaluate AI-assisted teaching effectiveness using anonymized or aggregated data.',
        'If research requires personally identifiable information, we will obtain your separate explicit consent, or ensure that a school or other lawful controller has provided the required authorization.',
      ],
    },
    {
      title: '8. Third-party services and processors',
      paragraphs: [
        'To operate the Platform, we may use third-party services and share necessary information with them, such as:',
        '(1) large-model and AI inference providers (for generation, understanding, and analysis);',
        '(2) collaboration and messaging platforms (such as DingTalk);',
        '(3) cloud infrastructure, databases, caches, search, and object storage services;',
        '(4) SMS verification, security, and other technical service providers.',
        'We require third parties to process information within the entrusted scope and apply reasonable security measures. Specific providers and scope may change as our business evolves; we will update this document or provide in-product notice for material changes where practical.',
      ],
    },
    {
      title: '9. Sharing, transfer, and disclosure',
      paragraphs: [
        'We do not sell personally identifiable information to unrelated third parties. Except as described below, we do not share your personal information with third parties:',
        '(1) with your explicit consent;',
        '(2) as required by applicable law, litigation/arbitration, or lawful requests from government or judicial authorities;',
        '(3) as necessary to perform this document or provide services, including to third parties listed in Section 8;',
        '(4) in school or organization deployments, to authorized administrators of your organization for duties within their management scope.',
        'If a merger, acquisition, or asset transfer occurs, we will require the successor to remain bound by this document or obtain your consent again.',
      ],
    },
    {
      title: '10. Storage and retention',
      paragraphs: [
        "Your information is generally stored within the People's Republic of China. We retain information only as long as necessary for the purposes described in this document, unless a longer period is required by law or agreed with you.",
        'After account cancellation, school contract termination, or when processing purposes are fulfilled, we will delete or anonymize relevant information as required by law, except where retention is legally required. Data in backups may be deleted later, but we will stop processing it except for storage and security protection.',
      ],
    },
    {
      title: '11. Your rights',
      paragraphs: [
        'Under applicable law, you may have the following rights regarding personal information:',
        '(1) access and copy: learn what information we hold about you through account settings or your platform administrator;',
        '(2) correction and supplementation: request correction or supplementation if information is inaccurate;',
        '(3) deletion: request deletion where legal conditions are met;',
        '(4) withdraw consent: withdraw consent for specific processing, without affecting prior processing based on consent;',
        '(5) account cancellation: request account cancellation and we will handle related data as required by law.',
        'Contact us through in-platform feedback or your school administrator to exercise these rights. We will respond within a reasonable period and may verify your identity for security.',
      ],
    },
    {
      title: '12. Minors and student personal information',
      paragraphs: [
        'The Platform is primarily intended for teachers and school staff. If students use the Platform directly or indirectly, schools and teachers must ensure lawful authorization from guardians or the school, and avoid uploading student personal information beyond what is necessary for teaching.',
        'We do not knowingly collect personal information from children under 14 without guardian consent or valid school authorization. If you believe we have collected such information improperly, contact us for deletion.',
      ],
    },
    {
      title: '13. Information security',
      paragraphs: [
        'We use reasonable safeguards such as access control, encryption in transit, log auditing, and role-based permissions, and we continue to improve our security posture.',
        'Despite reasonable measures, no internet environment is absolutely secure. Please protect your credentials and report suspicious security events promptly.',
        'If a personal information security incident occurs, we will activate our response plan as required by law and inform you of the general situation, potential impact, and measures taken by reasonable means.',
      ],
    },
    {
      title: '14. Changes, suspension, and termination',
      paragraphs: [
        'We may suspend or discontinue some or all services for maintenance, upgrades, compliance, or force majeure, and will try to provide advance notice when practical.',
        'If you materially breach this document or applicable law, we may restrict, suspend, or terminate your access and retain records as required by law.',
      ],
    },
    {
      title: '15. Disclaimer',
      paragraphs: [
        'To the maximum extent permitted by law, we are not liable beyond legal requirements for losses caused by force majeure, third-party failures, network interruption, or your own actions.',
        'You are responsible for disputes, infringement claims, or teaching decisions arising from content you upload, publish, or rely on from AI-generated output, except where applicable law provides otherwise.',
      ],
    },
    {
      title: '16. Revisions',
      paragraphs: [
        'We may revise this document as our business or legal obligations change. Updated versions will be published on the Platform; continued use means acceptance. For material changes affecting your significant rights, we will notify you by dialog, in-product notice, or other reasonable means.',
      ],
    },
    {
      title: '17. Governing law and dispute resolution',
      paragraphs: [
        "This document is governed by the laws of the mainland of the People's Republic of China (excluding conflict-of-law rules).",
        "Disputes arising from or relating to this document should first be resolved through friendly negotiation. If negotiation fails, either party may bring suit in a court with jurisdiction at the Company's domicile.",
      ],
    },
    {
      title: '18. Contact',
      paragraphs: [
        `Questions, complaints, or requests regarding this document, personal information processing, or software licensing may be sent through in-platform feedback or your school's platform administrator.`,
        `Requests for self-hosting, modification, or any use beyond sign-in on this Platform require written permission from ${COMPANY_EN} (${COMPANY_ZH}).`,
      ],
    },
  ],
}

/** Chinese UI (`zh`, `zh-tw`) → simplified Chinese; all other locales → English. */
export function softwareAgreementForUiCode(uiCode: string): SoftwareAgreementContent {
  if (isChineseUiLocale(uiCode)) {
    return SOFTWARE_AGREEMENT_ZH
  }
  return SOFTWARE_AGREEMENT_EN
}
