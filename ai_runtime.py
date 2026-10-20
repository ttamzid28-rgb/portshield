"""Bounded AI jobs and content-free diagnostics. No Streamlit dependency."""
import base64
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

DEFAULT_MODELS = {'OpenRouter': 'dots-studio/dots-3-note-preview:free', 'Gemini': 'gemini-3.8-flash'}
DEADLINE_SECONDS = 75
MAX_RESPONSE_BYTES = 8 * 1024 * 1024

class Failure(Exception):
    def __init__(self, category, message, http_status=None):
        super().__init__(message)
        self.category, self.message, self.http_status = category, message, http_status

class Context:
    def __init__(self, diagnostic, emit=lambda d: None):
        self.diagnostic, self.emit = diagnostic, emit
    def stage(self, name):
        self.diagnostic['stage'] = name
        self.emit(self.diagnostic)


def http_failure(status):
    category, message = {
        400: ('REQUEST_REJECTED', 'Provider rejected the request format or parameters. Check model capabilities and request schema.'),
        401: ('AUTHENTICATION', 'API key was rejected. Check this provider’s secret in Streamlit settings.'),
        402: ('CREDITS_REQUIRED', 'Provider requires credits. No paid model fallback was attempted.'),
        403: ('ACCESS_DENIED', 'Provider denied access. Check project permissions or regional restrictions.'),
        404: ('MODEL_OR_ENDPOINT_UNAVAILABLE', 'Configured model or endpoint is unavailable to this request. Check model access and supported parameters.'),
        408: ('NETWORK_TIMEOUT', 'Provider timed out. Retry later.'),
        413: ('PAYLOAD_TOO_LARGE', 'Provider rejected the request size. Reduce the packet.'),
        422: ('REQUEST_REJECTED', 'Provider could not process the request schema or parameters.'),
        429: ('RATE_LIMIT', 'Provider quota or rate limit reached. Wait before retrying.'),
    }.get(status, ('PROVIDER_UNAVAILABLE', 'Provider service failed. Retry later.') if status >= 500 else ('HTTP_ERROR', 'Provider returned an unexpected HTTP error.'))
    return Failure(category, message, status)


def request_json(request, ctx):
    # No application retries; the outer worker deadline also bounds DNS, TLS and slow reads.
    ctx.diagnostic['http_requests'] += 1
    ctx.stage(ctx.diagnostic['stage'])
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()  # Never expose provider bodies: they may echo uploaded content.
        raise http_failure(status) from None
    except (TimeoutError,):
        raise Failure('NETWORK_TIMEOUT', 'Network operation timed out. Retry later.') from None
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise Failure('NETWORK_TIMEOUT', 'Network operation timed out. Retry later.') from None
        raise Failure('NETWORK_ERROR', 'Could not reach the provider. Check connectivity and retry later.') from None
    if len(body) > MAX_RESPONSE_BYTES:
        raise Failure('RESPONSE_TOO_LARGE', 'Provider response exceeded the safety limit.')
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        raise Failure('INVALID_RESPONSE_JSON', 'Provider returned unreadable JSON, before field extraction.') from None
    if not isinstance(data, dict):
        raise Failure('RESPONSE_ENVELOPE', 'Provider response was not a JSON object.')
    if data.get('error'):
        error = data['error']
        code = error.get('code') if isinstance(error, dict) else None
        if isinstance(code, int) and 400 <= code <= 599:
            raise http_failure(code)
        raise Failure('PROVIDER_ERROR', 'Provider reported an error inside its response.')
    return data


def add_response_format(payload, mode, schema, name):
    if mode == 'json_schema':
        payload['response_format'] = {'type': 'json_schema', 'json_schema': {'name': name, 'strict': True, 'schema': schema}}
    elif mode == 'json_object':
        payload['response_format'] = {'type': 'json_object'}
    # prompt_json is explicit in diagnostics, never represented as schema-enforced.


def decode_completion(raw, provider, model, ctx):
    ctx.stage('response_parsing')
    try:
        if provider == 'OpenRouter':
            actual = raw.get('model')
            if not isinstance(actual, str):
                raise Failure('RESPONSE_ENVELOPE', 'Provider omitted the model identity.')
            # OpenRouter commonly removes the routing variant from its response identity.
            if actual not in (model, model.removesuffix(':free')):
                raise Failure('MODEL_MISMATCH', 'Response model differs from the configured model. No fields accepted.')
            ctx.diagnostic['actual_model'] = actual
            candidate = raw['choices'][0]
            finish = candidate.get('finish_reason')
            if finish == 'length':
                raise Failure('OUTPUT_TRUNCATED', 'Model reached its output limit. No partial JSON accepted.')
            if finish in ('content_filter', 'error') or candidate.get('message', {}).get('refusal'):
                raise Failure('MODEL_REFUSAL', 'Model declined or filtered the request.')
            if finish != 'stop':
                raise Failure('RESPONSE_ENVELOPE', 'Model did not report a completed response.')
            answer = candidate['message']['content']
        else:
            if raw.get('promptFeedback', {}).get('blockReason'):
                raise Failure('MODEL_REFUSAL', 'Provider blocked the request.')
            candidate = raw['candidates'][0]
            finish = candidate.get('finishReason')
            if finish == 'MAX_TOKENS':
                raise Failure('OUTPUT_TRUNCATED', 'Model reached its output limit. No partial JSON accepted.')
            if finish in ('SAFETY', 'RECITATION', 'BLOCKLIST', 'PROHIBITED_CONTENT'):
                raise Failure('MODEL_REFUSAL', 'Model declined or filtered the request.')
            if finish != 'STOP':
                raise Failure('RESPONSE_ENVELOPE', 'Model did not report a completed response.')
            answer = ''.join(p.get('text', '') for p in candidate['content']['parts'] if not p.get('thought'))
        if not isinstance(answer, str):
            raise Failure('RESPONSE_ENVELOPE', 'Model returned no text response.')
        answer = answer.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        raise Failure('RESPONSE_ENVELOPE', 'Provider response structure was missing or malformed.') from None
    ctx.stage('json_decoding')
    try:
        result = json.loads(answer)
    except ValueError:
        raise Failure('INVALID_MODEL_JSON', 'Model output was not valid JSON. No fields accepted.') from None
    if not isinstance(result, dict):
        raise Failure('FIELD_SCHEMA', 'Model output must be a JSON object.')
    return result


def capability_check(provider, model, api_key, ctx):
    ctx.stage('capability_metadata')
    if provider == 'OpenRouter':
        headers = {'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'}
        catalog = request_json(urllib.request.Request('https://openrouter.ai/api/v1/models', headers=headers), ctx)
        models = catalog.get('data')
        if not isinstance(models, list):
            raise Failure('CAPABILITY_RESPONSE', 'Model catalog has an unexpected format.')
        info = next((m for m in models if isinstance(m, dict) and m.get('id') == model), None)
        if info is None:
            raise Failure('MODEL_UNAVAILABLE', 'Configured model is absent from the current catalog. Choose an available explicit free model in settings.')
        architecture = info.get('architecture') or {}
        if 'text' not in (architecture.get('input_modalities') or []) or 'text' not in (architecture.get('output_modalities') or []):
            raise Failure('UNSUPPORTED_CAPABILITY', 'Configured model does not advertise text input and output.')
        params = info.get('supported_parameters') or []
        mode = 'json_schema' if 'structured_outputs' in params else 'json_object' if 'response_format' in params else 'prompt_json'
        ctx.diagnostic['output_mode'] = mode
        schema = {'type': 'object', 'properties': {'ready': {'type': 'boolean'}}, 'required': ['ready'], 'additionalProperties': False}
        payload = {'model': model, 'messages': [{'role': 'user', 'content': 'Return only this JSON object, without explanation: {"ready": true}'}], 'max_tokens': 1024,
                   'provider': {'require_parameters': True, 'max_price': {'prompt': 0, 'completion': 0}}}
        add_response_format(payload, mode, schema, 'connection_check')
        url = 'https://openrouter.ai/api/v1/chat/completions'
    else:
        headers = {'x-goog-api-key': api_key, 'Content-Type': 'application/json'}
        info = request_json(urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models/' + model, headers=headers), ctx)
        if 'generateContent' not in (info.get('supportedGenerationMethods') or []):
            raise Failure('UNSUPPORTED_CAPABILITY', 'Model does not advertise generateContent support.')
        mode = 'json_schema'
        ctx.diagnostic['output_mode'] = mode
        payload = {'contents': [{'parts': [{'text': 'Return {"ready":true} as JSON.'}]}], 'generationConfig': {'responseMimeType': 'application/json', 'responseSchema': {'type': 'OBJECT', 'properties': {'ready': {'type': 'BOOLEAN'}}, 'required': ['ready']}, 'maxOutputTokens': 1024}}
        url = 'https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent'
    ctx.stage('capability_probe')
    raw = request_json(urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method='POST'), ctx)
    result = decode_completion(raw, provider, model, ctx)
    if result.get('ready') is not True:
        raise Failure('CAPABILITY_PROBE_FAILED', 'Model did not pass the synthetic JSON response check.')
    ctx.diagnostic['capability_check'] = 'metadata_and_synthetic_json_passed'
    ctx.stage('capability_complete')
    return {'output_mode': mode}


def execute_job(job, diagnostic, emit=lambda d: None):
    ctx = Context(diagnostic, emit)
    try:
        provider, model, key = job['provider'], job['model'], job['api_key']
        ctx.stage('configuration')
        if provider not in DEFAULT_MODELS or not isinstance(key, str) or not key.strip():
            raise Failure('CONFIGURATION', 'Select a supported provider and configure its API key.')
        if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9_./:-]{1,160}', model):
            raise Failure('CONFIGURATION', 'Model setting must contain a model identifier only.')
        if provider == 'OpenRouter' and (not model.endswith(':free') or model.startswith('openrouter/')):
            raise Failure('CONFIGURATION', 'Select a specific :free model, not an automatic router. Paid fallback is disabled.')
        if provider == 'Gemini' and not re.fullmatch(r'gemini-[A-Za-z0-9_.-]+', model):
            raise Failure('CONFIGURATION', 'Use the bare Gemini model ID from the provider catalog.')
        if job['operation'] == 'check':
            data = capability_check(provider, model, key, ctx)
            message = 'Connection check passed: model metadata and synthetic JSON response verified. PDF extraction accuracy and future availability are not guaranteed.'
        elif job['operation'] == 'extract':
            from extraction import extract_ai
            packet = [(name, base64.b64decode(body, validate=True)) for name, body in job.get('packet', [])]
            data = extract_ai(packet, key, job['field_names'], provider, model, ctx)
            message = 'Extraction completed. Source-linked fields require human review.'
        else:
            raise Failure('CONFIGURATION', 'Unknown AI operation.')
        diagnostic.update(status='success', category='SUCCESS', message=message, stage='complete')
        return {'ok': True, 'data': data, 'diagnostic': diagnostic}
    except Failure as exc:
        diagnostic.update(status='failed', category=exc.category, message=exc.message)
        if exc.http_status is not None: diagnostic['http_status'] = exc.http_status
    except (ValueError, TypeError) as exc:
        diagnostic.update(status='failed', category='INVALID_INPUT', message='Input could not be processed. Check PDF count, size, encryption and required fields.')
    except Exception as exc:
        diagnostic.update(status='failed', category='INTERNAL_ERROR', message='Unexpected internal failure. Use the diagnostic ID for troubleshooting.', exception_type=type(exc).__name__)
    return {'ok': False, 'diagnostic': diagnostic}


def _run_worker(job, diagnostic, deadline, command=None):
    started = time.monotonic()
    process = None
    output = b''
    timed_out = False
    try:
        process = subprocess.Popen(command or [sys.executable, str(Path(__file__).with_name('ai_worker.py'))], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            output, _ = process.communicate(json.dumps({'job': job, 'diagnostic': diagnostic}).encode(), timeout=max(0.001, deadline-(time.monotonic()-started)))
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            output, _ = process.communicate(timeout=2)
        result = None
        for line in output.splitlines():
            try: event = json.loads(line)
            except (ValueError, UnicodeError): continue
            if event.get('event') == 'progress': diagnostic.update(event['diagnostic'])
            elif event.get('event') == 'result': result = event['result']
        if timed_out:
            diagnostic.update(status='failed', category='DEADLINE_EXCEEDED', message=f'Overall {deadline:g}-second deadline reached. Local worker stopped; no new fields accepted. Provider processing may continue remotely.')
        elif result is not None:
            diagnostic = result['diagnostic']
            result['diagnostic']['elapsed_seconds'] = round(time.monotonic()-started, 2)
            return result
        else:
            diagnostic.update(status='failed', category='WORKER_FAILED', message='Extraction worker exited without a result. No new fields accepted.')
    except Exception:
        diagnostic.update(status='failed', category='WORKER_FAILED', message='Could not complete the isolated worker. No new fields accepted.')
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=2)
    diagnostic['elapsed_seconds'] = round(time.monotonic()-started, 2)
    return {'ok': False, 'diagnostic': diagnostic}


def run_job(operation, provider, model, api_key, packet=None, field_names=None):
    diagnostic = {'request_id': uuid.uuid4().hex[:12], 'operation': operation, 'provider': provider,
                  'configured_model': model if isinstance(model, str) and re.fullmatch(r'[A-Za-z0-9_./:-]{1,160}', model) else 'invalid',
                  'stage': 'worker_start', 'status': 'running', 'http_requests': 0, 'deadline_seconds': DEADLINE_SECONDS}
    job = {'operation': operation, 'provider': provider, 'model': model, 'api_key': api_key,
           'packet': [(name, base64.b64encode(data).decode()) for name, data in packet or []], 'field_names': field_names or []}
    return _run_worker(job, diagnostic, DEADLINE_SECONDS)
