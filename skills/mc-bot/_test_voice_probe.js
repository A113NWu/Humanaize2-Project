// 完整棧語音探針：mineflayer + FML3 握手 + simplevoice 插件，觀測 voicechat 通道往返
'use strict'
const mineflayer = require('mineflayer')
const sv = require('./vendor/simplevoice')
const { installForgeHandshake } = require('./vendor/forge')

const bot = mineflayer.createBot({
  host: '127.0.0.1',
  port: 1234,
  username: 'AizeTest2',
  version: '1.20.1',
  auth: 'offline',
  hideErrors: false
})
installForgeHandshake(bot._client)

const orig = bot._client.write.bind(bot._client)
bot._client.write = (n, d) => {
  if (n === 'custom_payload' && /voicechat/.test(d.channel)) console.log(`[vp] OUT ${d.channel} ${d.data ? d.data.length : 0}B hex=${d.data ? d.data.toString('hex').slice(0, 40) : ''}`)
  return orig(n, d)
}
bot._client.on('custom_payload', d => {
  if (/voicechat/.test(d.channel)) console.log(`[vp] IN ${d.channel} ${d.data ? d.data.length : 0}B hex=${d.data ? d.data.toString('hex').slice(0, 40) : ''}`)
})
bot.loadPlugin(sv.plugin)
bot.on('spawn', () => console.log('[vp] spawn ✓'))
bot.on('voicechat_connect', () => console.log('[vp] voicechat_connect ✓✓✓'))
bot.on('voicechat_player_sound', d => console.log('[vp] 有玩家語音幀 sender=', d.sender, 'bytes=', d.data.length))
bot.on('kicked', r => console.log('[vp] kicked:', JSON.stringify(r)))
bot.on('error', e => console.log('[vp] error:', e.message))
bot.on('end', r => console.log('[vp] end:', r))
setTimeout(() => { console.log('[vp] 30s 到，退出'); process.exit(0) }, 30000)
