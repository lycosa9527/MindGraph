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
const rosterPinned = ref(false)

export function useMindmateSeminarFaces() {
  return { faces }
}

export function pinSeminarRoster(next: SeminarFace[]): void {
  rosterPinned.value = true
  faces.value = next
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
  rosterPinned.value = false
  faces.value = []
}

export function showSeminarFaces(next: SeminarFace[]): void {
  if (rosterPinned.value) {
    // Header faces = people currently in the room (online), not the full invite list.
    const presentIds = new Set(next.map((face) => face.userId))
    const kept = faces.value.filter((face) => presentIds.has(face.userId))
    const known = new Set(kept.map((face) => face.userId))
    const extras = next.filter((face) => !known.has(face.userId))
    faces.value = extras.length > 0 ? [...kept, ...extras] : kept
    return
  }
  faces.value = next
}
