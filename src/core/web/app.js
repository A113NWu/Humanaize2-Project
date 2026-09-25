const state={settings:{},messages:0};const $=selector=>document.querySelector(selector);const $$=selector=>document.querySelectorAll(selector);
const basicSettings=$('[data-section-view="basic"]');basicSettings.insertAdjacentHTML('afterbegin','<div class="openai-settings"><label><input name="openai_enabled" type="checkbox">启用 OpenAI API 模式（默认关闭）</label><label>OpenAI API Key<input name="openai_api_key" type="password" placeholder="留空则使用本地模型"></label><label>OpenAI Base URL<input name="openai_base_url" placeholder="https://api.openai.com/v1"></label><label>OpenAI 模型<input name="openai_model" placeholder="gpt-4o-mini"></label></div>');
function addMessage(text,role){const item=document.createElement('div');item.className=`message ${role}`;item.textContent=text;$('#messages').appendChild(item);$('#messages').scrollTop=$('#messages').scrollHeight;return item}
function showView(name){$$('.view').forEach(view=>view.classList.toggle('active',view.id===`view-${name}`));$$('.nav-item[data-view]').forEach(item=>item.classList.toggle('active',item.dataset.view===name));const label={chat:'对话',thoughts:'GAN 思考',skills:'Skill 输出',status:'系统状态',settings:'设置'}[name];$('#page-title').textContent=label;$('#view-label').textContent=label;$('#sidebar').classList.remove('open')}
async function loadSettings(){const response=await fetch('/api/settings');state.settings=await response.json();for(const [key,value] of Object.entries(state.settings)){const field=$(`#settings-form [name="${key}"]`);if(!field)continue;if(field.type==='checkbox')field.checked=Boolean(value);else field.value=value}$('#model-name').textContent=state.settings.model_name||'未设置'}
async function checkHealth(){try{const response=await fetch('/health');if(!response.ok)throw Error();$('#status').textContent='在线';$('#api-health').textContent='在线'}catch(error){$('#status').textContent='离线';$('#api-health').textContent='离线'}}
async function refreshStatus(){try{const data=await (await fetch('/api/status')).json();$('#message-count').textContent=data.messages.length;$('#model-name').textContent=data.model||'本地模型';const av=$('#app-version');if(av)av.textContent=data.version?('v'+data.version):'—';$('#thought-output').textContent=data.thoughts.length?data.thoughts.map(item=>`[${item.time||''}] ${item.content||''}`).join('\n'):'暂无 GAN 思考输出';$('#skill-output').textContent=data.decisions.length?data.decisions.map(item=>`[${item.time||''}] ${item.decision||''} ${item.reason||''}`).join('\n'):'暂无 Skill 输出'}catch(error){$('#thought-output').textContent=`读取状态失败：${error.message}`}}
$('#collapse-sidebar').onclick=()=>$('#sidebar').classList.toggle('collapsed');$('#open-sidebar').onclick=()=>$('#sidebar').classList.add('open');$$('.nav-item[data-view]').forEach(item=>item.onclick=()=>showView(item.dataset.view));$$('.settings-tab').forEach(tab=>tab.onclick=()=>{$$('.settings-tab').forEach(item=>item.classList.remove('active'));$$('.settings-section').forEach(item=>item.classList.remove('active'));tab.classList.add('active');$(`[data-section-view="${tab.dataset.section}"]`).classList.add('active')});
$('#chat-form').onsubmit=async event=>{event.preventDefault();const text=$('#prompt').value.trim();if(!text)return;addMessage(text,'user');$('#prompt').value='';voice.resetTurn();const reply=addMessage('','assistant');const thoughtLog=document.createElement('div');thoughtLog.className='thought-log';const replyText=document.createElement('div');replyText.className='reply-text';replyText.textContent='思考中...';reply.appendChild(thoughtLog);reply.appendChild(replyText);const skillOutput=document.createElement('div');skillOutput.className='skill-output';reply.appendChild(skillOutput);const addCommand=(ev,c)=>{if(replyText.textContent==='思考中...')replyText.textContent='';if(ev==='command_start'){const l=document.createElement('div');l.className='skill-cmd-start';l.textContent='⚙ '+(c||'執行技能中...');skillOutput.appendChild(l);}else{const box=document.createElement('div');box.className='skill-cmd-result';const lab=document.createElement('div');lab.className='skill-cmd-label';lab.textContent='輸出 Output';const pre=document.createElement('pre');pre.textContent=(c||'').replace(/\s+$/,'');box.appendChild(lab);box.appendChild(pre);skillOutput.appendChild(box);}};const thoughtLabels={gan_decision:'GAN 決策',gan_topic:'議題',gan_argument:'正方論點',gan_counter_argument:'反方論點',gan_synthesis:'綜合結論',solve_mode:'Solve 模式',skill:'Skill',gan:'思考'};const addThought=(t,c)=>{if(replyText.textContent==='思考中...')replyText.textContent='';const line=document.createElement('div');line.className='thought-line '+(t?'t-'+t:'');line.dataset.label=thoughtLabels[t]||'思考';line.textContent=(c||'').replace(/^\[[^\]]+\]\s*/,'');thoughtLog.appendChild(line);$('#messages').scrollTop=$('#messages').scrollHeight};try{const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:text}],stream:true})});if(!response.ok){const data=await response.json().catch(()=>({}));const err=new Error(data.error?.message||'请求失败');err.status=response.status;throw err}
const reader=response.body?.getReader();if(!reader){throw Error('该浏览器不支持流式响应');}
const decoder=new TextDecoder();let buffer='';let sawContent=false;while(true){const {value,done}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const parts=buffer.split('\n\n');buffer=parts.pop()||'';for(const part of parts){const line=part.trim();if(!line.startsWith('data:'))continue;const payload=line.slice(5).trim();if(!payload||payload==='[DONE]')continue;try{const data=JSON.parse(payload);const content=data.choices?.[0]?.delta?.content;if(data.error){addThought('error',content||'生成失敗');}else if(data.command_event){addCommand(data.command_event,content);}else if(data.thought){addThought(data.thought_type||'',content);}else if(typeof content==='string'&&content){if(replyText.textContent==='思考中...')replyText.textContent='';replyText.textContent+=content;sawContent=true;voice.feed(content);}if(data.choices?.[0]?.finish_reason==='stop'){if(!sawContent){reply.textContent='錯誤：AI 沒有產生任何有效內容';}}}catch(error){console.warn('Stream parse error',error,payload)}}}
if(!sawContent){reply.textContent='錯誤：AI 沒有產生任何有效內容';voice.cancel();}else{replyText.textContent=replyText.textContent.replace(/^\n+/,'');voice.flush();}
state.messages++;$('#message-count').textContent=state.messages}catch(error){voice.cancel();if(error.status===409){reply.textContent=error.message;reply.classList.add('busy-notice');$('#prompt').value=text}else{reply.textContent=`请求失败：${error.message}`}}};
$('#settings-form').onsubmit=async event=>{event.preventDefault();const values={};for(const field of $('#settings-form').elements){if(!field.name)continue;values[field.name]=field.type==='checkbox'?field.checked:field.value}try{const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)});const data=await response.json();if(!response.ok)throw Error(data.error?.message||'保存失败');$('#settings-notice').textContent=data.message||'已保存';setTimeout(()=>$('#settings-notice').textContent='',1800)}catch(error){$('#settings-notice').textContent=`保存失败：${error.message}`}};
$('#prompt').onkeydown=event=>{if(event.key==='Enter'&&event.ctrlKey)$('#chat-form').requestSubmit()};loadSettings().catch(error=>$('#settings-notice').textContent=`读取失败：${error.message}`);checkHealth();refreshStatus();setInterval(refreshStatus,3000);

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

