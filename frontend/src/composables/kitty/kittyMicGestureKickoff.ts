/**
 * iOS Safari Kitty mic kickoff — follows WebKit user-activation rules.
 *
 * References:
 * - https://webkit.org/blog/13862/the-user-activation-api/
 * - https://webkit.org/blog/6784/new-video-policies-for-ios/
 * - https://bugs.webkit.org/show_bug.cgi?id=180680 (AudioContext while capturing)
 *
 * Rules we follow:
 * 1. Start getUserMedia from the gesture call stack (no await before the call).
 * 2. Create AudioContext in that same stack; bless sync (silent buffer + resume).
 * 3. After the stream resolves, the document is capturing — bless again (WebKit
 *    allows AudioContext start while getUserMedia capture is active).
 * 4. Do not treat touch pointerdown as activation; callers must also bless on
 *    pointerup / touchend (activation-triggering for non-mouse) or rely on sticky
 *    activation from a prior qualifying gesture.
 *
 * Orange mic LED ≠ PCM flowing. Web Audio must be running (state === "running").
 */
export interface KittyMicGestureAssets {
  stream: MediaStream
  audioContext: AudioContext
  mediaSource: MediaStreamAudioSourceNode
  scriptProcessor: ScriptProcessorNode
  silentGain: GainNode
}

type AudioContextConstructor = typeof AudioContext

export const KITTY_SCRIPT_PROCESSOR_BUFFER = 4096

export function resolveAudioContextConstructor(): AudioContextConstructor {
  if (typeof window === 'undefined') {
    throw new Error('mic_unavailable')
  }
  // Prefer globalThis — Window's AudioContext property is not always in lib.dom.
  const globals = globalThis as typeof globalThis & {
    AudioContext?: AudioContextConstructor
    webkitAudioContext?: AudioContextConstructor
  }
  const Ctor = globals.AudioContext ?? globals.webkitAudioContext
  if (!Ctor) {
    throw new Error('mic_unavailable')
  }
  return Ctor
}

export function connectMutedDestination(ctx: AudioContext, node: AudioNode): GainNode {
  const mute = ctx.createGain()
  // Safari can suspend graphs with exact zero gain; keep a near-silent tap.
  mute.gain.value = 0.001
  node.connect(mute)
  mute.connect(ctx.destination)
  return mute
}

/**
 * Sync Web Audio unlock — call only inside an activation-triggering handler
 * (or after sticky activation / while media capture is active).
 */
export function blessAudioContextSync(ctx: AudioContext): void {
  if (ctx.state === 'closed') {
    return
  }
  try {
    const rate = ctx.sampleRate > 0 ? ctx.sampleRate : 44100
    const buffer = ctx.createBuffer(1, 1, rate)
    const source = ctx.createBufferSource()
    source.buffer = buffer
    source.connect(ctx.destination)
    source.start(0)
  } catch {
    /* ignore prime failures */
  }
  void ctx.resume()
}

export function setMicTracksEnabled(stream: MediaStream, enabled: boolean): void {
  stream.getAudioTracks().forEach((track) => {
    track.enabled = enabled
  })
}

/**
 * Kick off getUserMedia + AudioContext from the current call stack.
 * The returned promise resolves after the stream is attached; callers may await
 * it after other async work (WS connect) without losing the initial gesture call.
 */
export function kickoffKittyMicGestureAssets(): Promise<KittyMicGestureAssets> {
  if (!navigator.mediaDevices?.getUserMedia) {
    return Promise.reject(new Error('mic_unavailable'))
  }

  // 1) Start permission / capture from this call stack (no await before this).
  const streamPromise = navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    },
  })

  // 2) Build the Web Audio graph in the same stack; may stay suspended until
  //    sticky activation, a later activation-triggering event, or capturing unlock.
  let audioContext: AudioContext
  let scriptProcessor: ScriptProcessorNode
  let silentGain: GainNode
  try {
    const AudioCtx = resolveAudioContextConstructor()
    audioContext = new AudioCtx()
    scriptProcessor = audioContext.createScriptProcessor(KITTY_SCRIPT_PROCESSOR_BUFFER, 1, 1)
    silentGain = connectMutedDestination(audioContext, scriptProcessor)
    blessAudioContextSync(audioContext)
  } catch (err) {
    void streamPromise
      .then((granted) => {
        granted.getTracks().forEach((track) => track.stop())
      })
      .catch(() => undefined)
    throw err
  }

  return (async () => {
    let stream: MediaStream | null = null
    try {
      stream = await streamPromise
      // 3) Document is now capturing — WebKit allows AudioContext start (180680).
      blessAudioContextSync(audioContext)
      if (audioContext.state === 'suspended') {
        await Promise.race([
          audioContext.resume().catch(() => undefined),
          new Promise<void>((resolve) => {
            setTimeout(resolve, 400)
          }),
        ])
      }
      const mediaSource = audioContext.createMediaStreamSource(stream)
      mediaSource.connect(scriptProcessor)
      blessAudioContextSync(audioContext)
      return {
        stream,
        audioContext,
        mediaSource,
        scriptProcessor,
        silentGain,
      }
    } catch (err) {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop())
      } else {
        void streamPromise
          .then((granted) => {
            granted.getTracks().forEach((track) => track.stop())
          })
          .catch(() => undefined)
      }
      try {
        scriptProcessor.disconnect()
      } catch {
        /* ignore */
      }
      try {
        silentGain.disconnect()
      } catch {
        /* ignore */
      }
      void audioContext.close()
      throw err
    }
  })()
}

export function releaseKittyMicGestureAssets(assets: KittyMicGestureAssets): void {
  try {
    assets.scriptProcessor.onaudioprocess = null
    assets.scriptProcessor.disconnect()
  } catch {
    /* ignore */
  }
  try {
    assets.mediaSource.disconnect()
  } catch {
    /* ignore */
  }
  try {
    assets.silentGain.disconnect()
  } catch {
    /* ignore */
  }
  assets.stream.getTracks().forEach((track) => track.stop())
  if (assets.audioContext.state !== 'closed') {
    void assets.audioContext.close()
  }
}
