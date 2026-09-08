declare module 'vod-js-sdk-v6' {
  interface VodJsUploader {
    on: (event: string, handler: (info: { percent?: number }) => void) => void
    done: () => Promise<{ fileId?: string }>
  }

  interface VodJsClient {
    upload: (options: { mediaFile: File }) => VodJsUploader
  }

  class TcVod {
    constructor(options: { getSignature: () => Promise<string> })
    upload: (options: { mediaFile: File }) => VodJsUploader
  }

  export default TcVod
}

declare module 'tcplayer.js/dist/tcplayer.min.css'

declare module 'tcplayer.js' {
  interface TcPlayerInstance {
    dispose: () => void
  }

  function TCPlayer(
    containerId: string,
    options: {
      fileID: string
      appID: string
      psign: string
      licenseUrl: string
      licenseKey?: string
      language?: string
    }
  ): TcPlayerInstance

  export default TCPlayer
}
