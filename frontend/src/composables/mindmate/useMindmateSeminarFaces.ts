/**
 * Shared seminar face list so the header and the room socket stay in step.
 */
import { ref } from 'vue'

import {
  type SeminarFace,
  removeSeminarFace,
  seminarFacesFromJoined,
  upsertSeminarFace,
} from '@/utils/mindmateSeminarFaces'

const faces = ref<SeminarFace[]>([])

export function useMindmateSeminarFaces() {
  return { faces }
}

export function replaceSeminarFaces(raw: unknown, selfFace: SeminarFace | null): void {
  faces.value = seminarFacesFromJoined(raw, selfFace)
}

export function addSeminarFace(face: SeminarFace): void {
  faces.value = upsertSeminarFace(faces.value, face)
}

export function dropSeminarFace(userId: number): void {
  faces.value = removeSeminarFace(faces.value, userId)
}

export function clearSeminarFaces(): void {
  faces.value = []
}

export function showSeminarFaces(next: SeminarFace[]): void {
  faces.value = next
}
