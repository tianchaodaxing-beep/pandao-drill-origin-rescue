/* Strict browser profile: solid dark flashes and absolute decimal round drilling. */
(function(g){'use strict';const fail=m=>{throw new Error(m)};
function copper(text){
if(text.length>5*1024*1024||/[^\x00-\x7f]/.test(text))fail('Use ASCII files within the 5 MiB limit.');
const tokens=text.trim().match(/%[^%]*%|[^%]*?\*/g)||[];if(tokens.join('').replace(/\s/g,'')!==text.replace(/\s/g,''))fail('Unsupported or incomplete Gerber syntax.');
let format=null,unit=null,aperture=null,ended=false;const apertures=new Map(),pads=[];
for(let token of tokens){token=token.trim();if(ended)fail('Unexpected data after M02.');if(/^G04[^*]*\*$/.test(token))continue;
let m;if((m=token.match(/^%FSLAX([2-6])([2-6])Y([2-6])([2-6])\*%$/))){if(format||m[1]!==m[3]||m[2]!==m[4])fail('Gerber requires one consistent absolute leading-zero format.');format=+m[2];}
else if((m=token.match(/^%MO(MM|IN)\*%$/))){if(unit)fail('Duplicate unit declarations.');unit=m[1]==='MM'?1:25.4;}
else if((m=token.match(/^%ADD(\d+)(C|R|O),([\d.]+)(?:X([\d.]+))?\*%$/))){if(!unit||apertures.has(m[1])||(m[2]!=='C'&&!m[4])||(m[2]==='C'&&m[4]))fail('Unsupported or duplicate aperture.');apertures.set(m[1],{shape:{C:'circle',R:'rectangle',O:'obround'}[m[2]],width:+m[3]*unit,height:+(m[4]||m[3])*unit});}
else if(token==='%LPD*%'){}
else if((m=token.match(/^D(\d+)\*$/))){if(!apertures.has(m[1]))fail('Unknown aperture selection.');aperture=apertures.get(m[1]);}
else if((m=token.match(/^X([+-]?\d+)Y([+-]?\d+)D0?([23])\*$/))){if(!format||!unit||!aperture)fail('Coordinates require declared units, format and aperture.');if(m[3]==='3')pads.push({x:+m[1]*unit/10**format,y:+m[2]*unit/10**format,...aperture});}
else if(token==='M02*')ended=true;
else fail('Browser Gerber profile supports only explicit dark C/R/O flashes and full absolute XY coordinates. Use the CLI for other supported exports.');
}
if(!format||!unit||!ended||!pads.length)fail('Missing Gerber format, units, flashes or M02.');return pads;}
function drill(text){
if(text.length>5*1024*1024||/[^\x00-\x7f]/.test(text))fail('Use ASCII files within the 5 MiB limit.');
let unit=null,header=false,body=false,ended=false,tool=null;const tools=new Map(),holes=[],lines=text.replace(/\r\n?/g,'\n').split('\n');
for(let i=0;i<lines.length;i++){const raw=lines[i],line=raw.split(';')[0].trim();if(!line)continue;if(ended)fail('Unexpected data after M30.');let m;
if(line==='M48'){if(header)fail('Duplicate M48.');header=true;}
else if((m=line.match(/^(METRIC|INCH)(?:,[LT]Z)?$/))){if(!header||body||unit)fail('One unit declaration is required in the header.');unit=m[1]==='METRIC'?1:25.4;}
else if((m=line.match(/^T(\d+)C(\d+\.\d+)$/))){if(!unit)fail('Declare METRIC or INCH before defining drill tools.');if(!header||body||tools.has(m[1]))fail('Unsupported or duplicate tool definition.');tools.set(m[1],+m[2]*unit);}
else if(line==='G90'||line==='G05'){}
else if(line==='%'){if(!header||body||!unit)fail('Missing/duplicate header terminator or units.');body=true;}
else if((m=line.match(/^T(\d+)$/))){if(!body||!tools.has(m[1]))fail('Unknown drill tool.');tool=tools.get(m[1]);}
else if((m=line.match(/^X([+-]?\d+\.\d+)Y([+-]?\d+\.\d+)$/))){if(!body||!tool)fail('Coordinates require a selected drill tool.');holes.push({x:+m[1]*unit,y:+m[2]*unit,diameter:tool,line_index:i});}
else if(line==='M30')ended=true;
else fail('Browser drill profile requires absolute decimal XY round hits. Slots, routes, repeats and integer coordinates are refused.');
}
if(!header||!body||!unit||!ended||!holes.length)fail('Excellon requires declared units, M48, %, M30 and round drill hits.');return {holes,unit,lines};}
function corrected(parsed,offset){const lines=[...parsed.lines];for(const h of parsed.holes)lines[h.line_index]='X'+((h.x+offset[0])/parsed.unit).toFixed(9)+'Y'+((h.y+offset[1])/parsed.unit).toFixed(9);const result=lines.join('\n').replace(/\n*$/,'\n'),check=drill(result);if(check.holes.length!==parsed.holes.length||check.holes.some((h,i)=>Math.abs(h.diameter-parsed.holes[i].diameter)>1e-9||Math.abs(h.x-parsed.holes[i].x-offset[0])>1e-6||Math.abs(h.y-parsed.holes[i].y-offset[1])>1e-6))fail('Corrected file reparse failed.');return result;}
g.DrillParser={copper,drill,corrected};if(typeof module!=='undefined')module.exports=g.DrillParser;
})(globalThis);
