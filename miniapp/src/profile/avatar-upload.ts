function extensionFromPath(filePath: string): string {
  const match = filePath.toLowerCase().match(/\.(png|jpe?g|webp)(?:\?|$)/)
  if (!match) return 'jpg'
  return match[1] === 'jpeg' ? 'jpg' : match[1]
}

function fnv1aHex(data: ArrayBuffer | string): string {
  const bytes = typeof data === 'string'
    ? Array.from(data, (character) => character.charCodeAt(0) & 0xff)
    : Array.from(new Uint8Array(data))
  let hash = 0x811c9dc5
  for (const byte of bytes) {
    hash ^= byte
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return hash.toString(16).padStart(8, '0')
}

export async function uploadProfileAvatar(
  userId: number,
  filePath: string,
): Promise<string> {
  const content = wx.getFileSystemManager().readFileSync(filePath)
  const hash = fnv1aHex(content)
  const extension = extensionFromPath(filePath)
  const cloudPath = `avatars/${userId}/${hash}.${extension}`

  return new Promise((resolve, reject) => {
    wx.cloud.uploadFile({
      cloudPath,
      filePath,
      success: (result) => {
        if (!result.fileID) {
          reject(new Error('头像上传未返回 fileID'))
          return
        }
        resolve(result.fileID)
      },
      fail: (error) => reject(new Error(error.errMsg || '头像上传失败')),
    })
  })
}
