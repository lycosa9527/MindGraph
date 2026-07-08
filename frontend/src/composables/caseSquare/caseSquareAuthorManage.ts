import type { CaseSquarePost } from '@/utils/apiClient'

/** Mine list / own-post UI: prefer API flags, fall back to status when backend omits them. */
export function postCanWithdraw(post: CaseSquarePost, ownPost = true): boolean {
  if (post.can_withdraw === true) return true
  if (post.can_withdraw === false) return false
  return ownPost && post.status === 'pending'
}

export function postCanDelist(post: CaseSquarePost, ownPost = true): boolean {
  if (post.can_delist === true) return true
  if (post.can_delist === false) return false
  return ownPost && post.status === 'approved'
}

export function postCanResubmit(post: CaseSquarePost, ownPost = true): boolean {
  if (post.can_resubmit === true) return true
  if (post.can_resubmit === false) return false
  return ownPost && post.status === 'rejected'
}

export function postHasAuthorManageActions(post: CaseSquarePost, ownPost = true): boolean {
  return (
    postCanWithdraw(post, ownPost) ||
    postCanDelist(post, ownPost) ||
    postCanResubmit(post, ownPost)
  )
}
