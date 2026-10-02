const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {solve}=require('../docs/solver.js'),parser=require('../docs/parser.js');
if(process.argv.includes('--cases')){
const output=JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(c=>solve(c.pads,c.holes)));
process.stdout.write(output,error=>{if(error){console.error(error);process.exitCode=1;}});
}else{
const sample=n=>fs.readFileSync(path.join(__dirname,'../docs/samples',n),'ascii');
const pads=parser.copper(sample('copper.gbr')),drill=parser.drill(sample('drill-offset.drl')),report=solve(pads,drill.holes);
assert.equal(report.status,'recovered');assert.deepEqual(report.translation_mm,[-5,-7]);assert.equal(report.matches.length,7);
const copy=parser.corrected(drill,report.translation_mm),after=parser.drill(copy);assert.equal(after.holes.length,8);after.holes.forEach((h,i)=>{assert.equal(h.diameter,drill.holes[i].diameter);assert.ok(Math.abs(h.x-drill.holes[i].x+5)<1e-8);assert.ok(Math.abs(h.y-drill.holes[i].y+7)<1e-8);});
assert.equal(solve(pads,parser.drill(sample('aligned-drill.drl')).holes).status,'already_aligned');
assert.equal(solve(parser.copper(sample('ambiguous-copper.gbr')),parser.drill(sample('ambiguous-drill.drl')).holes).status,'review_required');
assert.throws(()=>parser.drill(sample('missing-units.drl')));assert.throws(()=>parser.drill(sample('slots.drl')));assert.throws(()=>parser.copper(sample('copper.gbr').replace('%LPD*%','%LPC*%')));
assert.ok(!copy.includes('\r'));console.log('Browser core checks passed: actual samples, corrected reparse, ambiguity, already aligned, missing units, slots and polarity.');

/* Exercise UI state transitions without replacing the parser or solver. */
async function testInputLabels(){
const vm=require('node:vm'),nodes=new Map(),noop=()=>{};
const context2d=new Proxy({}, {get:(target,key)=>target[key]||noop,set:(target,key,value)=>(target[key]=value,true)});
function node(id){if(!nodes.has(id)){const n={files:[],textContent:'',hidden:false,disabled:false,clientWidth:600,clientHeight:410,classList:{toggle:noop},append:noop,replaceChildren:noop,click:noop,getContext:()=>context2d};let value='';Object.defineProperty(n,'value',{get:()=>value,set:v=>{value=v;if((id==='copper-file'||id==='drill-file')&&v==='')n.files=[];}});nodes.set(id,n);}return nodes.get(id);}
node('minimum').value='4';node('coverage').value='0.8';node('tolerance').value='0.02';
const sandbox={console,TextEncoder,TextDecoder,crypto:require('node:crypto').webcrypto,DrillSolver:{solve},DrillParser:parser,devicePixelRatio:1,document:{getElementById:node,createElement:()=>({append:noop,remove:noop}),body:{append:noop}},window:{addEventListener:noop},setTimeout,fetch:async url=>{const data=Buffer.from(sample(url.split('/').pop()));return{ok:true,arrayBuffer:async()=>data.buffer.slice(data.byteOffset,data.byteOffset+data.byteLength)};}};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(__dirname,'../docs/app.js'),'utf8'),sandbox);
function file(name){const data=Buffer.from(sample(name));return{name,size:data.length,arrayBuffer:async()=>data.buffer.slice(data.byteOffset,data.byteOffset+data.byteLength)};}
node('copper-file').files=[file('copper.gbr')];node('drill-file').files=[file('missing-units.drl')];
await vm.runInContext('files()',sandbox);assert.match(node('outcome').textContent,/invalid/);assert.equal(node('drill-name').textContent,'missing-units.drl');
await vm.runInContext('sample()',sandbox);assert.equal(node('copper-name').textContent,'Sample: copper.gbr');assert.equal(node('drill-name').textContent,'Sample: drill-offset.drl');assert.equal(node('drill-file').files.length,0);assert.match(node('outcome').textContent,/recovered/);
await vm.runInContext('files()',sandbox);assert.match(node('status').textContent,/Choose the copper layer and drill file first/);
await vm.runInContext('sample(true)',sandbox);assert.equal(node('copper-name').textContent,'Sample: ambiguous-copper.gbr');assert.equal(node('drill-name').textContent,'Sample: ambiguous-drill.drl');assert.match(node('outcome').textContent,/review/);
node('copper-file').files=[file('copper.gbr')];node('drill-file').files=[file('aligned-drill.drl')];await vm.runInContext('files()',sandbox);assert.equal(node('drill-name').textContent,'aligned-drill.drl');assert.equal(node('copper-name').textContent,'copper.gbr');assert.match(node('outcome').textContent,/Already aligned/);
console.log('Browser UI state checks passed: invalid local input, actual sample labels, cleared selectors, repeated grid labels, and subsequent local input labels.');
}
testInputLabels().catch(error=>{console.error(error);process.exitCode=1;});
}
