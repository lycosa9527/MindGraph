/**
 * Voice Types - Type definitions for voice agent
 */

export interface VoiceState {
  active: boolean
  sessionId: string | null
  lastTranscription: string
  isListening: boolean
  isSpeaking: boolean
}

export interface VoiceConfig {
  language: string
  autoStart: boolean
  continuous: boolean
}

export interface TranscriptionResult {
  text: string
  confidence: number
  isFinal: boolean
}
