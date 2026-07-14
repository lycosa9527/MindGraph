import type { ShowcasePost } from '@/utils/apiClient'

/** Mine list / own-post UI: prefer API flags, fall back to status when backend omits them. */
export function postCanWithdraw(post: ShowcasePost, ownPost = true): boolean {
  if (post.can_withdraw === true) return true
  if (post.can_withdraw === false) return false
  return ownPost && post.status === 'pending'
}

export function postCanDelist(post: ShowcasePost, ownPost = true): boolean {
  if (post.can_delist === true) return true
  if (post.can_delist === false) return false
  return ownPost && post.status === 'approved'
}

export function postCanResubmit(post: ShowcasePost, ownPost = true): boolean {
  if (post.can_resubmit === true) return true
  if (post.can_resubmit === false) return false
  return ownPost && post.status === 'rejected'
}

export function postHasAuthorManageActions(post: ShowcasePost, ownPost = true): boolean {
  return (
    postCanWithdraw(post, ownPost) ||
    postCanDelist(post, ownPost) ||
    postCanResubmit(post, ownPost)
  )
}
