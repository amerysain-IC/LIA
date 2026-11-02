/* Selection and atomic parameter drafts. No topology or source writes. */
(function(root){
'use strict';
const ranges={w:[.1e-6,2000e-6],l:[.1e-6,100e-6],c:[1e-15,1e-6],r:[.1,1e12],idc:[1e-9,.01]};
const clone=v=>JSON.parse(JSON.stringify(v));
function numeric(value){
 const m=String(value??'').trim().replace(/[µμ]/g,'u').match(/^([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)(meg|[TGMkKmunpf]?)$/);
 return m?Number(m[1])*({'':1,T:1e12,G:1e9,M:1e6,meg:1e6,k:1e3,K:1e3,m:1e-3,u:1e-6,n:1e-9,p:1e-12,f:1e-15}[m[2]]):NaN;
}
function family(d){return ['nmos','pmos','mos'].includes(d?.kind)?'mos':d?.kind}
function sameMaster(a,b){return a.lib===b.lib&&a.cell===b.cell&&a.kind===b.kind&&(a.params?.model||'')===(b.params?.model||'')}
function plan(instances,currentName,selected,scope,key){
 if(!['current','selected','all'].includes(scope))throw new Error('请选择有效的应用范围');
 const current=instances.find(d=>d.name===currentName);
 if(!current)return {targets:[],skipped:[]};
 const set=new Set(selected),candidates=scope==='current'?[current]:scope==='selected'?instances.filter(d=>set.has(d.name)):instances.filter(d=>sameMaster(d,current));
 const compatible=d=>family(d)===family(current)&&(d.editable||[]).includes(key)&&Number.isFinite(numeric(d.params?.[key]));
 return {targets:candidates.filter(compatible).map(d=>d.name),skipped:candidates.filter(d=>!compatible(d)).map(d=>d.name)};
}
function apply(instances,changes,current,selected,scope,key,value){
 const range=ranges[key],n=numeric(value);
 if(!range||!Number.isFinite(n)||n<range[0]||n>range[1])throw new Error('参数超出允许范围'+(range?' ['+range.join(', ')+']（基本单位）':''));
 const p=plan(instances,current,selected,scope,key);
 if(!p.targets.length)throw new Error('当前范围没有可编辑此参数的器件');
 const next=clone(changes),byName=new Map(instances.map(d=>[d.name,d]));
 for(const name of p.targets){
  const original=numeric(byName.get(name).params[key]);
  if(Math.abs(n-original)<=1e-10*Math.max(Math.abs(original),Math.abs(n),1e-30)){
   if(next[name]){delete next[name][key];if(!Object.keys(next[name]).length)delete next[name]}
  }else{(next[name]??={})[key]=String(value)}
 }
 if(Object.keys(next).length>200)throw new Error('当前草稿最多支持修改 200 个器件；本次修改未应用');
 return {...p,changes:next,changed:JSON.stringify(changes)!==JSON.stringify(next)};
}
// Uses SVG-local hit rectangles, so selection also works after zoom/pan.
function intersects(a,b){return a.x<=b.x+b.width&&a.x+a.width>=b.x&&a.y<=b.y+b.height&&a.y+a.height>=b.y}
function toggle(selected,name){const next=new Set(selected);next.has(name)?next.delete(name):next.add(name);return [...next]}
const api={ranges,numeric,family,sameMaster,plan,apply,intersects,toggle};
if(typeof module!=='undefined')module.exports=api;else root.DeviceEdit=api;
})(typeof window!=='undefined'?window:globalThis);
