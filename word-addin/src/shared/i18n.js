/* global mgLoadPrefs */
/**
 * zh / en strings for MindGraph for Word (task-pane shell).
 */

var MG_I18N = {
  zh: {
    btnMindMate: 'MindMate',
    btnMindGraph: 'MindGraph',
    btnVoice: '语音笔记',
    btnShowcase: '案例广场',
    btnManual: '使用手册',
    btnSettings: '设置',
    spaOpening: '正在打开…',
    spaNeedAuth: '请先在「设置」中保存手机号与 API 令牌，或继续以访客打开。',
    spaOpenGuest: '以访客打开',
    voiceHint: '语音笔记原型：开始 / 暂停 / 停止与假电平、转写区。尚未接入麦克风与后端。',
    voiceStart: '开始录音',
    voicePause: '暂停',
    voiceResume: '继续',
    voiceStop: '停止',
    voiceTranscript: '转写文本将显示在这里。',
    voiceIdle: '空闲',
    voiceRecording: '录音中',
    voicePaused: '已暂停',
    manualTitle: 'MindGraph 使用手册',
    manualIntro: '在 Microsoft Word 中打开 MindMate、图示工作室、语音笔记与案例广场。',
    manualStep1: '在「设置」中填写服务器地址（默认测试环境）、手机号与 API 令牌（mgat_…）。',
    manualStep2: '令牌在网页端「设置 → API 令牌」生成，有效期约 90 天。',
    manualStep3: '调试：安装桌面版 Word 后，于本目录执行 npm start（需 HTTPS 证书）。',
    manualStep4: '已保存令牌时，MindMate / MindGraph / 案例广场会自动登录并打开桌面版页面。',
    settingsLanguage: '界面语言',
    settingsLanguageHint: '默认跟随 Word 界面语言；可在此手动覆盖。',
    settingsBaseUrl: '服务器地址',
    settingsPhone: '账户手机号',
    settingsToken: 'API 令牌 (mgat_…)',
    settingsSave: '保存',
    settingsClear: '清除令牌',
    settingsStatusEmpty: '未保存登录信息（需手机号与 API 令牌）',
    settingsStatusSaved: '已保存登录信息',
    settingsSavedToast: '已保存',
    settingsClearedToast: '已清除令牌',
    langZh: '中文',
    langEn: 'English',
    handoffFailed: '自动登录失败，将以访客打开。',
  },
  en: {
    btnMindMate: 'MindMate',
    btnMindGraph: 'MindGraph',
    btnVoice: 'Voice',
    btnShowcase: 'Showcase',
    btnManual: 'Manual',
    btnSettings: 'Settings',
    spaOpening: 'Opening…',
    spaNeedAuth: 'Save phone + API token in Settings for login-free access, or continue as guest.',
    spaOpenGuest: 'Open as guest',
    voiceHint: 'Voice Notes stub: start / pause / stop, fake level meter, transcript. No mic/backend yet.',
    voiceStart: 'Start',
    voicePause: 'Pause',
    voiceResume: 'Resume',
    voiceStop: 'Stop',
    voiceTranscript: 'Transcript will appear here.',
    voiceIdle: 'Idle',
    voiceRecording: 'Recording',
    voicePaused: 'Paused',
    manualTitle: 'MindGraph manual',
    manualIntro: 'Open MindMate, diagram studio, voice notes, and showcase from Microsoft Word.',
    manualStep1: 'In Settings, set server URL (default test), phone, and API token (mgat_…).',
    manualStep2: 'Mint the token in the web app under Settings → API token (about 90 days).',
    manualStep3: 'Debug: install desktop Word, then run npm start in this folder (HTTPS cert required).',
    manualStep4: 'With a saved token, MindMate / MindGraph / Showcase sign in and open the desktop web app.',
    settingsLanguage: 'Language',
    settingsLanguageHint: 'Defaults to Word’s UI language; override here if you prefer.',
    settingsBaseUrl: 'Server URL',
    settingsPhone: 'Account phone',
    settingsToken: 'API token (mgat_…)',
    settingsSave: 'Save',
    settingsClear: 'Clear token',
    settingsStatusEmpty: 'No credentials saved (phone + API token required)',
    settingsStatusSaved: 'Credentials saved',
    settingsSavedToast: 'Saved',
    settingsClearedToast: 'Token cleared',
    langZh: '中文',
    langEn: 'English',
    handoffFailed: 'Auto sign-in failed; opening as guest.',
  },
}

function mgT(key) {
  var prefs = typeof mgLoadPrefs === 'function' ? mgLoadPrefs() : { language: 'en' }
  var lang = prefs.language === 'zh' ? 'zh' : 'en'
  var table = MG_I18N[lang] || MG_I18N.en
  if (Object.prototype.hasOwnProperty.call(table, key)) {
    return table[key]
  }
  if (Object.prototype.hasOwnProperty.call(MG_I18N.en, key)) {
    return MG_I18N.en[key]
  }
  return key
}
