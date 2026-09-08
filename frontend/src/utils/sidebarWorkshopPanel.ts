/**
 * 研习社 sidebar accordion: first entry stays collapsed.
 * Expand only when the user clicks the item while already on the page.
 */
export function shouldExpandWorkshopOnNavClick(
  alreadyOnWorkshopPage: boolean,
  sidebarCollapsed: boolean
): boolean {
  if (sidebarCollapsed) {
    return false
  }
  return alreadyOnWorkshopPage
}
