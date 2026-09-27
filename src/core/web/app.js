const state={settings:{},messages:0};const $=selector=>document.querySelector(selector);const $$=selector=>document.querySelectorAll(selector);
/* 401 統一處理：任何 API 返回未登錄 → 刷新頁面（服務器會在 / 返回登錄頁） */
const rawFetch=window.fetch.bind(window);window.fetch=(...args)=>rawFetch(...args).then(r=>{if(r.status===401){location.reload()}return r});
const basicSettings=$('[data-section-view="basic"]');basicSettings.insertAdjacentHTML('afterbegin','<div class="openai-settings"><label><input name="openai_enabled" type="checkbox">启用 OpenAI API 模式（默认关闭）</label><label>OpenAI API Key<input name="openai_api_key" type="password" placeholder="留空则使用本地模型"></label><label>OpenAI Base URL<input name="openai_base_url" placeholder="https://api.openai.com/v1"></label><label>OpenAI 模型<input name="openai_model" placeholder="gpt-4o-mini"></label></div>');
function addMessage(text,role){const item=document.createElement('div');item.className=`message ${role}`;item.textContent=text;$('#messages').appendChild(item);$('#messages').scrollTop=$('#messages').scrollHeight;return item}
function showView(name){$$('.view').forEach(view=>view.classList.toggle('active',view.id===`view-${name}`));$$('.nav-item[data-view]').forEach(item=>item.classList.toggle('active',item.dataset.view===name));const label={chat:'对话',thoughts:'GAN 思考',skills:'Skill 输出',status:'系统状态',settings:'设置'}[name];$('#page-title').textContent=label;$('#view-label').textContent=label;$('#sidebar').classList.remove('open')}
async function loadSettings(){const response=await fetch('/api/settings');state.settings=await response.json();for(const [key,value] of Object.entries(state.settings)){const field=$(`#settings-form [name="${key}"]`);if(!field)continue;if(field.type==='checkbox')field.checked=Boolean(value);else field.value=value}const pwField=$('#settings-form [name="web_auth_password"]');if(pwField)pwField.placeholder=state.settings.web_auth_enabled?'已设置密码（留空不修改）':'未设置密码';$('#model-name').textContent=state.settings.model_name||'未设置'}
async function checkHealth(){try{const response=await fetch('/health');if(!response.ok)throw Error();$('#status').textContent='在线';$('#api-health').textContent='在线'}catch(error){$('#status').textContent='离线';$('#api-health').textContent='离线'}}
/* fix5：啟動時加載持久化聊天記錄（服務端 memory.json），跨設備訪問同一後端可見相同歷史 */
async function loadChatHistory(){try{const data=await (await fetch('/api/chat/history')).json();const list=data.messages||[];if(!list.length)return;const box=$('#messages');const placeholder=box.querySelector('.message.assistant');for(const m of list){const item=document.createElement('div');item.className=`message ${m.role==='user'?'user':'assistant'}`;item.textContent=m.content;box.appendChild(item)}box.scrollTop=box.scrollHeight;state.messages=list.length;$('#message-count').textContent=list.length}catch(e){/* 歷史加載失敗不影響聊天 */}}
async function refreshStatus(){try{const data=await (await fetch('/api/status')).json();$('#message-count').textContent=data.messages.length;$('#model-name').textContent=data.model||'本地模型';const av=$('#app-version');if(av)av.textContent=data.version?('v'+data.version):'—'}catch(error){/* 輪詢失敗保持安靜，健康檢查會更新離線狀態 */}}
$('#collapse-sidebar').onclick=()=>$('#sidebar').classList.toggle('collapsed');$('#open-sidebar').onclick=()=>$('#sidebar').classList.add('open');$$('.nav-item[data-view]').forEach(item=>item.onclick=()=>showView(item.dataset.view));$$('.settings-tab').forEach(tab=>tab.onclick=()=>{$$('.settings-tab').forEach(item=>item.classList.remove('active'));$$('.settings-section').forEach(item=>item.classList.remove('active'));tab.classList.add('active');$(`[data-section-view="${tab.dataset.section}"]`).classList.add('active')});
$('#chat-form').onsubmit=async event=>{event.preventDefault();const text=$('#prompt').value.trim();if(!text)return;addMessage(text,'user');$('#prompt').value='';voice.resetTurn();const reply=addMessage('','assistant');const thoughtLog=document.createElement('div');thoughtLog.className='thought-log';reply.appendChild(thoughtLog);/* 回覆文本塊與命令塊按事件到達順序交錯插入，避免 followup 總結出現在命令框上方 */const streamRoot=document.createElement('div');streamRoot.className='skill-output';reply.appendChild(streamRoot);let textNode=document.createElement('div');textNode.className='reply-text';textNode.textContent='思考中...';streamRoot.appendChild(textNode);const appendText=()=>{if(!textNode||!textNode.isConnected||streamRoot.lastElementChild!==textNode){textNode=document.createElement('div');textNode.className='reply-text';streamRoot.appendChild(textNode);}return textNode};const clearThinking=()=>{const n0=streamRoot.querySelector('.reply-text');if(n0&&n0.textContent==='思考中...')n0.textContent='';};const addCommand=(ev,c)=>{clearThinking();/* 命令狀態行之後到達的文本要開新文本塊，保證到達順序即顯示順序 */textNode=null;if(ev==='command_start'){const l=document.createElement('div');l.className='skill-cmd-start';l.textContent='⚙ '+(c||'執行技能中...');streamRoot.appendChild(l);}else{const box=document.createElement('div');box.className='skill-cmd-result';const lab=document.createElement('div');lab.className='skill-cmd-label';lab.textContent='輸出 Output';const pre=document.createElement('pre');pre.textContent=(c||'').replace(/\s+$/,'');box.appendChild(lab);box.appendChild(pre);streamRoot.appendChild(box);}};const thoughtLabels={gan_decision:'GAN 決策',gan_topic:'議題',gan_argument:'正方論點',gan_counter_argument:'反方論點',gan_synthesis:'綜合結論',solve_mode:'Solve 模式',skill:'Skill',gan:'思考'};const addThought=(t,c)=>{clearThinking();const line=document.createElement('div');line.className='thought-line '+(t?'t-'+t:'');line.dataset.label=thoughtLabels[t]||'思考';line.textContent=(c||'').replace(/^\[[^\]]+\]\s*/,'');thoughtLog.appendChild(line);$('#messages').scrollTop=$('#messages').scrollHeight};try{const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:text}],stream:true})});if(!response.ok){const data=await response.json().catch(()=>({}));const err=new Error(data.error?.message||'请求失败');err.status=response.status;throw err}
const reader=response.body?.getReader();if(!reader){throw Error('该浏览器不支持流式响应');}
const decoder=new TextDecoder();let buffer='';let sawContent=false;while(true){const {value,done}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const parts=buffer.split('\n\n');buffer=parts.pop()||'';for(const part of parts){const line=part.trim();if(!line.startsWith('data:'))continue;const payload=line.slice(5).trim();if(!payload||payload==='[DONE]')continue;try{const data=JSON.parse(payload);const content=data.choices?.[0]?.delta?.content;if(data.error){addThought('error',content||'生成失敗');}else if(data.command_event){addCommand(data.command_event,content);}else if(data.thought){addThought(data.thought_type||'',content);}else if(typeof content==='string'&&content){const n=appendText();if(n.textContent==='思考中...')n.textContent='';n.textContent+=content;sawContent=true;voice.feed(content);}if(data.choices?.[0]?.finish_reason==='stop'){if(!sawContent){reply.textContent='錯誤：AI 沒有產生任何有效內容';}}}catch(error){console.warn('Stream parse error',error,payload)}}}
if(!sawContent){reply.textContent='錯誤：AI 沒有產生任何有效內容';voice.cancel();}else{/* 收尾：去掉每個文本塊首部空行；把「思考下一步」狀態行標記為完成，避免看起來永久卡死 */streamRoot.querySelectorAll('.reply-text').forEach(n=>{n.textContent=n.textContent.replace(/^\n+/,'')});streamRoot.querySelectorAll('.skill-cmd-start').forEach(el=>{if(/thinking about the next step/.test(el.textContent))el.textContent=el.textContent.replace('⚙','✓')});voice.flush();}
state.messages++;$('#message-count').textContent=state.messages}catch(error){voice.cancel();if(error.status===409){reply.textContent=error.message;reply.classList.add('busy-notice');$('#prompt').value=text}else{reply.textContent=`请求失败：${error.message}`}}};
$('#settings-form').onsubmit=async event=>{event.preventDefault();const values={};for(const field of $('#settings-form').elements){if(!field.name)continue;values[field.name]=field.type==='checkbox'?field.checked:field.value}try{const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)});const data=await response.json();if(!response.ok)throw Error(data.error?.message||'保存失败');$('#settings-notice').textContent=data.message||'已保存';setTimeout(()=>$('#settings-notice').textContent='',1800)}catch(error){$('#settings-notice').textContent=`保存失败：${error.message}`}};
$('#prompt').onkeydown=event=>{if(event.key==='Enter'&&event.ctrlKey)$('#chat-form').requestSubmit()};loadSettings().catch(error=>$('#settings-notice').textContent=`读取失败：${error.message}`);checkHealth();refreshStatus();setInterval(refreshStatus,3000);loadChatHistory();

/* ====================== 語音對話（STT + 流式 TTS） ====================== */
const voice={
  on:false, cap:null, recognition:null, wantStop:false,
  speakBuf:'', inCode:false, queue:[], pumping:false, current:null, urls:[],
  supported:('SpeechRecognition' in window)||('webkitSpeechRecognition' in window),
  lang(){return (state.settings&&state.settings.language)==='English'?'en-US':'zh-TW';},
  /* ---- 對話流鉤子 ---- */
  resetTurn(){this.speakBuf='';this.inCode=false;this._abortPlayback();this.queue=[];},
  cancel(){this.resetTurn();},
  feed(chunk){
    if(!this.on||!chunk)return;
    // 追蹤 ``` 代碼塊，代碼內容不朗讀
    const parts=String(chunk).split('```');
    for(let i=0;i<parts.length;i++){
      if(i>0)this.inCode=!this.inCode;
      if(!this.inCode)this.speakBuf+=parts[i];
    }
    this._extract(false);
  },
  flush(){
    if(!this.on)return;
    this._extract(true);
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
        if(!this.on)break;
        try{await this._synthAndPlay(text);}catch(e){console.warn('[voice] tts skip',e);}
      }
    }finally{this.pumping=false;}
  },
  _synthAndPlay(text){
    return new Promise(async (resolve)=>{
      let timer=setTimeout(()=>{try{audio&&audio.pause();}catch(_){}resolve();},60000);
      let audio=null,url='';
      const finish=()=>{clearTimeout(timer);if(url)URL.revokeObjectURL(url);resolve();};
      try{
        const resp=await fetch('/api/tts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
        if(!resp.ok){finish();return;}
        const blob=await resp.blob();
        if(!this.on){finish();return;}
        url=URL.createObjectURL(blob);this.urls.push(url);
        audio=new Audio(url);this.current=audio;
        audio.onended=finish;audio.onerror=finish;
        await audio.play().catch(()=>finish());
      }catch(e){finish();}
    });
  },
  _abortPlayback(){
    this.queue=[];
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
      window.alert('伺服器尚未安裝 TTS 引擎（edge-tts），AI 回覆將不會朗讀，語音輸入仍可使用。');
    }
    this.on=true;this._updateUI();this._startRecognition();
  },
  off(){
    this.on=false;this.wantStop=true;
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
      if(!this.on||this.wantStop)return;
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
          if(d.content)addMessage(d.content,'assistant');
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
    const data=await (await fetch('/api/skills')).json();
    this.skills=data.skills||[];
    this.render();
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
      row.appendChild(cb);row.appendChild(meta);
      box.appendChild(row);
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
  /* ---------- Misskey 配置卡片 ---------- */
  setStatus(text,ok){
    const el=$('#mk-status');
    el.textContent=text||'';
    el.style.color=ok===false?'#ff7a7a':'';
  },
  async misskeyStatus(){
    try{
      const resp=await fetch('/api/skills/execute',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name:'misskey-bot',action:'status'})});
      const data=await resp.json();
      const r=(data&&data.result)||{};
      if(!resp.ok||r.success===false)throw Error(r.error||r.connect_error||'讀取狀態失敗');
      if(r.host)$('#mk-host').value=r.host;
      if(r.default_visibility)$('#mk-visibility').value=r.default_visibility;
      $('#mk-token').value='';
      $('#mk-token').placeholder=r.has_token?'已配置 Token（留空不修改）':'尚未配置 Token';
      const who=r.username?`@${r.username}@${r.host}`:r.host;
      this.setStatus(`${who}｜機器人標註：${r.remote_isBot===true?'是':'否'}`,true);
    }catch(e){
      this.setStatus(`狀態讀取失敗：${e.message}`,false);
    }
  },
  async misskeyConfigure(){
    const params={
      host:$('#mk-host').value.trim(),
      default_visibility:$('#mk-visibility').value,
      token:$('#mk-token').value.trim()
    };
    if(!params.host){window.alert('請填寫伺服器 Host');return;}
    this.setStatus('保存並驗證中…');
    try{
      const resp=await fetch('/api/skills/execute',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name:'misskey-bot',action:'configure',params})});
      const data=await resp.json();
      const r=(data&&data.result)||{};
      if(!resp.ok||r.success===false)throw Error(r.error||r.message||'保存失敗');
      $('#mk-token').value='';
      this.setStatus(r.message||'配置已保存',true);
      await this.misskeyStatus();
    }catch(e){
      this.setStatus(`配置失敗：${e.message}`,false);
    }
  },
  async misskeySetBot(){
    this.setStatus('正在標註為機器人…');
    try{
      const resp=await fetch('/api/skills/execute',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name:'misskey-bot',action:'set_bot'})});
      const data=await resp.json();
      const r=(data&&data.result)||{};
      if(!resp.ok||r.success===false)throw Error(r.error||'標註失敗');
      this.setStatus(r.message||'已標註為機器人',true);
      await this.misskeyStatus();
    }catch(e){
      this.setStatus(`標註失敗：${e.message}`,false);
    }
  },
  loaded:false,
  init(){
    $('#mk-save').onclick=()=>this.misskeyConfigure();
    $('#mk-bot').onclick=()=>this.misskeySetBot();
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
        this.misskeyStatus();
      });
    });
  }
};
skillsAdmin.init();

