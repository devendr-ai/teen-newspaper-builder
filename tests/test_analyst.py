import copy,json,os,re,socket,subprocess,threading
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import pytest
from ygc import analyst,edition,play,site,prompt,skeleton


def sample(eid='global-citizen-plus',date='2026-10-26'):
 ed=edition.load(eid);issue=json.load(open(Path(ed['_dir'])/'issues'/date[:4]/(date+'.json')))
 return ed,issue


def test_curated_challenges_reference_exact_existing_reporting_and_leave_pdfs_alone():
 count=0
 for f in Path(analyst.ROOT).glob('*/*.json'):
  ed,issue=sample(f.parent.name,f.stem);value=json.loads(f.read_text())
  assert analyst.errors(issue,value)==[]
  assert analyst.get(ed,issue)==value
  assert analyst.wants(ed)
  count+=1
 assert count==5


def test_age_gate_and_legacy_fallback():
 ed,issue=sample();good=analyst.get(ed,issue)
 assert good['domino'] and good['call']
 issue['play']['analyst']=good
 young=copy.deepcopy(ed);young['reader']['age']='9-11'
 assert analyst.get(young,issue)=={}
 assert analyst.get(*sample('global-citizen-plus','2026-10-24'))=={}
 assert 'Analyst challenges' in prompt.generate(ed)
 assert 'Analyst challenges' not in prompt.generate(young)
 assert 'analyst' not in skeleton.play_skeleton(young)
 assert skeleton.play_skeleton(ed)['analyst']=={'domino':None,'call':None}


@pytest.mark.parametrize('change',[lambda d:d['domino']['steps'].pop(),lambda d:d['domino']['links'].pop(),lambda d:d['domino']['steps'][0].update(evidence='Invented evidence which is not in the story.'),lambda d:d['call'].update(story='economics'),lambda d:d['call']['options'][0].update(cost=''),lambda d:d['call']['options'][1].update(label=d['call']['options'][0]['label'])])
def test_bad_challenges_are_rejected(change):
 ed,issue=sample();d=copy.deepcopy(analyst.get(ed,issue));change(d);assert analyst.errors(issue,d)
 issue['play']['analyst']=d;assert analyst.get(ed,issue)=={}


def test_ids_are_stable_and_change_when_the_question_changes():
 ed,issue=sample();d=analyst.get(ed,issue)['call'];a=analyst.poll_id(ed,issue,d)
 assert a==analyst.poll_id(ed,issue,json.loads(json.dumps(d)))
 d=copy.deepcopy(d);d['options'][0]['cost']+=' Potentially.';assert analyst.poll_id(ed,issue,d)!=a


def test_reader_data_and_manifest_do_not_include_evidence_or_unapproved_polls(tmp_path):
 ed,issue=sample();_,data,_=play.sections(ed,issue,issue['date'])
 assert data['analyst']['call']['poll_id'] and len(data['analyst']['domino']['steps'])==4
 assert '"evidence":' not in json.dumps(data['analyst'])
 play.build(str(tmp_path),site.site_config(),keep=2,log=lambda *_:None)
 manifest=json.loads((tmp_path/'play/polls.json').read_text())
 assert data['analyst']['call']['poll_id'] in manifest
 assert len(manifest)==5


def test_analyst_interactions_and_no_un_gated_requests(tmp_path):
 from test_kids_mode import _browser
 found=_browser()
 if not found:pytest.skip('Playwright required')
 node,env=found
 # Build both real public and app pages; no mocked DOM or generated news.
 real=site.issues_of
 mp=pytest.MonkeyPatch();mp.setattr(site,'issues_of',lambda ed:real(ed)[:2])
 try:
  for mode in ('web','kids'):site.build(str(tmp_path/mode),keep=2,log=lambda *_:None,kids=mode=='kids')
 finally:mp.undo()
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 server=ThreadingHTTPServer(('127.0.0.1',port),partial(SimpleHTTPRequestHandler,directory=str(tmp_path)))
 t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
 try:
  result=subprocess.run([node,str(Path(__file__).with_name('analyst-games.cjs')),f'http://127.0.0.1:{port}'],env=env,capture_output=True,text=True,timeout=180)
  assert result.returncode==0,result.stdout+result.stderr
 finally:server.shutdown()
