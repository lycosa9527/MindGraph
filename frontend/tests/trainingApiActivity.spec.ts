import { beforeEach, describe, expect, it, vi } from 'vitest'

import { postTrainingActivity } from '@/utils/trainingApi'

const apiRequestMock = vi.hoisted(() => vi.fn())

vi.mock('@/utils/apiClient', () => ({
  apiRequest: (...args: unknown[]) => apiRequestMock(...args),
  apiUpload: vi.fn(),
  parseApiErrorDetail: vi.fn(),
}))

describe('postTrainingActivity', () => {
  beforeEach(() => {
    apiRequestMock.mockReset()
  })

  it('resolves when the network request fails', async () => {
    apiRequestMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(postTrainingActivity({ page_key: 'canvas' })).resolves.toBeUndefined()
    expect(apiRequestMock).toHaveBeenCalledTimes(1)
  })
})
