"""Mandatory regressions use synthetic sources, never personal files."""
import csv
from datetime import date
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from zipfile import ZipFile
from legal_qa.context import parse_context
from legal_qa.corpus import build_snapshot
from legal_qa.answer import answer, ModelUnavailable, validate_draft, ProxyGenerator


class Provider(BaseHTTPRequestHandler):
    paths = []
    mode = 'normal'
    def do_POST(self):
        if self.mode == 'failure':
            self.send_response(503);self.end_headers();return
        if self.mode == 'invalid_json':
            self.send_response(200);self.end_headers();self.wfile.write(b'not-json');return
        if self.mode == 'slow':
            time.sleep(.1)
            self.send_response(503);self.end_headers();return
        self.paths.append(self.path)
        data = json.loads(json.loads(self.rfile.read(int(self.headers['Content-Length'])))['messages'][-1]['content'])
        if 'draft' in data:
            result = {'supported':True,'complete':True}
        else:
            e = data['evidence'][0]
            result = {'outcome':'answered','claims':[{'text':e['text'],'citations':[{'chunk_id':e['id'],'quote':e['text']}]}], 'missing_information':[],'clarification_question':None}
        body=json.dumps({'choices':[{'message':{'content':json.dumps(result)}}]}).encode()
        self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*args): pass


class FinalTests(unittest.TestCase):
    def test_dates_roles_and_month(self):
        c=parse_context([('user','Договор заключали в августе 2024 года')])
        self.assertEqual((c.as_of_date,c.interval_end),(date(2024,8,1),date(2024,8,31)))
        c=parse_context([('user','Спецификация 2 октября 2024, доставка 2024-10-20')])
        self.assertFalse(c.date_conflict)
        self.assertEqual(c.fact('specification_signed_on')[0],date(2024,10,2))
        self.assertEqual(c.fact('delivery_on')[0],date(2024,10,20))

    def test_invalid_claims(self):
        evidence=[{'id':'one','text':'Плата 450 000 рублей.','source':'Договор','provision':'3.1'}]
        base={'outcome':'answered','claims':[{'text':'Плата 500 000 рублей.','citations':[{'chunk_id':'one','quote':'Плата 450 000 рублей.'}]}],'missing_information':[]}
        with self.assertRaises(ValueError): validate_draft(base,evidence)
        base['claims'][0]['text']='Плата 450 000 рублей.'
        base['claims'][0]['citations'][0]['chunk_id']='fake'
        with self.assertRaises(ValueError): validate_draft(base,evidence)

    def test_root_only_zip_with_real_http(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);data=tmp/'data';data.mkdir()
            with ZipFile(data/'knowledge-base.zip','w') as z:
                z.writestr('synthetic.txt','Статья 1. Арендная плата составляет 100 рублей.\n')
            with (data/'questions.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.writer(f);w.writerow(['id','question']);
                for i in range(1,19):
                    w.writerow([f'{i:03}', 'Пользователь: Проверяем аренду.\nАссистент: Уточните вопрос.\nПользователь: Какова арендная плата?'])
            subprocess.run([sys.executable,str(root/'build_submission.py'),str(tmp/'bundle.zip')],check=True,capture_output=True)
            with ZipFile(tmp/'bundle.zip') as z:
                self.assertTrue(all('/' not in name for name in z.namelist()))
                for name in z.namelist():
                    if name.endswith('.py') or name=='requirements.txt':
                        (tmp/name).write_bytes(z.read(name))
            server=ThreadingHTTPServer(('127.0.0.1',0),Provider)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                env={**os.environ,'PYTHONPATH':'','LLM_BASE_URL':f'http://127.0.0.1:{server.server_port}/v1','LLM_API_KEY':'test','LLM_MODEL':'fake','DATA_DIR':str(data)}
                subprocess.run([sys.executable,'-S','solution.py'],cwd=tmp,env=env,check=True,timeout=20,capture_output=True)
                with (tmp/'submission.csv').open() as f: rows=list(csv.DictReader(f))
                self.assertEqual([r['id'] for r in rows],[f'{i:03}' for i in range(1,19)])
                self.assertTrue(all('100 рублей' in r['answer'] for r in rows))
                self.assertTrue(all(p=='/v1/chat/completions' for p in Provider.paths))
                manifest,_=build_snapshot(data/'knowledge-base.zip')
                direct=answer(manifest,[('user','Какова арендная плата?')],ProxyGenerator(f'http://127.0.0.1:{server.server_port}/v1','test','fake'),deadline=time.monotonic()+5)
                self.assertEqual(rows[0]['answer'],direct.text)
            finally:
                server.shutdown();server.server_close();thread.join()

    def test_outcomes_and_semantic_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'corpus.zip'
            with ZipFile(path,'w') as z:
                z.writestr('law.txt','Статья 1. Оплата составляет 100 рублей.\n')
            manifest,_=build_snapshot(path)
            class Controlled:
                model='fake'
                supported=True
                def generate(self,question,evidence,deadline):
                    e=evidence[0] if evidence else None
                    claims=[{'text':'Оплата составляет 100 рублей.','citations':[{'chunk_id':e['id'],'quote':e['text']}]}] if self.outcome in ('answered','partially_answered','invalid_premise') else []
                    return {'outcome':self.outcome,'claims':claims,'missing_information':['Не указан срок'] if self.outcome=='partially_answered' else [],'clarification_question':'Какой срок?' if self.outcome=='needs_clarification' else None}
                def verify(self,*args):
                    return {'supported':self.supported,'complete':True}
            from legal_qa.answer import OUTCOMES
            for outcome in OUTCOMES:
                with self.subTest(outcome=outcome):
                    generator=Controlled();generator.outcome=outcome
                    questions={'answered':'Какая оплата?', 'partially_answered':'Какая оплата и срок?', 'invalid_premise':'Почему оплата 500 рублей?', 'needs_clarification':'По какому договору платить?', 'insufficient_evidence':'Какая страховка?', 'out_of_scope':'Какая погода?', 'disallowed':'Как подделать платежку?'}
                    result=answer(manifest,[('user',questions[outcome])],generator,deadline=time.monotonic()+5)
                    self.assertEqual(result.outcome,outcome)
                    self.assertTrue(result.text)
            generator=Controlled();generator.outcome='answered';generator.supported=False
            with self.assertRaises(ModelUnavailable):
                answer(manifest,[('user','Оплата?')],generator,deadline=time.monotonic()+5)

    def test_temporal_evidence_is_selected_before_generation(self):
        from legal_qa.evidence import retrieve
        files=[];chunks=[]
        def add(fid,title,version,start,end,text):
            files.append({'id':fid,'title':title,'version_label':version,'effective_from':start,'effective_to':end,'coverage_kind':'company_revision' if version else 'statute_excerpt','observed_on':'2026-10-10','document_id':'reg' if version else fid})
            chunks.append({'id':fid+'-chunk','file_id':fid,'text':text,'content_kind':'normative_text','line_start':1,'provision_label':'2.4'})
        add('old','Регламент 2023','2023','2023-01-10','2025-03-01','2.4. Свыше 10 000 000 требуется одобрение.')
        add('new','Регламент 2025','2025','2025-03-01',None,'2.4. Свыше 15 000 000 требуется одобрение.')
        add('law','Закон',None,None,None,'Статья 70. Испытание.')
        manifest={'files':files,'chunks':chunks,'effects':[]}
        for day,expected,excluded in [(date(2024,8,1),'old-chunk','new-chunk'),(date(2025,3,1),'new-chunk','old-chunk')]:
            messages=[('user','Регламент: требуется одобрение?')]
            evidence,_=retrieve(manifest,parse_context(messages,day),messages)
            self.assertIn(expected,{e['id'] for e in evidence});self.assertNotIn(excluded,{e['id'] for e in evidence})
        for day,present in [(date(2026,10,10),True),(date(2024,1,1),False)]:
            messages=[('user','Статья 70 испытание')]
            evidence,_=retrieve(manifest,parse_context(messages,day),messages)
            self.assertEqual('law-chunk' in {e['id'] for e in evidence},present)

    def test_replacement_and_supplement_evidence_without_personal_files(self):
        from legal_qa.evidence import retrieve
        def file(id,title):
            return {'id':id,'title':title,'document_id':id,'version_label':None,'coverage_kind':'company_revision','observed_on':None}
        def chunk(id,fid,text,provision=None):
            return {'id':id,'file_id':fid,'text':text,'content_kind':'normative_text','line_start':1,'provision_label':provision}
        manifest={'files':[file('supply','Договор поставки П-17-2024 synthetic'),file('amend','Доп соглашение synthetic'),file('reg','Регламент synthetic'),file('letter','Письмо synthetic')],
                  'chunks':[chunk('old','supply','3.2. Адрес доставки: Старый склад.','3.2'),chunk('new','amend','Новый адрес доставки: Новый склад. Применяется к спецификациям после 01.10.2024.'),chunk('base','reg','Проверка иностранного контрагента юридическим отделом.','5.4'),chunk('extra','letter','Санкционная проверка иностранного контрагента.')],
                  'effects':[{'source':'Доп соглашение synthetic','source_file_id':'amend','target':'Договор поставки П-17-2024 synthetic','target_document_id':'supply','provision':'3.2','kind':'replace','effective_from':'2024-09-03','resolution_status':'reviewed','conditions':[{'fact_key':'specification_date','operator':'gt','value':'2024-10-01'}]}, {'source':'Письмо synthetic','source_file_id':'letter','target':'Регламент synthetic','target_document_id':'reg','provision':'5.4','kind':'supplement','effective_from':'2025-04-21','resolution_status':'reviewed','conditions':[{'fact_key':'foreign_counterparty','operator':'eq','value':True}]}]}
        for day,new in [(1,False),(2,True)]:
            messages=[('user',f'П-17/2024: спецификация {day} октября 2024, доставка 20 октября 2024. Какой адрес?')]
            context=parse_context(messages)
            evidence,missing=retrieve(manifest,context,messages)
            ids={e['id'] for e in evidence}
            self.assertFalse(missing);self.assertFalse(context.date_conflict)
            self.assertEqual('new' in ids,new);self.assertEqual('old' in ids,not new)
        for day,extra in [(20,False),(21,True)]:
            messages=[('user','Как проверить иностранного контрагента?')]
            evidence,_=retrieve(manifest,parse_context(messages,date(2025,4,day)),messages)
            ids={e['id'] for e in evidence}
            self.assertIn('base',ids);self.assertEqual('extra' in ids,extra)

    def test_legacy_snapshot_survives_republication(self):
        from legal_qa.corpus import digest, load_snapshot, publish
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'catalog';archive=Path(tmp)/'input.zip'
            with ZipFile(archive,'w') as z: z.writestr('legacy.txt','Статья 1. Старый текст.\n')
            manifest,originals=build_snapshot(archive)
            manifest['schema_version']=1
            raw=json.dumps(manifest,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
            old=digest(raw);directory=root/'snapshots'/old
            (directory/'files').mkdir(parents=True)
            (directory/'manifest.json').write_bytes(raw)
            for fid,data in originals.items(): (directory/'files'/fid).write_bytes(data)
            (root/'active').write_text(old)
            with ZipFile(archive,'w') as z: z.writestr('legacy.txt','Статья 1. Новый текст.\n')
            new=publish(archive,root)
            self.assertNotEqual(old,new)
            self.assertEqual(load_snapshot(root,old)[1],originals)
            (root/'snapshots'/new/'manifest.json').write_bytes(b'broken')
            with self.assertRaises(ValueError): load_snapshot(root)
            self.assertEqual(load_snapshot(root,old)[1],originals)

    def test_provider_errors_are_technical(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Provider)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        generator=ProxyGenerator(f'http://127.0.0.1:{server.server_port}/v1','test','fake')
        try:
            for mode in ('failure','invalid_json'):
                Provider.mode=mode
                with self.assertRaises(ModelUnavailable):
                    generator.generate('question',[],time.monotonic()+2)
            Provider.mode='slow'
            with self.assertRaises(TimeoutError):
                generator.generate('question',[],time.monotonic()+.02)
        finally:
            Provider.mode='normal';server.shutdown();server.server_close();thread.join()
