// Aize Minecraft 机器人 —— 入口
// Java 版 1.20.1 离线模式，连入局域网世界（Forge 47.4.0 对局域网开放的房间可收纯原版协议客户端）
// 生存反射在 behaviors.js 硬编码（保命优先），高层决策与聊天在 brain.js 走本机 Aize API
'use strict'

const fs = require('fs')
const path = require('path')
const http = require('http')

const mineflayer = require('mineflayer')
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder')
const collectBlock = require('mineflayer-collectblock').plugin
const pvp = require('mineflayer-pvp').plugin
let autoEatPlugin = null
try {
  const ae = require('mineflayer-auto-eat')
  autoEatPlugin = ae.plugin || ae.loader || ae
} catch (e) {
  console.warn('[warn] mineflayer-auto-eat 加载失败，退化为手动进食逻辑:', e.message)
}

const { Brain } = require('./brain')
// Simple Voice Chat 語音接入（vendor 版：opus 走 mediaplex，免本機編譯）
const simplevoice = require('./vendor/simplevoice')
const { StoredData: VoiceStoredData } = require('./vendor/simplevoice/StoredData')
const { VoiceBridge } = require('./voice')
const { installForgeHandshake } = require('./vendor/forge')

const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8'))

// 命令行覆蓋：node bot.js --port 61234 --host 127.0.0.1
for (let i = 2; i < process.argv.length - 1; i++) {
  if (process.argv[i] === '--port') cfg.port = Number(process.argv[i + 1])
  if (process.argv[i] === '--host') cfg.host = process.argv[i + 1]
}

const HOSTILE_MOBS = new Set([
  'zombie', 'zombie_villager', 'husk', 'drowned', 'skeleton', 'stray', 'wither_skeleton',
  'spider', 'cave_spider', 'creeper', 'witch', 'slime', 'magma_cube', 'phantom',
  'enderman', 'pillager', 'vindicator', 'evoker', 'vex', 'ravager', 'hoglin', 'piglin_brute',
  'blaze', 'ghast', 'warden', 'silverfish', 'guardian', 'elder_guardian', 'zoglin', 'breeze'
])

// ---------- 游戏内聊天 / 网页日志共享缓冲 ----------
const chatLog = [] // {from, text, ts}
function pushChat (from, text) {
  chatLog.push({ from, text, ts: Date.now() })
  if (chatLog.length > 200) chatLog.shift()
}

// ---------- 创建机器人 ----------
let bot = null
let brain = null
let voiceBridge = null
let reconnectTimer = null

function createBot () {
  console.log(`[bot] 连接 ${cfg.host}:${cfg.port}，用户名 ${cfg.username}，版本 ${cfg.version}（离线模式）`)
  bot = mineflayer.createBot({
    host: cfg.host,
    port: cfg.port,
    username: cfg.username,
    version: cfg.version,
    auth: 'offline',
    hideErrors: false
  })

  // Forge（FML3）登入握手：讓 bot 能進裝了 Simple Voice Chat 的 Forge 房間；原版伺服器不受影響
  if (cfg.forge !== false) installForgeHandshake(bot._client)

  bot.loadPlugin(pathfinder)
  bot.loadPlugin(collectBlock)
  bot.loadPlugin(pvp)
  if (autoEatPlugin) bot.loadPlugin(autoEatPlugin)
  if (cfg.voice && cfg.voice.enabled !== false) {
    // 語音 UDP 回退主機（SVC secret 不帶 voiceHost 時使用遊戲服務器 host）
    VoiceStoredData.gameHost = cfg.host || '127.0.0.1'
    try {
      bot.loadPlugin(simplevoice.plugin)
    } catch (e) {
      console.warn('[warn] Simple Voice Chat 插件加載失敗（文字玩法不受影響）:', e.message)
    }
  }

  bot.once('spawn', onSpawn)
  bot.on('chat', onChat)
  bot.on('whisper', (u, m) => onChat(u, m))
  bot.on('death', onDeath)
  bot.on('kicked', (reason) => {
    console.log('[bot] 被踢出:', reason)
    pushChat('系统', '我被踢出了房间：' + String(reason).slice(0, 200))
  })
  bot.on('end', () => {
    console.log('[bot] 连接断开，10 秒后重连')
    pushChat('系统', '连接断开，10 秒后自动重连…')
    cleanup()
    reconnectTimer = setTimeout(createBot, 10000)
  })
  bot.on('error', (err) => {
    console.log('[bot] 错误:', err.message)
  })
}

function cleanup () {
  if (dangerTimer) { clearInterval(dangerTimer); dangerTimer = null }
  if (voiceBridge) { try { voiceBridge.dispose() } catch (e) {} voiceBridge = null }
  if (brain) { brain.dispose(); brain = null }
}

// ---------- 状态与目标 ----------
const state = {
  goal: 'none',       // none | follow | gather_wood | mine | explore | come
  targetPlayer: null,
  busy: false,        // 正在执行收集类任务时不再被新目标打断
  fleeing: false
}

let defaultMoves = null
let dangerTimer = null

function onSpawn () {
  defaultMoves = new Movements(bot)
  defaultMoves.allowParkour = false       // 不跑酷，防摔死
  defaultMoves.allow1by1towers = true
  defaultMoves.canDig = true
  defaultMoves.scafoldingBlocks = []      // 不主动搭方块
  bot.pathfinder.setMovements(defaultMoves)

  if (bot.autoEat) {
    // mineflayer-auto-eat v5：enableAuto()/disableAuto()，選項為 minHunger/minHealth 等
    bot.autoEat.opts = Object.assign({}, bot.autoEat.opts, {
      priority: 'foodPoints',
      minHunger: cfg.safety.eatBelowFood,
      bannedFood: ['rotten_flesh', 'spider_eye', 'poisonous_potato', 'pufferfish'],
      eatingTimeout: 4000,
      offhand: false
    })
    bot.autoEat.enableAuto()
  }

  // 危险扫描：发现近身敌对生物就逃/反击，不经过 LLM，纯反射
  dangerTimer = setInterval(dangerScan, 600)

  // 語音橋先建：聽到的話直接進 brain，brain 的 say 通過它播進語音頻道
  if (cfg.voice && cfg.voice.enabled !== false) {
    voiceBridge = new VoiceBridge(
      bot,
      Object.assign({ owners: cfg.owners || [] }, cfg.voice),
      cfg.aize,
      {
        getToken: () => brain && brain.token,
        ensureLogin: async () => { if (brain && !brain.token) await brain.login() },
        onSpeech: (name, text, isOwner) => {
          if (!brain) { pushChat(isOwner ? '主人(語音)' : `${name}(語音)`, text); return }
          if (isOwner) {
            // brain.onOwnerVoice 內部已 pushChat，避免面板重複兩條
            brain.onOwnerVoice(text)
          } else {
            pushChat(`${name}(語音)`, text)
            brain.onPlayerChat(name, '🎙（語音）' + text)
          }
        }
      }
    )
  }

  brain = new Brain(bot, cfg.aize, {
    chatLog,
    pushChat,
    act,
    speak: (text) => { if (voiceBridge) voiceBridge.say(text) }
  })
  brain.start()

  pushChat(cfg.username, '我进来啦！')
  bot.chat('我进来啦！大家下午好～')
  console.log('[bot] 已出生，位置:', bot.entity.position.floored())
}

// ---------- 危险反射（最高优先级，不经过 Aize）----------
function nearestHostile (radius) {
  let best = null
  let bestDist = radius
  for (const id in bot.entities) {
    const e = bot.entities[id]
    if (!e || !e.name || !HOSTILE_MOBS.has(e.name)) continue
    const d = bot.entity.position.distanceTo(e.position)
    if (d < bestDist) { best = e; bestDist = d }
  }
  return best ? { entity: best, dist: bestDist } : null
}

function dangerScan () {
  if (!bot.entity) return
  const near = nearestHostile(cfg.safety.dangerScanRadius)
  const lowHealth = bot.health <= cfg.safety.fleeHealth

  // 苦力怕贴脸：无条件逃跑
  let creeperNear = false
  for (const id in bot.entities) {
    const e = bot.entities[id]
    if (e && e.name === 'creeper' &&
        bot.entity.position.distanceTo(e.position) <= cfg.safety.creeperPanicRadius) {
      creeperNear = true
      if (!state.fleeing) fleeFrom(e)
      break
    }
  }
  if (creeperNear) return

  if (lowHealth && near && !state.fleeing) {
    pushChat(cfg.username, `血量太低（${Math.round(bot.health)}），先跑了！`)
    bot.chat(`血量太低，我先跑了！`)
    fleeFrom(near.entity)
  } else if (near && near.dist < 3 && !state.fleeing && bot.pvp) {
    // 被贴身就反击
    if (bot.pvp.target !== near.entity) {
      try { bot.pvp.attack(near.entity) } catch (e) {}
    }
  }
}

bot && void 0

function fleeFrom (entity) {
  state.fleeing = true
  state.busy = false
  try { bot.pvp.stop() } catch (e) {}
  // 反方向跑 16 格
  const away = bot.entity.position.minus(entity.position).normalize()
  const dest = bot.entity.position.plus(away.scaled(16))
  bot.pathfinder.setGoal(new goals.GoalNear(dest.x, dest.y, dest.z, 2), false)
  setTimeout(() => { state.fleeing = false }, 4000)
}

function onDeath () {
  state.goal = 'none'
  state.busy = false
  state.fleeing = false
  pushChat('系统', '我死了…马上重生回来')
  bot.chat('我死了……等我回来！')
}

// ---------- 动作执行（brain 调用）----------
async function act (action, opts = {}) {
  if (!bot || !bot.entity) return 'bot 不在线'
  switch (action) {
    case 'follow': return followPlayer(opts.target)
    case 'come': return comeTo(opts.target)
    case 'gather_wood': return gatherWood(opts.count || 4)
    case 'mine': return mine(opts.block || 'stone', opts.count || 8)
    case 'explore': return explore()
    case 'stop': return stopAll()
    case 'defend': return defendSelf()
    default: return 'none'
  }
}

function findPlayer (name) {
  if (!name) return null
  const p = bot.players[name]
  return p && p.entity ? p.entity : null
}

function followPlayer (name) {
  const target = findPlayer(name) || nearestPlayerEntity()
  if (!target) return '附近没看到玩家'
  state.goal = 'follow'
  state.targetPlayer = target.username || name
  bot.pathfinder.setGoal(new goals.GoalFollow(target, 2), true)
  return `开始跟随 ${state.targetPlayer}`
}

function comeTo (name) {
  const target = findPlayer(name) || nearestPlayerEntity()
  if (!target) return '附近没看到玩家'
  state.goal = 'come'
  bot.pathfinder.setGoal(new goals.GoalNear(target.position.x, target.position.y, target.position.z, 1), false)
  return '马上过来'
}

function nearestPlayerEntity () {
  let best = null
  let bestDist = 32
  for (const name in bot.players) {
    const p = bot.players[name]
    if (!p.entity || name === bot.username) continue
    const d = bot.entity.position.distanceTo(p.entity.position)
    if (d < bestDist) { best = p.entity; bestDist = d }
  }
  return best
}

async function gatherWood (count) {
  if (state.busy) return '手头有活，等下'
  state.busy = true
  state.goal = 'gather_wood'
  try {
    const ids = bot.registry.blocksByName
    const logIds = Object.keys(ids).filter(n => n.endsWith('_log')).map(n => ids[n].id)
    const found = bot.findBlocks({ matching: logIds, maxDistance: 48, count: count * 2 })
    if (!found.length) { state.busy = false; return '附近没找到树' }
    await bot.collectBlock.collect(found.map(p => bot.blockAt(p)).filter(Boolean).slice(0, count))
    const got = countItem(n => n.endsWith('_log'))
    return `砍完了，现在身上有 ${got} 个原木`
  } catch (e) {
    return '砍树中途被打断: ' + e.message
  } finally {
    state.busy = false
  }
}

async function mine (blockName, count) {
  if (state.busy) return '手头有活，等下'
  const nameMap = { stone: 'stone', coal: 'coal_ore', iron: 'iron_ore', dirt: 'dirt', sand: 'sand' }
  const real = nameMap[blockName] || blockName
  const meta = bot.registry.blocksByName[real]
  if (!meta) return `不认识方块 ${blockName}`
  state.busy = true
  state.goal = 'mine'
  try {
    const found = bot.findBlocks({ matching: meta.id, maxDistance: 32, count: count * 2 })
    if (!found.length) { state.busy = false; return `附近没有 ${blockName}` }
    await bot.collectBlock.collect(found.map(p => bot.blockAt(p)).filter(Boolean).slice(0, count))
    return `挖好了，现在有 ${countItem(n => n === real)} 个 ${blockName}`
  } catch (e) {
    return '挖矿被打断: ' + e.message
  } finally {
    state.busy = false
  }
}

function explore () {
  state.goal = 'explore'
  const angle = Math.random() * Math.PI * 2
  const dist = 20 + Math.random() * 20
  const dest = bot.entity.position.offset(Math.cos(angle) * dist, 0, Math.sin(angle) * dist)
  bot.pathfinder.setGoal(new goals.GoalNear(dest.x, dest.y, dest.z, 3), false)
  return '去附近逛逛'
}

function stopAll () {
  state.goal = 'none'
  state.targetPlayer = null
  state.busy = false
  bot.pathfinder.setGoal(null)
  try { bot.pvp.stop() } catch (e) {}
  return '停下来了'
}

function defendSelf () {
  const near = nearestHostile(10)
  if (near) {
    try { bot.pvp.attack(near.entity) } catch (e) {}
    return `反击 ${near.entity.name}`
  }
  return '附近没有敌人'
}

function countItem (match) {
  return bot.inventory.items()
    .filter(i => match(i.name))
    .reduce((s, i) => s + i.count, 0)
}

// ---------- 聊天 ----------
function onChat (username, message) {
  if (!username || username === bot.username) return
  pushChat(username, message)
  console.log(`[chat] <${username}> ${message}`)
  if (brain) brain.onPlayerChat(username, message)
}

// ---------- 网页：语音输入 + 聊天日志 + TTS 播报 ----------
function startWeb () {
  const page = fs.readFileSync(path.join(__dirname, 'stt.html'), 'utf8')
  const server = http.createServer((req, res) => {
    if (req.method === 'GET' && req.url === '/') {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
      res.end(page)
    } else if (req.method === 'GET' && req.url.startsWith('/chats')) {
      const since = Number(new URL(req.url, 'http://x').searchParams.get('since') || 0)
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' })
      res.end(JSON.stringify(chatLog.filter(c => c.ts > since)))
    } else if (req.method === 'GET' && req.url.startsWith('/voice/status')) {
      res.writeHead(200, {
        'Content-Type': 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin': '*'
      })
      res.end(JSON.stringify(voiceBridge
        ? voiceBridge.status()
        : { enabled: !(cfg.voice && cfg.voice.enabled === false), connected: false, asrReady: false, speaking: false, pendingSay: 0, listeners: [] }))
    } else if (req.method === 'POST' && req.url === '/say') {
      let body = ''
      req.on('data', d => { body += d })
      req.on('end', () => {
        try {
          const { text } = JSON.parse(body)
          if (text && brain) brain.onOwnerVoice(String(text).slice(0, 200))
        } catch (e) {}
        res.writeHead(200, { 'Content-Type': 'application/json' })
        res.end('{"ok":true}')
      })
    } else {
      res.writeHead(404); res.end()
    }
  })
  server.listen(cfg.web.port, () => {
    console.log(`[web] 语音/聊天面板: http://127.0.0.1:${cfg.web.port}/ （按住按钮说话，Aize 的回复会在此朗读）`)
  })
}

startWeb()
createBot()

process.on('SIGINT', () => {
  console.log('\n[bot] 退出')
  if (reconnectTimer) clearTimeout(reconnectTimer)
  try { bot && bot.quit() } catch (e) {}
  process.exit(0)
})
