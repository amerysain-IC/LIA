const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const geometry=require('../web/native-scene.js');
const fixture=path.resolve(__dirname,'../cases/image_001/readback.json');
if(!fs.existsSync(fixture)){console.log('SKIP: private native CAD readback fixture is not distributed. Run build_image_case.py with licensed Virtuoso to regenerate.');process.exit(0)}
const data=JSON.parse(fs.readFileSync(fixture,'utf8'));
const rendered=geometry.renderer(data,d=>d.cell);
const expected=data.scene.shapes.filter(s=>s.layer==='wire'&&['line','path','ellipse','arc','rect','polygon'].includes(s.type)).length;
assert.equal((rendered.html.match(/class="native-wire"/g)||[]).length,expected);
assert.equal((rendered.html.match(/class="device-group native-device"/g)||[]).length,52);
assert(expected>200,'Full connecting wires and junctions must be present');
assert.equal(rendered.diagnostics.length,0);
assert(!/NaN|Infinity/.test(rendered.html));
console.log(JSON.stringify({passed:true,devices:52,visibleWireAndJunctionShapes:expected}));
