import { afterEach, describe, expect, it, vi } from 'vitest'

import { uploadProfileAvatar } from './avatar-upload'

describe('uploadProfileAvatar', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uploads an explicitly chosen file into the authenticated user namespace', async () => {
    const uploadFile = vi.fn((options) => {
      expect(options.cloudPath).toMatch(/^avatars\/7\/[0-9a-f]{8}\.png$/)
      options.success({ fileID: 'cloud://env.avatar/avatars/7/hash.png' })
    })
    vi.stubGlobal('wx', {
      getFileSystemManager: () => ({
        readFileSync: vi.fn(() => new Uint8Array([1, 2, 3, 4]).buffer),
      }),
      cloud: { uploadFile },
    })

    await expect(uploadProfileAvatar(7, 'wxfile://tmp/avatar.png')).resolves.toBe(
      'cloud://env.avatar/avatars/7/hash.png',
    )
    expect(uploadFile).toHaveBeenCalledOnce()
  })

  it('rejects a CloudBase upload response without a file id', async () => {
    vi.stubGlobal('wx', {
      getFileSystemManager: () => ({
        readFileSync: vi.fn(() => new Uint8Array([1]).buffer),
      }),
      cloud: {
        uploadFile: vi.fn((options) => options.success({})),
      },
    })

    await expect(uploadProfileAvatar(7, 'wxfile://tmp/avatar.jpg')).rejects.toThrow(
      '头像上传未返回 fileID',
    )
  })
})
