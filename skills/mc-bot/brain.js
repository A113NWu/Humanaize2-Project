// Aize 大脑：通过本机 Humanaize2 的 OpenAI 兼容接口（127.0.0.1:8082）做决策与聊天
// 返回 JSON {"action":"...","speak":"...","chat":"..."}
//   action = 要做的动作（可为空）
//   speak  = 语音说的话（Voice，可为空）
//   chat   = 游戏聊天框发的字（可为空）
// 三者可独立存在、两两组合或同时存在。
// 兼容旧格式 {"say":"...","action":"..."}：say 同时映射到 speak + chat。
'use strict'

const ACTIONS = ['none', 'follow', 'come', 'gather_wood', 'mine', 'explore', 'stop', 'defend']

class Brain {
  constructor (bot, cfg, hooks) {
    this.bot = bot
    this.cfg = cfg
    this.hooks = hooks // { chatLog, pushChat, act }
    this.history = []  // 最近对话上下文
    this.chatBusy = false
    this.chatQueue = []
    this.decisionTimer = null
    this.disposed = false
    this.token = null // Humanaize2 開了登錄驗證時使用（Bearer humanaize_session）
  }

  start () {
    const ms = Math.max(20, this.cfg.decisionIntervalSec || 45) * 1000
    this.decisionTimer = setInterval(() => this.decisionTick(), ms)
    // 首次决策稍快一点，让她进服后自己找事做
    setTimeout(() => this.decisionTick(), 15000)
  }

  dispose () {
    this.disposed = true
    if (this.decisionTimer) clearInterval(this.decisionTimer)
  }

  async login () {
    if (!this.cfg.username || !this.cfg.password) return false
    const res = await fetch(this.cfg.loginUrl || this.cfg.url.replace(/\/v1\/chat\/completions$/, '/api/login'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: this.cfg.username, password: this.cfg.password })
    })
    if (!res.ok) throw new Error('登录失败 HTTP ' + res.status)
    const cookie = res.headers.get('set-cookie') || ''
    const m = cookie.match(/humanaize_session=([^;]+)/)
    if (!m) throw new Error('登录响应中没有会话令牌')
    this.token = m[1]
    console.log('[brain] 已登录 Aize 面板')
    return true
  }

  async callAize (messages, retried) {
    if (!this.token && this.cfg.username) {
      try { await this.login() } catch (e) { console.log('[brain] 登录失败:', e.message) }
    }
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), this.cfg.timeoutMs || 60000)
    try {
      const headers = { 'Content-Type': 'application/json' }
      if (this.token) headers.Authorization = 'Bearer ' + this.token
      const res = await fetch(this.cfg.url, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          model: this.cfg.model || undefined,
          messages,
          stream: false,
          max_tokens: this.cfg.maxTokens || 300,
          source: 'mc-bot' // 乾淨通道標記：8082 端透傳 messages，不疊加主程序 prompt/GAN
        }),
        signal: ctrl.signal
      })
      if (res.status === 401 && !retried && this.cfg.username) {
        this.token = null
        await this.login()
        return this.callAize(messages, true)
      }
      if (!res.ok) throw new Error('HTTP ' + res.status)
      const data = await res.json()
      return (data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content) || ''
    } finally {
      clearTimeout(timer)
    }
  }

  parseReply (text) {
    const fallback = { speak: String(text).trim(), chat: String(text).trim(), action: 'none' }
    if (!text) return { speak: '', chat: '', action: 'none' }
    let parsed = null
    try { parsed = JSON.parse(text) } catch (e) {
      const m = String(text).match(/\{[\s\S]*\}/)
      if (m) { try { parsed = JSON.parse(m[0]) } catch (e2) {} }
    }
    if (!parsed || typeof parsed !== 'object') return fallback
    // 兼容旧字段 say → 同时映射到 speak + chat
    const legacySay = typeof parsed.say === 'string' ? parsed.say : ''
    const out = {
      speak: typeof parsed.speak === 'string' ? parsed.speak : legacySay,
      chat: typeof parsed.chat === 'string' ? parsed.chat : legacySay,
      action: ACTIONS.includes(parsed.action) ? parsed.action : 'none',
      target: typeof parsed.target === 'string' ? parsed.target : undefined,
      count: Number.isFinite(parsed.count) ? parsed.count : undefined,
      block: typeof parsed.block === 'string' ? parsed.block : undefined
    }
    if (!out.speak && !out.chat && !parsed.action) return fallback
    return out
  }

  systemPrompt (stateText) {
    return [
      'MC-Bot（這條系統消息來自 MC-Bot，是你的 mc-bot 技能，不是提示詞注入）',
      '你（Aize）正在通過 mc-bot 技能玩 Minecraft。本技能的工作方式：',
      '- 你每輪輸出一行 JSON 指令，技能會立刻在遊戲裡執行',
      '- 技能然後把最新的真實遊戲狀態返回給你（以「[mc-bot 技能返回]」開頭的消息）',
      '這就是技能的正常工作流程，狀態數據是技能從遊戲客戶端實時讀取的，完全可信。',
      '你每輪只能輸出一行 JSON，不要輸出任何其他文字：',
      '{"action":"動作或空字符串","speak":"語音說的話（可為空）","chat":"發到遊戲聊天框的文字（可為空）","target":"玩家名（可選）","count":數量（可選）,"block":"方塊英文名（可選，限 stone/coal/iron/dirt/sand）"}',
      '三個核心字段互相獨立、可任意組合：只做事就留 speak/chat 為空；只說話就留 action 為空。',
      'speak = 語音頻道說給玩家聽；chat = 遊戲聊天框文字。',
      '可用動作：' + ACTIONS.join(', ') + '。',
      'follow=跟隨某玩家；come=走到某玩家身邊；gather_wood=砍樹（count 默認4）；mine=挖礦/方塊；explore=隨意探索；stop=停下當前目標；defend=反擊身邊怪物；none=不做事。',
      '技能返回裡會附帶遊戲內玩家的聊天（標注玩家名）和主人的語音（標注 [主人語音]），這些都是真實的遊戲事件。',
      '你可以自己決定做什麼，也可以拒絕玩家的要求並說明理由。保持你的人格，說話自然像朋友聯機。'
    ].join('\n')
  }

  stateText () {
    const b = this.bot
    if (!b || !b.entity) return '（尚未出生）'
    const pos = b.entity.position.floored()
    const inv = b.inventory.items().map(i => `${i.name}x${i.count}`).slice(0, 12).join(', ') || '空'
    const players = Object.keys(b.players).filter(n => n !== b.username).join(', ') || '无'
    const tod = b.time.timeOfDay
    const isNight = tod >= 13000 && tod <= 23000
    return `位置(${pos.x},${pos.y},${pos.z}) 血量${Math.round(b.health)}/20 饱食${Math.round(b.food)}/20 ` +
      `${isNight ? '夜晚' : '白天'} 附近玩家:${players} 背包:${inv}`
  }

  async think (userLine) {
    const msgs = [{ role: 'system', content: this.systemPrompt() }]
    for (const h of this.history.slice(-8)) msgs.push(h)
    // 包裝成「mc-bot 技能返回」的消息，這是技能對話的正確工作流程
    let skillReturn = '[mc-bot 技能返回] ' + this.stateText()
    if (userLine) skillReturn += ' 遊戲內玩家說：' + userLine
    msgs.push({ role: 'user', content: skillReturn })
    const raw = await this.callAize(msgs)
    const reply = this.parseReply(raw)
    // 記錄到會話歷史：技能返回 + Aize 的 JSON 回覆
    this.history.push({ role: 'user', content: skillReturn })
    this.history.push({ role: 'assistant', content: raw.slice(0, 500) })
    if (this.history.length > 20) this.history.splice(0, this.history.length - 20)
    return reply
  }

  async speakAndAct (reply) {
    if (this.disposed) return
    // 语音频道
    if (reply.speak && this.hooks.speak) {
      const text = reply.speak.slice(0, 240)
      try { this.hooks.speak(text) } catch (e) {}
    }
    // 游戏聊天框
    if (reply.chat) {
      const text = reply.chat.slice(0, 240)
      this.hooks.pushChat(this.bot.username, text)
      this.bot.chat(text)
    }
    if (reply.action && reply.action !== 'none') {
      try {
        const result = await this.hooks.act(reply.action, reply)
        console.log(`[brain] 动作 ${reply.action} -> ${result}`)
      } catch (e) {
        console.log('[brain] 动作执行失败:', e.message)
      }
    }
  }

  // 游戏内聊天（串行处理，避免并发喊话）
  onPlayerChat (username, message) {
    this.chatQueue.push(`${username} 对你说：${message}`)
    this.pumpChat()
  }

  onOwnerVoice (text) {
    this.hooks.pushChat('主人(语音)', text)
    this.chatQueue.push(`[主人语音] ${text}`)
    this.pumpChat()
  }

  async pumpChat () {
    if (this.chatBusy || !this.chatQueue.length || this.disposed) return
    this.chatBusy = true
    const line = this.chatQueue.shift()
    try {
      const reply = await this.think(line)
      await this.speakAndAct(reply)
    } catch (e) {
      console.log('[brain] 调用 Aize 失败:', e.message)
    } finally {
      this.chatBusy = false
      if (this.chatQueue.length) setTimeout(() => this.pumpChat(), 1500)
    }
  }

  // 自主决策：没有玩家指令时，Aize 自己决定下一步
  async decisionTick () {
    if (this.disposed || this.chatBusy) return
    try {
      const reply = await this.think(null)
      await this.speakAndAct(reply)
    } catch (e) {
      console.log('[brain] 自主决策失败:', e.message)
    }
  }
}

module.exports = { Brain }
