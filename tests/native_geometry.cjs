const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const geo=require('../web/native-scene.js');
assert.deepEqual(geo.transform([2,3],[[10,20],[9,20],[10,21]]),[8,23]);
assert.deepEqual(geo.transform([2,3],[[0,0],[0,1],[-1,0]]),[-3,2]);
assert.deepEqual(geo.project([2,3],[[[1,0],[2,0],[1,1]],[[0,4],[1,4],[0,5]]]),[3,7]);
let count=0;
const dir=path.resolve(__dirname,'../runtime/circuits');
if(fs.existsSync(dir))for(const name of fs.readdirSync(dir)){
 const circuit=JSON.parse(fs.readFileSync(path.join(dir,name),'utf8'));
 if(circuit.lib!=='BJT_test'||!circuit.scene)continue;
 const {html,diagnostics}=geo.renderer(circuit,d=>d.cell);
 assert.equal((html.match(/class="device-group native-device"/g)||[]).length,circuit.instances.length);
 assert(!html.includes('NaN'));assert(!html.includes('Infinity'));assert.equal(diagnostics.length,0);
 assert(html.includes('native-wire'));assert(html.includes('native-symbol'));count++;
}
console.log(JSON.stringify({passed:true,transformTests:3,livePDKScenes:count}));
