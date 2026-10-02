// Simple Voice Chat 語音橋：讓 Aize 在房間語音裡「能聽會說」
// 聽：玩家麥克風 PCM（48k mono）-> 能量 VAD 斷句 -> 16k 重採樣 -> sherpa-onnx 本地中文識別 -> 餵給 brain
// 說：Aize 文本 -> Humanaize2 /api/tts（edge-tts）-> mp3 -> SVC 頻道播放
'use strict'

const fs = require('fs')
const os = require('os')
const path = require('path')
const sherpa = require('sherpa-onnx')

const FRAME_MS = 20
const RATE_ASR = 16000

// 把一句長話按標點切成短片段（SVC 單幀流播放，短句反應更快）
function splitSentences (text, maxLen) {
  const pieces = []
  const parts = String(text).replace(/\s+/g, ' ').match(/[^，。！？!?；;：:、\n]+[，。！？!?；;：:、\n]?/g) || [String(text)]
  let cur = ''
  for (const p0 of parts) {
    // 無標點的超長片段硬切兜底
    let p = p0
    while (p.length > maxLen) {
      if (cur) { pieces.push(cur); cur = '' }
      pieces.push(p.slice(0, maxLen))
      p = p.slice(maxLen)
    }
    if ((cur + p).length > maxLen && cur) { pieces.push(cur); cur = p } else cur += p
  }
  if (cur) pieces.push(cur)
  return pieces.map(s => s.trim()).filter(Boolean).slice(0, 8)
}

class VoiceBridge {
  // hooks: { getToken(), ensureLogin(), onSpeech(name, text, isOwner) }
  constructor (bot, vcfg, aizeCfg, hooks) {
    this.bot = bot
    this.cfg = vcfg || {}
    this.aize = aizeCfg || {}
    this.hooks = hooks || {}
    this.connected = false
    this.speaking = false
    this.pendingSay = 0
    this.asrReady = false
    this.recognizer = null
    this.talkers = new Map() // 玩家名 -> { buf:Float32Array[], voiced, silence, total }
    this.asrChain = Promise.resolve()
    this.sayChain = Promise.resolve()
    this.disposed = false
    this._initRecognizer()
    this._bind()
  }

  _initRecognizer () {
    try {
      const dir = path.join(__dirname, 'models', 'zh-14m')
      const enc = path.join(dir, 'encoder-epoch-99-avg-1.int8.onnx')
      if (!fs.existsSync(enc)) {
        console.log('[voice] 找不到語音識別模型，聽力禁用（說話不受影響）')
        return
      }
      this.recognizer = sherpa.createOnlineRecognizer({
        featConfig: { sampleRate: RATE_ASR, featureDim: 80 },
        modelConfig: {
          transducer: {
            encoder: enc,
            decoder: path.join(dir, 'decoder-epoch-99-avg-1.int8.onnx'),
            joiner: path.join(dir, 'joiner-epoch-99-avg-1.int8.onnx')
          },
          tokens: path.join(dir, 'tokens.txt'),
          numThreads: 1,
          provider: 'cpu',
          debug: 0
        },
        enableEndpoint: 1,
        decodingMethod: 'greedy_search'
      })
      this.asrReady = true
      console.log('[voice] 中文語音識別已就緒')
    } catch (e) {
      console.log('[voice] 語音識別初始化失敗:', e.message)
    }
  }

  _bind () {
    this.bot.on('voicechat_connect', () => {
      this.connected = true
      console.log('[voice] 已接入房間語音頻道')
      this.hooks.onStatus && this.hooks.onStatus()
    })
    this.bot.on('voicechat_player_sound', d => this._onSound(d))
  }

  // ---------- 聽 ----------
  _onSound (d) {
    if (this.disposed || !this.asrReady || this.speaking) return
    const radius = Number(this.cfg.hearRadius) || 48
    // 距離過遠的不聽（群組語音沒有 distance 概念，undefined 時放行）
    if (typeof d.distance === 'number' && d.distance > radius) return
    const name = d.sender || '陌生人'
    const pcm = d.data // s16le 48k mono，每幀 1920 位元組
    if (!Buffer.isBuffer(pcm) || pcm.length < 2) return

    // 能量閾值（RMS）
    let sum = 0
    const samples = pcm.length >> 1
    for (let i = 0; i < samples; i++) {
      const s = pcm.readInt16LE(i * 2)
      sum += s * s
    }
    const rms = Math.sqrt(sum / samples)
    const threshold = Number(this.cfg.energyThreshold) || 500

    let st = this.talkers.get(name)
    if (rms <= threshold) {
      if (!st || !st.voiced) return // 還沒開口，忽略
      st.silence += FRAME_MS
    } else {
      if (!st) { st = { buf: [], voiced: false, silence: 0, total: 0 }; this.talkers.set(name, st) }
      st.voiced = true
      st.silence = 0
    }
    st.buf.push(this._pcm48To16k(pcm))
    st.total += FRAME_MS

    const silenceMs = Number(this.cfg.silenceMs) || 700
    const maxMs = (Number(this.cfg.maxClipSec) || 15) * 1000
    if (st.voiced && (st.silence >= silenceMs || st.total >= maxMs)) this._flush(name, st)
  }

  _flush (name, st) {
    this.talkers.delete(name)
    const total = st.buf.reduce((n, a) => n + a.length, 0)
    if (total < RATE_ASR * 0.35) return // 短於 0.35 秒當噪聲
    const audio = new Float32Array(total)
    let off = 0
    for (const a of st.buf) { audio.set(a, off); off += a.length }
    this.asrChain = this.asrChain
      .then(() => this._recognize(name, audio))
      .catch(e => console.log('[voice] 識別失敗:', e.message))
  }

  async _recognize (name, audio) {
    const stream = this.recognizer.createStream()
    stream.acceptWaveform(RATE_ASR, audio)
    stream.acceptWaveform(RATE_ASR, new Float32Array(Math.floor(RATE_ASR * 0.2))) // 尾靜音幫助出字
    while (this.recognizer.isReady(stream)) this.recognizer.decode(stream)
    let text = (this.recognizer.getResult(stream).text || '').trim()
    try { this.recognizer.reset(stream) } catch (e) {}
    text = text.replace(/[\s,，。！？!?、]+$/g, '').slice(0, 120)
    if (!text) return
    const owners = Array.isArray(this.cfg.owners) ? this.cfg.owners.map(n => String(n).toLowerCase()) : []
    const isOwner = owners.includes(String(name).toLowerCase())
    console.log(`[voice] 聽到 <${name}>：${text}`)
    this.hooks.onSpeech && this.hooks.onSpeech(name, text, isOwner)
  }

  // 48k s16le -> 16k Float32（三點均值，自帶簡易抗混疊）
  _pcm48To16k (pcm) {
    const n = pcm.length >> 1
    const out = new Float32Array(n / 3)
    for (let i = 0, k = 0; i + 2 < n; i += 3, k++) {
      const s = pcm.readInt16LE(i * 2) + pcm.readInt16LE((i + 1) * 2) + pcm.readInt16LE((i + 2) * 2)
      out[k] = s / 3 / 32768
    }
    return out
  }

  // ---------- 說 ----------
  say (text) {
    text = String(text || '').trim()
    if (!text || this.cfg.speakEnabled === false) return
    for (const piece of splitSentences(text, 60)) {
      this.pendingSay++
      this.sayChain = this.sayChain
        .then(() => this._speakOne(piece))
        .catch(e => console.log('[voice] 播放失敗:', e.message))
        .finally(() => { this.pendingSay-- })
    }
  }

  async _speakOne (piece) {
    if (this.disposed || !this.connected) return // 沒進語音頻道就只發文字
    let file = null
    try {
      file = await this._ttsToFile(piece)
      this.speaking = true
      await this.bot.voicechat.sendAudio(file)
    } finally {
      this.speaking = false
      if (file) { try { fs.unlinkSync(file) } catch (e) {} }
    }
  }

  async _ttsToFile (text) {
    const loginUrl = this.aize.loginUrl || 'http://127.0.0.1:8082/api/login'
    const base = loginUrl.replace(/\/api\/login\/?$/, '')
    let token = this.hooks.getToken && this.hooks.getToken()
    if (!token && this.hooks.ensureLogin) {
      try { await this.hooks.ensureLogin() } catch (e) {}
      token = this.hooks.getToken && this.hooks.getToken()
    }
    const headers = { 'Content-Type': 'application/json' }
    if (token) headers.Authorization = 'Bearer ' + token
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 30000)
    try {
      const res = await fetch(base + '/api/tts', {
        method: 'POST',
        headers,
        body: JSON.stringify({ text, voice: this.cfg.ttsVoice || 'zh-TW-HsiaoChenNeural' }),
        signal: ctrl.signal
      })
      if (!res.ok) throw new Error('TTS HTTP ' + res.status)
      const buf = Buffer.from(await res.arrayBuffer())
      const file = path.join(os.tmpdir(), `mcbot-tts-${Date.now()}-${Math.random().toString(36).slice(2, 8)}.mp3`)
      fs.writeFileSync(file, buf)
      return file
    } finally {
      clearTimeout(timer)
    }
  }

  status () {
    return {
      enabled: this.cfg.enabled !== false,
      connected: this.connected,
      asrReady: this.asrReady,
      speaking: this.speaking,
      pendingSay: this.pendingSay,
      listeners: Array.from(this.talkers.keys())
    }
  }

  dispose () {
    this.disposed = true
    this.talkers.clear()
  }
}

module.exports = { VoiceBridge, splitSentences }
