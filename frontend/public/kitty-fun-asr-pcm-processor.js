/**
 * Fun-ASR mic PCM capture worklet (16 kHz path handled on main thread).
 * Served from /public so CSP script-src/worker-src 'self' allows it (no blob:).
 */
class KittyFunAsrPcmProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0] && inputs[0][0]
    if (channel && channel.length > 0) {
      const copy = new Float32Array(channel.length)
      copy.set(channel)
      this.port.postMessage(
        { type: 'samples', sampleRate: sampleRate, buffer: copy.buffer },
        [copy.buffer]
      )
    }
    return true
  }
}

registerProcessor('kitty-fun-asr-pcm-processor', KittyFunAsrPcmProcessor)
