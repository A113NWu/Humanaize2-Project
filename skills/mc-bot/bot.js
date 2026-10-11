// Aize Minecraft 机器人 —— 入口
// Java 版 1.20.1 离线模式，连入局域网世界（Forge 47.4.0 对局域网开放的房间可收纯原版协议客户端）
// 生存反射在 behaviors.js 硬编码（保命优先），高层决策与聊天在 brain.js 走本机 Aize API
'use strict'

const fs = require('fs')
const path = require('path')
const http = require('http')

const mineflayer = require('mineflayer')
const vec3 = require('vec3')
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

// ---- 解析錯誤風暴抑制 ----
// mineflayer 對 Forge 1.20.1 自定義物品 NBT（entityMetadataItem→slot→optionalNbt）解析
// 必然拋 PartialReadError，且以未捕獲 rejection 形式進入 stderr。曾 1.5 小時刷出
// 78MB/58 萬行堆棧，吃掉 62% CPU 並拖垮同機 MC 服務器。此處限流：同類錯誤只記
// 計數，每 60 秒匯總一行；其餘異常照常打印。
const _SUPPRESS_RE = /PartialReadError|Read error|Missing characters in string|unexpected size|Reading Error/i
let _suppressedCount = 0
let _suppressWindowStart = 0
function _summarizeSuppressed () {
  if (_suppressedCount > 0) {
    console.log('[bot] 忽略 %d 條 Forge NBT 解析錯誤（60 秒內）', _suppressedCount)
    _suppressedCount = 0
  }
}
setInterval(_summarizeSuppressed, 60000).unref()
function _handleProcessError (err, kind) {
  const msg = String((err && err.message) || err)
  if (_SUPPRESS_RE.test(msg) || _SUPPRESS_RE.test(String((err && err.stack) || ''))) {
    _suppressedCount++
    if (!_suppressWindowStart) { _suppressWindowStart = 1; _summarizeSuppressed() }
    return
  }
  console.error(`[${kind}]`, (err && err.stack) || msg)
}
process.on('unhandledRejection', (err) => _handleProcessError(err, 'rejection'))
process.on('uncaughtException', (err) => _handleProcessError(err, 'uncaught'))

const cfgPath = path.join(__dirname, 'config.json')
const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'))

// 命令行覆蓋：node bot.js --port 61234 --host 127.0.0.1
const CLI_OVERRIDES = []
for (let i = 2; i < process.argv.length - 1; i++) {
  if (process.argv[i] === '--port') { cfg.port = Number(process.argv[i + 1]); CLI_OVERRIDES.push('port') }
  if (process.argv[i] === '--host') { cfg.host = process.argv[i + 1]; CLI_OVERRIDES.push('host') }
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

// ---------- 登錄驗證（Sol's AuthLogin，固定密碼自動 /register、/login） ----------
function installAutoAuth (clientBot) {
  const auth = cfg.auth
  if (!auth || auth.enabled === false || !auth.password) return

  const pw = auth.password
  let authed = false
  let regSent = 0
  let loginSent = 0
  // Brigadier 的 SINGLE_QUOTABLE_WORD 不接受裸寫的 @ 等字符，參數統一加引號
  const quoted = () => `"${pw}"`
  const sendReg = () => {
    if (regSent++ < 3) {
      console.log('[auth] 發送 /register')
      clientBot.chat(`/register ${quoted()} ${quoted()}`)
    }
  }
  const sendLogin = () => {
    if (loginSent++ < 3 && !authed) {
      console.log('[auth] 發送 /login')
      clientBot.chat(`/login ${quoted()}`)
    }
  }

  clientBot.on('messagestr', (raw) => {
    if (authed) return
    const s = String(raw).toLowerCase()
    if (s.includes('login successful') ||
        s.includes('registration successful') ||
        s.includes('auto-login') ||
        s.includes('returned to your previous location')) {
      authed = true
      console.log('[auth] 登錄驗證已通過，賬號已解鎖')
      return
    }
    // 已註冊賬號：服務器提示改用 /login
    if (s.includes('already registered') || s.includes('please login') || s.includes('use /login')) {
      return sendLogin()
    }
    // 新賬號 / 註冊提示
    if (s.includes('please register') || s.includes('register with') || s.includes('/register')) {
      return sendReg()
    }
  })

  // 兜底主動發送：spawn 後先試註冊，再試登錄；服務器的錯誤回執也會被上面的消息回補
  clientBot.once('spawn', () => {
    setTimeout(sendReg, 1200)
    setTimeout(sendLogin, 4000)
    setTimeout(() => {
      if (!authed) console.warn('[auth] 15 秒內未確認登錄成功，若服務器重啟過請檢查密碼配置')
    }, 15000)
  })
}

// ---------- 创建机器人 ----------
let bot = null
let brain = null
let voiceBridge = null
let reconnectTimer = null
let reconnectDelayMs = 10000
let botAlive = false
let botStarting = false

function scheduleReconnect (ms) {
  if (reconnectTimer) clearTimeout(reconnectTimer)
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    createBot()
  }, ms)
}

// ---------- 配置熱加載（面板保存 config.json 後自動生效，無需重啟） ----------
const CONN_KEYS = ['host', 'port', 'username', 'version', 'forge']
let cfgMtimeMs = 0
try { cfgMtimeMs = fs.statSync(cfgPath).mtimeMs } catch (e) {}

function reloadConfigIfChanged () {
  let st
  try { st = fs.statSync(cfgPath) } catch (e) { return }
  if (st.mtimeMs === cfgMtimeMs) return
  cfgMtimeMs = st.mtimeMs

  let next
  try {
    next = JSON.parse(fs.readFileSync(cfgPath, 'utf8'))
  } catch (e) {
    console.warn('[cfg] config.json 解析失敗，保留舊配置:', e.message)
    return
  }

  // 命令行臨時覆蓋過的鍤不允許被文件改回（本進程生命週期內）
  for (const k of CLI_OVERRIDES) next[k] = cfg[k]

  const connChanged = CONN_KEYS.some(k => String(next[k]) !== String(cfg[k]))
  const oldWebPort = cfg.web && cfg.web.port

  Object.assign(cfg, next)

  if (connChanged) {
    console.log(`[cfg] 連接配置變更 → ${cfg.host}:${cfg.port}（${cfg.username}），3 秒後自動重連`)
    pushChat('系统', `服務器配置變更（${cfg.host}:${cfg.port}），自動重連中…`)
    reconnectDelayMs = 3000
    setTimeout(() => { reconnectDelayMs = 10000 }, 12000)
    // 先掛一個兜底定時器；若連接活著，quit 觸發的 end 會用新定時器覆蓋它
    if (bot) { try { bot.quit('config changed') } catch (e) {} }
    scheduleReconnect(3000)
  } else {
    console.log('[cfg] 配置已熱更新（語音/安全/大腦等參數即時生效）')
  }

  // 網頁面板端口改了需要重啟進程（http.Server 不支持無痛換端口）
  if (oldWebPort && next.web && Number(next.web.port) !== Number(oldWebPort)) {
    console.warn('[cfg] 面板端口變更需重啟機器人服務後生效')
  }
}
setInterval(reloadConfigIfChanged, 2000)

function createBot () {
  if (botAlive || botStarting) return // 已有連接/正在連接，忽略重複的重連調度
  botStarting = true
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

  // 登錄驗證（Sol's AuthLogin）：進服後自動完成 /register、/login，
  // 固定密碼純反射處理，不經過 Aize 的 LLM 決策
  installAutoAuth(bot)

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
  bot.on('login', () => { botStarting = false; botAlive = true })
  bot.on('chat', onChat)
  bot.on('whisper', (u, m) => onChat(u, m))
  bot.on('death', onDeath)
  bot.on('kicked', (reason) => {
    console.log('[bot] 被踢出:', reason)
    pushChat('系统', '我被踢出了房间：' + String(reason).slice(0, 200))
  })
  bot.on('end', () => {
    botAlive = false
    botStarting = false
    console.log('[bot] 连接断开，%s 后重连', (reconnectDelayMs / 1000) + ' 秒')
    pushChat('系统', `连接断开，${reconnectDelayMs / 1000} 秒后自动重连…`)
    cleanup()
    scheduleReconnect(reconnectDelayMs)
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
  goal: 'none',       // none | follow | gather_wood | mine | explore | come | build
  targetPlayer: null,
  busy: false,        // 正在执行收集类任务时不再被新目标打断
  fleeing: false,
  buildAbort: false   // 建造过程中收到 stop 时中断
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
    // 被贴身就反击（开战前自动切到身上最好的剑/斧）
    if (bot.pvp.target !== near.entity) ensureWeaponAndAttack(near.entity)
  }
}

// ---------- 自动切武器（近战反射：开战前装备身上最好的剑/斧）----------
// 剑优先于斧；同类型按材质排序。pvp 插件不会自己换武器，必须手动 equip。
const WEAPON_RANK = [
  'netherite_sword', 'diamond_sword', 'iron_sword', 'golden_sword', 'stone_sword', 'wooden_sword',
  'netherite_axe', 'diamond_axe', 'iron_axe', 'stone_axe', 'golden_axe', 'wooden_axe'
]

function findBestWeapon () {
  let best = null
  let bestRank = WEAPON_RANK.length
  for (const it of bot.inventory.items()) {
    const r = WEAPON_RANK.indexOf(it.name)
    if (r !== -1 && r < bestRank) { best = it; bestRank = r }
  }
  return best
}

async function equipBestWeapon () {
  const w = findBestWeapon()
  if (!w) return false
  // 手里已经拿着同级武器就不重复切换
  if (bot.heldItem && bot.heldItem.name === w.name) return true
  try {
    await bot.equip(w, 'hand')
    console.log('[bot] 自动切换武器:', w.name)
    return true
  } catch (e) {
    console.log('[bot] 装备武器失败:', e.message)
    return false
  }
}

// 切武器是异步的，await 期间怪可能移动/死亡，装备完再校验目标有效才开打
async function ensureWeaponAndAttack (entity) {
  await equipBestWeapon()
  try {
    if (entity && typeof entity.isValid === 'function' && entity.isValid &&
        bot.entity && bot.entity.position.distanceTo(entity.position) < 6) {
      bot.pvp.attack(entity)
    }
  } catch (e) {}
}

// ==================== TaCZ 枪械支持 ====================
// TaCZ 物品 name 規則：tacz:modern_kinetic_gun / tacz:attachment 等，
// data 里 gunId 存在 nbt 中。mineflayer item.name 會是 'tacz:modern_kinetic_gun' 或帶自定義。
// 判斷一把槍：name 以 tacz: 開頭且不是 attachment/ammo。
function isTaczGun (item) {
  if (!item || !item.name) return false
  const n = item.name
  return n.startsWith('tacz:') && !n.includes('attachment') && !n.includes('ammo')
}

function findTaczGun () {
  return bot.inventory.items().find(isTaczGun) || null
}

// TaCZ 網絡包 channel: tacz:network
// 上行消息 ID（來自 TaCZ 源碼 NetworkHandler）：
//   1=SHOOT  5=AIM  6=CRAWL  22=MELEE
// mineflayer 寫 plugin message：bot._client.writeChannel('tacz:network', Buffer)
// 但實際上 TaCZ 1.20.1 走自定義 payload，包體首字節為消息類型 ordinal。
// 這裡提供高階封裝：舉槍/開火/肘擊/趴下。
const TACZ_CHANNEL = 'tacz:network'
const TACZ_MSG = { SHOOT: 1, AIM: 5, CRAWL: 6, MELEE: 22 }

let taczAiming = false
let taczCrawling = false

function taczSend (msgId, pressed) {
  try {
    // TaCZ 封包格式（1.20.1）：varint msgId + bool pressed
    const buf = Buffer.alloc(2)
    buf.writeUInt8(msgId, 0)
    buf.writeUInt8(pressed ? 1 : 0, 1)
    bot._client.writeChannel(TACZ_CHANNEL, buf)
    return true
  } catch (e) {
    console.log('[tacz] 發包失敗:', e.message)
    return false
  }
}

async function taczAim (enable) {
  const gun = bot.heldItem && isTaczGun(bot.heldItem) ? bot.heldItem : findTaczGun()
  if (!gun) return '身上沒有 TaCZ 槍械'
  if (bot.heldItem !== gun) {
    try { await bot.equip(gun, 'hand') } catch (e) { return '切槍失敗: ' + e.message }
  }
  if (taczSend(TACZ_MSG.AIM, enable)) {
    taczAiming = enable
    return enable ? '已舉槍瞄準' : '已放下槍'
  }
  return '發送瞄準封包失敗'
}

async function taczShoot () {
  const gun = bot.heldItem && isTaczGun(bot.heldItem) ? bot.heldItem : findTaczGun()
  if (!gun) return '身上沒有 TaCZ 槍械'
  if (bot.heldItem !== gun) {
    try { await bot.equip(gun, 'hand') } catch (e) { return '切槍失敗: ' + e.message }
  }
  // TaCZ 客戶端實際是按住左鍵觸發連發；這裡發一次 SHOOT press+release 模擬單發
  taczSend(TACZ_MSG.SHOOT, true)
  setTimeout(() => taczSend(TACZ_MSG.SHOOT, false), 80)
  return '砰！'
}

async function taczMelee () {
  const gun = bot.heldItem && isTaczGun(bot.heldItem) ? bot.heldItem : findTaczGun()
  if (!gun) return '身上沒有 TaCZ 槍械'
  if (bot.heldItem !== gun) {
    try { await bot.equip(gun, 'hand') } catch (e) { return '切槍失敗: ' + e.message }
  }
  if (taczSend(TACZ_MSG.MELEE, true)) return '肘擊！'
  return '發送肘擊封包失敗'
}

function taczCrawl (enable) {
  if (taczSend(TACZ_MSG.CRAWL, enable)) {
    taczCrawling = enable
    return enable ? '趴下了' : '站起來了'
  }
  return '發送趴下封包失敗'
}

// ==================== VS2 / Clockwork 飞机构 ====================
// Clockwork 提供飛機用引擎與螺旋槳。玩家右鍵坐上「駕駛座」實體後，
// 客戶端通過 vs2 的 PacketPlayerDriving 上傳輸入（前傾/油門/視角）。
// 該包為 CBOR 格式，channel: valkyrienskies:vs_packet。
// 實現複雜度較高，先做「上機/下機 + 簡易油門模擬」。
const VS2_CHANNEL = 'valkyrienskies:vs_packet'

// 坐上附近的駕駛座（或船/礦車等可騎乘實體）
async function mountNearestVehicle () {
  // VS2 飛機的座位實體在客戶端類型一般是 minecraft:boat / minecraft:minecart 或 vs2 自定義。
  // 這裡找半徑 6 內最近的可騎乘實體。
  let best = null
  let bestDist = 6
  for (const id in bot.entities) {
    const e = bot.entities[id]
    if (!e || !e.name) continue
    const n = String(e.name).toLowerCase()
    const rideable = n.includes('boat') || n.includes('minecart') || n.includes('seat') ||
      n.includes('ship') || n.includes('plane') || n.includes('vehicle') ||
      (e.metadata && e.metadata[6] && typeof e.metadata[6] === 'object')
    if (!rideable) continue
    const d = bot.entity.position.distanceTo(e.position)
    if (d < bestDist) { best = e; bestDist = d }
  }
  if (!best) return '附近沒有可乘坐的載具/飛機'
  try {
    await bot.mount(best)
    return `已上機：${best.name || '載具'}`
  } catch (e) {
    return '上機失敗: ' + e.message
  }
}

function dismountVehicle () {
  try { bot.dismount(); return '已下機' } catch (e) { return '下機失敗: ' + e.message }
}

// VS2 駕駛封包：CBOR 編碼 {seat:..., inputs:{throttle, pitch, yaw, ...}}
// 真實包結構需要對照 VS2 源碼 PacketPlayerDriving。此處發送一個簡化版：
// 只送 throttle (0..1)。若伺服器拒收，會被忽略，不影響其他邏輯。
function vs2SendDrive (throttle, forward) {
  if (!bot.vehicle) return '沒有坐在載具上'
  try {
    // CBOR 手工編碼一個最小 map：{"t": throttle, "f": forward}
    // VS2 真實字段名可能不同，這裡使用 0xA2 開頭的 map(2)
    const t = Math.max(0, Math.min(1, throttle))
    const f = forward ? 1 : 0
    // 極簡 CBOR: A2 61 74 FB <double t> 61 66 FB <double f>
    const buf = Buffer.alloc(2 + 2 + 9 + 2 + 9)
    let o = 0
    buf.writeUInt8(0xA2, o); o += 1
    buf.writeUInt8(0x61, o); o += 1
    buf.writeUInt8(0x74, o); o += 1 // 't'
    buf.writeUInt8(0xFB, o); o += 1
    buf.writeDoubleBE(t, o); o += 8
    buf.writeUInt8(0x61, o); o += 1
    buf.writeUInt8(0x66, o); o += 1 // 'f'
    buf.writeUInt8(0xFB, o); o += 1
    buf.writeDoubleBE(f, o); o += 8
    bot._client.writeChannel(VS2_CHANNEL, buf)
    return `油門 ${(t * 100) | 0}%`
  } catch (e) {
    return 'VS2 發包失敗: ' + e.message
  }
}

// 裝備 TaCZ 槍械
async function equipGun () {
  const gun = findTaczGun()
  if (!gun) return '背包里沒有 TaCZ 槍械'
  if (bot.heldItem && bot.heldItem.name === gun.name) return `手上已經拿著 ${gun.name}`
  try {
    await bot.equip(gun, 'hand')
    console.log('[bot] 裝備槍械:', gun.name)
    return `已切換到 ${gun.name}`
  } catch (e) {
    return '切槍失敗: ' + e.message
  }
}

// 聊天里 Aize 自己决定切剑时调用：返回中文结果（brain 只记日志，她自己会用 chat/speak 回应玩家）
async function equipSword () {
  const w = findBestWeapon()
  if (!w) return '背包里没有剑或斧'
  if (bot.heldItem && bot.heldItem.name === w.name) return `手上已经拿着 ${w.name}`
  try {
    await bot.equip(w, 'hand')
    console.log('[bot] 应要求切换武器:', w.name)
    return `已切换到 ${w.name}`
  } catch (e) {
    return '切换武器失败: ' + e.message
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
    case 'equip_sword': return equipSword()
    case 'equip_gun': return equipGun()
    case 'aim': return taczAim(opts.enable !== false)
    case 'shoot': return taczShoot()
    case 'melee': return taczMelee()
    case 'crawl': return taczCrawl(opts.enable !== false)
    case 'mount': return mountNearestVehicle()
    case 'dismount': return dismountVehicle()
    case 'drive': return vs2SendDrive(opts.throttle != null ? opts.throttle : 1, opts.forward !== false)
    case 'build': return buildBlueprint(opts.blueprint)
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

// ---------- 建造（藍圖逐塊放置，由 brain.js 聯網查教程後生成藍圖）----------
const PLACE_DIRS = [[0, 1, 0], [0, -1, 0], [1, 0, 0], [-1, 0, 0], [0, 0, 1], [0, 0, -1]]
const AIR_NAMES = new Set(['air', 'cave_air', 'void_air', 'light', 'structure_void'])

function itemForBlock (blockName) {
  const items = bot.inventory.items()
  let it = items.find(i => i.name === blockName)
  if (it) return it
  // 材料家族回退：藍圖方塊身上沒有時，用同家族的頂替
  if (blockName.endsWith('_planks')) it = items.find(i => i.name.endsWith('_planks'))
  else if (blockName.endsWith('_log') || blockName.endsWith('_wood')) it = items.find(i => i.name.endsWith('_log'))
  else if (blockName.includes('glass')) it = items.find(i => i.name.includes('glass'))
  else if (blockName.endsWith('_stairs')) it = items.find(i => i.name.endsWith('_stairs'))
  else if (blockName.endsWith('_slab')) it = items.find(i => i.name.endsWith('_slab'))
  else if (blockName === 'cobblestone' || blockName === 'stone') it = items.find(i => i.name === 'cobblestone' || i.name === 'cobbled_deepslate' || i.name === 'dirt')
  else if (blockName.endsWith('_fence')) it = items.find(i => i.name.endsWith('_fence'))
  return it || null
}

async function gotoNear (x, y, z, range, timeoutMs = 10000) {
  try {
    await Promise.race([
      bot.pathfinder.goto(new goals.GoalNear(x, y, z, range)),
      new Promise((_, rej) => setTimeout(() => rej(new Error('goto超时')), timeoutMs))
    ])
    return true
  } catch (e) {
    try { bot.pathfinder.setGoal(null) } catch (e2) {}
    return false
  }
}

async function placeBlockAt (pos, blockName) {
  try {
    const cur = bot.blockAt(pos)
    if (!cur) return 'unloaded'
    if (!AIR_NAMES.has(cur.name) && cur.boundingBox !== 'empty') return 'occupied'
    const item = itemForBlock(blockName)
    if (!item) return 'no-item'
    // 距離太遠先走過去
    if (bot.entity.position.distanceTo(pos) > 4.5) {
      await gotoNear(pos.x, pos.y, pos.z, 3)
    }
    // 自己站在目標位置上時先讓開
    if (bot.entity.position.floored().equals(pos)) {
      await gotoNear(pos.x + 2, pos.y, pos.z + 2, 1, 6000)
    }
    await bot.equip(item, 'hand')
    let lastErr = null
    for (const [dx, dy, dz] of PLACE_DIRS) {
      const ref = bot.blockAt(pos.offset(dx, dy, dz))
      if (!ref || AIR_NAMES.has(ref.name) || ref.boundingBox !== 'block') continue
      try {
        await bot.placeBlock(ref, vec3(-dx, -dy, -dz))
        return 'ok'
      } catch (e) { lastErr = e }
    }
    return 'no-ref' + (lastErr ? ':' + lastErr.message : '')
  } catch (e) {
    return 'err:' + e.message
  }
}

async function buildBlueprint (bp) {
  if (!bp || !bp.palette || !Array.isArray(bp.blocks) || !bp.blocks.length) return '蓝图无效'
  if (state.busy) return '手头有活，等下'
  state.busy = true
  state.goal = 'build'
  state.buildAbort = false
  try {
    // 從腳邊前方 2 格開始蓋，地面對齊腳下
    const origin = bot.entity.position.floored().offset(2, 0, 2)
    // 統計材料缺口
    const need = {}
    for (const b of bp.blocks) {
      const name = bp.palette[b[3]] || b[3]
      need[name] = (need[name] || 0) + 1
    }
    const missing = Object.entries(need)
      .map(([n, c]) => [n, c - countItem(x => x === n)])
      .filter(([, lack]) => lack > 0)
    const missText = missing.length
      ? `（缺材料：${missing.map(([n, l]) => `${n}缺${l}`).join('、')}，用相近方塊頂替或跳過）`
      : ''
    pushChat(cfg.username, `開工！建造「${bp.name || '建築'}」，共 ${bp.blocks.length} 塊${missText}`)
    // 自下而上逐塊放（同層從裡到外），結構穩定不易懸空
    const sorted = [...bp.blocks].sort((a, b) => (a[1] - b[1]) || (a[2] - b[2]) || (a[0] - b[0]))
    let done = 0
    let skipped = 0
    const total = sorted.length
    for (let i = 0; i < total; i++) {
      if (state.buildAbort) {
        pushChat(cfg.username, '建造被叫停了')
        break
      }
      const [dx, dy, dz, key] = sorted[i]
      const r = await placeBlockAt(origin.offset(dx, dy, dz), bp.palette[key] || key)
      if (r === 'ok' || r === 'occupied') done++
      else skipped++
      if ((i + 1) % 40 === 0) pushChat(cfg.username, `建造進度 ${done}/${total}…`)
    }
    const summary = `建造結束：「${bp.name || '建築'}」完成 ${done}/${total} 塊${skipped ? `，跳過 ${skipped} 塊` : ''}`
    pushChat(cfg.username, summary)
    return summary
  } finally {
    state.busy = false
    state.buildAbort = false
  }
}

function stopAll () {
  state.goal = 'none'
  state.targetPlayer = null
  state.busy = false
  state.buildAbort = true
  bot.pathfinder.setGoal(null)
  try { bot.pvp.stop() } catch (e) {}
  return '停下来了'
}

async function defendSelf () {
  const near = nearestHostile(10)
  if (near) {
    await equipBestWeapon()
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
