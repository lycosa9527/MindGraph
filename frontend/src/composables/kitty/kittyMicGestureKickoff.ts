/**
 * iOS-safe Kitty mic kickoff helpers (gesture-stack unlock).
 *
 * Cross-checked patterns:
 * - Microsoft BotFramework-WebChat: reuse one AudioContext; resume() on pointerdown
 * - ptt-radio: warm getUserMedia once; PTT toggles track.enabled
 * - AMD GAIA mobile voice: getUserMedia sync in pointerdown; pointer events only
 *
 * Orange mic LED ≠ PCM flowing. Web Audio must be blessed in the gesture stack.
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
  mute.gain.value = 0
  node.connect(mute)
  mute.connect(ctx.destination)
  return mute
}

/** Sync Web Audio unlock — must run inside pointerdown (no await before this). */
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
 * Create AudioContext + ScriptProcessor (synced to destination) + getUserMedia
 * from the current user-gesture turn. Attach MediaStream when the permission
 * promise resolves.
 */
export function kickoffKittyMicGestureAssets(): Promise<KittyMicGestureAssets> {
  if (!navigator.mediaDevices?.getUserMedia) {
    return Promise.reject(new Error('mic_unavailable'))
  }

  const AudioCtx = resolveAudioContextConstructor()
  const audioContext = new AudioCtx()
  const scriptProcessor = audioContext.createScriptProcessor(
    KITTY_SCRIPT_PROCESSOR_BUFFER,
    1,
    1
  )
  const silentGain = connectMutedDestination(audioContext, scriptProcessor)
  blessAudioContextSync(audioContext)

  const streamPromise = navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    },
  })

  return (async () => {
    try {
      blessAudioContextSync(audioContext)
      const stream = await streamPromise
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
