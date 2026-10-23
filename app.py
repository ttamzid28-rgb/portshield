import io,json,re,zipfile
import html
import base64, urllib.request, urllib.error, time
from pathlib import Path
import streamlit as st
from pypdf import PdfReader
from checks import audit
from field_states import review_fields
from ai_runtime import run_job, DEFAULT_MODELS, DEADLINE_SECONDS
from pdf_viewer import render_pdf_viewer, bind_packet, packet_provenance_manifest, render_source_evidence

st.set_page_config(page_title='PortShield AI | Document Readiness',page_icon='🛡️',layout='wide')
st.markdown("""<style>
.stApp{background:#f5f7fb}h1,h2,h3{color:#142b45}div[data-testid="stSidebar"]{background:#eaf0f7}
.stButton>button{border-radius:8px}div[data-testid="stMetric"]{background:white;padding:16px;border:1px solid #dfe6ef;border-radius:10px}
.hero{background:#142b45;color:white;padding:25px 30px;border-radius:14px;margin-bottom:18px}.hero h1{color:white;font-size:32px;margin:4px 0}.hero p{color:#d4e5f4;margin:4px 0}.eyebrow{font-size:12px;letter-spacing:2px;color:#87d9d2}
.stagebar{padding:12px 16px;background:#e5f3f1;border:1px solid #c5e3df;border-radius:8px;color:#146c63;margin-bottom:18px}
</style>""",unsafe_allow_html=True)
st.markdown('<div class="hero"><div class="eyebrow">PORTSHIELD AI / IMPORT OPERATIONS</div><h1>Trade document review workbench</h1><p>Find conflicts. Review the evidence. Prepare corrections before submission.</p></div>',unsafe_allow_html=True)
st.caption('LIVE PROTOTYPE v0.9 · Eight deterministic checks · Gemini PDF and OpenRouter text AI options')
fields=['lc_currency','lc_amount','latest_shipment_date','lc_port_of_discharge','invoice_currency','invoice_total','invoice_quantity','unit_price','packing_quantity','packing_container','bl_container','on_board_date','bl_port_of_discharge','pl_cargo_gross_weight','pl_cargo_gross_weight_unit','bl_cargo_gross_weight','bl_cargo_gross_weight_unit']
base={'lc_currency':'USD','lc_amount':'25000','latest_shipment_date':'2026-10-20','lc_port_of_discharge':'Chattogram Sea Port','invoice_currency':'USD','invoice_total':'27000','invoice_quantity':'100','unit_price':'250','packing_quantity':'100','packing_container':'ABCD1234567','bl_container':'ABCD1234568','on_board_date':'2026-10-21','bl_port_of_discharge':'Mongla Port','pl_cargo_gross_weight':'21600','pl_cargo_gross_weight_unit':'KGS','bl_cargo_gross_weight':'20700','bl_cargo_gross_weight_unit':'KGS'}
fixed={**base,'invoice_total':'25000','bl_container':'ABCD1234567','bl_port_of_discharge':'Chattogram Sea Port','bl_cargo_gross_weight':'21600'}
with st.sidebar:
    st.title('PortShield AI')
    st.caption('COMMERCIAL DESK')
    st.header('Shipment workspace')
    st.caption('Fictional polymer import • Chattogram')
    scenario=st.selectbox('Sample packet',['Problem shipment','Corrected shipment','Unreadable field'])
    if st.button('Load sample',type='primary') or 'fields' not in st.session_state:
        sample=dict(fixed if scenario=='Corrected shipment' else base)
        if scenario=='Unreadable field':
            sample['invoice_total']=''
            sample['bl_port_of_discharge']=''
            sample['pl_cargo_gross_weight']=''
            sample['bl_cargo_gross_weight']=''
        st.session_state.previous=st.session_state.pop('results',st.session_state.get('previous',[]))
        st.session_state.ai_pending=False;st.session_state.fields=sample;st.session_state.evidence={k:f'Fictional sample field: {k} = {v}' for k,v in sample.items()}
        st.session_state.bound_packet=None
    st.download_button('Download sample PDFs',(Path(__file__).parent / 'sample_documents.zip').read_bytes(),'portshield-sample-documents.zip','application/zip')
    st.caption('Upload the sample PDFs below to exercise actual text extraction. Other layouts may need manual entry.')
overview,upload,review,actions,about=st.tabs(['Shipment overview','Document intake','Review & evidence','Corrections & report','Scope & roadmap'])
current=audit(st.session_state.fields, st.session_state.evidence.get('_field_states'))
if st.session_state.get('ai_pending'):
    current=[{**r,'status':'Incomplete','evidence':'AI-extracted fields await human confirmation.'} for r in current]
with overview:
    st.markdown('<div class="stagebar">01 Intake → 02 Confirm fields → 03 Review exceptions → 04 Prepare corrections</div>',unsafe_allow_html=True)
    st.subheader('PS-DEMO-001 | Polymer raw material import')
    st.caption('Fictional demonstration case · Destination: Chattogram · No bank or customs approval implied')
    cols=st.columns(3)
    for col,status in zip(cols,['Passed','Review required','Incomplete']):
        count = sum(x['status'] in (status, 'Insufficient data') if status == 'Incomplete' else x['status'] == status for x in current)
        col.metric(status, count)
    st.subheader('Cross-document reconciliation')
    d=st.session_state.fields
    def v(k): return d.get(k,'') or 'Not available'
    rows=[
        {'Field':'Currency','L/C':v('lc_currency'),'Invoice':v('invoice_currency'),'Packing list':'—','B/L':'—'},
        {'Field':'Amount / credit limit','L/C':v('lc_amount'),'Invoice':v('invoice_total'),'Packing list':'—','B/L':'—'},
        {'Field':'Quantity (equivalent units)','L/C':'—','Invoice':v('invoice_quantity'),'Packing list':v('packing_quantity'),'B/L':'—'},
        {'Field':'Container','L/C':'—','Invoice':'—','Packing list':v('packing_container'),'B/L':v('bl_container')},
        {'Field':'Shipment date / deadline','L/C':v('latest_shipment_date'),'Invoice':'—','Packing list':'—','B/L':v('on_board_date')},
        {'Field':'Port of discharge','L/C':v('lc_port_of_discharge'),'Invoice':'—','Packing list':'—','B/L':v('bl_port_of_discharge')},
        {'Field':'Cargo gross weight','L/C':'—','Invoice':'—','Packing list':f"{v('pl_cargo_gross_weight')} {v('pl_cargo_gross_weight_unit')}".strip(),'B/L':f"{v('bl_cargo_gross_weight')} {v('bl_cargo_gross_weight_unit')}".strip()},
    ]
    st.dataframe(rows,hide_index=True,use_container_width=True)
    st.caption('Matrix reflects loaded or confirmed fields. Confirm source values in Review & evidence before relying on a result.')
    st.subheader('Exception queue')
    pending=[r for r in current if r['status']!='Passed']
    if pending:st.dataframe(pending,hide_index=True,use_container_width=True)
    else:st.success('No issues detected in the eight supported checks. Human review remains required.')
    st.info('Start with the sample packet, or upload the supplied PDFs in Document intake. Change confirmed values, run checks, then open Corrections & report.')
with upload:
    st.subheader('Upload a document packet')
    st.caption('AI mode reads varied PDF layouts and scans; accuracy requires review. Labelled text mode works without an API key. Demo scope: one line item and one container per packet.')
    use_demo=st.checkbox('Use bundled sample PDFs — no upload needed')
    benchmark_case=None
    if use_demo:
        benchmark_data=json.loads((Path(__file__).parent/'benchmark_data.json').read_text())
        case_options=['Original quick demo']+[c['case_id']+' | '+c['scenario']+' | '+c['split'] for c in benchmark_data['cases']]
        chosen_case=st.selectbox('Built-in document packet',case_options)
        if chosen_case!='Original quick demo':
            benchmark_case=next(c for c in benchmark_data['cases'] if chosen_case.startswith(c['case_id']+' |'))
            st.caption('Fictional benchmark PDFs. The answer key is not sent to the AI. Holdout cases should be reserved until development testing is complete.')
            if benchmark_case['case_id']=='PSB-11':st.info('Image-only scan test: OpenRouter text extraction should request OCR or manual review.')
        st.download_button('Download all benchmark packets',base64.b64decode(benchmark_data['zip_base64']),'PortShield-Benchmark-v1.zip','application/zip')
    files=st.file_uploader('PDF documents',type=['pdf'],accept_multiple_files=True,disabled=use_demo)
    if use_demo:
        st.caption('The selected fictional PDF packet will be processed by the selected AI provider.')
    try:
        gemini_key=st.secrets.get('GEMINI_API_KEY','')
        router_key=st.secrets.get('OPENROUTER_API_KEY','')
        model_config={p:st.secrets.get(p.upper()+'_MODEL',m) for p,m in DEFAULT_MODELS.items()}
    except Exception:
        gemini_key=router_key=''
        model_config=dict(DEFAULT_MODELS)
    provider=st.selectbox('AI provider',['OpenRouter (pinned free model, text PDFs)','Gemini (PDF and scans)'])
    selected='OpenRouter' if provider.startswith('OpenRouter') else 'Gemini'
    api_key=router_key if selected=='OpenRouter' else gemini_key
    model=model_config[selected]
    st.caption(f'Model: {model} · Overall deadline: {DEADLINE_SECONDS} seconds · No automatic retries or model switching.')
    if not api_key:
        secret_name='OPENROUTER_API_KEY' if selected=='OpenRouter' else 'GEMINI_API_KEY'
        st.info(f'Add {secret_name} in Streamlit app settings → Secrets to enable this provider.')
        st.link_button('Get provider API key','https://openrouter.ai/keys' if selected=='OpenRouter' else 'https://aistudio.google.com/apikey')
    elif selected=='OpenRouter':
        st.caption('A specific free OpenRouter model processes PDF text. Capability and response checks run before document extraction; scanned pages require a vision provider.')
    else:
        st.caption('Gemini reads PDFs and scans. Model access and quota depend on your Google project; capability checks do not guarantee free-tier access.')
    if st.button('Check AI connection',disabled=not api_key):
        with st.spinner('Checking model capabilities and a small synthetic response…'):
            outcome=run_job('check',selected,model,api_key)
        st.session_state.ai_diagnostic=outcome['diagnostic']
    consent=st.checkbox(f'These PDFs are fictional or redacted, and I agree to send '+('extracted PDF text to OpenRouter and its routed model.' if selected=='OpenRouter' else 'the PDFs to Google Gemini. Free-tier content may be used to improve Google products.'))
    if st.button('Extract with AI',type='primary',disabled=not api_key or not consent):
        if time.time()-st.session_state.get('last_ai_call',0)<20:
            st.warning('Please wait 20 seconds between extraction attempts.')
        else:
            st.session_state.last_ai_call=time.time()
            try:
                with st.spinner('Extracting source-linked fields…'):
                    if use_demo and benchmark_case:
                        with zipfile.ZipFile(io.BytesIO(base64.b64decode(benchmark_data['zip_base64']))) as bundle:
                            packet=[(Path(name).name,bundle.read(name)) for name in bundle.namelist() if '/'+benchmark_case['case_id']+'/' in name and name.endswith('.pdf')]
                    elif use_demo:
                        with zipfile.ZipFile(Path(__file__).parent/'sample_documents.zip') as bundle:
                            packet=[(name,bundle.read(name)) for name in bundle.namelist() if name.endswith('.pdf')]
                    else:packet=[(f.name,f.getvalue()) for f in files or []]
                    started=time.perf_counter()
                    outcome=run_job('extract',selected,model,api_key,packet,fields)
                    st.session_state.ai_diagnostic=outcome['diagnostic']
                    if not outcome['ok']:
                        st.session_state.benchmark_run=None
                        raise ValueError(outcome['diagnostic']['message'])
                    values,source=outcome['data']
                    bound=bind_packet(packet)
                    st.session_state.bound_packet=bound
                    source['_packet_provenance']=packet_provenance_manifest(bound)
                    st.session_state.benchmark_run={'case_id':benchmark_case['case_id'],'provider':selected,'elapsed_seconds':round(time.perf_counter()-started,2),'raw_fields':dict(values),'source_evidence':dict(source)} if benchmark_case else None
                st.session_state.previous=st.session_state.pop('results',st.session_state.get('previous',[]))
                st.session_state.fields=values;st.session_state.evidence=source;st.session_state.ai_pending=True
                st.rerun()
            except ValueError as exc:st.error(str(exc))
            except Exception:st.error('Extraction failed. No new fields accepted. Try another provider or use labelled text extraction.')
    diagnostic=st.session_state.get('ai_diagnostic')
    if diagnostic:
        if diagnostic['status']=='success':
            st.success(diagnostic['message'])
        else:
            st.error(diagnostic['category']+' — '+diagnostic['message']+' Previous workspace values, if any, are unchanged.')
        with st.expander('Latest AI diagnostic',expanded=diagnostic['status']!='success'):
            st.json(diagnostic)
            st.download_button('Download diagnostic',json.dumps(diagnostic,indent=2),'portshield-ai-diagnostic.json','application/json')
            st.caption('Diagnostic excludes API keys, document content and raw provider responses. A connection check uses synthetic data only.')
    if st.session_state.get('ai_pending') and diagnostic and diagnostic['status']=='success' and diagnostic['operation']=='extract':
        st.success('AI extraction complete. Open Review & evidence to confirm the extracted fields.')
    run=st.session_state.get('benchmark_run')
    if run:
        with st.expander('Latest benchmark extraction record'):
            st.caption('Raw extraction captured before reviewer edits. This record remains tied to the tested case, even if you select another packet.')
            st.write('Case: '+run['case_id']+' | Provider: '+run['provider']+' | '+str(run['elapsed_seconds'])+' seconds')
            st.json(run['raw_fields'])
            st.download_button('Download benchmark extraction record',json.dumps(run,indent=2),'portshield-'+run['case_id']+'-extraction.json','application/json')
    st.divider()
    if st.button('Extract uploaded text',disabled=use_demo):
        extracted={}; evidence={}; conflicts=set(); unreadable=False; labelled_candidates={k:[] for k in fields}
        if not files:st.warning('Upload at least one PDF.')
        packet=[(f.name,f.getvalue()) for f in files or []]
        bound=bind_packet(packet)
        for f in files or []:
            try:
                reader=PdfReader(io.BytesIO(f.getvalue()))
                if len(reader.pages)>50:unreadable=True;st.warning(f'{f.name}: limit 50 pages');continue
                for n,p in enumerate(reader.pages,1):
                    text=p.extract_text() or ''
                    if not text.strip():unreadable=True
                    for key in fields:
                        label=key.replace('_',' ')
                        for match in re.finditer(r'(?im)^\s*'+re.escape(label)+r'\s*:\s*([^\n\r]+)',text):
                            value=match.group(1).strip()
                            labelled_candidates[key].append({'value':value,'quote':match.group(0).strip(),'filename':f.name,'page':n})
                            if key in conflicts or (key in extracted and extracted[key]!=value):
                                conflicts.add(key);extracted[key]='';evidence[key]='Conflicting extracted values: manual confirmation required'
                            else:extracted[key]=value;evidence[key]=f'{f.name} · page {n} · {match.group(0).strip()}'
            except Exception:
                unreadable=True
                st.warning(f'Could not read {f.name}. Please use an unencrypted text PDF.')
        if files:
            evidence['_field_states']={k:{'status':'conflicting' if k in conflicts else 'extracted' if extracted.get(k) else 'unreadable' if unreadable else 'missing', 'reason':'Labelled extraction; unreadable means incomplete packet text coverage, not proven field location.', 'candidates':labelled_candidates[k], 'review_status':'pending'} for k in fields}
            evidence['_packet_provenance']=packet_provenance_manifest(bound)
            st.session_state.bound_packet=bound
            st.session_state.previous=st.session_state.pop('results',st.session_state.get('previous',[]))
            st.session_state.ai_pending=True;st.session_state.fields={k:extracted.get(k,'') for k in fields};st.session_state.evidence=evidence
            st.rerun()
with review:
    st.subheader('Review extracted fields')
    st.caption('Amounts use the same currency; quantities use the same unit. The configured amount limit must include any applicable tolerance. No prior credit utilisation is modelled.')
    if st.session_state.get('ai_pending'):
        st.warning('Extraction complete. Verify every value against the PDFs before confirming. Credit amount is the extracted face value; review tolerances separately.')
    states=st.session_state.evidence.get('_field_states',{})
    if states:
        st.dataframe([{'Field':k,'Extraction state':r['status'],'Review':r['review_status'],'Reason':r['reason']} for k,r in states.items()],hide_index=True,use_container_width=True)
    with st.expander('Source extraction evidence',expanded=st.session_state.get('ai_pending',False)):
        render_source_evidence(st.session_state.evidence)
    render_pdf_viewer(st.session_state.get('bound_packet'), st.session_state.evidence)
    with st.form('review_form'):
        vals={};cols=st.columns(3)
        for i,k in enumerate(fields):
            with cols[i%3]:vals[k]=st.text_input(k.replace('_',' ').title(),value=st.session_state.fields.get(k,''))
        confirmed=st.checkbox('I have checked all populated values, including corrections, against the source PDFs.')
        submitted=st.form_submit_button('Run document checks',type='primary')
    if submitted and not confirmed:st.warning('Confirm the extracted values before running checks.')
    if submitted and confirmed:
        st.session_state.ai_pending=False
        st.session_state.previous=st.session_state.get('results',st.session_state.get('previous',[]))
        reviewed=review_fields(vals,st.session_state.evidence.get('_field_states',{}))
        st.session_state.evidence['_field_states']=reviewed
        st.session_state.results=audit(vals,reviewed);st.session_state.fields=vals
        st.rerun()
    if 'results' in st.session_state:
        results=st.session_state.results
        cols=st.columns(3)
        for col,status in zip(cols,['Passed','Review required','Incomplete']):
            count = sum(x['status'] in (status, 'Insufficient data') if status == 'Incomplete' else x['status'] == status for x in results)
            col.metric(status, count)
        previous={x['check']:x['status'] for x in st.session_state.get('previous',[])}
        resolved=[x['check'] for x in results if x['status']=='Passed' and previous.get(x['check'])=='Review required']
        if resolved:st.success('Resolved since previous run: '+', '.join(resolved))
        for result in results:
            with st.expander(f"{result['status']} — {result['check']}",expanded=result['status']!='Passed'):
                st.write(result['evidence']);st.caption('Evidence refers to confirmed values; edits require reviewer verification against the source.')
        with st.expander('Source extraction evidence'):
            render_source_evidence(st.session_state.evidence)
        report={'prototype':'PortShield v0.9','scope':'Eight limited checks; human approval required','fields':st.session_state.fields,'findings':results,'source_evidence':st.session_state.evidence}
        st.download_button('Download review report (JSON)',json.dumps(report,indent=2),'portshield-review.json','application/json')
with actions:
    st.subheader('Correction desk')
    st.caption('Drafts are generated from supported rule findings. An officer must verify the evidence and approve any request before sending. No messages are sent by this app.')
    if 'results' not in st.session_state:
        st.info('Run document checks in Review & evidence to generate an action pack.')
    else:
        recommendations={
            'Currency':('Commercial officer / supplier','Reconcile the invoice currency with the credit. Confirm the agreed currency before issuing revised documents.'),
            'Quantity (same unit required)':('Commercial officer / supplier','Confirm equivalent units and the actual shipped quantity. Reconcile invoice and packing list; do not change factual quantities merely to match.'),
            'Container identifier':('Commercial officer / carrier / supplier','Confirm the actual container identifier against the shipping record and correct the document containing the error.'),
            'Invoice amount within configured limit':('Commercial officer / bank','Confirm the configured limit, applicable tolerance and credit utilisation. Seek bank guidance on the appropriate correction, waiver or amendment path.'),
            'Invoice arithmetic':('Commercial officer / supplier','Reconcile quantity multiplied by unit price against the invoice total, including any legitimate adjustments not modelled by this prototype.'),
            'Shipment deadline':('Commercial officer / bank','Verify the actual on-board date and latest shipment date. Escalate for specialist review; do not alter an actual shipment date to remove a flag.'),
            'Port of discharge consistency':('Commercial officer / carrier / bank','Reconcile Port of Discharge on the Bill of Lading with Letter of Credit Field 44F. If the vessel discharged at an alternate port, obtain a credit amendment or revised Bill of Lading before document submission.'),
            'Cargo gross weight consistency':('Commercial officer / carrier / supplier','Reconcile Cargo Gross Weight on the Packing List with the Bill of Lading. Confirm actual physical weighment and obtain a revised document before submission.'),
        }
        lines=['PORTSHIELD | OFFICER REVIEW DRAFT','Fictional demo shipment PS-DEMO-001','']
        for r in st.session_state.results:
            if r['status']=='Passed':continue
            owner,action=recommendations[r['check']]
            if r['status'] in ('Incomplete', 'Insufficient data'):action='Obtain readable source information and confirm missing values before completing this check.'
            with st.expander(r['status']+' | '+r['check'],expanded=True):
                st.write('**Suggested owner:** '+owner)
                st.write('**Evidence:** '+r['evidence'])
                st.write('**Next action:** '+action)
            lines.extend([r['check'],r['evidence'],'Suggested owner: '+owner,'Requested action: '+action,''])
        draft='Subject: Document review - please confirm outstanding items\n\nPlease review the items below against the actual shipment and credit terms. Confirm the appropriate correction or escalation before final submission.\n\n'+'\n'.join(lines)
        st.download_button('Download correction-request draft',draft,'portshield-correction-request.txt','text/plain')
        report={'prototype':'PortShield v0.9','fields':st.session_state.fields,'findings':st.session_state.results,'source_evidence':st.session_state.evidence,'scope':'Eight limited checks; human approval required'}
        st.download_button('Download full review data',json.dumps(report,indent=2),'portshield-review.json','application/json')
with about:
    st.subheader('Working today')
    st.write('Gemini PDF extraction and OpenRouter free text AI (provider API key required; review mandatory) • sample PDF upload • labelled text extraction • editable fields • eight deterministic checks • source text evidence • comparison with previous review • downloadable JSON report')
    st.subheader('Next milestones')
    st.write('Benchmark AI extraction on real layouts; PDF evidence viewer; versioned correction uploads; expert-reviewed rules and evaluation dataset.')
    st.caption('No financial savings, accuracy percentage or regulatory certification is claimed. Uploaded files are processed in the app session; do not upload confidential trade documents to this public prototype.')

