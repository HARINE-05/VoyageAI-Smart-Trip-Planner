# Validation record

Built and checked on 2026-09-27 using Python 3.12 in a Linux environment.

- Dependencies installed successfully; exact installed versions are in requirements-lock.txt.
- Python source compilation checked.
- Eighteen pytest checks passed, including the real MCP stdio server/client, real LangGraph execution,
  group/room costing, successful and exhausted budget replanning, input validation, citation retrieval,
  weather horizon handling, currency/same-day behaviour, API key validation, capped ReAct tool calling
  with a fake model, and the Streamlit form/results flow using Streamlit AppTest.
- Live Gemini and Tavily calls were not end-to-end tested because no user API keys were supplied.
- Live weather and Frankfurter service integration code was checked against official documentation;
  external responses are subject to network availability and were not validated with a full live trip.
- Windows launcher supplied; validation ran on Linux, not Windows.
- First retrieval test found a cross-destination ranking problem; destination metadata filtering fixed it.

Do not describe mock flights/hotels as live prices or demo mode as live AI reasoning.

Version 1.1 regression checks: unavailable-model fallback, non-text model filtering, paginated account model discovery,
secret redaction (including grouped exceptions), quota messages, and Streamlit live-error rendering.
Provider responses were mocked for those checks. No user API keys were supplied; account-specific live success remains unverified.

Version 1.2, 2026-09-28: 22 tests passed in 14.68 seconds, including mocked transient-503 recovery,
three-attempt exhaustion, tool-bound retry handling and preference for the newer model when listed.
No real Google outage or user-key live success could be verified here.
