import hashlib
import io
import json
import math
from pathlib import Path
import random
import shutil
import subprocess
import zipfile
import pytest
from gerbonara import ExcellonFile
from gerbonara.utils import MM
from generate_samples import generate, gerber, drill, POINTS
from drill_origin_rescue.cli import run, main
from drill_origin_rescue.parser import load
from drill_origin_rescue.solver import solve, InputError


@pytest.fixture
def samples(tmp_path):
    generate(tmp_path)
    return tmp_path


@pytest.mark.parametrize('name,status',[('drill-offset.drl','recovered'),('aligned-drill.drl','already_aligned'),('ambiguous-drill.drl','review_required'),('missing-units.drl','invalid'),('slots.drl','invalid')])
def test_actual_fixtures(samples,name,status):
    copper='ambiguous-copper.gbr' if 'ambiguous' in name else 'copper.gbr'
    before={p:p.read_bytes() for p in samples.iterdir() if p.is_file()}
    result=run(samples/copper,samples/name,samples/'review')
    assert result['status']==status
    assert (samples/'review'/'corrected-copy.drl').exists()==(status=='recovered')
    assert before=={p:p.read_bytes() for p in before}
    if status=='recovered':
        assert result['translation_mm']==pytest.approx([-5,-7])
        assert len(result['matches'])==7 and result['unmatched_holes']==[7]
        output=ExcellonFile.open(samples/'review'/'corrected-copy.drl')
        original=ExcellonFile.open(samples/name)
        assert len(output.objects)==len(original.objects)==8
        for old,new in zip(original.objects,output.objects):
            assert new.tool.diameter==old.tool.diameter
            assert new.x==pytest.approx(old.x-5) and new.y==pytest.approx(old.y-7)
        assert result['inputs']['drill']['sha256']==hashlib.sha256((samples/name).read_bytes()).hexdigest()


@pytest.mark.parametrize('inch',[False,True])
def test_explicit_decimal_units_and_benign_g90_warning(samples,inch):
    text=drill(POINTS,5,7).replace('G90\n%','%\nG90')
    if inch:
        text=text.replace('METRIC','INCH').replace('C0.800','C0.031496062992').replace('C1.500','C0.059055118110')
        import re
        text=re.sub(r'([XY])([+-]?\d+\.\d+)',lambda m:m[1]+f'{float(m[2])/25.4:.12f}',text)
    (samples/'decimal.drl').write_text(text,encoding='ascii',newline='\n')
    result=run(samples/'copper.gbr',samples/'decimal.drl',samples/'review')
    assert result['status']=='recovered' and result['translation_mm']==pytest.approx([-5,-7],abs=1e-8)
    assert 'METRIC' in (samples/'review'/'corrected-copy.drl').read_text() if not inch else 'INCH' in (samples/'review'/'corrected-copy.drl').read_text()


@pytest.mark.parametrize('change',['no_format','clear','repeat','macro','feed','duplicate_hit','bad_tool','mixed_units'])
def test_unsafe_or_unsupported_exports(samples,change):
    copper=(samples/'copper.gbr').read_text();holes=(samples/'drill-offset.drl').read_text()
    if change=='no_format': copper=copper.replace('%FSLAX36Y36*%','')
    if change=='clear': copper=copper.replace('%LPD*%','%LPC*%')
    if change=='repeat': copper=copper.replace('%LPD*%','%SRX2Y2I1J1*%')
    if change=='macro': copper=copper.replace('%LPD*%','%AMBAD*1,1,1,0,0*%')
    if change=='feed': holes=holes.replace('T01C0.800','T01C0.800F100S500')
    if change=='duplicate_hit': holes=holes.replace('M30','X7.000000Y10.000000\nM30')
    if change=='bad_tool': holes=holes.replace('\nT01\n','\nT99\n')
    if change=='mixed_units': holes=holes.replace('METRIC','METRIC\nINCH')
    (samples/'copper.gbr').write_text(copper,encoding='ascii',newline='\n');(samples/'drill-offset.drl').write_text(holes,encoding='ascii',newline='\n')
    result=run(samples/'copper.gbr',samples/'drill-offset.drl',samples/'review')
    assert result['status']=='invalid' and not (samples/'review'/'corrected-copy.drl').exists()


def points_case(offset=(5,7)):
    pads=[{'x':x,'y':y,'width':1.8,'height':1.8,'shape':'circle'} for x,y in POINTS]
    holes=[{'x':x+offset[0],'y':y+offset[1],'diameter':.8} for x,y in POINTS]
    return pads,holes


@pytest.mark.parametrize('kind',['rotate','mirror','scale','mixed','too_many_unmatched','small_smd','overlapping_pads'])
def test_no_incompatible_geometry_recovery(kind):
    pads,holes=points_case()
    if kind=='rotate':
        for h in holes:h['x'],h['y']=-h['y'],h['x']
    if kind=='mirror':
        for h in holes:h['x']=-h['x']
    if kind=='scale':
        for h in holes:h['x']*=1.4;h['y']*=1.4
    if kind=='mixed':
        for h in holes[:3]:h['x']+=2
    if kind=='too_many_unmatched': holes.extend([{'x':100+i*3,'y':100,'diameter':.8} for i in range(3)])
    if kind=='small_smd':
        for p in pads:p['width']=p['height']=.85
    if kind=='overlapping_pads':pads.extend([dict(p) for p in pads])
    assert solve(pads,holes)['status']=='review_required'


def test_finite_limits_and_thresholds():
    pads,holes=points_case()
    for kwargs in ({'minimum':2},{'coverage':.1},{'tolerance':1}):
        with pytest.raises(InputError):solve(pads,holes,**kwargs)
    with pytest.raises(InputError):solve(pads*600,holes)
    densepads=[dict(pads[0],x=float(i)) for i in range(1000)]
    denseholes=[dict(holes[0],x=float(i)) for i in range(400)]
    assert solve(densepads,denseholes)['status']=='review_required'


def test_original_metadata_and_existing_outputs_protected(samples):
    source=(samples/'drill-offset.drl').read_text().replace('T01','T23').replace('T02','T87')
    (samples/'tools.drl').write_text(source,encoding='ascii',newline='\n')
    result=run(samples/'copper.gbr',samples/'tools.drl',samples/'review')
    copy=(samples/'review'/'corrected-copy.drl').read_text()
    assert 'T23C0.800' in copy and 'T87C1.500' in copy
    saved={p.name:p.read_bytes() for p in (samples/'review').iterdir()}
    with pytest.raises(InputError):run(samples/'copper.gbr',samples/'tools.drl',samples/'review')
    assert saved=={p.name:p.read_bytes() for p in (samples/'review').iterdir()}


def test_svg_valid_xml_lf_packet_and_deterministic(samples):
    import xml.etree.ElementTree as ET
    run(samples/'copper.gbr',samples/'drill-offset.drl',samples/'first')
    run(samples/'copper.gbr',samples/'drill-offset.drl',samples/'second')
    assert {p.name:p.read_bytes() for p in (samples/'first').iterdir()}=={p.name:p.read_bytes() for p in (samples/'second').iterdir()}
    for p in (samples/'first').iterdir():
        if p.suffix=='.zip':
            with zipfile.ZipFile(p) as z:
                for name in z.namelist():assert b'\r' not in z.read(name)
        else:assert b'\r' not in p.read_bytes()
        if p.suffix=='.svg':ET.fromstring(p.read_bytes())


def test_python_browser_solver_equivalence_random_geometry():
    if not shutil.which('node'):pytest.skip('Node is required for independent browser solver equivalence checks.')
    randomizer=random.Random(4201);cases=[]
    for i in range(50):
        pts=[(randomizer.uniform(-40,40),randomizer.uniform(-30,30)) for _ in range(12)]
        dx,dy=randomizer.uniform(-100,100),randomizer.uniform(-100,100)
        pads=[{'x':x,'y':y,'width':1.8,'height':1.8,'shape':'circle'} for x,y in pts]
        holes=[{'x':x+dx+randomizer.uniform(-.004,.004),'y':y+dy+randomizer.uniform(-.004,.004),'diameter':.8} for x,y in pts]
        cases.append({'pads':pads,'holes':holes})
    node=subprocess.run(['node',str(Path(__file__).with_name('test_core.cjs')),'--cases'],input=json.dumps(cases),text=True,capture_output=True,check=True)
    assert len(node.stdout.encode('utf-8')) > 65536
    results=json.loads(node.stdout)
    assert len(results) == len(cases) == 50
    for case,result in zip(cases,results):
        python=solve(case['pads'],case['holes']);assert python['status']==result['status']=='recovered'
        assert python['translation_mm']==pytest.approx(result['translation_mm'],abs=1e-10)
        assert [(r['hole_index'],r['pad_index']) for r in python['matches']]==[(r['hole_index'],r['pad_index']) for r in result['matches']]


def test_cli_exit_invalid_report(samples,capsys):
    assert main([str(samples/'copper.gbr'),str(samples/'slots.drl'),'--out',str(samples/'invalid')])==2
    assert (samples/'invalid'/'review.json').exists()
    capsys.readouterr()


def test_public_text_and_nested_packets_are_lf_and_english():
    root=Path(__file__).resolve().parents[1]
    text={'.py','.js','.cjs','.html','.css','.md','.toml','.json','.yml','.yaml','.gbr','.drl','.svg','.csv','.txt'}
    def check(name,raw):
        if name.endswith(('.zip','.whl')):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                for item in archive.infolist():
                    if not item.is_dir():check(name+'!/'+item.filename,archive.read(item))
        elif Path(name).suffix in text or Path(name).name in {'LICENSE','.gitignore'}:
            assert b'\r' not in raw,name
            assert not any(19968<=ord(char)<=40959 for char in raw.decode('utf-8')),name
    for file in root.rglob('*'):
        if file.is_file() and not any(part in {'.git','.pytest_cache','__pycache__','build','dist'} or part.endswith('.egg-info') for part in file.relative_to(root).parts):
            check(file.relative_to(root).as_posix(),file.read_bytes())
