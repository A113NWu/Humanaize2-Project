// FML3 握手探針：觀察登入階段每個報文（用 AizeTest 避免與服務中的 Aize 撞名）
'use strict'
const mc = require('./node_modules/minecraft-protocol')
const { installForgeHandshake } = require('./vendor/forge')

const client = mc.createClient({
  host: '127.0.0.1',
  port: 1234,
  username: 'AizeTest',
  version: '1.20.1',
  auth: 'offline'
})
installForgeHandshake(client)

// 觀測 custom_payload 往返（找 voicechat secret 交換卡點）
const origWrite = client.write.bind(client)
client.write = (name, data) => {
  if (name === 'custom_payload' && /voicechat|minecraft:(register|unregister)/.test(data.channel)) {
    console.log(`[probe] OUT ch=${data.channel} len=${data.data ? data.data.length : 0} hex=${data.data ? data.data.toString('hex').slice(0, 60) : ''}`)
  }
  return origWrite(name, data)
}
client.on('custom_payload', d => {
  if (/voicechat|minecraft:(register|unregister)/.test(d.channel)) {
    console.log(`[probe] IN ch=${d.channel} len=${d.data ? d.data.length : 0} hex=${d.data ? d.data.toString('hex').slice(0, 60) : ''}`)
  }
})

client.on('login_plugin_request', p => {
  if (p.channel === 'fml:loginwrapper') {
    try {
      const i = { b: p.data, o: 0 }
      // 讀 RL
      const rlLen = (() => { let r = 0, s = 0; for (;;) { const b = i.b[i.o++]; r |= (b & 0x7f) << s; if (!(b & 0x80)) break; s += 7 } return r })()
      const rl = i.b.subarray(i.o, i.o + rlLen).toString('utf8'); i.o += rlLen
      let len = 0, s = 0
      for (;;) { const b = i.b[i.o++]; len |= (b & 0x7f) << s; if (!(b & 0x80)) break; s += 7 }
      const type = i.b[i.o]
      console.log(`[probe] LPR id=${p.messageId} rl=${rl} type=${type} 內層=${len}B`)
    } catch (e) { console.log('[probe] LPR id=' + p.messageId + ' 解析失敗 ' + e.message) }
  } else {
    console.log(`[probe] LPR id=${p.messageId} ch=${p.channel} len=${p.data ? p.data.length : 0}`)
  }
})
client.on('compress', p => console.log('[probe] set_compression', p.threshold))
client.on('success', p => console.log('[probe] login_success', JSON.stringify(p).slice(0, 120)))
client.on('disconnect', p => console.log('[probe] disconnect:', JSON.stringify(p)))
client.on('error', e => console.log('[probe] error:', e.message))
client.on('end', r => { console.log('[probe] end:', r); process.exit(0) })
client.on('spawn_position', () => console.log('[probe] 進入遊戲 ✓'))
client.on('health', h => { console.log('[probe] 收到遊戲數據 ✓ health=' + h.health); process.exit(0) })
setTimeout(() => { console.log('[probe] 40 秒超時，退出'); process.exit(2) }, 40000)
