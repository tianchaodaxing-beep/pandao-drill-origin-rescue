/* Conservative translation solver. Algorithm crosschecked against the Python CLI. */
(function(g){'use strict';
const fail=m=>{throw new Error(m)}, compatible=(h,p)=>{const s=Math.min(p.width,p.height);return h.diameter+.1<=s+1e-9&&s<=h.diameter*3&&Math.max(p.width,p.height)/s<=2};
function solve(pads,holes,minimum=4,coverage=.8,tolerance=.02){
if(!Number.isInteger(minimum)||minimum<3||coverage<.5||coverage>1||tolerance<.000001||tolerance>.1)fail('Use minimum matches >=3, coverage 0.5..1, tolerance 0.000001..0.1 mm.');
if(pads.length>4000||holes.length>2000)fail('Limit exceeded: 4000 flash pads and 2000 round drill hits.');
for(const p of [...pads,...holes])if(!['x','y'].every(k=>Number.isFinite(p[k])&&Math.abs(p[k])<=1000000))fail('Invalid or out-of-range coordinates.');
for(const p of pads)if(!['width','height'].every(k=>Number.isFinite(p[k])&&p[k]>0&&p[k]<=1000))fail('Invalid pad dimensions.');
for(const h of holes)if(!Number.isFinite(h.diameter)||h.diameter<=0||h.diameter>1000)fail('Invalid hole diameter.');
if(new Set(holes.map(h=>JSON.stringify([h.x,h.y]))).size!==holes.length)fail('Duplicate drill hit coordinates require manual review.');
const base={format:'drill-origin-rescue-report/1',status:'review_required',translation_mm:null,pad_count:pads.length,hole_count:holes.length,matches:[],unmatched_holes:holes.map((_,i)=>i),thresholds:{minimum_matches:minimum,minimum_coverage:coverage,maximum_residual_mm:tolerance},notice:'Review draft. Verify all fabrication layers and original fabrication requirements before use.'};
const review=reason=>({...base,reason});
if(holes.length<minimum)return review('Not enough drill hits for the required evidence.');
if(pads.length*holes.length>300000)return review('Candidate pair limit exceeded (300000). Analyze a smaller exported layer or review manually.');
const bins=new Map(),key=(x,y)=>x+','+y,q=tolerance;
for(const h of holes)for(const p of pads)if(compatible(h,p)){
const dx=p.x-h.x,dy=p.y-h.y,k=key(Math.floor(dx/q+.5),Math.floor(dy/q+.5)),v=bins.get(k)||[0,0,0];v[0]++;v[1]+=dx;v[2]+=dy;bins.set(k,v);
if(bins.size>300000)return review('Offset-bin limit exceeded; the geometry does not give a bounded reliable match.');}
const candidates=[],requiredVotes=Math.max(minimum,Math.ceil(coverage*holes.length)-Math.max(1,Math.ceil(holes.length*.1)));
for(const [x,y] of [...bins.keys()].map(k=>k.split(',').map(Number)).sort((a,b)=>a[0]-b[0]||a[1]-b[1])){
let n=0,sx=0,sy=0;for(const a of [-1,0,1])for(const b of [-1,0,1]){const v=bins.get(key(x+a,y+b))||[0,0,0];n+=v[0];sx+=v[1];sy+=v[2];}
if(n>=requiredVotes)candidates.push([sx/n,sy/n]);}
if(candidates.length>500)return review('More than 500 supported offset candidates; repeated geometry requires manual review.');
const grid=new Map(),cell=tolerance*2;
pads.forEach((p,i)=>{const k=key(Math.floor(p.x/cell),Math.floor(p.y/cell));grid.set(k,[...(grid.get(k)||[]),i]);});
function evaluate(dx,dy,radius){const edges=[],incoming=new Map();holes.forEach((h,i)=>{const x=h.x+dx,y=h.y+dy,cx=Math.floor(x/cell),cy=Math.floor(y/cell),neighbors=[];
for(const a of [-1,0,1])for(const b of [-1,0,1])for(const pi of grid.get(key(cx+a,cy+b))||[]){const p=pads[pi];if(compatible(h,p)&&Math.hypot(p.x-x,p.y-y)<=radius+1e-12){neighbors.push(pi);incoming.set(pi,(incoming.get(pi)||0)+1);}}
edges[i]=neighbors;});return edges.flatMap((v,i)=>v.length===1&&incoming.get(v[0])===1?[[i,v[0]]]:[]);}
const solutions=new Map();
for(let [dx,dy] of candidates){let pairs=evaluate(dx,dy,tolerance*2);if(pairs.length<minimum)continue;
dx=pairs.reduce((s,[h,p])=>s+pads[p].x-holes[h].x,0)/pairs.length;dy=pairs.reduce((s,[h,p])=>s+pads[p].y-holes[h].y,0)/pairs.length;pairs=evaluate(dx,dy,tolerance);if(pairs.length<minimum)continue;
solutions.set(JSON.stringify(pairs),{dx,dy,coverage:pairs.length/holes.length,matches:pairs.map(([h,p])=>({hole_index:h,pad_index:p,residual_mm:Math.hypot(holes[h].x+dx-pads[p].x,holes[h].y+dy-pads[p].y)}))});}
const ranked=[...solutions.values()].sort((a,b)=>b.matches.length-a.matches.length||a.dx-b.dx||a.dy-b.dy);
if(!ranked.length||ranked[0].coverage+1e-12<coverage)return review('No translation satisfies the minimum unique matches and coverage.');
const winner=ranked[0],near=winner.matches.length-Math.max(1,Math.ceil(holes.length*.1)),rivals=ranked.slice(1).filter(s=>s.matches.length>=Math.max(minimum,near));
if(rivals.length)return {...base,reason:'Competing translations fit this repeated or symmetrical geometry. No corrected file was created.',competing_offsets_mm:[winner,...rivals].map(s=>[s.dx,s.dy])};
const matched=new Set(winner.matches.map(r=>r.hole_index));return {...base,status:Math.hypot(winner.dx,winner.dy)<=tolerance?'already_aligned':'recovered',reason:'One distinct translation satisfies the evidence thresholds. Inspect the overlay and unmatched holes.',translation_mm:[winner.dx,winner.dy],matches:winner.matches,match_coverage:winner.coverage,maximum_residual_mm:Math.max(...winner.matches.map(r=>r.residual_mm)),unmatched_holes:holes.map((_,i)=>i).filter(i=>!matched.has(i))};
}
g.DrillSolver={solve};if(typeof module!=='undefined')module.exports=g.DrillSolver;
})(globalThis);
