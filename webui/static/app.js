// Grok 注册机 WebUI 前端逻辑（原生 JS，无构建）
let SCRIPTS = [];
let curRun = null;     // 当前运行 run_id
let curSrc = null;     // 当前选中脚本
let evtSrc = null;     // EventSource

const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => [...r.querySelectorAll(s)];

function setNavOpen(open){
  document.body.classList.toggle('nav-open', open);
  $('#btn-nav').setAttribute('aria-expanded', String(open));
}

$('#btn-nav').onclick = ()=>setNavOpen(!document.body.classList.contains('nav-open'));
$('#nav-backdrop').onclick = ()=>setNavOpen(false);

// ---------------------------------------------------------------- 状态轮询
async function pollStatus(){
  try{
    const s = await (await fetch('/api/status')).json();
    $('#dot-proxy').classList.toggle('on', !!s.proxy_ctrl_alive);
    $('#running').textContent = s.running ? `● ${s.running} 个任务运行中` : '';
  }catch(e){}
}
setInterval(pollStatus, 5000);

// ---------------------------------------------------------------- 视图切换
function showView(v){
  setNavOpen(false);
  $('#view-run').style.display = v==='run' ? '' : 'none';
  $('#view-env').style.display = v==='env' ? 'block' : 'none';
  $$('.navbtn').forEach(b=>b.classList.toggle('active', b.dataset.view===v));
  if(v==='env') loadEnv();
}
$$('.navbtn').forEach(b=> b.onclick = ()=> showView(b.dataset.view));

// ---------------------------------------------------------------- 脚本导航
async function loadScripts(){
  SCRIPTS = (await (await fetch('/api/scripts')).json()).scripts;
  const nav = $('#script-nav');
  const cats = {};
  SCRIPTS.forEach(s => (cats[s.category]=cats[s.category]||[]).push(s));
  nav.innerHTML = '';
  for(const cat of Object.keys(cats)){
    const t = document.createElement('div');
    t.className='cat-title'; t.textContent=cat; nav.appendChild(t);
    cats[cat].forEach(s=>{
      const b=document.createElement('button');
      b.className='scriptbtn'; b.textContent=s.title; b.dataset.id=s.id;
      b.onclick=()=>{ showView('run'); selectScript(s.id); };
      nav.appendChild(b);
    });
  }
  // 外部工具链接(新标签打开)
  try{
    const links = (await (await fetch('/api/links')).json()).links || [];
    if(links.length){
      const t = document.createElement('div');
      t.className='cat-title'; t.textContent='外部工具'; nav.appendChild(t);
      links.forEach(l=>{
        const a=document.createElement('a');
        a.className='scriptbtn linkbtn'; a.href=l.url; a.target='_blank'; a.rel='noopener';
        a.title=l.desc||l.url; a.innerHTML=`🔗 ${l.title}`;
        nav.appendChild(a);
      });
    }
  }catch(e){}
}

function selectScript(id){
  curSrc = SCRIPTS.find(s=>s.id===id);
  $$('.scriptbtn').forEach(b=>b.classList.toggle('active', b.dataset.id===id));
  if(!evtSrc) setRunState('idle', '待运行');
  renderForm(curSrc);
}

// ---------------------------------------------------------------- 渲染表单
function renderForm(s){
  const p = $('#form-panel');
  p.innerHTML = '';
  const h = document.createElement('div');
  h.innerHTML = `<h2 class="form-title">${s.title}</h2><p class="form-desc">${s.desc||''}</p>`;
  p.appendChild(h);
  if(s.warning){
    const warning = document.createElement('div');
    warning.className = 'form-warning';
    warning.setAttribute('role', 'alert');
    warning.textContent = s.warning;
    p.appendChild(warning);
  }

  s.args.forEach(a=>{
    const f = document.createElement('div'); f.className='field';
    const label = a.flag.replace(/^--/,'');
    if(a.type==='bool'){
      f.className='field checkbox';
      f.innerHTML = `<input type="checkbox" id="f_${label}" ${a.default?'checked':''}>
        <label for="f_${label}">${label}</label>`;
      if(a.help){ const hh=document.createElement('div'); hh.className='fhelp'; hh.textContent=a.help; f.appendChild(hh); }
    }else if(a.type==='choice'){
      f.innerHTML = `<label>${label}</label>
        <select id="f_${label}">${a.choices.map(c=>`<option ${c==a.default?'selected':''}>${c}</option>`).join('')}</select>
        ${a.help?`<div class="fhelp">${a.help}</div>`:''}`;
    }else if(a.type==='multi'){
      const def = a.default||[];
      f.innerHTML = `<label>${label}</label>
        <div class="multi">${a.choices.map(c=>`<label><input type="checkbox" value="${c}" ${def.includes(c)?'checked':''} data-multi="${label}">${c}</label>`).join('')}</div>
        ${a.help?`<div class="fhelp">${a.help}</div>`:''}`;
    }else{
      const t = a.type==='int' ? 'number' : 'text';
      f.innerHTML = `<label>${label}</label>
        <input type="${t}" id="f_${label}" value="${a.default!==undefined&&a.default!==''?a.default:''}" placeholder="${a.help||''}">
        ${a.help?`<div class="fhelp">${a.help}</div>`:''}`;
    }
    p.appendChild(f);
  });

  const btn = document.createElement('button');
  btn.className='btn-run'; btn.textContent='▶ 运行';
  btn.onclick = runScript;
  p.appendChild(btn);
  const cmd = document.createElement('div'); cmd.className='cmd-line'; cmd.id='cmd-preview';
  p.appendChild(cmd);
}

function collectArgs(s){
  const args = {};
  s.args.forEach(a=>{
    const label = a.flag.replace(/^--/,'');
    if(a.type==='bool'){
      args[a.flag] = $(`#f_${label}`).checked;
    }else if(a.type==='multi'){
      args[a.flag] = $$(`input[data-multi="${label}"]:checked`).map(x=>x.value);
    }else{
      const v = $(`#f_${label}`).value.trim();
      if(v!=='') args[a.flag] = a.type==='int' ? parseInt(v,10) : v;
    }
  });
  return args;
}

// ---------------------------------------------------------------- 运行 + SSE 日志
function setRunState(state, label){
  const el = $('#run-state');
  el.className = `run-state ${state}`;
  el.textContent = label;
}

async function runScript(){
  if(curRun && evtSrc){ evtSrc.close(); evtSrc = null; }
  const args = collectArgs(curSrc);
  const log = $('#log'); log.textContent='';
  $('#log-title').textContent = `运行日志 — ${curSrc.title}`;
  setRunState('running', '运行中');
  let r;
  try{
    r = await (await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({script:curSrc.id, args})})).json();
  }catch(e){
    log.textContent='启动失败: '+e;
    setRunState('failed', '启动失败');
    return;
  }
  if(r.error){
    log.textContent='错误: '+r.error;
    setRunState('failed', '启动失败');
    return;
  }
  curRun = r.run_id;
  $('#cmd-preview').textContent = '$ '+r.cmd;
  $('#btn-stop').disabled = false;
  const stream = new EventSource(`/api/logs/${curRun}`);
  evtSrc = stream;
  stream.onmessage = e=>{ log.textContent += e.data+'\n'; log.scrollTop = log.scrollHeight; };
  stream.addEventListener('done', e=>{
    let result = {};
    try{ result = JSON.parse(e.data); }catch(err){}
    if(result.stopped) setRunState('stopped', '已停止');
    else if(result.returncode===0) setRunState('success', '已成功');
    else setRunState('failed', `失败 (${result.returncode ?? '?'})`);
    stream.close();
    if(evtSrc === stream){ evtSrc = null; curRun = null; }
    $('#btn-stop').disabled = true;
    pollStatus();
  });
  stream.onerror = ()=>{
    stream.close();
    if(evtSrc !== stream) return;
    evtSrc = null;
    curRun = null;
    $('#btn-stop').disabled = true;
    if($('#run-state').classList.contains('running')) setRunState('failed', '日志连接中断');
  };
}

$('#btn-stop').onclick = async ()=>{
  if(!curRun) return;
  setRunState('stopped', '停止中');
  await fetch(`/api/stop/${curRun}`,{method:'POST'});
  $('#btn-stop').disabled = true;
};

// ---------------------------------------------------------------- 配置页
async function loadEnv(){
  const data = await (await fetch('/api/env')).json();
  const wrap = $('#env-groups'); wrap.innerHTML='';
  data.groups.forEach(g=>{
    const box = document.createElement('div'); box.className='env-group';
    const tests = (g.tests||[]).map(t=>
      `<button class="btn-test" data-test="${t.target}">${t.label}</button>`).join('');
    box.innerHTML = `<div class="env-group-title">
        <span>${g.group}</span>
        <span class="test-area">${tests}<span class="test-result" data-result-for="${g.group}"></span></span>
      </div>`;
    g.items.forEach(it=>{
      const row = document.createElement('div'); row.className='env-item';
      const type = it.secret ? 'password':'text';
      const value = it.value || it.default || '';
      let control;
      if(it.type === 'choice'){
        control = `<select data-env="${it.key}">${(it.choices||[]).map(c=>`<option value="${c}" ${c===value?'selected':''}>${c}</option>`).join('')}</select>`;
      }else if(it.type === 'textarea'){
        control = `<textarea data-env="${it.key}" rows="6" spellcheck="false"
          placeholder="${(it.help||'').replace(/"/g,'&quot;')}">${value.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</textarea>`;
      }else{
        control = `<input type="${type}" data-env="${it.key}" value="${(it.value||'').replace(/"/g,'&quot;')}"
                 placeholder="${it.default? '默认 '+it.default : ''}">`;
      }
      row.innerHTML = `
        <div class="k">${it.key}${it.required?'<span class="req">*</span>':''}</div>
        <div class="v">
          ${control}
          ${it.help?`<div class="ehelp">${it.help}</div>`:''}
        </div>`;
      box.appendChild(row);
    });
    box.querySelectorAll('.btn-test').forEach(btn=>{
      btn.onclick = ()=> runTest(btn.dataset.test, btn);
    });
    wrap.appendChild(box);
  });
}

// 连通测试：把当前页面所有 .env 输入(含未保存的)一起发过去，用最新值测
async function runTest(target, btn){
  const env = {};
  $$('input[data-env],select[data-env],textarea[data-env]').forEach(i=>{ if(i.value!=='') env[i.dataset.env]=i.value; });
  const old = btn.textContent;
  btn.disabled = true; btn.textContent = '测试中…';
  const res = btn.closest('.env-group').querySelector('.test-result');
  res.textContent=''; res.className='test-result';
  try{
    const r = await (await fetch(`/api/test/${target}`,{method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify({env})})).json();
    res.textContent = (r.ok?'✓ ':'✗ ') + r.msg;
    res.classList.add(r.ok?'ok':'bad');
  }catch(e){
    res.textContent = '✗ 测试请求失败: '+e; res.classList.add('bad');
  }finally{
    btn.disabled=false; btn.textContent=old;
  }
}

$('#btn-save-env').onclick = async ()=>{
  const env = {};
  $$('input[data-env],select[data-env],textarea[data-env]').forEach(i=>{ env[i.dataset.env] = i.value; });
  const r = await (await fetch('/api/env',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({env})})).json();
  const msg = $('#env-msg');
  msg.textContent = r.ok
    ? ('✓ 已保存 '+r.saved+' 项，新任务立即生效，无需重启')
    : ('保存失败: '+(r.error||''));
  setTimeout(()=>msg.textContent='', 5000);
};

// ---------------------------------------------------------------- 启动
loadScripts();
pollStatus();
