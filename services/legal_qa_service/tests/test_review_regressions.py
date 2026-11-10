"""Review regressions: user premises, hostile model JSON and corrected facts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone, date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import grpc
from legal_qa.v1 import legal_qa_service_pb2 as pb
from legal_qa.v1 import legal_qa_service_pb2_grpc as rpc
from legal_qa.answer import validate_draft
from legal_qa.context import parse_context
from legal_qa.corpus import publish
from legal_qa.transport.grpc_server import Servicer

QUOTE = 'Договоры на сумму свыше 10 000 000 рублей требуют одобрения.'


def draft(text, chunk_id='norm'):
    return {'outcome':'answered', 'claims':[{'text':text,'citations':[{'chunk_id':chunk_id,'quote':QUOTE}]}], 'missing_information':[]}


class ReviewTests(unittest.TestCase):
    def test_user_amount_is_conditional_not_a_normative_number(self):
        facts=parse_context([('user','Договор на 12 млн рублей.')]).facts
        evidence=[{'id':'norm','source':'Регламент','text':QUOTE,'provision':'2.4'}]
        for representation in ('12 млн','12 000 000 рублей'):
            claim=draft(f'Если сумма составляет {representation}, требуется одобрение, поскольку порог — 10 млн рублей.')
            self.assertEqual(validate_draft(claim,evidence,facts)[0]['text'],claim['claims'][0]['text'])
        for text in ('Если сумма составляет 13 млн, требуется одобрение.',
                     'Порог одобрения составляет 12 млн рублей.',
                     'Если порог одобрения составляет 12 млн, требуется одобрение.'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_draft(draft(text),evidence,facts)
        rent_evidence=[{'id':'norm','source':'Аренда','text':'Арендная плата — 450 000 рублей.','provision':'3.1'}]
        claim=draft('Арендная плата — 500 000 рублей.')
        claim['claims'][0]['citations'][0]['quote']=rent_evidence[0]['text']
        with self.assertRaises(ValueError):
            validate_draft(claim,rent_evidence,parse_context([('user','Почему плата 500 000 рублей?')]).facts)

    def test_all_malformed_nested_types_raise_validation_error(self):
        evidence=[{'id':'norm','source':'Регламент','text':QUOTE,'provision':'2.4'}]
        for citation in (None, 'bad', [], {'chunk_id':[],'quote':QUOTE}, {'chunk_id':'norm','quote':None}):
            bad=draft('Требуется одобрение.');bad['claims'][0]['citations']=[citation]
            with self.subTest(citation=citation), self.assertRaises(ValueError):
                validate_draft(bad,evidence)
        for outcome in (None, [], {}):
            bad=draft('Требуется одобрение.');bad['outcome']=outcome
            with self.subTest(outcome=outcome), self.assertRaises(ValueError):
                validate_draft(bad,evidence)

    def test_correction_resolves_only_the_named_date_conflict(self):
        history=[('user','Спецификация подписана 01.10.2024 или 02.10.2024.')]
        self.assertTrue(parse_context(history).date_conflict)
        direct=parse_context(history+[('user','Подтверждаю: правильная дата 02.10.2024.')])
        self.assertFalse(direct.date_conflict)
        self.assertEqual(direct.fact('specification_signed_on'),(date(2024,10,2),date(2024,10,2)))
        history += [('assistant','Какая дата подписания спецификации верна?'),
                    ('user','Подтверждаю: правильная дата 02.10.2024.')]
        context=parse_context(history)
        self.assertFalse(context.date_conflict)
        self.assertEqual(context.fact('specification_signed_on'),(date(2024,10,2),date(2024,10,2)))
        history=[('user','Спецификация 01.10.2024 или 02.10.2024; доставка 20.10.2024 или 21.10.2024.'),
                 ('user','Исправляю: спецификация подписана 02.10.2024.')]
        self.assertTrue(parse_context(history).date_conflict)
        history.append(('user','Подтверждаю: доставка 21.10.2024.'))
        self.assertFalse(parse_context(history).date_conflict)
        # A bad new correction must not erase a conflict; explicit as_of is independent.
        history.append(('user','Исправляю: доставка 20.10.2024 или 22.10.2024.'))
        self.assertTrue(parse_context(history).date_conflict)
        context=parse_context([('user','На 01.10.2024?'),('user','Нет, верно на 02.10.2024.')],date(2024,10,1))
        self.assertTrue(context.date_conflict)

    def test_real_grpc_preserves_model_error_code_and_accepts_user_amount(self):
        class Controlled:
            model='controlled'
            invalid=False
            verification_question=None
            def generate(self,question,evidence,deadline):
                result=draft('Если сумма составляет 12 млн, требуется одобрение.',evidence[0]['id'])
                if self.invalid:
                    result['claims'][0]['citations']=[None]
                return result
            def verify(self,question,evidence,result,deadline):
                self.verification_question=json.loads(question)
                return {'supported':True,'complete':True}
        generator=Controlled()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'corpus.zip'
            with ZipFile(archive,'w') as z: z.writestr('regulation.txt','Статья 1.\n'+QUOTE+'\n')
            publish(archive,root/'catalog')
            executor=ThreadPoolExecutor(max_workers=2)
            server=grpc.server(executor)
            rpc.add_LegalQaServiceServicer_to_server(Servicer(root/'catalog','gw-test','conv-test'),server)
            port=server.add_insecure_port('127.0.0.1:0');server.start()
            try:
                with grpc.insecure_channel(f'127.0.0.1:{port}') as channel, patch('legal_qa.transport.grpc_server.ProxyGenerator.from_env',return_value=generator):
                    stub=rpc.LegalQaServiceStub(channel)
                    request=pb.AnswerRequest(request_id='request',run_id='run',knowledge_base_id='meridian',messages=[pb.HistoryMessage(role=pb.MESSAGE_ROLE_USER,text='Договор на 12 млн рублей. Нужно одобрение?')])
                    request.deadline_at.FromDatetime(datetime.now(timezone.utc)+timedelta(seconds=20))
                    auth=(('x-jurion-service-token','conv-test'),)
                    response=stub.Answer(request,metadata=auth,timeout=5)
                    self.assertEqual(response.outcome,pb.OUTCOME_ANSWERED)
                    self.assertIn('12 млн',response.text)
                    self.assertTrue(any(f['role']=='amount' and f['value']=='12000000' for f in generator.verification_question['user_facts']))
                    del request.messages[:]
                    request.messages.extend([
                        pb.HistoryMessage(role=pb.MESSAGE_ROLE_USER,text='Договор на 12 млн рублей. Нужно одобрение?'),
                        pb.HistoryMessage(role=pb.MESSAGE_ROLE_USER,text='На 09.10.2026 или 10.10.2026?'),
                        pb.HistoryMessage(role=pb.MESSAGE_ROLE_ASSISTANT,text='Какая дата верна?'),
                        pb.HistoryMessage(role=pb.MESSAGE_ROLE_USER,text='Подтверждаю: правильная дата 10.10.2026.')])
                    corrected=stub.Answer(request,metadata=auth,timeout=5)
                    self.assertEqual(corrected.outcome,pb.OUTCOME_ANSWERED)
                    self.assertEqual(generator.verification_question['legal_as_of'],'2026-10-10')
                    generator.invalid=True
                    with self.assertRaises(grpc.RpcError) as error:
                        stub.Answer(request,metadata=auth,timeout=5)
                    self.assertEqual(error.exception.code(),grpc.StatusCode.UNAVAILABLE)
                    self.assertEqual(dict(error.exception.trailing_metadata())['jurion-error-code'],'MODEL_UNAVAILABLE')
            finally:
                server.stop(0).wait();executor.shutdown(wait=True)
