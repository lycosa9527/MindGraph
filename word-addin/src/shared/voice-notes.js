/* global MG_CLIENT_ID, mgAuthStatus, mgBaseUrl, mgHydratePrefs, mgLoadPrefs, mgT */
/**
 * Dedicated Voice Notes session for the Word add-in dialog.
 * Mic → WS /api/ws/voice-notes (mgat_ + account query) → Fun-ASR.
 */

var MG_VOICE_TARGET_RATE = 16000
var MG_VOICE_PROCESS_BUFFER = 2048
var MG_VOICE_MAX_SESSION_MS = 60 * 60 * 1000
var MG_VOICE_SILENCE_MS = 2 * 60 * 1000
var MG_VOICE_SILENCE_CHECK_MS = 5000
var MG_VOICE_STARTED_TIMEOUT_MS = 15000
var MG_VOICE_SPEECH_RMS = 0.012

/**
 * @param {Float32Array} input
 * @returns {number}
 */
function mgVoiceRms(input) {
  if (!input || !input.length) {
    return 0
  }
  var sum = 0
  var i
  for (i = 0; i < input.length; i += 1) {
    sum += input[i] * input[i]
  }
  return Math.sqrt(sum / input.length)
}

/**
 * @param {Float32Array} input
 * @param {number} inputRate
 * @returns {string} base64 PCM16 @ 16 kHz
 */
function mgVoicePcm16Base64(input, inputRate) {
  var pcm
  var i
  if (inputRate === MG_VOICE_TARGET_RATE) {
    pcm = new Int16Array(input.length)
    for (i = 0; i < input.length; i += 1) {
      var s = Math.max(-1, Math.min(1, input[i]))
      pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff
    }
  } else {
    var ratio = inputRate / MG_VOICE_TARGET_RATE
    var outLen = Math.floor(input.length / ratio)
    pcm = new Int16Array(outLen)
    for (i = 0; i < outLen; i += 1) {
      var start = Math.floor(i * ratio)
      var end = Math.min(Math.floor((i + 1) * ratio), input.length)
      var acc = 0
      var j
      for (j = start; j < end; j += 1) {
        acc += input[j]
      }
      var avg = acc / Math.max(1, end - start)
      var sample = Math.max(-1, Math.min(1, avg))
      pcm[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
    }
  }
  var bytes = new Uint8Array(pcm.buffer)
  var binary = ''
  for (i = 0; i < bytes.byteLength; i += 1) {
    binary += String.fromCharCode(bytes[i])
  }
  return window.btoa(binary)
}

/**
 * @param {{ baseUrl?: string, phone?: string, apiToken?: string, language?: string }} prefs
 * @returns {string}
 */
function mgVoiceWsUrl(prefs) {
  var base = mgBaseUrl(prefs)
  var proto = base.indexOf('https') === 0 ? 'wss:' : 'ws:'
  var host = base.replace(/^https?:/, '')
  var token = encodeURIComponent(String(prefs.apiToken || '').trim())
  var account = encodeURIComponent(String(prefs.phone || '').trim())
  var client = encodeURIComponent(MG_CLIENT_ID || 'word-addin')
  return (
    proto +
    host +
    '/api/ws/voice-notes?token=' +
    token +
    '&account=' +
    account +
    '&client=' +
    client
  )
}

/**
 * HTTPS Office shell cannot open ws:// to a local HTTP API (mixed content).
 * @param {string} baseUrl
 * @returns {boolean}
 */
function mgVoiceMixedContentBlocked(baseUrl) {
  try {
    if (typeof window === 'undefined' || !window.location) {
      return false
    }
    if (String(window.location.protocol || '') !== 'https:') {
      return false
    }
    return String(baseUrl || '').indexOf('http://') === 0
  } catch (err) {
    return false
  }
}

/**
 * @param {string} baseUrl
 * @returns {string}
 */
function mgVoiceBaseHostLabel(baseUrl) {
  try {
    return String(baseUrl || '')
      .replace(/^https?:\/\//i, '')
      .replace(/\/+$/, '')
  } catch (err2) {
    return ''
  }
}

/**
 * @param {string} lang
 * @returns {string[]}
 */
function mgVoiceLanguageHints(lang) {
  var base = String(lang || 'zh').toLowerCase().split('-')[0] || 'zh'
  if (base === 'en') {
    return ['en']
  }
  if (base === 'ja') {
    return ['ja']
  }
  return ['zh']
}

/**
 * Wire the Voice dialog UI.
 * @param {{
 *   statusEl: HTMLElement,
 *   meterEl: HTMLElement,
 *   transcriptEl: HTMLElement,
 *   elapsedEl: HTMLElement,
 *   startBtn: HTMLButtonElement,
 *   pauseBtn: HTMLButtonElement,
 *   stopBtn: HTMLButtonElement,
 *   copyBtn: HTMLButtonElement,
 * }} ui
 */
function mgBootVoiceNotes(ui) {
  var lines = []
  var liveText = ''
  var recording = false
  var paused = false
  var connecting = false
  var sessionReady = false
  var intentionalClose = false
  var sessionStamp = 0
  var startedAt = 0
  var pausedAccumMs = 0
  var lastSpeechAt = 0
  var elapsedTimer = null
  var startedTimeoutTimer = null
  var maxDurationTimer = null
  var silenceCheckTimer = null
  /** @type {WebSocket|null} */
  var socket = null
  /** @type {AudioContext|null} */
  var audioCtx = null
  /** @type {MediaStream|null} */
  var micStream = null
  /** @type {ScriptProcessorNode|null} */
  var processor = null
  /** @type {MediaStreamAudioSourceNode|null} */
  var mediaSource = null

  function markSpeech() {
    lastSpeechAt = Date.now()
  }

  function clearWatchTimers() {
    if (elapsedTimer) {
      window.clearInterval(elapsedTimer)
      elapsedTimer = null
    }
    if (startedTimeoutTimer) {
      window.clearTimeout(startedTimeoutTimer)
      startedTimeoutTimer = null
    }
    if (maxDurationTimer) {
      window.clearTimeout(maxDurationTimer)
      maxDurationTimer = null
    }
    if (silenceCheckTimer) {
      window.clearInterval(silenceCheckTimer)
      silenceCheckTimer = null
    }
  }

  function armSessionWatchers(stamp) {
    clearWatchTimers()
    elapsedTimer = window.setInterval(tickElapsed, 500)
    startedTimeoutTimer = window.setTimeout(function () {
      if (stamp !== sessionStamp || sessionReady) {
        return
      }
      setStatus(mgT('voiceStartedTimeout'), 'err')
      stopAll(false)
    }, MG_VOICE_STARTED_TIMEOUT_MS)
    maxDurationTimer = window.setTimeout(function () {
      if (stamp !== sessionStamp || !recording) {
        return
      }
      setStatus(mgT('voiceMaxDuration'), '')
      stopAll(true)
    }, MG_VOICE_MAX_SESSION_MS)
    silenceCheckTimer = window.setInterval(function () {
      if (stamp !== sessionStamp || !recording || paused || !sessionReady) {
        return
      }
      if (Date.now() - lastSpeechAt >= MG_VOICE_SILENCE_MS) {
        setStatus(mgT('voiceSilenceStop'), '')
        stopAll(true)
      }
    }, MG_VOICE_SILENCE_CHECK_MS)
  }

  function setStatus(text, kind) {
    ui.statusEl.textContent = text
    ui.statusEl.className = 'mg-status' + (kind === 'ok' ? ' ok' : kind === 'err' ? ' err' : '')
  }

  function renderTranscript() {
    var committed = lines.filter(function (s) {
      return s.trim()
    })
    var live = liveText.trim()
    var text = committed.join('\n')
    if (live) {
      text = text ? text + '\n' + live : live
    }
    ui.transcriptEl.textContent = text || mgT('voiceTranscriptEmpty')
  }

  function formatElapsed(ms) {
    var total = Math.floor(ms / 1000)
    var m = Math.floor(total / 60)
    var s = total % 60
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s
  }

  function tickElapsed() {
    if (!recording || paused) {
      return
    }
    ui.elapsedEl.textContent = formatElapsed(pausedAccumMs + (Date.now() - startedAt))
  }

  function setMeter(level) {
    var pct = Math.max(4, Math.min(100, Math.round(level * 100)))
    ui.meterEl.style.width = pct + '%'
  }

  function syncButtons() {
    var prefsOk = mgAuthStatus(mgLoadPrefs()) === 'saved'
    ui.startBtn.disabled = !prefsOk || recording || connecting
    ui.pauseBtn.disabled = !recording || connecting
    ui.stopBtn.disabled = (!recording && !connecting) || false
    ui.copyBtn.disabled = !(lines.length || liveText.trim())
    ui.pauseBtn.textContent = paused ? mgT('voiceResume') : mgT('voicePause')
  }

  function stopMicGraph() {
    if (processor) {
      try {
        processor.disconnect()
      } catch (err) {
        /* ignore */
      }
      processor.onaudioprocess = null
      processor = null
    }
    if (mediaSource) {
      try {
        mediaSource.disconnect()
      } catch (err2) {
        /* ignore */
      }
      mediaSource = null
    }
    if (micStream) {
      micStream.getTracks().forEach(function (track) {
        track.stop()
      })
      micStream = null
    }
    if (audioCtx) {
      void audioCtx.close().catch(function () {})
      audioCtx = null
    }
    setMeter(0)
  }

  function closeSocket(sendStop) {
    if (!socket) {
      return
    }
    intentionalClose = true
    try {
      if (sendStop && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'stop' }))
      }
    } catch (err) {
      /* ignore */
    }
    try {
      socket.close()
    } catch (err2) {
      /* ignore */
    }
    socket = null
  }

  function resetSessionUi() {
    clearWatchTimers()
    recording = false
    paused = false
    connecting = false
    sessionReady = false
    startedAt = 0
    pausedAccumMs = 0
    lastSpeechAt = 0
    ui.elapsedEl.textContent = '00:00'
    setMeter(0)
    syncButtons()
  }

  function handlePayload(data) {
    var type = data && data.type
    if (type === 'started') {
      sessionReady = true
      connecting = false
      if (startedTimeoutTimer) {
        window.clearTimeout(startedTimeoutTimer)
        startedTimeoutTimer = null
      }
      markSpeech()
      setStatus(mgT('voiceRecording'), 'ok')
      syncButtons()
      return
    }
    if (type === 'partial') {
      liveText = String(data.text || '')
      if (liveText.trim()) {
        markSpeech()
      }
      renderTranscript()
      return
    }
    if (type === 'final') {
      var finalText = String(data.text || '').trim()
      if (finalText) {
        lines.push(finalText)
        markSpeech()
      }
      liveText = ''
      renderTranscript()
      syncButtons()
      return
    }
    if (type === 'error') {
      setStatus(String(data.message || mgT('voiceWsError')), 'err')
      stopAll(false)
    }
  }

  function attachMic(stamp) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus(mgT('voiceMicUnavailable'), 'err')
      stopAll(false)
      return Promise.resolve()
    }
    return navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      if (stamp !== sessionStamp) {
        stream.getTracks().forEach(function (t) {
          t.stop()
        })
        return
      }
      micStream = stream
      stream.getTracks().forEach(function (track) {
        track.addEventListener('ended', function () {
          if (stamp !== sessionStamp) {
            return
          }
          setStatus(mgT('voiceMicFailed'), 'err')
          stopAll(false)
        })
      })
      var Ctx = window.AudioContext || window.webkitAudioContext
      audioCtx = new Ctx()
      mediaSource = audioCtx.createMediaStreamSource(stream)
      processor = audioCtx.createScriptProcessor(MG_VOICE_PROCESS_BUFFER, 1, 1)
      processor.onaudioprocess = function (event) {
        if (stamp !== sessionStamp || !recording || paused || !sessionReady) {
          return
        }
        if (!socket || socket.readyState !== WebSocket.OPEN) {
          return
        }
        var input = event.inputBuffer.getChannelData(0)
        var rms = mgVoiceRms(input)
        setMeter(Math.min(1, rms * 8))
        if (rms >= MG_VOICE_SPEECH_RMS) {
          markSpeech()
        }
        try {
          socket.send(
            JSON.stringify({
              type: 'append',
              audio: mgVoicePcm16Base64(input, audioCtx.sampleRate),
            })
          )
        } catch (err) {
          /* ignore */
        }
      }
      mediaSource.connect(processor)
      processor.connect(audioCtx.destination)
    })
  }

  function stopAll(sendStop) {
    sessionStamp += 1
    stopMicGraph()
    closeSocket(sendStop)
    resetSessionUi()
  }

  function beginSocketSession(prefs) {
    lines = []
    liveText = ''
    renderTranscript()
    connecting = true
    recording = true
    paused = false
    sessionReady = false
    intentionalClose = false
    sessionStamp += 1
    var stamp = sessionStamp
    startedAt = Date.now()
    pausedAccumMs = 0
    markSpeech()
    var hostLabel = mgVoiceBaseHostLabel(mgBaseUrl(prefs))
    setStatus(
      hostLabel ? mgT('voiceConnectingTo').replace('{host}', hostLabel) : mgT('voiceConnecting'),
      ''
    )
    syncButtons()
    armSessionWatchers(stamp)

    try {
      socket = new WebSocket(mgVoiceWsUrl(prefs))
    } catch (err) {
      setStatus(mgT('voiceWsError'), 'err')
      stopAll(false)
      return
    }

    socket.onopen = function () {
      if (stamp !== sessionStamp) {
        return
      }
      try {
        socket.send(
          JSON.stringify({
            type: 'start',
            language_hints: mgVoiceLanguageHints(prefs.language),
          })
        )
      } catch (err2) {
        setStatus(mgT('voiceWsError'), 'err')
        stopAll(false)
        return
      }
      attachMic(stamp).catch(function () {
        setStatus(mgT('voiceMicFailed'), 'err')
        stopAll(false)
      })
    }

    socket.onmessage = function (event) {
      if (stamp !== sessionStamp) {
        return
      }
      try {
        handlePayload(JSON.parse(event.data))
      } catch (err3) {
        /* ignore */
      }
    }

    socket.onerror = function () {
      if (stamp !== sessionStamp) {
        return
      }
      setStatus(mgT('voiceWsError'), 'err')
    }

    socket.onclose = function (event) {
      if (stamp !== sessionStamp) {
        return
      }
      socket = null
      var wasIntentional = intentionalClose
      intentionalClose = false
      stopMicGraph()
      if (wasIntentional) {
        resetSessionUi()
        setStatus(mgT('voiceStopped'), '')
        return
      }
      if (event.code === 4001) {
        setStatus(mgT('voiceAuthFailed'), 'err')
      } else if (event.code === 1008) {
        setStatus(mgT('voiceWsOrigin'), 'err')
      } else if (event.code === 4403) {
        setStatus(mgT('voiceWsPolicy'), 'err')
      } else {
        setStatus(mgT('voiceWsClosed'), 'err')
      }
      resetSessionUi()
    }
  }

  function startRecording() {
    if (recording || connecting) {
      return
    }
    connecting = true
    syncButtons()
    setStatus(mgT('voiceConnecting'), '')
    var hydrate =
      typeof mgHydratePrefs === 'function'
        ? mgHydratePrefs()
        : Promise.resolve(mgLoadPrefs())
    hydrate
      .then(function (prefs) {
        connecting = false
        if (recording) {
          return
        }
        if (mgAuthStatus(prefs) !== 'saved') {
          setStatus(mgT('voiceNeedAuth'), 'err')
          syncButtons()
          return
        }
        if (mgVoiceMixedContentBlocked(mgBaseUrl(prefs))) {
          setStatus(mgT('voiceMixedContent'), 'err')
          syncButtons()
          return
        }
        beginSocketSession(prefs)
      })
      .catch(function () {
        connecting = false
        setStatus(mgT('voiceWsError'), 'err')
        syncButtons()
      })
  }

  function togglePause() {
    if (!recording || connecting) {
      return
    }
    if (!paused) {
      pausedAccumMs += Date.now() - startedAt
      paused = true
      setMeter(0)
      setStatus(mgT('voicePaused'), '')
    } else {
      startedAt = Date.now()
      paused = false
      setStatus(mgT('voiceRecording'), 'ok')
      if (audioCtx && audioCtx.state === 'suspended') {
        void audioCtx.resume().catch(function () {})
      }
    }
    syncButtons()
  }

  ui.startBtn.addEventListener('click', startRecording)
  ui.pauseBtn.addEventListener('click', togglePause)
  ui.stopBtn.addEventListener('click', function () {
    stopAll(true)
    setStatus(mgT('voiceStopped'), '')
  })
  ui.copyBtn.addEventListener('click', function () {
    var text = ui.transcriptEl.textContent || ''
    if (!text || text === mgT('voiceTranscriptEmpty')) {
      return
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      void navigator.clipboard.writeText(text).then(
        function () {
          setStatus(mgT('voiceCopied'), 'ok')
        },
        function () {
          setStatus(mgT('voiceWsError'), 'err')
        }
      )
    }
  })

  window.addEventListener('pagehide', function () {
    stopAll(true)
  })

  renderTranscript()
  if (mgAuthStatus(mgLoadPrefs()) !== 'saved') {
    setStatus(mgT('voiceNeedAuth'), 'err')
  } else {
    setStatus(mgT('voiceReady'), '')
  }
  syncButtons()
}
