import io
import json
import sys
import time
import unittest
import urllib.error
from unittest.mock import patch
from ai_runtime import (Context, Failure, DEFAULT_MODELS, http_failure, request_json,
    decode_completion, capability_check, execute_job, run_job, _run_worker)

MODEL=DEFAULT_MODELS['OpenRouter']

def context():
    return Context({'stage':'test','http_requests':0})

def response(content='{"ready":true}', finish='stop', model=MODEL):
    return {'model':model,'choices':[{'finish_reason':finish,'message':{'content':content}}]}

class RuntimeTests(unittest.TestCase):
    def test_http_categories(self):
        for status, category in [(401,'AUTHENTICATION'),(403,'ACCESS_DENIED'),(404,'MODEL_OR_ENDPOINT_UNAVAILABLE'),(429,'RATE_LIMIT'),(503,'PROVIDER_UNAVAILABLE'),(400,'REQUEST_REJECTED'),(402,'CREDITS_REQUIRED')]:
            self.assertEqual(http_failure(status).category,category)

    def test_http_body_never_disclosed(self):
        exc=urllib.error.HTTPError('https://example.invalid',401,'secret',{},io.BytesIO(b'customer invoice and api key'))
        with patch('urllib.request.urlopen',side_effect=exc):
            with self.assertRaises(Failure) as cm:request_json(None,context())
        self.assertNotIn('customer',str(cm.exception))
        self.assertEqual(cm.exception.http_status,401)

    def test_network_timeout(self):
        with patch('urllib.request.urlopen',side_effect=TimeoutError()):
            with self.assertRaises(Failure) as cm:request_json(None,context())
        self.assertEqual(cm.exception.category,'NETWORK_TIMEOUT')

    def test_null_envelope(self):
        for raw in ({'model':MODEL,'choices':None},{'model':MODEL,'choices':[None]}):
            with self.assertRaises(Failure) as cm:decode_completion(raw,'OpenRouter',MODEL,context())
            self.assertEqual(cm.exception.category,'RESPONSE_ENVELOPE')

    def test_truncation(self):
        with self.assertRaises(Failure) as cm:decode_completion(response('{','length'),'OpenRouter',MODEL,context())
        self.assertEqual(cm.exception.category,'OUTPUT_TRUNCATED')

    def test_invalid_model_json(self):
        with self.assertRaises(Failure) as cm:decode_completion(response('not JSON'),'OpenRouter',MODEL,context())
        self.assertEqual(cm.exception.category,'INVALID_MODEL_JSON')

    def test_model_identity(self):
        with self.assertRaises(Failure) as cm:decode_completion(response(model='another/model'),'OpenRouter',MODEL,context())
        self.assertEqual(cm.exception.category,'MODEL_MISMATCH')
        self.assertTrue(decode_completion(response(model=MODEL.removesuffix(':free')),'OpenRouter',MODEL,context())['ready'])

    def test_missing_model_stops_before_inference(self):
        with patch('ai_runtime.request_json',return_value={'data':[]}) as request:
            with self.assertRaises(Failure) as cm:capability_check('OpenRouter',MODEL,'private-key',context())
        self.assertEqual(cm.exception.category,'MODEL_UNAVAILABLE')
        self.assertEqual(request.call_count,1)

    def test_capability_modes_and_zero_price(self):
        for parameters, mode in [(['structured_outputs'],'json_schema'),(['response_format'],'json_object'),([], 'prompt_json')]:
            metadata={'data':[{'id':MODEL,'architecture':{'input_modalities':['text'],'output_modalities':['text']},'supported_parameters':parameters}]}
            with patch('ai_runtime.request_json',side_effect=[metadata,response()]) as request:
                result=capability_check('OpenRouter',MODEL,'private-key',context())
            self.assertEqual(result['output_mode'],mode)
            payload=json.loads(request.call_args_list[1].args[0].data)
            self.assertEqual(payload['model'],MODEL)
            self.assertEqual(payload['provider']['max_price'],{'prompt':0,'completion':0})

    def test_gemini_generation_capability_required(self):
        with patch('ai_runtime.request_json',return_value={'supportedGenerationMethods':['embedContent']}):
            with self.assertRaises(Failure) as cm:capability_check('Gemini','gemini-3.8-flash','key',context())
        self.assertEqual(cm.exception.category,'UNSUPPORTED_CAPABILITY')

    def test_no_router_or_paid_model(self):
        for model in ('openrouter/free','vendor/paid','openrouter/auto:free'):
            result=execute_job({'provider':'OpenRouter','model':model,'api_key':'private','operation':'check'},context().diagnostic)
            self.assertEqual(result['diagnostic']['category'],'CONFIGURATION')
            self.assertNotIn('private',json.dumps(result))

    def test_real_subprocess_deadline_and_stage(self):
        code='import json,time; print(json.dumps({"event":"progress","diagnostic":{"stage":"extraction_request"}}),flush=True); time.sleep(30)'
        started=time.monotonic()
        result=_run_worker({},context().diagnostic,0.3,[sys.executable,'-c',code])
        self.assertLess(time.monotonic()-started,2)
        self.assertEqual(result['diagnostic']['category'],'DEADLINE_EXCEEDED')
        self.assertEqual(result['diagnostic']['stage'],'extraction_request')

    def test_worker_crash(self):
        result=_run_worker({},context().diagnostic,2,[sys.executable,'-c','raise RuntimeError("secret")'])
        self.assertEqual(result['diagnostic']['category'],'WORKER_FAILED')
        self.assertNotIn('secret',json.dumps(result))

    def test_real_worker_missing_key(self):
        result=run_job('check','OpenRouter',MODEL,'')
        self.assertEqual(result['diagnostic']['category'],'CONFIGURATION')

    def test_real_extraction_parser_malformed_field(self):
        from extraction import extract_ai
        from pypdf import PdfWriter
        writer=PdfWriter();writer.add_blank_page(width=100,height=100)
        stream=io.BytesIO();writer.write(stream)
        raw={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'fields':[None,{'field':'invoice_total','value':None,'document':1,'page':1,'quote':'Total 10'}]})}]}}]}
        with patch('extraction.capability_check'),patch('extraction.request_json',return_value=raw):
            values,evidence=extract_ai([('invoice.pdf',stream.getvalue())],'key',['invoice_total'],'Gemini','gemini-3.8-flash',context())
        self.assertEqual(values['invoice_total'],'')
        self.assertEqual(evidence['_field_states']['invoice_total']['status'],'rejected')

if __name__=='__main__':unittest.main()
