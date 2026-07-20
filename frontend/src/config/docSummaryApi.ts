/**
 * Document Summary HTTP base paths (split from Knowledge Space URLs).
 */
export const DOC_SUMMARY_API_BASE = '/api/doc-summary'
export const DOC_SUMMARY_PACKAGES_BASE = `${DOC_SUMMARY_API_BASE}/packages`
export const DOC_SUMMARY_DOCUMENTS_BASE = `${DOC_SUMMARY_API_BASE}/documents`
export const DOC_SUMMARY_CHAT_HANDOFF_BASE = `${DOC_SUMMARY_API_BASE}/chat-handoff`

/**
 * Hard cap for extracted / pasted text (qwen3.6-flash ~991K max input tokens,
 * with headroom — mirrors ``DOC_SUMMARY_MAX_INPUT_CHARS`` on the backend).
 */
export const DOC_SUMMARY_MAX_INPUT_CHARS = 900_000
/** Upload gate for original files (mirrors backend DOC_SUMMARY_MAX_FILE_BYTES). */
export const DOC_SUMMARY_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
export const DOC_SUMMARY_CONTENT_TOO_LONG_CODE = 'doc_summary_content_too_long'
export const DOC_SUMMARY_STORAGE_CONFLICT_CODE = 'doc_summary_storage_conflict'
