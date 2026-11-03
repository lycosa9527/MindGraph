/**
 * Knowledge document shape shared by File Center and personal knowledge.
 * Package lists and document rows come from Vue Query.
 */
export interface KnowledgeDocument {
  id: number
  file_name: string
  file_type: string
  file_size: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  chunk_count: number
  error_message?: string | null
  processing_progress?: string | null
  processing_progress_percent?: number
  chunking_engine?: string | null
  chunking_mode?: string | null
  rag_status?: 'not_yet' | 'processing' | 'complete' | 'failed' | null
  wiki_status?: 'disabled' | 'not_yet' | 'pending' | 'complete' | null
  /** Extracted markdown size when Document Summary lite has finished. */
  extract_char_count?: number | null
  /** Document Summary ingest family: upload, paste, web, voice_notes, … */
  ingest_source?: string | null
  created_at: string
  updated_at: string
}
