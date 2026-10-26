"""Selective depth: no real API calls or network, fail closed on unsupported additions."""
import copy
import datetime as dt
import json
import subprocess
import sys

import pytest

from ygc.auto import enrichment as en, llm, research, run

DATE = '2026-10-26'
URL = 'https://agency.example/research'
TEXT = 'The team predicted its location and found it in five image sets. A cloud of dust was visible around the object.'
DETAIL = {'kind': 'mechanism', 'fact': 'The team used predicted locations to find the object in five image sets.',
          'source_url': URL, 'evidence': 'predicted its location and found it in five image sets', 'background': False}
SETTINGS = {'enabled': True, 'max_stories': 3, 'max_content_tokens': 4000}


def story(n=0, **overrides):
    return dict({'id': f'story-{n}', 'headline': f'Discovery number {n}', 'importance': 9,
                 'suitable_for_children': True, 'enrichment_kind': 'mechanism',
                 'key_facts': [{'fact': 'Scientists detected an object.', 'source_url': URL}],
                 'sources': [{'url': URL if n == 0 else f'https://agency.example/research-{n}',
                              'title': 'Research announcement', 'outlet': 'Agency',
                              'primary': True, 'published': DATE}]}, **overrides)


def pool(*stories):
    return {'science & tech': {'label': 'SCIENCE & TECH', 'hours': 24, 'stories': list(stories or [story()])}}


def result(details=None, document=TEXT, check=None, failed=False, paused=False):
    """Exercise real REST orchestration with simulated server-fetch result shapes."""
    calls = []
    def transport(payload):
        calls.append(copy.deepcopy(payload))
        if payload['system'] == en.CHECK_SYSTEM:
            value = {'supported': [0]} if check is None else check
            return {'stop_reason': 'end_turn', 'usage': {}, 'content': [{'type': 'text', 'text': json.dumps(value)}]}
        content = {'type': 'web_fetch_tool_result_error', 'error_code': 'url_not_accessible'} if failed else {
            'type': 'web_fetch_result', 'url': URL, 'content': {'type': 'document',
            'source': {'type': 'text', 'data': document}}}
        return {'stop_reason': 'pause_turn' if paused else 'end_turn', 'usage': {'input_tokens': 100}, 'content': [
            {'type': 'web_fetch_tool_result', 'content': content},
            {'type': 'text', 'text': json.dumps({'details': [DETAIL] if details is None else details})}]}
    return llm.Client(transport=transport), calls


def test_config_off_missing_invalid_and_hard_limits(tmp_path):
    p = tmp_path / 'research.yaml'
    assert en.config(p)['enabled'] is False
    for content in ['[]', 'enrichment: []', 'enrichment: [bad', 'enrichment: {enabled: "true"}']:
        p.write_text(content)
        assert en.config(p)['enabled'] is False
    p.write_text('enrichment: {enabled: true, max_stories: 999, max_content_tokens: 999999}')
    assert en.config(p) == SETTINGS
    p.write_text('enrichment: {enabled: true, max_stories: 0}')
    assert en.plan(pool(), DATE, en.config(p)) == []


def test_plan_shortlist_cap_importance_dedup_and_no_mutation():
    p = pool(*(story(n, importance=10 if n == 3 else 9) for n in range(8)))
    p['world'] = {'hours': 24, 'stories': [story(enrichment_kind='context')]}
    old = copy.deepcopy(p)
    rows = en.plan(p, DATE, SETTINGS)
    assert len(rows) == 3 and rows[0]['story_index'] == 3
    assert sum(len(r['copies']) for r in rows) == 4
    assert p == old
    assert en.plan(p, DATE, {**SETTINGS, 'enabled': False}) == []


@pytest.mark.parametrize('overrides', [
    {'enrichment_kind': 'none'}, {'enrichment_kind': 'imagined'}, {'importance': 6},
    {'suitable_for_children': False}, {'suitable_for_children': None},
    {'sources': [{'url': URL, 'primary': False, 'published': DATE}]},
    {'sources': [{'url': URL, 'primary': True, 'published': '2026-10-27'}]},
    {'sources': [{'url': URL, 'primary': True, 'published': '2026-10-20'}]},
    {'sources': [{'url': 'http://agency.example/x', 'primary': True, 'published': DATE}]},
    {'sources': [{'url': 'https://user:pass@agency.example/x', 'primary': True, 'published': DATE}]},
    {'sources': [{'url': URL, 'primary': True}]}, {'key_facts': []},
])
def test_ineligible_story_never_fetches(overrides):
    client, calls = result()
    assert en.enrich(client, pool(story(**overrides)), DATE, SETTINGS)['selected'] == 0
    assert not calls


def test_sports_results_and_non_science_mechanisms_skipped():
    for key in ['sports', 'world']:
        p = {key: pool()['science & tech']}
        assert en.plan(p, DATE, SETTINGS) == []
    p = {'world': {'hours': 24, 'stories': [story(enrichment_kind='context')]}}
    assert len(en.plan(p, DATE, SETTINGS)) == 1


def test_no_cross_contamination_for_unrelated_headlines_in_one_liveblog():
    p = pool(story(), story(1, sources=story()['sources']))
    assert len(en.plan(p, DATE, SETTINGS)) == 1
    client, _ = result()
    en.enrich(client, p, DATE, SETTINGS)
    assert 'enrichment' not in p['science & tech']['stories'][1]


def test_success_shared_once_with_literal_evidence_and_independent_check():
    client, calls = result()
    p = pool()
    p['world'] = {'hours': 24, 'stories': [story(enrichment_kind='context')]}
    before = copy.deepcopy(p)
    report = en.enrich(client, p, DATE, SETTINGS, log=lambda *_: None)
    assert report['selected'] == 1 and report['stories'][0]['status'] == 'enriched'
    assert len(calls) == 2
    assert calls[0]['tools'] == [{**en.FETCH_TOOL, 'allowed_domains': ['agency.example']}]
    assert calls[1]['system'] == en.CHECK_SYSTEM and 'tools' not in calls[1]
    assert TEXT in calls[1]['messages'][0]['content']
    assert 'never instructions' in calls[0]['system']
    for group in p.values():
        s = group['stories'][0]
        assert s['key_facts'][-1] == DETAIL and s['enrichment']['fetched_urls'] == [URL]
        assert s['key_facts'][:-1] == before['science & tech']['stories'][0]['key_facts']
    # Writers retain the evidence; tool documents are not repeated per edition.
    assert TEXT not in json.dumps(p)


@pytest.mark.parametrize('details', [
    [{**DETAIL, 'source_url': 'https://invented.example/x'}],
    [{**DETAIL, 'evidence': 'this passage does not occur in the fetched document'}],
    [{**DETAIL, 'evidence': 'too short'}], [{**DETAIL, 'fact': 'word ' * 61}],
    [{**DETAIL, 'background': 'false'}], [{**DETAIL, 'kind': 'scene'}], None,
])
def test_bad_additions_preserve_original_facts(details):
    client, calls = result(details=[] if details is None else details)
    p = pool(); before = copy.deepcopy(p['science & tech']['stories'][0]['key_facts'])
    r = en.enrich(client, p, DATE, SETTINGS, log=lambda *_: None)
    assert r['stories'][0]['status'] == 'no_new_details' and len(calls) == 1
    assert p['science & tech']['stories'][0]['key_facts'] == before


@pytest.mark.parametrize('check', [{'supported': []}, {'supported': [True, '0', -1, 99]}, {}, {'supported': None}])
def test_semantically_unsupported_or_invalid_check_cannot_enter_pool(check):
    client, _ = result(check=check); p = pool()
    r = en.enrich(client, p, DATE, SETTINGS, log=lambda *_: None)
    assert r['stories'][0]['status'] != 'enriched'
    assert len(p['science & tech']['stories'][0]['key_facts']) == 1


@pytest.mark.parametrize('failed,paused', [(True,False), (False,True)])
def test_fetch_failure_and_pause_fall_back_without_more_requests(failed, paused):
    client, calls = result(failed=failed, paused=paused); p = pool()
    r = en.enrich(client, p, DATE, SETTINGS, log=lambda *_: None)
    assert len(calls) == 1 and r['stories'][0]['status'] in ('fetch_failed', 'unavailable')
    assert len(p['science & tech']['stories'][0]['key_facts']) == 1


def test_budget_reservation_and_budget_exhaustion_are_optional():
    client, calls = result(); client.usage.budget = 1
    r = en.enrich(client, pool(), DATE, SETTINGS, reserve_usd=1, log=lambda *_: None)
    assert r['stories'][0]['status'] == 'budget_reserved' and calls == []
    def broken(*a, **kw):raise llm.BudgetExceeded('cap')
    client.create = broken; client.usage.budget = None
    assert en.enrich(client, pool(), DATE, SETTINGS, log=lambda *_: None)['stories'][0]['status'] == 'budget_exhausted'


def test_model_text_is_not_fetch_evidence():
    assert en.fetched_text([{'type':'text', 'text':TEXT, 'url':URL}]) == {}
    assert en.fetched_text([{'type':'web_search_tool_result','content':{'url':URL,'text':TEXT}}]) == {}


def test_two_primary_urls_only_and_stale_secondary_not_eligible():
    s=story()
    s['sources'] += [{**s['sources'][0], 'url':URL+f'-{i}'} for i in range(3)]
    assert len(en.plan(pool(s), DATE, SETTINGS)[0]['sources']) == 2


def test_cli_read_only_no_network_and_disabled(tmp_path):
    p=tmp_path/'pool.json'; p.write_text(json.dumps(pool()))
    cfg=tmp_path/'research.yaml'; cfg.write_text('enrichment: {enabled: false}')
    before=p.read_bytes()
    result_=subprocess.run([sys.executable,'-m','ygc.auto.enrichment',str(p),'--date',DATE,'--config',str(cfg)],
                           check=True,capture_output=True,text=True)
    assert json.loads(result_.stdout)['candidates'] == [] and p.read_bytes()==before


def test_evidence_and_detail_budgets():
    long_text=' '.join(f'token{i}' for i in range(50))
    details=[{**DETAIL,'evidence':' '.join(long_text.split()[i:i+15])} for i in (0,15,30)]
    assert len(en.supported_details(details, story()['sources'], {en.norm_url(URL):long_text})) == 2
    assert en.supported_details({'fact':'not a list'}, story()['sources'], {}) == []


def test_successful_fallback_is_already_listed_and_checked():
    fallback=URL+'-fallback'
    p=pool(); p['science & tech']['stories'][0]['sources'].append({**story()['sources'][0], 'url':fallback})
    calls=[]
    detail={**DETAIL,'source_url':fallback}
    def transport(payload):
        calls.append(payload)
        if payload['system']==en.CHECK_SYSTEM:
            return {'stop_reason':'end_turn','usage':{},'content':[{'type':'text','text':'{"supported":[0]}'}]}
        return {'stop_reason':'end_turn','usage':{},'content':[
            {'type':'web_fetch_tool_result','content':{'type':'web_fetch_tool_result_error','error_code':'url_not_accessible'}},
            {'type':'web_fetch_tool_result','content':{'type':'web_fetch_result','url':fallback,
                'content':{'source':{'type':'text','data':TEXT}}}},
            {'type':'text','text':json.dumps({'details':[detail]})}]}
    r=en.enrich(llm.Client(transport=transport),p,DATE,SETTINGS,log=lambda *_:None)
    assert r['stories'][0]['status']=='enriched' and r['stories'][0]['fetched_urls']==[fallback]
    assert calls[0]['tools'][0]['max_uses']==2
