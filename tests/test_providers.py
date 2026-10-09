from unittest.mock import Mock
import pytest
from trip.providers import choose_model, safe_error, explain_error, available_models, ProviderError, SafeModel


def test_unavailable_configured_model_uses_account_list():
    assert choose_model(('gemini-2.5-flash', 'gemini-2.5-pro'), 'gemini-unavailable') == 'gemini-2.5-flash'
    assert choose_model(('gemini-2.5-flash',), '') == 'gemini-2.5-flash'
    assert choose_model(('gemini-2.5-flash', 'gemini-2.5-pro'), 'models/gemini-2.5-pro') == 'gemini-2.5-pro'


def test_non_text_models_not_selected():
    with pytest.raises(ProviderError):
        choose_model(('gemini-image-only', 'gemini-audio-tts', 'embedding-001'))


def test_discovery_pages_and_generation_filter(monkeypatch):
    first = Mock(ok=True)
    first.json.return_value = {'models':[{'name':'models/gemini-2.5-flash', 'supportedGenerationMethods':['generateContent']}], 'nextPageToken':'second'}
    second = Mock(ok=True)
    second.json.return_value = {'models':[{'name':'models/embedding-001','supportedGenerationMethods':['embedContent']}]}
    get = Mock(side_effect=[first,second])
    monkeypatch.setattr('trip.providers.requests.get',get)
    available_models.cache_clear()
    assert available_models('fixture-key') == ('gemini-2.5-flash',)
    assert get.call_args.kwargs['params']['pageToken'] == 'second'
    available_models.cache_clear()


def test_redacts_keys_and_nested_windows_errors(monkeypatch):
    monkeypatch.setenv('GOOGLE_API_KEY','private-fixture-key')
    message = safe_error(ExceptionGroup('group', [RuntimeError('failed private-fixture-key'), RuntimeError('tvly-some-secret')]))
    assert 'private-fixture-key' not in message
    assert 'tvly-some-secret' not in message
    assert '[REDACTED]' in message


def test_quota_diagnostic_is_actionable():
    inner = Mock()
    inner.invoke.side_effect = RuntimeError('429 RESOURCE_EXHAUSTED quota exceeded')
    with pytest.raises(ProviderError, match='quota/rate limit reached'):
        SafeModel(inner,'fixture-model').invoke('hello')
    assert inner.invoke.call_count == 1


def test_live_ui_shows_safe_provider_error(monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('GOOGLE_API_KEY','fake-key')
    monkeypatch.setenv('TAVILY_API_KEY','fake-tavily-key')
    monkeypatch.setattr('trip.agents.model', Mock(side_effect=ProviderError('429 quota exhausted')))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
    app.radio[0].set_value('Live AI — Gemini + Tavily').run()
    next(b for b in app.button if b.label=='Create my travel plan').click().run(timeout=30)
    assert not app.exception
    assert any('quota/rate limit' in c.value for c in app.code)
    assert len(app.metric)==0


def test_overload_retries_then_succeeds(monkeypatch):
    sleeper=Mock()
    monkeypatch.setattr('trip.providers.time.sleep',sleeper)
    inner=Mock()
    inner.invoke.side_effect=[RuntimeError('503 UNAVAILABLE high demand'), RuntimeError('503 UNAVAILABLE'), 'success']
    assert SafeModel(inner,'test-model').invoke('hello')=='success'
    assert inner.invoke.call_count==3
    assert sleeper.call_count==2


def test_overload_stops_at_three_attempts(monkeypatch):
    monkeypatch.setattr('trip.providers.time.sleep',Mock())
    inner=Mock()
    inner.invoke.side_effect=RuntimeError('503 UNAVAILABLE high demand')
    with pytest.raises(ProviderError,match='Stopped after 3 attempts'):
        SafeModel(inner,'test-model').invoke('hello')
    assert inner.invoke.call_count==3


def test_tool_bound_model_keeps_retry_behaviour(monkeypatch):
    monkeypatch.setattr('trip.providers.time.sleep',Mock())
    inner=Mock()
    inner.bind_tools.return_value.invoke.side_effect=[RuntimeError('503 UNAVAILABLE'),'tool response']
    assert SafeModel(inner,'test-model').bind_tools([]).invoke('hello')=='tool response'


def test_auto_prefers_new_model_over_retired_generation():
    assert choose_model(('gemini-2.5-flash','gemini-3.8-flash'),'auto')=='gemini-3.8-flash'
