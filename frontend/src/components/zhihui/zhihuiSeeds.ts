/**
 * Local fallback seed images for ZhiHui landing gallery (empty history).
 * Prefer signed COS URLs from GET /api/zhihui/seeds; these public files are the offline fallback.
 * Upload with: python scripts/db/seed_zhihui_landing_images.py
 */
export const ZHIHUI_SEED_IMAGE_URLS = [
  '/zhihui/seeds/seed-1.jpg',
  '/zhihui/seeds/seed-2.jpg',
  '/zhihui/seeds/seed-3.jpg',
  '/zhihui/seeds/seed-4.jpg',
  '/zhihui/seeds/seed-5.jpg',
  '/zhihui/seeds/seed-6.jpg',
] as const

export const ZHIHUI_LANDING_GALLERY_LIMIT = 6
