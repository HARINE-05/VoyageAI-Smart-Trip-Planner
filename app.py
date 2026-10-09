from datetime import date, timedelta
import json
import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from trip.core import TripRequest, DESTINATIONS, ORIGINS, CURRENCIES
from trip.agents import run_trip
from trip.providers import check_connections, explain_error, selected_model, available_models

load_dotenv(Path(__file__).parent / '.env', override=True)
st.set_page_config(page_title='Smart Trip Planner', page_icon='🧭', layout='wide')
st.title('🧭 Smart Trip Planner')
st.caption('Version 1.2 · bounded overload retries and model selection')
if not (Path(__file__).parent / '.env').exists() and (Path(__file__).parent / '.env.txt').exists():
    st.error('Your settings file is named .env.txt. Rename it to .env (enable File name extensions in Windows Explorer).')
st.caption('Your travel brief → five agents → a sourced itinerary and an estimated budget')
with st.sidebar:
    st.header('Project mode')
    mode = st.radio('Choose mode', ['Demo — no API keys', 'Live AI — Gemini + Tavily'])
    st.info('Flight and hotel prices are mock data in BOTH modes. Live AI adds model reasoning, web search, weather and exchange rates.')
    st.caption('Supported: Singapore, Bangkok, Dubai and Goa. This app does not book travel.')
    if st.button('Load model choices'):
        try:
            choices = available_models(os.getenv('GOOGLE_API_KEY', '').strip())
            st.session_state.model_choices = [n for n in choices if n.startswith('gemini-') and
                not any(word in n for word in ('image', 'audio', 'tts', 'live', 'robotics', 'computer-use', 'embedding'))]
        except Exception as exc:
            st.error(explain_error(exc, 'Gemini model list'))
    if st.session_state.get('model_choices'):
        def clear_connection_result():
            st.session_state.pop('connections', None)
        chosen = st.selectbox('Gemini model for this session', ['Use .env setting'] + st.session_state.model_choices,
                              on_change=clear_connection_result)
        if chosen != 'Use .env setting':
            os.environ['GEMINI_MODEL'] = chosen
        st.caption('Listed models can still have account, quota or availability restrictions. Test a selected model before planning. Its pricing may differ.')
    if st.button('Check API connections'):
        with st.spinner('Checking Gemini tool calling and Tavily search…'):
            st.session_state.connections = check_connections()
    if 'connections' in st.session_state:
        for check in st.session_state.connections:
            show = st.success if check['status'] == 'OK' else st.warning if check['status'] == 'WARNING' else st.error
            show(check['service'] + ': ' + check['status'])
            st.code(check['detail'], language=None)
with st.form('trip'):
    c1, c2, c3 = st.columns(3)
    origin = c1.selectbox('Departure city', ORIGINS)
    destination = c2.selectbox('Destination', list(DESTINATIONS))
    nationality = c3.text_input('Passport nationality', 'Indian')
    start = c1.date_input('Departure date', date.today() + timedelta(days=7), min_value=date.today())
    end = c2.date_input('Return date', date.today() + timedelta(days=10), min_value=date.today())
    travellers = c3.number_input('Travellers', 1, 10, 1)
    budget = c1.number_input('Total budget for everyone', min_value=1.0, value=80000.0, step=1000.0)
    currency = c2.selectbox('Budget currency', CURRENCIES)
    interests = st.text_input('Interests / preferences', 'Culture, sightseeing and local food', max_chars=500)
    submitted = st.form_submit_button('Create my travel plan', type='primary')
if submitted:
    st.session_state.pop('result', None)
    try:
        request = TripRequest(origin=origin, destination=destination, nationality=nationality.strip(),
                              start=start, end=end, travellers=travellers, budget=budget,
                              currency=currency, interests=interests)
        with st.spinner('Planning and checking costs… Temporary Gemini 503 errors retry up to twice per request.'):
            st.session_state.result = run_trip(request, demo=mode.startswith('Demo'))
    except Exception as exc:
        st.error('Planning stopped. The error details below identify what needs fixing.')
        st.code(explain_error(exc, 'Trip planner'), language=None)
        st.info('Click Check API connections in the sidebar. Share only the error text, never your .env file or keys.')
if 'result' in st.session_state:
    s = st.session_state.result
    st.subheader(f'{s["request"]["origin"]} → {s["request"]["destination"]}')
    st.caption('Saved result: ' + ('DEMO — deterministic output, no live research' if s['demo'] else 'LIVE AI with mock travel prices'))
    if not s['demo']:
        st.caption('Gemini model: ' + selected_model())
    a, b, c = st.columns(3)
    a.metric('Estimated group cost', f'{s["conversion"]["amount"]:,.2f} {s["request"]["currency"]}')
    b.metric('Budget revisions', s['revision'])
    c.metric('Budget status', 'Over budget' if s['over_budget'] else 'Within estimate')
    tabs = st.tabs(['Itinerary', 'Costs', 'Sources & weather', 'Agent trace', 'Download'])
    with tabs[0]:
        st.markdown(s['summary'])
    with tabs[1]:
        rate = s['conversion']['rate']
        st.table([{'Category': key, f'Amount ({s["request"]["currency"]})': round(value*rate, 2)}
                  for key, value in s['costs']['items_inr'].items()])
        st.caption('Conversion: ' + s['conversion']['source'] + ' — ' + s['conversion']['as_of'])
        st.write('Selected mock flight', s['flight'])
        st.write('Selected mock hotel', s['hotel'])
        st.info('Hotel assumes 2 people per room. Food, transport and activities are allowances, not verified vendor prices. Individual visa, insurance and baggage fees are excluded.')
    with tabs[2]:
        st.write('Retrieved local knowledge (editorial guides and dated source summaries; recheck before travel)')
        for d in s['evidence']:
            with st.expander(f'[{d["id"]}] {d["title"]}'):
                st.write(d['text'])
                st.write('Reference link: ' + d['url'])
                st.caption('Document: data/knowledge.json · section ' + d['id'])
        st.write('Tavily results and additional ReAct observations')
        st.json(s['web'])
        st.write('Weather response')
        st.json(s['weather'])
    with tabs[3]:
        st.table(s['trace'])
        st.write('Planner execution plan')
        st.write(s['planner_note'])
    with tabs[4]:
        st.download_button('Download complete result (JSON)', json.dumps(s, indent=2), 'trip_result.json', 'application/json')
        costs = '\n'.join(f'- {k}: INR {v:,.2f}' for k, v in s['costs']['items_inr'].items())
        sources = '\n'.join(f'- [{d["id"]}] {d["title"]}: {d["url"]}' for d in s['evidence'])
        report = s['summary'] + '\n\n## Costs (INR)\n' + costs + '\n\n## Sources\n' + sources + '\n\n## Web evidence\n```json\n' + json.dumps(s['web'], indent=2) + '\n```'
        st.download_button('Download travel report (Markdown)', report, 'trip_report.md', 'text/markdown')
