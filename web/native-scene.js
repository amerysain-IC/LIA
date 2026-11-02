/* Native symbol geometry is authoritative. No synthetic connection routing. */
(function(root){
'use strict';
const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite=v=>Number.isFinite(Number(v));
const point=p=>Array.isArray(p)&&p.length===2&&p.every(finite);
const identity=[[0,0],[1,0],[0,1]];
function transform(p,t=identity){const [o,u,v]=t;return [o[0]+p[0]*(u[0]-o[0])+p[1]*(v[0]-o[0]),o[1]+p[0]*(u[1]-o[1])+p[1]*(v[1]-o[1])];}
function project(p,chain){for(const t of chain)p=transform(p,t);return p;}
function renderer(circuit,describe){
 const scene=circuit.scene;if(!scene?.bbox)return {html:'',diagnostics:['没有源几何数据']};
 const b=scene.bbox;if(!point(b[0])||!point(b[1]))throw new Error('源原理图边界无效');
 const dx=Math.max(b[1][0]-b[0][0],.1),dy=Math.max(b[1][1]-b[0][1],.1),scale=Math.min(910/dx,490/dy);
 const cx=(b[0][0]+b[1][0])/2,cy=(b[0][1]+b[1][1])/2;
 const screen=p=>[520+(p[0]-cx)*scale,320-(p[1]-cy)*scale];
 const coords=(p,chain)=>screen(project(p,chain));
 const path=(points,chain,close=false)=>points.filter(point).map((p,i)=>(i?'L':'M')+coords(p,chain).map(n=>n.toFixed(3)).join(',')).join(' ')+(close?' Z':'');
 const errors=new Set();
 function draw(s,chain=[],symbol=false){
  if(['instance','annotate'].includes(s.layer)||s.purpose==='pin')return '';
  const typ=s.type,style=symbol?'native-symbol':'native-wire';let content='';
  if(['line','path','polygon'].includes(typ)&&s.points?.length){content=`<path class="${style}" d="${path(s.points,chain,typ==='polygon')}"${typ==='polygon'?' fill="currentColor"':''}/>`;}
  else if(typ==='rect'&&s.bbox){const [lo,hi]=s.bbox;content=`<path class="${style}" d="${path([lo,[hi[0],lo[1]],hi,[lo[0],hi[1]]],chain,true)}"/>`;}
  else if(['ellipse','arc'].includes(typ)&&s.bbox){
   const box=typ==='arc'&&s.ellipseBBox?s.ellipseBBox:s.bbox;
   const center=[(box[0][0]+box[1][0])/2,(box[0][1]+box[1][1])/2],rx=(box[1][0]-box[0][0])/2,ry=(box[1][1]-box[0][1])/2;
   const start=typ==='arc'?Number(s.startAngle):0,end=typ==='arc'?Number(s.stopAngle):Math.PI*2;
   if(!Number.isFinite(start)||!Number.isFinite(end)){errors.add('缺少圆弧角度');return '';}
   const span=end>=start?end-start:end-start+Math.PI*2,points=[];
   for(let n=0;n<=36;n++){const a=start+span*n/36;points.push([center[0]+rx*Math.cos(a),center[1]+ry*Math.sin(a)]);}
   content=`<path class="${style}" d="${path(points,chain)}"/>`;
  }else if(typ==='label'&&s.text&&s.xy){
   if(s.labelType==='ILLabel'||/cds(?:Param|Name|Term)|\[@|ilInst/i.test(s.text))return '';
   const text=String(s.text).slice(0,350),p=coords(s.xy,chain),font=Math.min(17,Math.max(symbol?7.5:9,Number(s.height||.1)*scale*.9));
   let anchor=String(s.justify).includes('Right')?'end':String(s.justify).includes('Center')?'middle':'start';
   const direction=String(s.orient||'R0');let rotation=direction==='R90'?-90:direction==='R270'?90:0;
   content=`<text class="native-label ${symbol?'native-terminal':''}" x="${p[0]}" y="${p[1]}" text-anchor="${anchor}" font-size="${font}"${rotation?` transform="rotate(${rotation} ${p.join(' ')})"`:''}>${escape(text)}</text>`;
  }else if(!['textDisplay','label'].includes(typ))errors.add(typ);
  return content;
 }
 function master(m,chain){if(!m)return '';return m.shapes.map(s=>draw(s,chain,true)).join('')+(m.children||[]).map(child=>master(child.master,[child.transform,...chain])).join('');}
 const devices=new Map(circuit.instances.map(d=>[d.name,d]));
 let html=scene.shapes.map(s=>draw(s)).join('');
 for(const i of scene.instances){const d=devices.get(i.name);let glyph=master(i.master,[i.transform]);
  if(!d){html+=`<g class="native-pin">${glyph}</g>`;continue;}
  const bb=i.bbox||i.master?.bbox;if(!bb)continue;
  const lo=screen(bb[0]),hi=screen(bb[1]),x=Math.min(lo[0],hi[0]),y=Math.min(lo[1],hi[1]),w=Math.max(hi[0]-lo[0],lo[0]-hi[0]),h=Math.max(hi[1]-lo[1],lo[1]-hi[1]);
  if(!i.master)glyph=`<rect class="native-missing" x="${x}" y="${y}" width="${Math.max(w,18)}" height="${Math.max(h,18)}"/>`;
  // Name and parameter annotations use actual readback values, not IL expressions.
  const labelX=x+w+4,labelY=y+Math.min(h/2,12),value=describe?describe(d):d.cell;
  html+=`<g class="device-group native-device" data-device="${escape(d.name)}" tabindex="0" role="button" aria-label="${escape(d.name+' '+d.cell)}"><title>${escape(d.name+' · '+d.lib+'/'+d.cell+' · '+value)}</title><rect class="device-glow" x="${x-5}" y="${y-5}" width="${Math.max(w+10,18)}" height="${Math.max(h+10,18)}" rx="4"/>${glyph}<text class="native-name" x="${labelX}" y="${labelY}">${escape(d.name)}</text><text class="native-value" x="${labelX}" y="${labelY+11}">${escape(value)}</text></g>`;
 }
 return {html,diagnostics:[...errors],scale};
}
const api={transform,project,renderer};
if(typeof module!=='undefined')module.exports=api;else root.CircuitGeometry=api;
})(typeof window!=='undefined'?window:globalThis);
