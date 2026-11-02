'use strict';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state={circuit:null,libraries:[],cells:{},cellFormats:{},expanded:'CircuitTutorLab',selected:null,selectedNames:new Set(),editScope:'current',selectionTool:'select',editUndo:[],editRedo:[],section:'input',changes:{},history:[],runs:[],simulation:null,baseline:null,plot:'ac',tab:'learn',zoom:1,pan:[0,0],explanation:null,chatLoading:false,busy:new Set()};
const token=$('meta[name="circuit-token"]').content;
let toastTimer,activityTimer,activityStart;
function toast(message,error=false){$('#toast').textContent=message;$('#toast').classList.toggle('error',error);$('#toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('show'),error?10000:4300)}
async function api(path,options={}){const r=await fetch(path,options);let data;try{data=await r.json()}catch{throw new Error('本地服务未返回有效数据')}if(!r.ok)throw new Error(data.error||'请求失败');return data}
const descriptions={sync:['同步库列表','扫描 cds.lib 并连接实际工程库'],load:['读取原理图','读取器件、参数与真实端子连接'],analyze:['Codex 正在理解电路','根据实际连接生成讲解，通常需要几十秒'],simulate:['Spectre 正在求解','开环 AC 与闭环阶跃 · 保持原始设计不变'],chat:['Codex 正在思考','结合电路、参数草稿与实际仿真结果'],revise:['正在同步讨论结论','核对实际连接，同时修订功能判断与讲解'], 'restore-analysis':['正在恢复讲解','保留所有修订记录']};
function activity(action,show){if(show){activityStart=Date.now();$('#activity-title').textContent=descriptions[action]?.[0]||'正在处理';$('#activity-detail').textContent=descriptions[action]?.[1]||'';$('#activity').classList.remove('hidden');clearInterval(activityTimer);activityTimer=setInterval(()=>$('#activity-time').textContent=Math.round((Date.now()-activityStart)/1000)+'s',1000)}else{clearInterval(activityTimer);$('#activity').classList.add('hidden')}}
function busyButtons(){for(const selector of ['#simulate','#simulate-params'])$(selector).disabled=state.busy.has('simulate')||!state.circuit?.teaching||!state.circuit?.verified;$('#sync').disabled=state.busy.has('sync');$('#analyze').disabled=state.busy.has('analyze')||!state.circuit;$('#chat-send').disabled=state.chatLoading||state.busy.has('chat')||state.busy.has('revise')||!state.circuit;$('#sync-discussion').disabled=state.chatLoading||state.busy.has('chat')||state.busy.has('revise')||!state.history.length;$('#analysis-history').disabled=!state.circuit;$('#read-again').disabled=state.busy.has('load')||!state.circuit;$('#reset-params').disabled=state.busy.has('simulate');$$('#parameter-fields input, #parameter-fields button').forEach(i=>i.disabled=state.busy.has('simulate'));$('#edit-scope').disabled=state.busy.has('simulate');$('#undo-edit').disabled=state.busy.has('simulate')||!state.editUndo.length;$('#redo-edit').disabled=state.busy.has('simulate')||!state.editRedo.length}
async function job(action,body={},silent=false){if(state.busy.has(action))throw new Error('该操作正在进行');state.busy.add(action);busyButtons();if(!silent)activity(action,true);try{const {jobId}=await api('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json','X-Circuit-Token':token},body:JSON.stringify({action,...body})});const start=Date.now();while(Date.now()-start<260000){await new Promise(r=>setTimeout(r,action==='status'?300:900));const j=await api('/api/jobs/'+jobId);if(j.status==='error')throw new Error(j.error);if(j.status==='done')return j.result}throw new Error('等待超时。请检查本地服务日志；不要重复提交尚未完成的操作。')}finally{state.busy.delete(action);busyButtons();if(!silent)activity(action,false)}}
function showTab(tab){state.tab=tab;$$('.inspector-tabs button').forEach(b=>{b.classList.toggle('active',b.dataset.tab===tab);b.setAttribute('aria-selected',b.dataset.tab===tab)});$$('.tab-content').forEach(p=>p.classList.toggle('active',p.id==='tab-'+tab))}
function showInfo(title,body){$('#dialog-content').innerHTML='<h2>'+esc(title)+'</h2>'+body;$('#info-dialog').showModal()}
async function updateStatus(reconnect=false){
 try{
  let s=await job('status',{},true);
  if(!s.connected&&reconnect){
   $('#connection-title').textContent='正在恢复专用桥接…';$('#connection-dot').className='status-dot status-pulse';
   s=await job('connect',{},true);
  }
  $('#connection-dot').className='status-dot '+(s.connected?'online':'offline');
  $('#connection-title').textContent=s.connected?'Virtuoso 已连接':'连接待恢复，点击 ↗';
  $('#connection-detail').textContent=s.connected?[s.host,s.version].filter(Boolean).join(' · '):(s.error||'请确认虚拟机已启动').slice(0,65);
 }catch(e){$('#connection-title').textContent='虚拟机连接未完成';$('#connection-dot').className='status-dot offline';$('#connection-detail').textContent='可使用缓存，点击 ↗ 重连';toast(e.message,true)}
}
function renderLibraries(){const query=$('#search').value.toLowerCase();$('#library-count').textContent=state.libraries.length;$('#library-list').innerHTML=state.libraries.filter(l=>l.name.toLowerCase().includes(query)).map(l=>{const opened=state.expanded===l.name;return `<div class="library-row ${opened?'selected':''}"><button class="library-button" data-library="${esc(l.name)}" title="${esc(l.source)}"><span class="folder">▱</span><span class="lib-name">${esc(l.name)}</span><span class="expand">${opened?'⌄':'›'}</span></button>${opened?`<div class="cell-list">${state.cells[l.name]?(state.cells[l.name].length?state.cells[l.name].map(c=>`<button class="cell-btn ${state.circuit?.lib===l.name&&state.circuit?.cell===c?'active':''}" data-cell="${esc(c)}" data-lib="${esc(l.name)}" title="${esc(c)}">◇ ${esc(c)}${state.cellFormats[l.name]?.[c]==='cdb'?'<span class="format-badge">CDB</span>':''}</button>`).join(''):'<div class="empty-small">没有 schematic 视图</div>'):'<div class="empty-small">读取单元列表…</div>'}</div>`:''}</div>`}).join('')||'<div class="empty-small">没有匹配的库。点击 ↻ 同步。</div>'}
async function expandLibrary(name){state.expanded=state.expanded===name?null:name;renderLibraries();if(state.expanded&&!state.cells[name]){try{rememberCells(name,await api('/api/cells?lib='+encodeURIComponent(name)));renderLibraries()}catch(e){state.cells[name]=[];renderLibraries();toast(e.message,true)}}}
async function sync(){try{const data=await job('sync');state.libraries=data.libraries;renderLibraries();toast(`已同步 ${data.libraries.length} 个库${data.conflicts.length?'，存在同名路径，请在说明中查看':''}`);if(data.conflicts.length)console.info('Library path conflicts',data.conflicts);if(state.expanded&&!state.cells[state.expanded]){rememberCells(state.expanded,await api('/api/cells?lib='+encodeURIComponent(state.expanded)));renderLibraries()}}catch(e){toast(e.message,true)}}
async function selectCircuit(lib,cell){if(Object.keys(state.changes).length&&!confirm('切换电路会清除当前未仿真的参数草稿，是否继续？'))return;try{const data=await job('load',{lib,cell});await setCircuit(data);toast('已从 Virtuoso 读取原理图')}catch(e){toast(e.message,true)}}
async function setCircuit(data){
 state.circuit=data;state.expanded=data.lib;state.selected=data.instances.find(d=>d.name==='M1')?.name||data.instances[0]?.name;
 state.selectedNames=new Set(state.selected?[state.selected]:[]);state.editScope='current';state.editUndo=[];state.editRedo=[];$('#edit-scope').value='current';$('#batch-result').textContent='';state.changes={};state.history=[];state.chatLoading=true;state.explanation=null;state.section=null;state.zoom=1;state.pan=[0,0];
 if(state.simulation?.snapshotId!==data.id){state.simulation=null;state.runs=[];state.baseline=null}
 $('#circuit-title').textContent=data.title;$('#breadcrumb-lib').textContent=data.lib;$('#breadcrumb-cell').textContent=data.cell;
 $('#circuit-subtitle').textContent=data.teaching?'输入差分对 · 有源负载 · 共源放大 · 米勒补偿':'保留原始布局、工艺符号与连线 · 子电路保留原符号';
 $('#device-count').textContent=data.instances.length+' 个器件';
 $('#verification').textContent=data.verified?'◉ 实际连接已校验':data.scene?'◉ 原始符号与连线':'◉ 几何读取异常';
 $('#verification').classList.toggle('warn',!data.scene&&!data.verified);
 $('#model-label').textContent=data.modelLabel;$('#snapshot-label').textContent='SNAPSHOT '+data.id.slice(0,8);
 $('#learn-summary').textContent=data.teaching?'从输入的微小差异，到输出的电压变化。一步步看看，这 11 个器件如何一起工作。':'已读取实际连接，正在自动识别电路功能并生成讲解。复杂子电路不会被猜测展开。';
 const prompts=data.teaching?[['为什么这里需要米勒补偿？','为什么需要 CC？'],['请结合当前的真实仿真结果，解释相位裕度意味着什么。','怎么看相位裕度？']]:[['请根据真实连接说明这个电路最可能的用途，以及仍需核实的证据。','这是什么电路？'],['请沿信号路径说明各部分如何共同形成输出。','信号怎样到输出？']];$$('[data-question]').forEach((b,i)=>{b.dataset.question=prompts[i][0];b.textContent=prompts[i][1]});
 $('#explanation-source').textContent=data.teaching?'经过校验的教学导览':'自动分析中';$('#try-cc').classList.toggle('hidden',!data.teaching);$('#simulation-panel').classList.toggle('hidden',!data.teaching);$('#simulation-unavailable').classList.toggle('hidden',!!data.teaching);
 $('#chat-messages').innerHTML='<div class="chat-message assistant"><span class="message-avatar">✦</span><div>当前电路已读取。可以询问器件作用、信号路径和已完成的实验。<small>提问后由 Codex 实时回答</small></div></div>';
 renderIdentity();renderLibraries();renderSections();renderSchematic();renderDeviceSelect();renderParameters();renderSimulation();busyButtons();
 const id=data.id;
 $('#analysis-provenance').textContent='';$('#discussion-status').textContent='有依据的新结论会更新功能判断和讲解，可从修订记录恢复。';
 try{const c=await api('/api/conversation/'+id);if(state.circuit?.id!==id)return;state.history=c.messages||[];if(state.history.length){$('#chat-messages').innerHTML='';for(const m of state.history)addMessage(m.role,m.content)}}catch(e){if(state.circuit?.id===id)toast('读取已保存对话失败：'+e.message,true)}finally{if(state.circuit?.id===id){state.chatLoading=false;busyButtons()}}
 try{const h=await api('/api/circuit-history/'+id);if(state.circuit.id!==id)return;state.runs=h.runs||[];state.baseline=h.baseline;state.simulation=h.baseline;renderSimulation()}catch{}
 try{const e=await api('/api/explanation/'+id);if(state.circuit.id!==id)return;
  if(e){applyAnalysisUpdate(id,e)}else autoIdentify(id);
 }catch(e){if(state.circuit.id===id)identityError(e.message)}
}

function sections(){return state.explanation?.sections||state.circuit?.sections||[]}
function renderSections(){const rows=sections();if(state.explanation){renderIdentity();$('#learn-summary').textContent=state.explanation.summary;$('#explanation-source').textContent=state.explanation.source==='codex-discussion'?'✦ 已根据讨论修订':state.explanation.source==='user-restore'?'↶ 已恢复历史讲解':state.explanation.classificationOnly?'✦ 功能判断已完成 · 可继续深入讲解':'✦ Codex · 原始参数讲解';}$('#sections').innerHTML=rows.map((s,i)=>`<article class="section-card ${state.section===s.id?'active':''}" data-section="${esc(s.id)}" tabindex="0" role="button" aria-expanded="${state.section===s.id}"><div class="section-head"><span class="section-number">${String(i+1).padStart(2,'0')}</span><div><h3>${esc(s.title)}</h3><small>${esc((s.devices||[]).join(' · '))}</small></div><span class="section-arrow">${state.section===s.id?'⌄':'›'}</span></div><div class="section-body">${esc(s.body)}<div class="section-effect"><strong>调整时留意</strong><br>${esc(s.effect)}</div></div></article>`).join('')||'<div class="empty-small">点击上方「AI 深入讲解」，根据实际连接生成学习导览。</div>';if(state.explanation?.caveats?.length)$('#sections').innerHTML+='<div class="empty-small">'+state.explanation.caveats.map(esc).join('<br>')+'</div>'}
function changeSection(id){state.section=state.section===id?null:id;renderSections();applyHighlight()}
function activeDevices(){return sections().find(s=>s.id===state.section)?.devices||[]}
function applyHighlight(){const active=activeDevices();$('#schematic').classList.toggle('schematic-muted',active.length>0);$$('.device-group').forEach(g=>{g.classList.toggle('highlighted',active.includes(g.dataset.device));g.classList.toggle('selected',state.selectedNames.has(g.dataset.device));g.classList.toggle('current-device',g.dataset.device===state.selected);g.setAttribute('aria-pressed',state.selectedNames.has(g.dataset.device)?'true':'false')});renderSelection()}
function value(device,key){return state.changes[device.name]?.[key]??device.params[key]}
function eng(value){const m=String(value).trim().replace(/[µμ]/g,'u').match(/^([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)(meg|[TGMkKmunpf]?)$/);return m?Number(m[1])*({'':1,T:1e12,G:1e9,M:1e6,meg:1e6,k:1e3,K:1e3,m:1e-3,u:1e-6,n:1e-9,p:1e-12,f:1e-15}[m[2]]):NaN}
function dimension(d){
 if(d.kind==='zener'){const nominal=d.param_evidence?.stored?.sourceNominalBreakdown??d.params.sourceNominalBreakdown;if(nominal)return String(nominal)}
 if(['nmos','pmos','mos'].includes(d.kind)){
  const w=eng(value(d,'w')),l=eng(value(d,'l'));
  if(Number.isFinite(w)&&Number.isFinite(l))return `${+(w*1e6).toPrecision(4)} / ${+(l*1e6).toPrecision(4)} µm`;
 }
 const key=d.kind==='capacitor'?'c':d.kind==='resistor'?'r':d.kind==='isource'?'idc':null;
 if(key&&value(d,key)!=null)return String(value(d,key))+(key==='r'?' Ω':key==='c'?' F':' A');
 return d.cell;
}
function wire(points,cls=''){return `<path class="wire ${cls}" d="${points.map((p,i)=>(i?'L':'M')+p.join(',')).join(' ')}"/>`}
function dot(x,y){return `<circle class="net-dot" cx="${x}" cy="${y}" r="2.6"/>`}
function label(x,y,text,anchor='start',cls='net-label'){return `<text x="${x}" y="${y}" text-anchor="${anchor}" class="${cls}">${esc(text)}</text>`}
const coordinates={M1:[310,340],M2:[500,340],M3:[310,180],M4:[500,180],M5:[405,480],M6:[760,180],M7:[760,480],M8:[120,480],IREF:[120,210],CC:[635,330],CL:[915,480]};
function symbol(d,x,y,horizontal=false){let inner='';if(['nmos','pmos'].includes(d.kind)){const p=d.kind==='pmos';inner=`<path class="device-symbol" d="M${x-45},${y} H${x-15} M${x-15},${y-22} V${y+22} M${x-7},${y-21} V${y+21} M${x-7},${y-17} H${x+8} V${y-45} M${x-7},${y+17} H${x+8} V${y+45} M${x+8},${y} H${x+23}"/>${p?`<circle class="device-symbol" cx="${x-21}" cy="${y}" r="4" fill="#fff"/>`:''}<path class="device-symbol" d="${p?`M${x+1},${y+12} l7,5 l-7,5`:`M${x+1},${y-22} l7,5 l-7,5`}"/>${label(x+28,y+9,d.terms.B,'start','device-body-label')}`;}else if(d.kind==='capacitor'){inner=horizontal?`<path class="device-symbol" d="M${x-45},${y} H${x-5} M${x-5},${y-15} V${y+15} M${x+5},${y-15} V${y+15} M${x+5},${y} H${x+45}"/>`:`<path class="device-symbol" d="M${x},${y-45} V${y-5} M${x-15},${y-5} H${x+15} M${x-15},${y+5} H${x+15} M${x},${y+5} V${y+45}"/>`;}else if(d.kind==='isource'){inner=`<circle class="device-symbol" cx="${x}" cy="${y}" r="22"/><path class="device-symbol" d="M${x},${y-45} V${y-22} M${x},${y+22} V${y+45} M${x},${y-11} V${y+11} M${x-5},${y+5} L${x},${y+11} L${x+5},${y+5}"/>`;}else{inner=`<rect x="${x-22}" y="${y-24}" width="44" height="48" rx="5" class="device-symbol"/><path class="device-symbol" d="M${x},${y-45} V${y-24} M${x},${y+24} V${y+45}"/>`;}
 const isCap=d.kind==='capacitor';const lx=horizontal?x:x+29, ly=horizontal?y-29:y-18;return `<g class="device-group" data-device="${esc(d.name)}" role="button" tabindex="0" aria-label="${esc(d.name+' '+d.cell+'，点击查看参数')}"><title>${esc(d.name+' · '+d.cell+' · '+dimension(d))}</title><rect class="device-glow" x="${x-53}" y="${y-51}" width="130" height="102" rx="13"/>${inner}${label(lx,ly,d.name,horizontal?'middle':'start','device-label')}${label(lx,ly+17,dimension(d),horizontal?'middle':'start','device-value')}</g>`}
function renderSchematic(){const c=state.circuit;if(!c){$('#schematic').innerHTML=label(520,315,'选择一个原理图，开始探索。','middle');return}let contents='';if(c.teaching&&c.verified){$('#canvas-hint').textContent='拖动框选 · Ctrl / ⌘ / Shift 点选增减 · 平移工具拖动画布';contents+=`<rect x="227" y="113" width="337" height="302" rx="23" fill="#f3f7f312"/>`;contents+=label(380,73,'FIRST STAGE','middle','group-caption')+label(780,73,'SECOND STAGE','middle','group-caption')+label(120,73,'BIAS','middle','group-caption');
 const routes=[[[120,165],[120,95],[768,95]],[[318,95],[318,135]],[[508,95],[508,135]],[[768,95],[768,135]],[[318,225],[318,295]],[[508,225],[508,295]],[[265,180],[250,180],[250,260],[318,260]],[[250,180],[250,125],[440,125],[440,180],[455,180]],[[318,385],[318,415],[508,415],[508,385]],[[413,415],[413,435]],[[265,340],[205,340]],[[455,340],[435,340]],[[508,265],[580,265],[580,180],[715,180]],[[580,265],[580,330],[590,330]],[[680,330],[768,330]],[[768,225],[768,435]],[[768,330],[960,330]],[[915,330],[915,435]],[[915,525],[915,570],[120,570]],[[768,525],[768,570]],[[413,525],[413,570]],[[128,525],[128,570]],[[120,255],[120,400],[128,400],[128,435]],[[128,435],[75,435],[75,480]],[[120,400],[220,400],[220,480],[360,480]],[[220,480],[220,540],[685,540],[685,480],[715,480]]];
 contents+=routes.map(r=>wire(r)).join('');contents+=[dot(318,260),dot(250,180),dot(318,95),dot(508,95),dot(413,415),dot(508,265),dot(580,265),dot(768,330),dot(120,400),dot(220,480),dot(128,435),dot(413,570),dot(768,570)].join('');contents+=label(966,98,'VDD 1.8V','end')+label(157,344,'IN−','start')+label(435,325,'IN+','middle')+label(525,253,'N1')+label(333,253,'NX')+label(973,334,'OUT')+label(237,528,'VB')+label(966,574,'VSS','end')+label(528,618,'TOPOLOGY VERIFIED · SYMBOLS REDRAWN FROM CONNECTIVITY','middle','circuit-watermark');
 for(const d of c.instances){const pos=coordinates[d.name];if(pos)contents+=symbol(d,...pos,d.name==='CC')}
 }else if(c.scene){
 const rendered=CircuitGeometry.renderer(c,dimension);contents=rendered.html;
 $('#canvas-hint').textContent='拖动框选 · Ctrl / ⌘ / Shift 点选增减 · 平移工具拖动画布';
 if(c.scene.diagnostics.missingMasters.length)$('#model-label').textContent='缺失符号：'+c.scene.diagnostics.missingMasters.join('、');
 }else{
 contents=label(520,290,'暂时无法读取源符号与连线','middle')+label(520,320,'连接表仍可查看；请重新读取或检查缺失的工艺库。','middle');
 $('#canvas-hint').textContent=c.geometryError||'几何数据暂不可用';
 }
 $('#schematic').setAttribute('viewBox','0 0 1040 640');
 $('#schematic').innerHTML='<g id="diagram-root">'+contents+'</g>';updateTransform();applyHighlight();renderConnectivity()}
function updateTransform(){const root=$('#diagram-root');if(root)root.setAttribute('transform',`translate(${state.pan[0]} ${state.pan[1]}) translate(520 320) scale(${state.zoom}) translate(-520 -320)`);$('#zoom-label').textContent=Math.round(state.zoom*100)+'%'}
function renderConnectivity(){if(!state.circuit)return;$('#connectivity').innerHTML='<table><thead><tr><th>器件</th><th>端子 → 网络（实际回读）</th><th>参数</th></tr></thead><tbody>'+state.circuit.instances.map(d=>`<tr><td>${esc(d.name)}<br><small>${esc(d.cell)}</small></td><td>${Object.entries(d.terms).map(([k,v])=>esc(k)+' → '+esc(v)).join('<br>')}</td><td>${esc(dimension(d))}</td></tr>`).join('')+'</tbody></table>'}
function renderDeviceSelect(){if(!state.circuit)return;const devices=state.circuit.instances.slice().sort((a,b)=>a.name.localeCompare(b.name,undefined,{numeric:true}));$('#device-select').innerHTML='<option value="">未选择器件</option>'+devices.map(d=>`<option value="${esc(d.name)}">${esc(d.name)} · ${esc(d.cell)}</option>`).join('');$('#device-select').value=state.selected||'';$('#selected-devices').innerHTML=devices.map(d=>`<label><input type="checkbox" data-select-device="${esc(d.name)}" aria-label="选择 ${esc(d.name)}"><span>${esc(d.name)} <small>${esc(d.cell)}</small></span></label>`).join('');renderSelection()}
function renderSelection(){
 const n=state.selectedNames.size;$('#selection-count').textContent='已选 '+n+' 个';$('#selection-summary').textContent='已选 '+n+' 个'+(state.selected?' · 当前 '+state.selected:'');
 $$('#selected-devices input').forEach(i=>i.checked=state.selectedNames.has(i.dataset.selectDevice));
 $('#device-select').value=state.selected||'';
 $('#scope-description').textContent=state.editScope==='all'?'应用到本原理图中与当前器件同单元、同模型的实例。':state.editScope==='selected'?'应用到已选中、同类且可编辑该参数的器件；不兼容项会列出并跳过。':'即使选中多个器件，也只修改上方的当前器件。';
 $('#clear-selection').disabled=!n;$('#select-all').disabled=!state.circuit;
}
const paramConfig={w:{label:'沟道宽度 W',unit:'µm',scale:1e6,suffix:'u',min:.1,max:500,help:'增加宽度时，也要留意寄生电容的变化。'},l:{label:'沟道长度 L',unit:'µm',scale:1e6,suffix:'u',min:.1,max:10,help:'先检查工作点，再比较输出电阻与速度。'},c:{label:'电容值 C',unit:'pF',scale:1e12,suffix:'p',min:.1,max:20,help:'对比带宽、相位裕度和阶跃响应。'},r:{label:'电阻值 R',unit:'Ω',scale:1,suffix:'',min:1,max:100000,help:'参数仅应用于独立仿真副本。'},idc:{label:'参考电流',unit:'µA',scale:1e6,suffix:'u',min:1,max:100,help:'比较跨导、速度与静态功耗之间的权衡。'}};
function renderParameters(){
 renderSelection();const d=state.circuit?.instances.find(d=>d.name===state.selected);
 if(!d){$('#device-details').innerHTML='';$('#parameter-fields').innerHTML='<div class="empty-small">在画布上点选或框选器件，也可以展开「已选器件」勾选。</div>';renderChanges();busyButtons();return}
 $('#device-details').innerHTML=`<div class="device-details"><div class="device-type">${esc(d.kind==='pmos'?'PMOS 晶体管':d.kind==='nmos'?'NMOS 晶体管':d.kind==='capacitor'?'电容':d.kind==='isource'?'参考电流源':d.cell)}</div><div class="terminal-chips">${Object.entries(d.terms).map(([k,v])=>`<span>${esc(k)} → ${esc(v)}</span>`).join('')}</div></div>`;
 $('#parameter-fields').innerHTML=(d.editable||[]).filter(key=>paramConfig[key]&&Number.isFinite(eng(value(d,key)))).map(key=>{
  const cfg=paramConfig[key],numeric=eng(value(d,key))*cfg.scale,changed=state.changes[d.name]?.[key]!==undefined;
  const p=DeviceEdit.plan(state.circuit.instances,d.name,[...state.selectedNames],state.editScope,key);
  const values=p.targets.map(name=>eng(value(state.circuit.instances.find(i=>i.name===name),key)));
  const mixed=values.some(v=>Math.abs(v-values[0])>1e-10*Math.max(Math.abs(v),Math.abs(values[0]),1e-30));
  const preview='将修改 '+p.targets.length+' 个：'+p.targets.join('、')+(p.skipped.length?'；跳过 '+p.skipped.length+' 个不兼容器件：'+p.skipped.join('、'):'');
  return `<div class="parameter-field"><label for="param-${esc(key)}">${cfg.label}<span>${mixed?'值不一致 · 显示当前值':changed?'当前器件已修改':'原始值 '+esc(d.params[key])}</span></label><div class="parameter-input"><input id="param-${key}" data-param="${key}" type="number" min="0.000001" step="any" value="${Number(numeric.toPrecision(7))}" class="${changed?'dirty':''}"><span>${cfg.unit}</span><button type="button" class="apply-param" data-apply-param="${key}" aria-label="应用${cfg.label}">应用</button></div><input type="range" data-range="${key}" min="${cfg.min}" max="${Math.max(cfg.max,numeric*1.5)}" step="${['l','w','c'].includes(key)?.1:1}" value="${numeric}" aria-label="调整${cfg.label}"><div class="batch-preview" data-preview="${key}">${esc(preview)}</div><div class="parameter-help">${cfg.help}</div></div>`;
 }).join('')||'<div class="empty-small">该器件的尺寸参数尚未接入编辑，可正常多选。未知子电路不自动展开。</div>';
 renderChanges();busyButtons();
}
function renderChanges(){const entries=Object.entries(state.changes).flatMap(([name,p])=>Object.entries(p).map(([key,v])=>({name,key,v})));$('#dirty-dot').classList.toggle('hidden',!entries.length);$('#change-list').innerHTML=entries.length?'<strong>'+entries.length+' 项草稿修改</strong><br>'+entries.map(({name,key,v})=>{const d=state.circuit.instances.find(x=>x.name===name);return esc(`${name}.${key}：${d.params[key]} → ${v}`)}).join('<br>'):'<span style="color:#b0b9b2">参数与原始快照一致。</span>';$('#simulate-params').textContent=entries.length?'仿真 '+entries.length+' 项修改 →':'运行基准仿真 →'}
function rememberEdit(){state.editUndo.push(JSON.parse(JSON.stringify(state.changes)));if(state.editUndo.length>50)state.editUndo.shift();state.editRedo=[]}
function renderDraft(){renderParameters();renderSchematic();busyButtons()}
function setParam(key,input){
 if(state.busy.has('simulate'))return;
 const n=Number(input),cfg=paramConfig[key];if(!cfg||!String(input).trim()||!Number.isFinite(n)||n<=0){toast('参数必须是有限正数',true);renderParameters();return}
 try{const bounds=DeviceEdit.ranges[key];if(bounds&&(n<bounds[0]*cfg.scale||n>bounds[1]*cfg.scale))throw new Error(cfg.label+'允许范围为 '+Number((bounds[0]*cfg.scale).toPrecision(8))+'–'+Number((bounds[1]*cfg.scale).toPrecision(8))+' '+cfg.unit);const edit=DeviceEdit.apply(state.circuit.instances,state.changes,state.selected,[...state.selectedNames],state.editScope,key,n+cfg.suffix);
  if(edit.changed){rememberEdit();state.changes=edit.changes}
  $('#batch-result').textContent='已应用到 '+edit.targets.length+' 个器件：'+edit.targets.join('、')+(edit.skipped.length?'；已跳过 '+edit.skipped.join('、'):'');renderDraft();
 }catch(e){toast(e.message,true);renderParameters()}
}
function setSelection(names,current,switchTab=true){
 const allowed=new Set(state.circuit?.instances.map(d=>d.name)||[]);state.selectedNames=new Set(names.filter(n=>allowed.has(n)));state.selected=state.selectedNames.has(current)?current:[...state.selectedNames].at(-1)||null;state.section=null;
 $('#batch-result').textContent='';renderSections();renderParameters();applyHighlight();if(switchTab)showTab('params');
}
function selectDevice(name,switchTab=true,additive=false,preserve=false){
 if(!name)return setSelection([],null,switchTab);
 const names=additive?DeviceEdit.toggle([...state.selectedNames],name):preserve?[...new Set([...state.selectedNames,name])]:[name];
 setSelection(names,names.includes(name)?name:null,switchTab);
}
function undoEdit(redo=false){if(state.busy.has('simulate'))return;const from=redo?state.editRedo:state.editUndo,to=redo?state.editUndo:state.editRedo;if(!from.length)return;to.push(JSON.parse(JSON.stringify(state.changes)));state.changes=from.pop();$('#batch-result').textContent=redo?'已重做整次修改':'已撤销整次修改';renderDraft()}
async function analyze(){if(!state.circuit)return;const id=state.circuit.id;try{await job('analyze',{snapshotId:id,force:true});await refreshAnalysis(id);if(state.circuit?.id===id)toast('Codex 讲解已更新')}catch(e){toast(e.message,true)}}
function markdown(text){return esc(text).replace(/```[^\n]*\n([\s\S]*?)```/g,'<pre>$1</pre>').replace(/`([^`\n]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/^#{1,4} (.+)$/gm,'<strong>$1</strong>').split(/\n\n+/).map(p=>'<p>'+p.replace(/\n/g,'<br>')+'</p>').join('')}
function addMessage(role,text,temporary=false){const row=document.createElement('div');row.className='chat-message '+role;if(temporary)row.id='chat-thinking';row.innerHTML=role==='assistant'?'<span class="message-avatar">✦</span><div>'+markdown(text)+'</div>':'<div>'+esc(text)+'</div>';$('#chat-messages').append(row);row.scrollIntoView({behavior:'smooth',block:'nearest'});return row}
function metricValue(key,value){if(value==null||!Number.isFinite(value))return '—';const n=key==='unityHz'?value/1e6:key==='powerW'?value*1e6:value;return n.toLocaleString('zh-CN',{maximumFractionDigits:2})}
async function sendChat(message){
 if(!state.circuit)return toast('请先选择一个原理图',true);
 if(state.chatLoading||state.busy.has('chat')||state.busy.has('revise'))return;
 const id=state.circuit.id;addMessage('user',message);$('#chat-input').value='';
 const thinking=addMessage('assistant','正在结合当前电路思考…',true);
 try{
  const result=await job('chat',{snapshotId:id,message,changes:state.changes,runId:state.simulation?.runId,syncExplanation:$('#auto-sync').checked});
  thinking.remove();
  if(state.circuit?.id!==id)return;
  let messages;try{messages=(await api('/api/conversation/'+id)).messages}catch{messages=[...state.history,{role:'user',content:message},{role:'assistant',content:result.answer}]}if(state.circuit?.id!==id)return;state.history=messages;$('#chat-messages').innerHTML='';for(const m of state.history)addMessage(m.role,m.content);busyButtons();
  if(result.analysis)await refreshAnalysis(id);
  if(state.circuit?.id===id)reportRevision(result);
 }catch(e){thinking.remove();if(state.circuit?.id===id){addMessage('assistant','这次回答未完成：'+e.message);toast(e.message,true)}}
}

function renderSimulation(){const r=state.simulation;const metrics=[['开环增益','gainDb','dB'],['单位增益频率','unityHz','MHz'],['相位裕度','phaseMargin','°'],['静态功耗','powerW','µW']];$('#metrics').innerHTML=metrics.map(([label,key,unit])=>{const baseline=state.baseline?.metrics[key];const diff=r&&baseline!=null&&r.runId!==state.baseline.runId&&r.metrics[key]!=null?r.metrics[key]-baseline:null;return `<div><span>${label}</span><strong>${r?metricValue(key,r.metrics[key]):'—'}<small>${unit}</small>${diff!==null?`<small class="delta">${diff>=0?'+':''}${metricValue(key,diff)} ${unit} 对比基准</small>`:''}</strong></div>`}).join('');$('#sim-source').textContent=r?'SPECTRE · 实际结果':'等待仿真';$('#baseline-legend').classList.toggle('hidden',!r||!state.baseline||r.runId===state.baseline.runId);$('#run-count').textContent=state.runs.length;$('#simulation-note').textContent=r?`RUN ${r.runId.slice(0,6)} · ${Object.keys(r.changes).length?'参数草稿':'原始参数'} · ${new Date(r.createdAt*1000).toLocaleTimeString('zh-CN',{hour12:false,timeZone:'Asia/Tokyo'})}`:'Spectre 实际求解 · 不以理论估计代替仿真';$('#history-list').innerHTML=state.runs.map((run,i)=>`<div class="run-item ${run.runId===r?.runId?'active':''}" data-run="${esc(run.runId)}">${i===0&&!Object.keys(run.changes).length?'基准实验':'实验 '+(i+1)} <span style="float:right">${new Date(run.createdAt*1000).toLocaleTimeString('zh-CN',{hour12:false,timeZone:'Asia/Tokyo'})}</span><small>${Object.entries(run.changes).flatMap(([name,params])=>Object.entries(params).map(([k,v])=>esc(`${name}.${k}=${v}`))).join(' · ')||'Virtuoso 原始参数'} · PM ${metricValue('phaseMargin',run.metrics.phaseMargin)}°</small></div>`).reverse().join('')||'完成一次仿真后，记录将出现在这里。';renderPlot()}
function pathFor(x,y,sx,sy,maxPoints=1400){let text='',step=Math.max(1,Math.floor(x.length/maxPoints));for(let i=0;i<x.length;i+=step){if(!Number.isFinite(x[i])||!Number.isFinite(y[i]))continue;text+=(text?'L':'M')+sx(x[i]).toFixed(2)+','+sy(y[i]).toFixed(2)}return text}
function renderPlot(){const run=state.simulation;$('#plot-ac').classList.toggle('active',state.plot==='ac');$('#plot-tran').classList.toggle('active',state.plot==='tran');$('#legend-a').textContent=state.plot==='ac'?'增益':'输出';$('#legend-b').textContent=state.plot==='ac'?'相位':'输入';$('#plot-title').textContent=state.plot==='ac'?'开环增益 & 相位':'闭环单位增益 · 10 mV 阶跃';if(!run){$('#plot').className='plot-empty';$('#plot').innerHTML='运行一次仿真，观察电路的真实响应。';return}$('#plot').className='';const W=760,H=176,L=45,R=719,T=17,B=146;let grid='',curves='',labels='';let hoverData;
 if(state.plot==='ac'){const data=run.ac;const x=f=>L+Math.log10(f)/9*(R-L);const minDb=-60,maxDb=120;const y=v=>T+(maxDb-v)/(maxDb-minDb)*(B-T);const yp=v=>T+(30-v)/300*(B-T);for(let e=0;e<=9;e++){const xx=x(10**e);grid+=`<line x1="${xx}" y1="${T}" x2="${xx}" y2="${B}" stroke="#edf1ef"/>`;if(e%2===0||e===9)labels+=label(xx,B+17,e<3?10**e+' Hz':e<6?10**(e-3)+' k':e<9?10**(e-6)+' M':'1 G','middle','plot-label')}for(let db=-60;db<=120;db+=60){const yy=y(db);grid+=`<line x1="${L}" y1="${yy}" x2="${R}" y2="${yy}" stroke="#edf1ef"/>`;labels+=`<text x="${L-8}" y="${yy+3}" text-anchor="end">${db}</text><text x="${R+7}" y="${yy+3}">${Math.round(30-(120-db)/180*300)}°</text>`}if(state.baseline&&state.baseline.runId!==run.runId){curves+=`<path d="${pathFor(state.baseline.ac.frequency,state.baseline.ac.gainDb,x,y)}" fill="none" stroke="#b9c5bc" stroke-width="1.4" stroke-dasharray="4 4"/>`}curves+=`<path d="${pathFor(data.frequency,data.gainDb,x,y)}" fill="none" stroke="#5c987c" stroke-width="2"/><path d="${pathFor(data.frequency,data.phaseDeg,x,yp)}" fill="none" stroke="#8ba2cd" stroke-width="1.7"/>`;if(run.metrics.unityHz){let cx=x(run.metrics.unityHz),cy=y(0);curves+=`<circle cx="${cx}" cy="${cy}" r="3.3" fill="#5c987c" stroke="white" stroke-width="1.5"/><line x1="${cx}" y1="${cy+6}" x2="${cx}" y2="${B}" stroke="#c0d6c9" stroke-dasharray="2 3"/>`}hoverData={x:data.frequency,y:data.gainDb,xscale:x,yscale:y,format:(f,v)=>`${(f/1e6).toPrecision(3)} MHz · ${v.toFixed(2)} dB`};
 }else{const d=run.tran;const maxT=Math.max(...d.time);const minV=Math.min(...d.input,...d.output)-.002,maxV=Math.max(...d.input,...d.output)+.002;const x=t=>L+t/maxT*(R-L),y=v=>T+(maxV-v)/(maxV-minV)*(B-T);for(let i=0;i<=5;i++){let xx=x(maxT*i/5);grid+=`<line x1="${xx}" y1="${T}" x2="${xx}" y2="${B}" stroke="#edf1ef"/>`;labels+=`<text x="${xx}" y="${B+17}" text-anchor="middle">${(maxT*i/5*1e6).toFixed(0)} µs</text>`}for(let i=0;i<=3;i++){const v=minV+(maxV-minV)*i/3,yy=y(v);grid+=`<line x1="${L}" y1="${yy}" x2="${R}" y2="${yy}" stroke="#edf1ef"/>`;labels+=`<text x="${L-8}" y="${yy+3}" text-anchor="end">${v.toFixed(3)}</text>`}if(state.baseline&&state.baseline.runId!==run.runId)curves+=`<path d="${pathFor(state.baseline.tran.time,state.baseline.tran.output,x,y)}" fill="none" stroke="#b9c5bc" stroke-width="1.3" stroke-dasharray="4 4"/>`;curves+=`<path d="${pathFor(d.time,d.input,x,y)}" fill="none" stroke="#8ba2cd" stroke-width="1.5"/><path d="${pathFor(d.time,d.output,x,y)}" fill="none" stroke="#5c987c" stroke-width="2"/>`;hoverData={x:d.time,y:d.output,xscale:x,yscale:y,format:(t,v)=>`${(t*1e6).toFixed(3)} µs · ${v.toFixed(5)} V`};}
 $('#plot').innerHTML=`<svg class="plot-svg plot-chart" viewBox="0 0 ${W} ${H}" aria-label="${state.plot==='ac'?'真实 Spectre 开环频率响应':'真实 Spectre 闭环阶跃响应'}"><defs><clipPath id="plot-clip"><rect x="${L}" y="${T}" width="${R-L}" height="${B-T}"/></clipPath></defs>${grid}${labels}<g clip-path="url(#plot-clip)">${curves}</g><g class="plot-hover"><line id="plot-crosshair" y1="${T}" y2="${B}" stroke="#bbc9c0" stroke-dasharray="3 3"/><rect id="plot-tooltip-bg" x="52" y="19" width="230" height="21" rx="4" fill="#f3f7f4"/><text id="plot-tooltip" x="61" y="33" style="fill:#6e8c78;font-size:10px"></text><circle id="plot-point" r="3" fill="#598870"/></g></svg>`;$('.plot-chart').addEventListener('pointermove',e=>{const box=e.currentTarget.getBoundingClientRect(),px=(e.clientX-box.left)/box.width*W;let best=0;for(let i=0;i<hoverData.x.length;i++)if(Math.abs(hoverData.xscale(hoverData.x[i])-px)<Math.abs(hoverData.xscale(hoverData.x[best])-px))best=i;const xx=hoverData.xscale(hoverData.x[best]),yy=hoverData.yscale(hoverData.y[best]);$('#plot-crosshair').setAttribute('x1',xx);$('#plot-crosshair').setAttribute('x2',xx);$('#plot-point').setAttribute('cx',xx);$('#plot-point').setAttribute('cy',yy);$('#plot-tooltip').textContent=hoverData.format(hoverData.x[best],hoverData.y[best])})}
async function simulate(){if(!state.circuit?.verified)return toast('该电路尚未配置自动仿真平台',true);const id=state.circuit.id,changes=JSON.parse(JSON.stringify(state.changes));try{const result=await job('simulate',{snapshotId:id,changes});if(state.circuit.id===id){state.simulation=result;if(!state.baseline&&!Object.keys(changes).length)state.baseline=result;state.runs.push(result);renderSimulation();toast('真实 Spectre 仿真完成，结果已保存');if(result.metrics.outputDc<.15||result.metrics.outputDc>1.65)toast('输出静态点接近电源轨，注意当前参数下的偏置状态',true)}}catch(e){toast(e.message,true)}}
function showArtifacts(){if(!state.simulation)return toast('完成一次仿真后可查看实际网表');const r=state.simulation;showInfo('可复查的真实实验',`<p>每一次结果都对应独立的 Spectre 网表和运行日志。参数草稿没有写回原始原理图。</p><p>${esc(r.testbench)}</p><h3>本次结果</h3><pre>${esc(JSON.stringify(r.metrics,null,2))}</pre><p><a target="_blank" rel="noopener" href="/api/runs/${r.runId}/ac/input.scs">开环 AC 网表 ↗</a>　<a target="_blank" rel="noopener" href="/api/runs/${r.runId}/tran/input.scs">闭环阶跃网表 ↗</a></p><p><a target="_blank" rel="noopener" href="/api/runs/${r.runId}/ac/spectre.out">AC 仿真日志 ↗</a>　<a target="_blank" rel="noopener" href="/api/runs/${r.runId}/tran/spectre.out">瞬态仿真日志 ↗</a></p><p>本模型是通用 MOS Level-1 教学模型，适合观察趋势，不代表 SMIC / TSMC 工艺结果。相位裕度是开环传递函数首次下降穿越 0 dB 的估计；多个穿越或不同反馈网络需要更完整的稳定性分析。</p>`)}
$('#library-list').addEventListener('click',e=>{const cell=e.target.closest('[data-cell]');if(cell)return selectCircuit(cell.dataset.lib,cell.dataset.cell);const lib=e.target.closest('[data-library]');if(lib)expandLibrary(lib.dataset.library)});
$('#search').addEventListener('input',renderLibraries);$('#sync').addEventListener('click',sync);$('#refresh-status').addEventListener('click',()=>updateStatus(true));$('#read-again').addEventListener('click',()=>state.circuit&&selectCircuit(state.circuit.lib,state.circuit.cell));$('#simulate').addEventListener('click',simulate);$('#simulate-params').addEventListener('click',simulate);$('#analyze').addEventListener('click',analyze);$$('[data-tab]').forEach(b=>b.addEventListener('click',()=>showTab(b.dataset.tab)));
$('#sections').addEventListener('click',e=>{const c=e.target.closest('[data-section]');if(c)changeSection(c.dataset.section)});$('#sections').addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){const c=e.target.closest('[data-section]');if(c){e.preventDefault();changeSection(c.dataset.section)}}});$('#schematic').addEventListener('click',e=>{if(dragMoved)return;const d=e.target.closest('[data-device]');if(d)selectDevice(d.dataset.device,true,e.ctrlKey||e.metaKey||e.shiftKey)});
$('#schematic').addEventListener('keydown',e=>{const mod=e.ctrlKey||e.metaKey;if(mod&&e.key.toLowerCase()==='a'){e.preventDefault();setSelection(state.circuit?.instances.map(d=>d.name)||[],state.selected);return}if(e.key==='Escape'){e.preventDefault();setSelection([],null,false);return}if(['Enter',' '].includes(e.key)){const d=e.target.closest('[data-device]');if(d){e.preventDefault();selectDevice(d.dataset.device,true,mod||e.shiftKey)}}});
$('#device-select').addEventListener('change',e=>selectDevice(e.target.value,false,false,true));
$('#selected-devices').addEventListener('change',e=>{if(e.target.dataset.selectDevice)selectDevice(e.target.dataset.selectDevice,false,true)});
$('#edit-scope').addEventListener('change',e=>{state.editScope=e.target.value;$('#batch-result').textContent='';renderParameters()});
$('#select-all').addEventListener('click',()=>setSelection(state.circuit?.instances.map(d=>d.name)||[],state.selected));
$('#clear-selection').addEventListener('click',()=>setSelection([],null,false));
$('#undo-edit').addEventListener('click',()=>undoEdit());$('#redo-edit').addEventListener('click',()=>undoEdit(true));
$('#parameter-fields').addEventListener('change',e=>{const key=e.target.dataset.range;if(key)setParam(key,e.target.value)});$('#parameter-fields').addEventListener('click',e=>{const key=e.target.closest('[data-apply-param]')?.dataset.applyParam;if(key)setParam(key,$('#param-'+key).value)});$('#parameter-fields').addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.dataset.param){e.preventDefault();setParam(e.target.dataset.param,e.target.value)}});$('#parameter-fields').addEventListener('input',e=>{const key=e.target.dataset.range;if(key){const input=$('#param-'+key);if(input)input.value=e.target.value}});$('#reset-params').addEventListener('click',()=>{if(Object.keys(state.changes).length)rememberEdit();state.changes={};$('#batch-result').textContent='已还原到 Virtuoso 原始参数，可撤销';renderDraft();toast('已还原到 Virtuoso 原始参数')});$('#try-cc').addEventListener('click',()=>{if(!state.circuit?.instances.some(d=>d.name==='CC'))return toast('当前电路没有名为 CC 的器件');selectDevice('CC');toast('试着将 CC 从 2 pF 增大到 4 pF，再运行仿真。')});$('#history-list').addEventListener('click',e=>{const target=e.target.closest('[data-run]');if(target){activateRun(state.runs.find(r=>r.runId===target.dataset.run))}});$('#plot-ac').addEventListener('click',()=>{state.plot='ac';renderPlot()});$('#plot-tran').addEventListener('click',()=>{state.plot='tran';renderPlot()});$('#artifacts').addEventListener('click',showArtifacts);$('#nav-experiment').addEventListener('click',()=>{showTab('params');$('#simulation-panel').scrollIntoView({behavior:'smooth',block:'center'})});$('#nav-circuits').addEventListener('click',()=>$('#search').focus());$('#chat-form').addEventListener('submit',e=>{e.preventDefault();const m=$('#chat-input').value.trim();if(m)sendChat(m)});$('#chat-input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('#chat-form').requestSubmit()}});$$('[data-question]').forEach(b=>b.addEventListener('click',()=>sendChat(b.dataset.question)));$('#close-dialog').addEventListener('click',()=>$('#info-dialog').close());$('#info-dialog').addEventListener('click',e=>{if(e.target===$('#info-dialog'))$('#info-dialog').close()});
$('#help').addEventListener('click',()=>showInfo('从看懂，到亲手验证。','<p>1. 从左侧同步 Virtuoso 库，选择含 schematic 的单元。</p><p>2. 点击右侧功能模块，高亮它对应的器件。点击 AI 深入讲解，生成基于真实连接的解释。</p><p>3. 点选、Ctrl/⌘/Shift 点选或拖动框选器件，在「调参数」选择 Only current / All selected / All 后修改数值。All 限于同单元同模型；支持整次撤销，原理图连接始终锁定。</p><p>4. 运行真实 Spectre 仿真，比较增益、带宽、相位裕度和闭环阶跃。支持查看实际网表与日志。</p><p>5. 在「问问 AI」中讨论当前电路与实验记录。有依据的新功能结论会自动更新顶部判断和讲解，也可点击「同步本次讨论」；「修订记录」可恢复旧版。最近 40 条消息保存在本机。使用本机已登录的 Codex，可能消耗当前账号用量。</p><p>首版自动仿真支持 CircuitTutorLab / two_stage_opamp。其他单元支持连接回读和 AI 解释；复杂层级电路暂不展开。所有库指当前 Virtuoso 会话和已发现 cds.lib 中可解析的库，并不包含未配置的外部目录。</p>'));
$('#topology-info').addEventListener('click',()=>showInfo('连接有依据，实验可复查。',`<p>图中的器件与端子网络来自 Virtuoso 数据库回读。二级运放的重绘使用经过拓扑哈希校验的布局；其他电路采用带网络标签的通用视图。</p><p>本地 UI 只允许编辑数值，不接受增加器件、修改网络、执行任意 SKILL 或 shell 命令。参数变化用于独立仿真副本。</p><pre>${esc(state.circuit?.topologyHash||'尚未读取')}</pre><p>渲染时的布局可以改变，电气连接保持不变。体端网络请参见器件旁的 VDD / VSS 小标签或「连接表」。</p>`));
$('#view-circuit').addEventListener('click',()=>{$('#connectivity').classList.add('hidden');$('#schematic').classList.remove('hidden');$('#view-circuit').classList.add('active');$('#view-connectivity').classList.remove('active')});$('#view-connectivity').addEventListener('click',()=>{$('#connectivity').classList.remove('hidden');$('#schematic').classList.add('hidden');$('#view-circuit').classList.remove('active');$('#view-connectivity').classList.add('active')});$('#fit').addEventListener('click',()=>{state.zoom=1;state.pan=[0,0];updateTransform()});$('#zoom-in').addEventListener('click',()=>{state.zoom=Math.min(2.5,state.zoom+.15);updateTransform()});$('#zoom-out').addEventListener('click',()=>{state.zoom=Math.max(.55,state.zoom-.15);updateTransform()});$('#schematic').addEventListener('wheel',e=>{e.preventDefault();state.zoom=Math.max(.55,Math.min(2.5,state.zoom-e.deltaY*.001));updateTransform()},{passive:false});let drag=null,dragMoved=false;
function setSelectionTool(tool){state.selectionTool=tool;for(const name of ['select','pan']){$('#tool-'+name).classList.toggle('active',tool===name);$('#tool-'+name).setAttribute('aria-pressed',String(tool===name))}$('#schematic').classList.toggle('pan-tool',tool==='pan')}
$('#tool-select').addEventListener('click',()=>setSelectionTool('select'));$('#tool-pan').addEventListener('click',()=>setSelectionTool('pan'));
function svgPoint(e){const p=$('#schematic').createSVGPoint();p.x=e.clientX;p.y=e.clientY;return p.matrixTransform($('#schematic').getScreenCTM().inverse())}
function boxBetween(a,b){return {x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),width:Math.abs(a.x-b.x),height:Math.abs(a.y-b.y)}}
$('#schematic').addEventListener('pointerdown',e=>{
 if(e.button!==0&&e.button!==1)return;dragMoved=false;
 const pan=state.selectionTool==='pan'||e.button===1;
 if(!pan&&e.target.closest('[data-device]'))return;
 e.preventDefault();const point=svgPoint(e);drag={x:e.clientX,y:e.clientY,start:point,pan:[...state.pan],mode:pan?'pan':'select',add:e.ctrlKey||e.metaKey||e.shiftKey};e.currentTarget.setPointerCapture(e.pointerId);
 if(!pan){const box=document.createElementNS('http://www.w3.org/2000/svg','rect');box.id='selection-marquee';box.classList.add('selection-marquee');$('#schematic').append(box)}
});
$('#schematic').addEventListener('pointermove',e=>{
 if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>4)dragMoved=true;const point=svgPoint(e);
 if(drag.mode==='pan'){state.pan=[drag.pan[0]+point.x-drag.start.x,drag.pan[1]+point.y-drag.start.y];updateTransform()}
 else{const b=boxBetween(drag.start,point),el=$('#selection-marquee');for(const [k,v] of Object.entries(b))el?.setAttribute(k,v)}
});
$('#schematic').addEventListener('pointerup',e=>{
 if(!drag)return;const done=drag;drag=null;$('#selection-marquee')?.remove();
 if(done.mode==='select'){
  if(!dragMoved){if(!done.add)setSelection([],null,false);return}
  const box=boxBetween(done.start,svgPoint(e)),hits=[];
  for(const g of $$('#schematic [data-device]')){const rect=g.querySelector('.device-glow');if(!rect)continue;const b=rect.getBBox();const matrix=$('#schematic').getScreenCTM().inverse().multiply(g.getScreenCTM());const points=[[b.x,b.y],[b.x+b.width,b.y],[b.x,b.y+b.height],[b.x+b.width,b.y+b.height]].map(([x,y])=>{const p=$('#schematic').createSVGPoint();p.x=x;p.y=y;return p.matrixTransform(matrix)});const xs=points.map(p=>p.x),ys=points.map(p=>p.y);const hit={x:Math.min(...xs),y:Math.min(...ys),width:Math.max(...xs)-Math.min(...xs),height:Math.max(...ys)-Math.min(...ys)};if(DeviceEdit.intersects(box,hit))hits.push(g.dataset.device)}
  setSelection(done.add?[...new Set([...state.selectedNames,...hits])]:hits,state.selected,true);
 }
});
$('#schematic').addEventListener('pointercancel',()=>{drag=null;dragMoved=true;$('#selection-marquee')?.remove()});
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('#search').focus()}});
async function boot(){busyButtons();try{const b=await api('/api/bootstrap');state.libraries=b.libraries.libraries||[];if(b.simulation){state.simulation=b.simulation;state.runs=b.runs?.length?b.runs:[b.simulation];state.baseline=b.baseline||(!Object.keys(b.simulation.changes).length?b.simulation:null);if(state.baseline&&!state.runs.some(r=>r.runId===state.baseline.runId))state.runs.unshift(state.baseline)}if(b.circuit){await setCircuit(b.circuit);if(b.simulation?.snapshotId===b.circuit.id)activateRun(b.simulation);}renderLibraries();if(state.expanded){try{rememberCells(state.expanded,await api('/api/cells?lib='+encodeURIComponent(state.expanded)));renderLibraries()}catch{}}updateStatus(true);if(!state.libraries.length)sync()}catch(e){toast(e.message,true);$('#library-list').innerHTML='<div class="error-block">本地服务未准备好。请通过桌面启动器运行应用。</div>'}}
function applyAnalysisUpdate(id,analysis){
 if(!analysis||state.circuit?.id!==id)return false;
 const previous=state.explanation;
 if(previous&&(previous.updatedAt||previous.generatedAt||0)>(analysis.updatedAt||analysis.generatedAt||0))return false;
 state.explanation=analysis;
 if(!sections().some(s=>s.id===state.section))state.section=state.tab==='params'?null:sections()[0]?.id||null;
 renderSections();renderIdentity();applyHighlight();
 const source=analysis.source==='codex-discussion'?'根据讨论更新':analysis.source==='user-restore'?'已恢复历史讲解':'';
 $('#analysis-provenance').textContent=source?(source+' · '+new Date((analysis.updatedAt||analysis.generatedAt)*1000).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Tokyo'})):'';
 $('#analysis-provenance').title=analysis.revisionReason||'';
 return true;
}
async function refreshAnalysis(id){const analysis=await api('/api/explanation/'+id);return applyAnalysisUpdate(id,analysis)}
function reportRevision(result){
 const text={updated:'已同步功能判断与电路讲解 · 可在修订记录中恢复',unchanged:'本次讨论没有产生需要修订的新功能结论',disabled:'已保留对话；自动同步已关闭，可手动同步',superseded:'已显示较新的讲解，本次旧结果没有覆盖它',invalid:'回答已保留，讲解修订未通过校验；可重试同步'}[result.revisionStatus]||'';
 $('#discussion-status').textContent=text;
 $('#discussion-status').title=result.revisionError||result.reason||'';
 if(result.revisionStatus==='updated')toast('功能判断和电路讲解已同步');
 if(result.revisionStatus==='invalid')toast(result.revisionError,true);
}
async function syncDiscussion(){
 const id=state.circuit?.id;if(!id||!state.history.length)return;
 try{const result=await job('revise',{snapshotId:id,expectedVersion:state.explanation?.revisionId});await refreshAnalysis(id);if(state.circuit?.id===id)reportRevision(result)}catch(e){if(state.circuit?.id===id){$('#discussion-status').textContent='同步未完成，原讲解与对话已保留，可重试。';toast(e.message,true)}}
}
async function showAnalysisHistory(){
 const id=state.circuit?.id;if(!id)return;
 try{
  const data=await api('/api/analysis-history/'+id);if(state.circuit?.id!==id)return;
  showInfo('讲解修订记录','<p>每次修订同时保存功能判断与完整讲解。恢复旧版也会留下记录。</p><div class="revision-list">'+(data.revisions.map(r=>'<article class="revision-item"><strong>'+esc(r.title)+'</strong><small>'+esc(new Date(r.updatedAt*1000).toLocaleString('zh-CN',{timeZone:'Asia/Tokyo'}))+(r.active?' · 当前版本':'')+'</small><p>'+esc(r.reason)+'</p>'+(r.active?'':'<button class="button secondary" data-restore-analysis="'+esc(r.revisionId)+'" data-snapshot="'+esc(id)+'" data-expected="'+esc(data.activeRevision)+'">恢复此版</button>')+'</article>').join('')||'<p>尚无修订。讨论得到新结论后，原版与新版都会出现在这里。</p>')+'</div>');
 }catch(e){toast(e.message,true)}
}
$('#sync-discussion').addEventListener('click',syncDiscussion);
$('#analysis-history').addEventListener('click',showAnalysisHistory);
$('#dialog-content').addEventListener('click',async e=>{
 const b=e.target.closest('[data-restore-analysis]');if(!b)return;
 if(state.circuit?.id!==b.dataset.snapshot)return;
 b.disabled=true;
 try{const result=await job('restore-analysis',{snapshotId:b.dataset.snapshot,revisionId:b.dataset.restoreAnalysis,expectedVersion:b.dataset.expected});await refreshAnalysis(b.dataset.snapshot);if(state.circuit?.id===b.dataset.snapshot){$('#info-dialog').close();reportRevision(result)}}catch(err){toast(err.message,true)}finally{b.disabled=false}
});
try{$('#auto-sync').checked=localStorage.getItem('circuit-auto-sync')!=='off'}catch{}
$('#auto-sync').addEventListener('change',()=>{try{localStorage.setItem('circuit-auto-sync',$('#auto-sync').checked?'on':'off')}catch{}$('#discussion-status').textContent=$('#auto-sync').checked?'新的电路结论将自动同步。':'自动同步已关闭，仍可点击「同步本次讨论」。'});
let analysisPolling=false;
setInterval(async()=>{if(analysisPolling||document.hidden||!state.circuit)return;analysisPolling=true;const id=state.circuit.id;try{const e=await api('/api/explanation/'+id);const key=a=>a?.revisionId||a?.generatedAt;if(key(e)!==key(state.explanation))applyAnalysisUpdate(id,e)}catch{}finally{analysisPolling=false}},3000);
boot();

function activateRun(run){if(!run)return;state.section=null;state.simulation=run;state.changes=JSON.parse(JSON.stringify(run.changes||{}));state.editUndo=[];state.editRedo=[];state.selected=Object.keys(state.changes)[0]||state.selected;state.selectedNames=new Set(state.selected?[state.selected]:[]);$('#batch-result').textContent='已恢复本次实验的参数草稿';renderParameters();renderSchematic();renderSimulation();busyButtons();}

function rememberCells(lib,data){state.cells[lib]=data.cells;state.cellFormats[lib]=data.formats||{}}
function renderIdentity(){
 const data=state.circuit,identity=state.explanation?.identity;
 const box=$('#circuit-identity');box.classList.remove('identity-error');
 if(identity){
  const guess=identity.status==='hypothesis';
  $('#identity-title').textContent=(guess?'推测：':'')+identity.label.replace(/^推测[：:]\s*/,'').replace(/[（(]推测[）)]$/,'');
  $('#identity-confidence').textContent=identity.status==='unknown'?'证据不足':guess?'功能推测':({high:'较高置信度',medium:'中等置信度',low:'低置信度'}[identity.confidence]);
  $('#identity-confidence').className='identity-badge '+(guess?'hypothesis':identity.status==='unknown'?'unknown':'identified');
  $('#identity-reason').textContent=identity.reason;
  box.title=[...(identity.evidence||[]),...(identity.limitations||[])].join('\n');
 }else{
  $('#identity-title').textContent=data?.teaching?'二级 CMOS 运算放大器':data?'正在识别电路功能…':'选择一个原理图';
  $('#identity-confidence').textContent=data?.teaching?'拓扑已校验':'分析中';
  $('#identity-confidence').className='identity-badge '+(data?.teaching?'identified':'pending');
  $('#identity-reason').textContent=data?.teaching?'输入差分级、镜像负载、第二级与米勒补偿。':'依据实际端子连接判断；证据不足时会明确标注推测。';
 }
}
function identityError(message){$('#identity-title').textContent='功能识别暂未完成';$('#identity-confidence').textContent='可重试';$('#identity-confidence').className='identity-badge unknown';$('#identity-reason').textContent=message+' 点击「AI 深入讲解」重试。';$('#explanation-source').textContent='AI 分析未完成';$('#circuit-identity').classList.add('identity-error')}
async function autoIdentify(id){
 try{
  while(state.busy.has('identify')||state.busy.has('analyze')){await new Promise(r=>setTimeout(r,600));if(state.circuit?.id!==id)return}
  if(state.circuit?.id!==id)return;
  const result=await job('identify',{snapshotId:id},true);
  if(state.circuit?.id===id)await refreshAnalysis(id)
 }catch(e){if(state.circuit?.id===id)identityError(e.message)}
}

document.querySelector('#identity-evidence').addEventListener('click',()=>{const i=state.explanation?.identity;if(!i)return toast('功能分析完成后可查看依据');const evidence=Array.isArray(i.evidence)?i.evidence:[];const limits=Array.isArray(i.limitations)?i.limitations:[];showInfo(i.label,'<p>'+esc(i.reason)+'</p><h3>连接依据</h3><p>'+evidence.map(esc).join('<br>')+'</p><h3>判断边界</h3><p>'+limits.map(esc).join('<br>')+'</p>')});
