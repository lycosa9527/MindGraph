/**
 * Push a 研习社 narrow with the matching query so store→URL sync cannot
 * race a bare `/workshop-chat` push back to the inbox.
 */
import type { Router } from 'vue-router'

import type { WorkshopRouteQueryState } from '@/utils/workshopChatRoute'
import { workshopQueryFromState } from '@/utils/workshopChatRoute'

export function workshopDmRouteQuery(partnerId: number): Record<string, string> {
  const state: WorkshopRouteQueryState = {
    currentChannelId: null,
    currentTopicId: null,
    currentDMPartnerId: partnerId,
    showChannelBrowser: false,
    workshopHomeViewActive: false,
    mainChannelFeedActive: false,
  }
  return workshopQueryFromState(state)
}

export function pushWorkshopDm(router: Router, partnerId: number): void {
  void router.push({ name: 'WorkshopChat', query: workshopDmRouteQuery(partnerId) })
}
