"""Account model discovery and safe, actionable provider diagnostics."""
import os
import re
import time
import random
import logging
from functools import lru_cache
import requests

class ProviderError(RuntimeError):
    pass


def safe_error(exc):
    """Redact credentials before a provider message can reach the UI or export."""
    leaves = getattr(exc, 'exceptions', None)
    raw = '; '.join(safe_error(e) for e in leaves) if leaves else str(exc)
    for name in ('GOOGLE_API_KEY', 'GEMINI_API_KEY', 'TAVILY_API_KEY'):
        secret = os.getenv(name, '')
        if secret:
            raw = raw.replace(secret, '[REDACTED]')
    raw = re.sub(r'AIza[\w-]+|tvly-[\w-]+', '[REDACTED]', raw)
    raw = re.sub(r'(?i)([?&]key=)[^&\s]+', r'\1[REDACTED]', raw)
    return raw[:1800]


def explain_error(exc, service='Service'):
    detail = safe_error(exc)
    lower = detail.lower()
    if isinstance(exc, ProviderError) and "\n\nDetail:" in detail:
        return detail
    if '503' in lower or 'high demand' in lower or 'overloaded' in lower:
        help_text = 'Google is temporarily overloaded. The request could not complete. Choose another listed text model in the sidebar, or retry later. Changing API keys will not fix an overloaded model.'
    elif any(word in lower for word in ('429', 'resource_exhausted', 'quota', 'rate limit')):
        help_text = 'API quota/rate limit reached. Check this project’s usage in the provider dashboard. Wait for reset if a free limit is exhausted; repeated retries will not restore quota.'
    elif any(word in lower for word in ('401', '403', 'api_key_invalid', 'api key not valid', 'permission_denied', 'unauthenticated')):
        help_text = 'Key rejected or access denied. Check the key’s project, API permissions and account availability; save .env and restart.'
    elif any(word in lower for word in ('404', 'not_found', 'not found', 'not supported for generatecontent')):
        help_text = 'Model or endpoint unavailable. Set GEMINI_MODEL=auto in .env, restart, and run Check API connections.'
    elif any(word in lower for word in ('timeout', 'timed out', 'connection', 'ssl', 'proxy')):
        help_text = 'Connection failed. Check internet, firewall/proxy and provider availability.'
    else:
        help_text = 'Use the detail below to identify the failing provider or local component.'
    return f'{service}: {help_text}\n\nDetail: {detail}'


@lru_cache(maxsize=8)
def available_models(api_key):
    if not api_key.strip():
        raise ProviderError('GOOGLE_API_KEY is empty. Add it to the .env file beside app.py.')
    names, page = [], None
    for _ in range(20):
        params = {'pageSize': 100}
        if page:
            params['pageToken'] = page
        try:
            response = requests.get('https://generativelanguage.googleapis.com/v1beta/models',
                                    headers={'x-goog-api-key': api_key}, params=params, timeout=20)
            if not response.ok:
                try:
                    message = response.json().get('error', {}).get('message', response.reason)
                except ValueError:
                    message = response.reason
                raise ProviderError(f'Gemini model discovery HTTP {response.status_code}: {message}')
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ProviderError(explain_error(exc, 'Gemini model discovery')) from None
        for item in data.get('models', []):
            name = item.get('name', '').removeprefix('models/')
            if 'generateContent' in item.get('supportedGenerationMethods', []):
                names.append(name)
        page = data.get('nextPageToken')
        if not page:
            return tuple(dict.fromkeys(names))
    raise ProviderError('Gemini model list exceeded the pagination limit; retry later.')


def choose_model(names, preferred='auto'):
    """Choose only a model actually listed by the key; no invented model identifiers."""
    preferred = preferred.strip().removeprefix('models/')
    excluded = ('image', 'tts', 'audio', 'live', 'robotics', 'computer-use', 'embedding')
    candidates = [n for n in names if n.startswith('gemini-') and not any(x in n.lower() for x in excluded)]
    if preferred and preferred.lower() != 'auto' and preferred in candidates:
        return preferred
    if not candidates:
        raise ProviderError('No Gemini text-generation model was returned for this key. Check Google AI Studio account/project access.')
    # Prefer current Flash models only when returned by the account's model list.
    for known in ('gemini-3.8-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'):
        if known in candidates:
            return known
    return sorted(candidates, key=lambda n: ('flash' not in n, 'preview' in n or 'exp' in n, n))[0]


def selected_model():
    return choose_model(available_models(os.getenv('GOOGLE_API_KEY', '').strip()),
                        os.getenv('GEMINI_MODEL', 'auto'))


class SafeModel:
    def __init__(self, inner, name):
        self.inner, self.name = inner, name

    def invoke(self, messages):
        # Retry only transient 503 failures. Do not retry invalid keys, retired models or quota errors.
        for attempt in range(3):
            try:
                return self.inner.invoke(messages)
            except Exception as exc:
                detail = safe_error(exc).lower()
                transient = bool(re.search(r'\b503\b', detail)) or 'high demand' in detail or 'overloaded' in detail
                if transient and attempt < 2:
                    delay = (3, 8)[attempt] + random.uniform(0, 1)
                    logging.getLogger(__name__).warning('Gemini is busy; retry %s/2 in %.1f seconds', attempt + 1, delay)
                    time.sleep(delay)
                    continue
                message = explain_error(exc, f'Gemini ({self.name})')
                if transient:
                    message += '\nStopped after 3 attempts. No demo output was substituted.'
                raise ProviderError(message) from None

    def bind_tools(self, tools):
        try:
            return SafeModel(self.inner.bind_tools(tools), self.name)
        except Exception as exc:
            raise ProviderError(explain_error(exc, f'Gemini tool binding ({self.name})')) from None


def make_model():
    from langchain_google_genai import ChatGoogleGenerativeAI
    name = selected_model()
    return SafeModel(ChatGoogleGenerativeAI(model=name, api_key=os.environ['GOOGLE_API_KEY'].strip(),
                     vertexai=False, timeout=60, max_retries=0), name)


def check_connections():
    """Explicitly invoked in the UI; uses one Gemini check (up to 3 attempts on 503) and one Tavily search."""
    from langchain_core.tools import tool
    results = []
    available_models.cache_clear()
    try:
        name = selected_model()
        @tool
        def connection_ping(value: str) -> str:
            """Echo a value to test tool calling."""
            return value
        llm = make_model().bind_tools([connection_ping])
        answer = llm.invoke('Call connection_ping with value OK to check your tool connection. Do not answer with text.')
        calls = getattr(answer, 'tool_calls', [])
        if any(c['name']=='connection_ping' for c in calls):
            results.append({'service':'Gemini', 'status':'OK', 'detail':f'{name}: authenticated generation and tool-call response verified.'})
        else:
            results.append({'service':'Gemini', 'status':'WARNING', 'detail':f'{name}: generation worked, but the model did not return the requested tool call. Try another text model if planning fails.'})
    except Exception as exc:
        results.append({'service':'Gemini','status':'ERROR','detail':explain_error(exc, 'Gemini')})
    key = os.getenv('TAVILY_API_KEY', '').strip()
    if not key:
        results.append({'service':'Tavily','status':'ERROR','detail':'TAVILY_API_KEY is empty in .env.'})
    else:
        try:
            response = requests.post('https://api.tavily.com/search', headers={'Authorization':f'Bearer {key}'},
                                    json={'query':'Singapore official tourism', 'max_results':1}, timeout=25)
            if not response.ok:
                raise ProviderError(f'HTTP {response.status_code}: {response.text[:900]}')
            data = response.json()
            if 'results' not in data:
                raise ProviderError('Search response did not contain a results field.')
            results.append({'service':'Tavily','status':'OK','detail':'Authenticated search completed.'})
        except Exception as exc:
            results.append({'service':'Tavily','status':'ERROR','detail':explain_error(exc, 'Tavily')})
    return results
