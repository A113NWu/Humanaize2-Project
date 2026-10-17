const state={settings:{},messages:0};const $=selector=>document.querySelector(selector);const $$=selector=>document.querySelectorAll(selector);
/* 401 統一處理：任何 API 返回未登錄 → 刷新頁面（服務器會在 / 返回登錄頁） */
const rawFetch=window.fetch.bind(window);window.fetch=(...args)=>rawFetch(...args).then(r=>{if(r.status===401){location.reload()}return r});
const basicSettings=$('[data-section-view="basic"]');basicSettings.insertAdjacentHTML('afterbegin','<div class="openai-settings"><label><input name="openai_enabled" type="checkbox">启用 OpenAI API 模式（默认关闭）</label><label>OpenAI API Key<input name="openai_api_key" type="password" placeholder="留空则使用本地模型"></label><label>OpenAI Base URL<input name="openai_base_url" placeholder="https://api.openai.com/v1"></label><label>OpenAI 模型<input name="openai_model" placeholder="gpt-4o-mini"></label><label>视觉模型（分析上传的图片用，留空沿用对话模型）<input name="vision_model" placeholder="如 gpt-4o / qwen-vl-max"></label></div>');
function addMessage(text,role){const item=document.createElement('div');item.className=`message ${role}`;item.textContent=text;$('#messages').appendChild(item);$('#messages').scrollTop=$('#messages').scrollHeight;return item}
function showView(name){$$('.view').forEach(view=>view.classList.toggle('active',view.id===`view-${name}`));$$('.nav-item[data-view]').forEach(item=>item.classList.toggle('active',item.dataset.view===name));const label={chat:'对话',thoughts:'GAN 思考',skills:'Skill 输出',status:'系统状态',settings:'设置'}[name];$('#page-title').textContent=label;$('#view-label').textContent=label;$('#sidebar').classList.remove('open')}
async function loadSettings(){const response=await fetch('/api/settings');state.settings=await response.json();for(const [key,value] of Object.entries(state.settings)){const field=$(`#settings-form [name="${key}"]`);if(!field)continue;if(field.type==='checkbox')field.checked=Boolean(value);else field.value=value}const pwField=$('#settings-form [name="web_auth_password"]');if(pwField)pwField.placeholder=state.settings.web_auth_enabled?'已设置密码（留空不修改）':'未设置密码';$('#model-name').textContent=state.settings.model_name||'未设置';applyUiPrefs()}
/* ====================== 右下角 Live2D 形象 + 動畫速度 ====================== */
const live2dWidget={
  el:null,frame:null,enabled:false,
  apply(on){this.enabled=!!on;if(!this.el)return;if(on&&!this.frame.src)this.frame.src=this.frame.dataset.src;this.el.style.display=on?'block':'none';},
  /* 推命令給 Live2D 頁面（說話/動作）；失敗靜默不影響聊天 */
  push(cmd){if(!this.enabled)return;fetch('/api/live2d/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cmd)}).catch(()=>{});},
  /* 說話時隨機選一個動作（TapBody / 各種 Idle），別老是循環同一個 */
  randomSpeakMotion(){const r=Math.random();if(r<0.5)return {type:'motion',group:'TapBody'};return {type:'motion',group:'Idle',index:Math.floor(Math.random()*9)};},
  onSpeakStart(){this.push(this.randomSpeakMotion());document.body.classList.add('aize-speaking');},
  /* 說話途中每隔一段內容再做一個動作，讓形象全程有動態而非只開頭動一下 */
  onSpeakProgress(){this.push(this.randomSpeakMotion());},
  /* 主頁語音模式開著時音頻由主頁播，這裡只讓形象動；否則形象自己開口說 */
  onReply(text){if(voice.speakActive())return;const t=String(text||'').replace(/\s+/g,' ').trim();if(t)this.push({type:'speak',text:t.slice(0,400)});}
};
function applyUiPrefs(){
  live2dWidget.apply(state.settings.live2d_enabled!==false&&String(state.settings.live2d_enabled)!=='false');
  document.documentElement.style.setProperty('--anim-mult',state.settings.animation_speed||'1.5');
  /* 語音引擎被關掉時立即停止正在播的語音（純 TTS 模式；麥克風對話模式不受影響） */
  if(!state.settings.tts_enabled&&typeof voice!=='undefined'&&!voice.on){try{voice._abortPlayback();voice.speakBuf='';}catch(e){}}
}
/* Live2D 浮窗拖動：手柄 pointer capture 後即使滑過 iframe 事件也不丟；
   位置存 localStorage，刷新保留，雙擊手柄歸位 */
(function initLive2dDrag(){
  const box=$('#live2d-box'), frame=$('#live2d-widget'), handle=$('#live2d-drag');
  live2dWidget.el=box; live2dWidget.frame=frame;
  const place=(l,t)=>{box.style.left=l+'px';box.style.top=t+'px';box.style.right='auto';box.style.bottom='auto';};
  try{
    const p=JSON.parse(localStorage.getItem('live2d_pos')||'null');
    if(p&&typeof p.left==='number'&&typeof p.top==='number') place(p.left,p.top);
  }catch(e){}
  let drag=null;
  handle.addEventListener('pointerdown',e=>{
    e.preventDefault();
    const r=box.getBoundingClientRect();
    drag={dx:e.clientX-r.left,dy:e.clientY-r.top};
    try{handle.setPointerCapture(e.pointerId);}catch(err){}
  });
  handle.addEventListener('pointermove',e=>{
    if(!drag)return;
    const maxL=innerWidth-box.offsetWidth, maxT=innerHeight-box.offsetHeight;
    const l=Math.min(Math.max(0,e.clientX-drag.dx),maxL);
    const t=Math.min(Math.max(0,e.clientY-drag.dy),maxT);
    place(l,t);
  });
  const end=()=>{
    if(!drag)return; drag=null;
    const r=box.getBoundingClientRect();
    try{localStorage.setItem('live2d_pos',JSON.stringify({left:Math.round(r.left),top:Math.round(r.top)}));}catch(e){}
  };
  handle.addEventListener('pointerup',end);
  handle.addEventListener('pointercancel',end);
  handle.addEventListener('dblclick',()=>{
    try{localStorage.removeItem('live2d_pos');}catch(e){}
    box.style.left=box.style.top=box.style.right=box.style.bottom='';
  });
})();
async function checkHealth(){try{const response=await fetch('/health');if(!response.ok)throw Error();$('#status').textContent='在线';$('#api-health').textContent='在线'}catch(error){$('#status').textContent='离线';$('#api-health').textContent='离线'}}
/* 刷新頁面後重建聊天：優先使用結構化時間線（思考行/命令區塊/正文分離，
   與實時流式渲染一致），時間線不可用時降級為 memory.json 純文本歷史 */
const THOUGHT_LABELS={gan_decision:'GAN 決策',gan_topic:'議題',gan_argument:'正方論點',gan_counter_argument:'反方論點',gan_synthesis:'綜合結論',solve_mode:'Solve 模式',skill:'Skill',gan:'思考'};
async function loadChatHistory(){
  const box=$('#messages');
  try{
    const data=await(await fetch('/api/chat/timeline')).json();
    const turns=data.turns||[];
    if(turns.length){
      let count=0;
      for(const turn of turns){
        if((turn.user||'').trim()){addMessage(turn.user,'user');count++}
        const items=turn.items||[];
        if(!items.length)continue;
        const reply=document.createElement('div');reply.className='message assistant';
        const thoughtLog=document.createElement('div');thoughtLog.className='thought-log';
        const streamRoot=document.createElement('div');streamRoot.className='skill-output';
        for(const it of items){
          if(it.k==='thought'){
            const line=document.createElement('div');
            line.className='thought-line '+(it.t?'t-'+it.t:'');
            line.dataset.label=THOUGHT_LABELS[it.t]||'思考';
            line.textContent=(it.c||'').replace(/^\[[^\]]+\]\s*/,'');
            thoughtLog.appendChild(line);
          }else if(it.k==='command_start'){
            const l=document.createElement('div');l.className='skill-cmd-start';
            l.textContent='⚙ '+(it.c||'執行技能中...');streamRoot.appendChild(l);
          }else if(it.k==='command_result'){
            const wrap=document.createElement('div');wrap.className='skill-cmd-result';
            const lab=document.createElement('div');lab.className='skill-cmd-label';lab.textContent='輸出 Output';
            const pre=document.createElement('pre');pre.textContent=(it.c||'').replace(/\s+$/,'');
            wrap.appendChild(lab);wrap.appendChild(pre);streamRoot.appendChild(wrap);
          }else{
            const n=document.createElement('div');n.className='reply-text';n.textContent=it.c||'';
            streamRoot.appendChild(n);
          }
        }
        if(thoughtLog.children.length)reply.appendChild(thoughtLog);
        if(streamRoot.children.length)reply.appendChild(streamRoot);
        if(reply.children.length){box.appendChild(reply);count++}
      }
      box.scrollTop=box.scrollHeight;
      state.messages=count;$('#message-count').textContent=count;
      return;
    }
  }catch(e){/* 時間線不可用（舊版後端），降級純文本歷史 */}
  try{const data=await (await fetch('/api/chat/history')).json();const list=data.messages||[];if(!list.length)return;for(const m of list){const item=document.createElement('div');item.className=`message ${m.role==='user'?'user':'assistant'}`;item.textContent=m.content;box.appendChild(item)}box.scrollTop=box.scrollHeight;state.messages=list.length;$('#message-count').textContent=list.length}catch(e){/* 歷史加載失敗不影響聊天 */}}
async function refreshStatus(){try{const data=await (await fetch('/api/status')).json();$('#message-count').textContent=data.messages.length;$('#model-name').textContent=data.model||'本地模型';const av=$('#app-version');if(av)av.textContent=data.version?('v'+data.version):'—'}catch(error){/* 輪詢失敗保持安靜，健康檢查會更新離線狀態 */}}
$('#collapse-sidebar').onclick=()=>$('#sidebar').classList.toggle('collapsed');$('#open-sidebar').onclick=()=>$('#sidebar').classList.add('open');$$('.nav-item[data-view]').forEach(item=>item.onclick=()=>showView(item.dataset.view));$$('.settings-tab').forEach(tab=>tab.onclick=()=>{$$('.settings-tab').forEach(item=>item.classList.remove('active'));$$('.settings-section').forEach(item=>item.classList.remove('active'));tab.classList.add('active');$(`[data-section-view="${tab.dataset.section}"]`).classList.add('active')});
$('#chat-form').onsubmit=async event=>{event.preventDefault();const text=$('#prompt').value.trim();const atts=uploadUI.payload();if(!text&&!atts.length)return;if(uploadUI.files.some(f=>f.uploading)){window.alert('文件還在上傳中，請稍候再發送');return;}addMessage(atts.length?((text?text+'\n':'')+atts.map(a=>`📎 ${a.name}`).join('\n')):text,'user');$('#prompt').value='';uploadUI.clear();voice.beginTurn();const reply=addMessage('','assistant');const thoughtLog=document.createElement('div');thoughtLog.className='thought-log';reply.appendChild(thoughtLog);/* 回覆文本塊與命令塊按事件到達順序交錯插入，避免 followup 總結出現在命令框上方 */const streamRoot=document.createElement('div');streamRoot.className='skill-output';reply.appendChild(streamRoot);let textNode=document.createElement('div');textNode.className='reply-text';textNode.textContent='思考中...';streamRoot.appendChild(textNode);let firstCommand=true;const appendText=()=>{if(!textNode||!textNode.isConnected||streamRoot.lastElementChild!==textNode){textNode=document.createElement('div');textNode.className='reply-text';streamRoot.appendChild(textNode);}return textNode};const clearThinking=()=>{const n0=streamRoot.querySelector('.reply-text');if(n0&&n0.textContent==='思考中...')n0.textContent='';};const addCommand=(ev,c)=>{/* 第一條命令到達：刪除命令前的所有解釋性文字，避免「好的我來幫你…」打斷工作流；命令完成後的總結在命令框之後，不受影響 */if(ev==='command_start'&&firstCommand){firstCommand=false;streamRoot.querySelectorAll('.reply-text').forEach(n=>n.remove());}clearThinking();/* 命令狀態行之後到達的文本要開新文本塊，保證到達順序即顯示順序 */textNode=null;if(ev==='command_start'){const l=document.createElement('div');l.className='skill-cmd-start';l.textContent='⚙ '+(c||'執行技能中...');streamRoot.appendChild(l);}else{const box=document.createElement('div');box.className='skill-cmd-result';const lab=document.createElement('div');lab.className='skill-cmd-label';lab.textContent='輸出 Output';const pre=document.createElement('pre');pre.textContent=(c||'').replace(/\s+$/,'');box.appendChild(lab);box.appendChild(pre);streamRoot.appendChild(box);}};const thoughtLabels={gan_decision:'GAN 決策',gan_topic:'議題',gan_argument:'正方論點',gan_counter_argument:'反方論點',gan_synthesis:'綜合結論',solve_mode:'Solve 模式',skill:'Skill',gan:'思考'};const addThought=(t,c)=>{clearThinking();const line=document.createElement('div');line.className='thought-line '+(t?'t-'+t:'');line.dataset.label=thoughtLabels[t]||'思考';line.textContent=(c||'').replace(/^\[[^\]]+\]\s*/,'');thoughtLog.appendChild(line);$('#messages').scrollTop=$('#messages').scrollHeight};try{const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:text}],stream:true,attachments:atts})});if(!response.ok){const data=await response.json().catch(()=>({}));const err=new Error(data.error?.message||'请求失败');err.status=response.status;throw err}
const reader=response.body?.getReader();if(!reader){throw Error('该浏览器不支持流式响应');}
const decoder=new TextDecoder();let buffer='';let sawContent=false;let replyText='';let nextMotionAt=80;while(true){const {value,done}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const parts=buffer.split('\n\n');buffer=parts.pop()||'';for(const part of parts){const line=part.trim();if(!line.startsWith('data:'))continue;const payload=line.slice(5).trim();if(!payload||payload==='[DONE]')continue;try{const data=JSON.parse(payload);const content=data.choices?.[0]?.delta?.content;if(data.error){addThought('error',content||'生成失敗');}else if(data.command_event){addCommand(data.command_event,content);}else if(data.thought){addThought(data.thought_type||'',content);}else if(typeof content==='string'&&content){const n=appendText();if(n.textContent==='思考中...')n.textContent='';n.textContent+=content;if(!sawContent)live2dWidget.onSpeakStart();sawContent=true;replyText+=content;voice.feed(content);/* 每累積約 80 字讓 Aize 再做一個動作，全程有動態 */if(replyText.length>=nextMotionAt){nextMotionAt+=80;live2dWidget.onSpeakProgress();}}if(data.choices?.[0]?.finish_reason==='stop'){if(!sawContent){reply.textContent='錯誤：AI 沒有產生任何有效內容';}}}catch(error){console.warn('Stream parse error',error,payload)}}}
if(!sawContent){reply.textContent='錯誤：AI 沒有產生任何有效內容';voice.cancel();document.body.classList.remove('aize-speaking');}else{/* 收尾：去掉每個文本塊首部空行；把「思考下一步」狀態行標記為完成，避免看起來永久卡死 */streamRoot.querySelectorAll('.reply-text').forEach(n=>{n.textContent=n.textContent.replace(/^\n+/,'')});streamRoot.querySelectorAll('.skill-cmd-start').forEach(el=>{if(/thinking about the next step/.test(el.textContent))el.textContent=el.textContent.replace('⚙','✓')});live2dWidget.onReply(replyText);voice.flush();/* 沒開 TTS：語音不會啟動，直接顯回 Skill 框 */if(!voice.speakActive())setTimeout(()=>document.body.classList.remove('aize-speaking'),120);}
state.messages++;$('#message-count').textContent=state.messages}catch(error){voice.cancel();if(error.status===409){reply.textContent=error.message;reply.classList.add('busy-notice');$('#prompt').value=text}else{reply.textContent=`请求失败：${error.message}`}}};
$('#settings-form').onsubmit=async event=>{event.preventDefault();const values={};for(const field of $('#settings-form').elements){if(!field.name)continue;values[field.name]=field.type==='checkbox'?field.checked:field.value}try{const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)});const data=await response.json();if(!response.ok)throw Error(data.error?.message||'保存失败');Object.assign(state.settings,values);applyUiPrefs();$('#settings-notice').textContent=data.message||'已保存';setTimeout(()=>$('#settings-notice').textContent='',1800)}catch(error){$('#settings-notice').textContent=`保存失败：${error.message}`}};
$('#prompt').onkeydown=event=>{if(event.key==='Enter'&&event.ctrlKey)$('#chat-form').requestSubmit()};loadSettings().catch(error=>$('#settings-notice').textContent=`读取失败：${error.message}`);checkHealth();refreshStatus();setInterval(refreshStatus,3000);loadChatHistory();

/* ====================== 語音對話（STT + 流式 TTS） ====================== */
const voice={
  on:false, cap:null, recognition:null, wantStop:false,
  speakBuf:'', inCode:false, queue:[], pumping:false, current:null, urls:[],
  micPaused:false, awaitingDrain:false,
  supported:('SpeechRecognition' in window)||('webkitSpeechRecognition' in window),
  lang(){return (state.settings&&state.settings.language)==='English'?'en-US':'zh-TW';},
  /* 是否應該出聲：麥克風對話模式，或設置裡開了語音引擎（純 TTS 自動朗讀） */
  speakActive(){return this.on||!!(state.settings&&state.settings.tts_enabled);},
  /* ---- 對話流鉤子 ---- */
  resetTurn(){this.speakBuf='';this.inCode=false;this.awaitingDrain=false;this._abortPlayback();this.queue=[];document.body.classList.remove('aize-speaking');},
  /* AI 回合開始：清空舊播放並靜音麥克風（半雙工，防止 Aize 語音被識別成新發言打斷自己） */
  beginTurn(){this.resetTurn();this.pauseMic();},
  /* AI 回合結束（出錯/無內容）：清理並恢復聽覺 */
  endTurn(){this.resetTurn();this.resumeMic();},
  cancel(){this.endTurn();},
  pauseMic(){
    if(!this.on||this.micPaused)return;
    this.micPaused=true;
    try{this.recognition&&this.recognition.stop();}catch(e){}
  },
  resumeMic(){
    if(!this.on||!this.micPaused)return;
    this.micPaused=false;
    const r=this.recognition;
    if(r){try{r.start();}catch(e){/* onend 裡也會兜底重啟 */}}
  },
  _onSpeakingDone(){
    // 所有句子播完（或沒有可播內容）後，恢復麥克風聽下一句，並顯回 Skill 執行框
    document.body.classList.remove('aize-speaking');
    if(this.awaitingDrain){this.awaitingDrain=false;this.resumeMic();}
  },
  feed(chunk){
    if(!this.speakActive()||!chunk)return;
    // 追蹤 ``` 代碼塊，代碼內容不朗讀
    const parts=String(chunk).split('```');
    for(let i=0;i<parts.length;i++){
      if(i>0)this.inCode=!this.inCode;
      if(!this.inCode)this.speakBuf+=parts[i];
    }
    this._extract(false);
  },
  flush(){
    if(!this.speakActive())return;
    this._extract(true);
    this.awaitingDrain=true;
    // 沒有任何待播/播放中的句子時直接解鎖；仍在播放則等 pump 收尾
    if(!this.queue.length&&!this.pumping)this._onSpeakingDone();
  },
  _extract(last){
    // 按句末標點切分；過長片段再按逗號切
    const enders=/[。！？!?；;\n]/;
    while(true){
      const m=this.speakBuf.match(/[。！？!?；;\n]/);
      if(!m)break;
      const idx=m.index;
      const sentence=this.speakBuf.slice(0,idx+1);
      this.speakBuf=this.speakBuf.slice(idx+1);
      this._splitLong(sentence).forEach(s=>this._enqueue(s));
    }
    if(last){
      this._splitLong(this.speakBuf).forEach(s=>this._enqueue(s));
      this.speakBuf='';
    }else if(this.speakBuf.length>80){
      const m=this.speakBuf.match(/[，、,]/g);
      if(m&&m.length){
        const cut=this.speakBuf.lastIndexOf(m[m.length-1]);
        if(cut>20){const seg=this.speakBuf.slice(0,cut+1);this.speakBuf=this.speakBuf.slice(cut+1);this._splitLong(seg).forEach(s=>this._enqueue(s));}
      }
    }
  },
  _splitLong(text){
    const out=[];
    const pieces=text.split(/([，、,])/);
    let cur='';
    for(const p of pieces){
      cur+=p;
      if(/[，、,]$/.test(cur)&&cur.length>=30){out.push(cur);cur='';}
    }
    if(cur.trim())out.push(cur);
    return out;
  },
  _clean(text){
    return text
      .replace(/```[\s\S]*?```/g,' ')
      .replace(/`([^`]*)`/g,'$1')
      .replace(/!\[[^\]]*\]\([^)]*\)/g,' ')
      .replace(/\[([^\]]+)\]\([^)]*\)/g,'$1')
      .replace(/https?:\/\/\S+/g,' ')
      .replace(/^#{1,6}\s*/gm,'')
      .replace(/[*_~>｜|]/g,'')
      .replace(/\s+/g,' ')
      .trim();
  },
  _enqueue(raw){
    const text=this._clean(raw);
    if(text.length<2)return;
    if(!/[A-Za-z\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]/.test(text))return;
    this.queue.push(text);
    this._pump();
  },
  async _pump(){
    if(this.pumping)return;
    this.pumping=true;
    try{
      while(this.queue.length){
        const text=this.queue.shift();
        if(!this.speakActive())break;
        try{await this._synthAndPlay(text);}catch(e){console.warn('[voice] tts skip',e);}
      }
    }finally{
      this.pumping=false;
      this._onSpeakingDone();
    }
  },
  _synthAndPlay(text){
    return new Promise(async (resolve)=>{
      let audio=null,url='';
      const ctrl=new AbortController();this._ctrl=ctrl;
      let timer=setTimeout(()=>{try{audio&&audio.pause();}catch(_){}try{ctrl.abort();}catch(_){}resolve();},60000);
      const finish=()=>{clearTimeout(timer);if(url)URL.revokeObjectURL(url);if(this._ctrl===ctrl)this._ctrl=null;resolve();};
      try{
        const resp=await fetch('/api/tts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text}),signal:ctrl.signal});
        if(!resp.ok){console.warn('[voice] tts HTTP',resp.status);finish();return;}
        const blob=await resp.blob();
        if(!this.speakActive()){finish();return;}
        url=URL.createObjectURL(blob);this.urls.push(url);
        audio=new Audio(url);this.current=audio;
        audio.onended=finish;audio.onerror=finish;
        try{
          await audio.play();
        }catch(err){
          if(err&&err.name==='NotAllowedError'){
            // 瀏覽器自動播放策略：頁面刷新後沒有用戶手勢會被拒，等手勢後重試一次
            await this._waitForUnlock();
            if(!this.on||this.current!==audio){finish();return;}
            try{await audio.play();}catch(e2){console.warn('[voice] 播放仍被拒絕',e2&&e2.name);}
          }else{console.warn('[voice] 播放失敗',err&&err.name);}
          finish();
        }
      }catch(e){finish();}
    });
  },
  /* 等待首次用戶手勢以解鎖音頻播放（Edge/Chrome 自動播放策略） */
  _waitForUnlock(){
    if(!this._unlockPromise){
      this._unlockPromise=new Promise((res)=>{
        const done=()=>{document.removeEventListener('pointerdown',done,true);document.removeEventListener('keydown',done,true);this._unlockPromise=null;res();};
        document.addEventListener('pointerdown',done,true);
        document.addEventListener('keydown',done,true);
        console.warn('[voice] 瀏覽器阻擋了聲音播放：點擊頁面任意位置即可啟用');
      });
    }
    return this._unlockPromise;
  },
  _abortPlayback(){
    this.queue=[];
    if(this._ctrl){try{this._ctrl.abort();}catch(_){}this._ctrl=null;}
    if(this.current){try{this.current.pause();}catch(_){}this.current=null;}
    this.urls.forEach(u=>{try{URL.revokeObjectURL(u);}catch(_){}});
    this.urls=[];
  },
  /* ---- 開關 ---- */
  async toggle(){
    if(this.on){this.off();return;}
    if(!this.supported){window.alert('當前瀏覽器不支援語音識別，請使用 Edge 或 Chrome 開啟網頁面板。');return;}
    if(this.cap===null){
      try{this.cap=await (await fetch('/api/voice/capabilities')).json();}catch(e){this.cap={};}
    }
    if(this.cap&&this.cap.tts_available===false){
      window.alert('伺服器尚未安裝 TTS 引擎，AI 回覆將不會朗讀，語音輸入仍可使用。');
    }
    this.on=true;this.micPaused=false;this.awaitingDrain=false;this._updateUI();this._startRecognition();
  },
  off(){
    this.on=false;this.wantStop=true;this.micPaused=false;
    try{this.recognition&&this.recognition.stop();}catch(e){}
    this._abortPlayback();this.speakBuf='';
    this._updateUI();
  },
  _updateUI(){
    const btn=$('#voice-toggle');
    btn.classList.toggle('on',this.on);
    btn.title=this.on?'語音對話開啟中，點擊關閉':'開啟語音對話（語音提問 + AI 語音回覆）';
  },
  _startRecognition(){
    const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
    const r=new SR();
    r.lang=this.lang();r.continuous=true;r.interimResults=true;
    let finals='';
    this.wantStop=false;
    r.onresult=e=>{
      // AI 思考/播報期間掛起麥克風：此時拾到的都是揚聲器裡 Aize 的聲音（回聲），不得送發
      if(this.micPaused)return;
      let interim='';
      for(let i=e.resultIndex;i<e.results.length;i++){
        const res=e.results[i];
        if(res.isFinal)finals+=res[0].transcript.trim()+' ';
        else interim+=res[0].transcript;
      }
      $('#prompt').value=(finals+interim).trim();
      if(finals.trim()){
        const spoken=finals.trim();finals='';
        $('#prompt').value='';
        this._sendSpoken(spoken);
      }
    };
    r.onerror=e=>{
      if(e.error==='not-allowed'||e.error==='service-not-allowed'){window.alert('無法使用麥克風，請在瀏覽器權限中允許麥克風存取。');this.off();}
      else if(e.error==='audio-capture'){window.alert('未偵測到麥克風設備。');this.off();}
      // no-speech / aborted / network 短暫錯誤交由 onend 自動重啟
    };
    r.onend=()=>{
      // Chrome 連續識別會在靜音後自動結束；語音模式開啟時自動重開
      if(!this.on||this.wantStop||this.micPaused)return;
      const restart=()=>{if(this.on&&!this.wantStop){try{r.start();}catch(_){}}};
      try{r.start();}catch(e){setTimeout(restart,600);}
    };
    this.recognition=r;
    try{r.start();}catch(e){console.warn('[voice] start failed',e);}
  },
  _sendSpoken(text){
    text=(text||'').trim();
    if(!text)return;
    // 直接復用表單提交流程（氣泡渲染、清空、請求都由 onsubmit 處理）
    $('#prompt').value=text;
    $('#chat-form').requestSubmit();
  }
};
$('#voice-toggle').addEventListener('click',()=>voice.toggle());

/* ====================== 聊天附件上傳 ====================== */
const uploadUI={
  files:[],
  bar:$('#attach-bar'),input:$('#file-input'),btn:$('#upload-toggle'),
  init(){
    this.btn.addEventListener('click',()=>this.input.click());
    this.input.addEventListener('change',()=>this.onSelect(Array.from(this.input.files)));
  },
  async onSelect(files){
    if(!files.length)return;
    const toUpload=[];
    for(const f of files){
      // 附件大小不限
      const item={name:f.name,file:f,isImage:f.type.startsWith('image/')||/\.(png|jpe?g|gif|webp|bmp)$/i.test(f.name)};
      toUpload.push(item);this.files.push(item);
    }
    this.render();
    for(const item of toUpload)await this.doUpload(item);
  },
  async doUpload(item){
    const fd=new FormData();fd.append('file',item.file,item.name);
    item.uploading=true;this.render();
    try{
      const resp=await fetch('/api/upload',{method:'POST',body:fd});
      const data=await resp.json();
      if(!resp.ok||!data.files||!data.files[0])throw Error(data.error?.message||'上傳失敗');
      Object.assign(item,data.files[0]);delete item.file;delete item.uploading;
    }catch(e){
      item.error=e.message;delete item.file;delete item.uploading;
      window.alert(`「${item.name}」上傳失敗：${e.message}`);
      this.files=this.files.filter(x=>x!==item);
    }
    this.render();
  },
  remove(item){
    this.files=this.files.filter(x=>x!==item);this.render();
  },
  clear(){this.files=[];this.render();},
  render(){
    this.bar.innerHTML='';
    if(!this.files.length){this.bar.classList.remove('has-items');return;}
    this.bar.classList.add('has-items');
    for(const f of this.files){
      const chip=document.createElement('div');chip.className='attach-chip'+(f.uploading?' uploading':'');
      if(f.isImage&&f.file){
        const img=document.createElement('img');img.src=URL.createObjectURL(f.file);chip.appendChild(img);
      }
      const n=document.createElement('span');n.className='attach-name';n.textContent=f.name;chip.appendChild(n);
      const del=document.createElement('button');del.className='attach-remove';del.textContent='×';
      del.addEventListener('click',()=>this.remove(f));chip.appendChild(del);
      this.bar.appendChild(chip);
    }
  },
  payload(){
    return this.files.filter(f=>f.path).map(f=>({name:f.name,path:f.path,mime:f.mime||'',is_image:f.isImage}));
  }
};uploadUI.init();

/* ====================== 发送聊天：增加附件 ====================== */
// 原 app.js 的 $('#chat-form').onsubmit 保持不動，只要在其中增加 attachments 字段即可

/* ====================== GAN 面板：閒置思考實時事件流 ====================== */
const thoughtFeed={
  labels:{gan_decision:'GAN 決策',gan_topic:'議題',gan_argument:'正方論點',gan_counter_argument:'反方論點',gan_synthesis:'綜合結論',solve_mode:'Solve 模式',skill:'Skill',gan:'閒置思考',social:'社交',internal:'思考',web_search:'聯網搜索',error:'錯誤'},
  seen:new Set(),  // 內容去重：記憶歷史與 SSE 補發可能重疊
  panel:null,
  init(){
    this.panel=$('#thought-output');
    // 1) 先渲染記憶中的思考歷史（重新整理頁面也有內容）
    fetch('/api/status').then(r=>r.json()).then(data=>{
      (data.thoughts||[]).forEach(item=>this.append({thought_type:item.type||'internal',content:item.content||'',time:item.time||''},true));
      const skillLog=$('#skill-output');
      if(skillLog&&(data.decisions||[]).length){
        skillLog.textContent=data.decisions.map(item=>`[${item.time||''}] ${item.decision||''} ${item.reason||''}`).join('\n');
      }
    }).catch(()=>{});
    // 2) 訂閱 SSE：閒置引擎/對話中的思考事件即時追加
    this.connect();
  },
  connect(){
    const es=new EventSource('/api/events');
    es.onmessage=e=>{
      try{
        const d=JSON.parse(e.data);
        if(d.type==='thought'||d.type==='error'){
          this.append({thought_type:d.thought_type||'',content:d.content||'',time:d.time||''});
        }else if(d.type==='autonomous'){
          this.append({thought_type:'social',content:d.content||'',time:d.time||''});
          // fix4：Aize 主動找用戶說話 → 直接 PO 到聊天區（assistant 氣泡）
          if(d.content){addMessage(d.content,'assistant');live2dWidget.onSpeakStart();live2dWidget.onReply(d.content);}
        }
      }catch(_){/* 忽略無法解析的幀（含 ping） */}
    };
    es.onerror=()=>{/* 斷線時探測是否因登錄過期，是則自動刷新 */fetch('/api/settings').catch(()=>{});};
  },
  append(item,isHistory){
    if(!this.panel||!item.content)return;
    const key=item.content;
    if(this.seen.has(key))return;
    this.seen.add(key);
    const placeholder=this.panel.querySelector('.t-internal');
    if(placeholder&&placeholder.textContent==='等待思考事件...')placeholder.remove();
    const nearBottom=this.panel.scrollHeight-this.panel.scrollTop-this.panel.clientHeight<80;
    const line=document.createElement('div');
    const t=item.thought_type||'internal';
    line.className='thought-line '+(t?'t-'+t:'');
    line.dataset.label=this.labels[t]||'思考';
    if(item.time)line.title=item.time;
    line.textContent=String(item.content).replace(/^\[[^\]]+\]\s*/,'');
    this.panel.appendChild(line);
    // 歷史批次不強行滾動；實時事件僅在用戶位於底部時自動貼底
    if(!isHistory&&nearBottom)this.panel.scrollTop=this.panel.scrollHeight;
  }
};
thoughtFeed.init();

/* ====================== 設置頁：技能管理 ====================== */
const skillsAdmin={
  skills:[],
  async list(){
    const box=$('#skills-list');
    if(box)box.innerHTML='<div class="muted">技能列表載入中…首次打開需掃描全部技能，可能要等十幾秒，請稍候。</div>';
    try{
      const resp=await fetch('/api/skills');
      if(!resp.ok)throw Error('HTTP '+resp.status);
      const data=await resp.json();
      this.skills=data.skills||[];
      this.render();
    }catch(e){
      console.warn('[skills] list failed',e);
      if(box)box.innerHTML='<div class="muted">技能列表加載失敗：'+String(e.message||e)+'　<button type="button" class="mini-btn" id="skills-retry">重試</button></div>';
      const btn=$('#skills-retry');if(btn)btn.onclick=()=>this.list();
    }
  },
  render(){
    const box=$('#skills-list');
    if(!box)return;
    if(!this.skills.length){box.innerHTML='<div class="muted">未發現任何技能。</div>';return;}
    box.innerHTML='';
    this.skills.forEach(skill=>{
      const row=document.createElement('div');
      row.className='skill-item';
      const cb=document.createElement('input');
      cb.type='checkbox';cb.checked=!!skill.enabled;
      cb.title=skill.enabled?'點擊停用':'點擊啟用';
      cb.onchange=()=>this.toggle(skill.name,cb.checked,cb);
      const meta=document.createElement('div');
      meta.className='skill-meta';
      const name=document.createElement('div');
      name.className='skill-name';
      name.textContent=skill.name+(skill.executable?'':'（僅說明）');
      const desc=document.createElement('div');
      desc.className='skill-desc muted';
      desc.textContent=skill.description||'—';
      meta.appendChild(name);meta.appendChild(desc);
      row.appendChild(meta);row.appendChild(cb);
      box.appendChild(row);
      // 有獨立配置界面的技能：加「配置」按鈕，展開內嵌 iframe
      if(skill.has_config_ui){
        const btn=document.createElement('button');
        btn.type='button';btn.className='mini-btn skill-cfg-toggle';btn.textContent='配置';
        const panel=document.createElement('div');
        panel.className='skill-cfg-panel';panel.style.display='none';
        btn.onclick=()=>{
          const open=panel.style.display!=='none';
          if(open){panel.style.display='none';btn.textContent='配置';return;}
          if(!panel.dataset.loaded){
            const frame=document.createElement('iframe');
            frame.className='skill-cfg-frame';
            frame.src='/api/skills/'+encodeURIComponent(skill.name)+'/config_ui';
            frame.setAttribute('sandbox','allow-scripts allow-same-origin allow-forms allow-popups');
            panel.appendChild(frame);
            panel.dataset.loaded='1';
          }
          panel.style.display='block';btn.textContent='收起';
        };
        row.appendChild(btn);
        box.appendChild(panel);
      }
    });
  },
  async toggle(name,enabled,cb){
    const old=!enabled;
    try{
      const resp=await fetch('/api/skills/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,enabled})});
      const data=await resp.json();
      if(!resp.ok)throw Error(data.error?.message||'切換失敗');
      this.skills=data.skills||this.skills;
      this.render();
    }catch(e){
      cb.checked=old;
      window.alert(`技能切換失敗：${e.message}`);
    }
  },
  /* ---------- Misskey 配置已移入技能折疊面板（skills/misskey-bot/config_ui.html） ---------- */
  loaded:false,
  init(){
    // 後端首次構造技能管理器需導入全部技能模塊（十幾秒），改為首次打開
    // 「技能管理」分頁時才加載，避免拖慢網頁啟動
    $$('.settings-tab').forEach(tab=>{
      if(tab.dataset.section!=='skills')return;
      tab.addEventListener('click',()=>{
        if(this.loaded)return;
        this.loaded=true;
        this.list().catch(e=>{
          this.loaded=false;
          const box=$('#skills-list');
          if(box)box.innerHTML=`<div class="muted">技能列表讀取失敗：${e.message}</div>`;
        });
      });
    });
  }
};
skillsAdmin.init();

