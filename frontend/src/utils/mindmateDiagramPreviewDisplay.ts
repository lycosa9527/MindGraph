/** Replace expired temp preview URLs with cached blob URLs in MindMate markdown. */

const TEMP_PREVIEW_IMAGE_MD_RE =
  /!\[([^\]]*)\]\([^)]*(?:\/temp_images\/dingtalk_[a-f0-9]{8}_\d+\.png|temp_images%2Fdingtalk_[a-f0-9]{8}_\d+\.png)[^)]*\)/i

/** Swap the generate_dingtalk preview markdown image src for a blob URL. */
export function replaceMindmatePreviewImageUrl(content: string, blobUrl: string): string {
  if (!content || !blobUrl) {
    return content || ''
  }
  return content.replace(TEMP_PREVIEW_IMAGE_MD_RE, `![$1](${blobUrl})`)
}

/** Drop a dead generate_dingtalk preview image so the bubble does not show a broken ``<img>``. */
export function stripMindmatePreviewImageMarkdown(content: string): string {
  return (content || '')
    .replace(TEMP_PREVIEW_IMAGE_MD_RE, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}
