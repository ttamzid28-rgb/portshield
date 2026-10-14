import io,json,re,zipfile
import html
from pathlib import Path
import streamlit as st
from pypdf import PdfReader
from checks import audit

st.set_page_config(page_title='PortShield AI | Document Readiness',page_icon='🛡️',layout='wide')
st.markdown("""<style>
.stApp{background:#f5f7fb}h1,h2,h3{color:#142b45}div[data-testid="stSidebar"]{background:#eaf0f7}
.stButton>button{border-radius:8px}div[data-testid="stMetric"]{background:white;padding:16px;border:1px solid #dfe6ef;border-radius:10px}
.hero{background:#142b45;color:white;padding:25px 30px;border-radius:14px;margin-bottom:18px}.hero h1{color:white;font-size:32px;margin:4px 0}.hero p{color:#d4e5f4;margin:4px 0}.eyebrow{font-size:12px;letter-spacing:2px;color:#87d9d2}
.stagebar{padding:12px 16px;background:#e5f3f1;border:1px solid #c5e3df;border-radius:8px;color:#146c63;margin-bottom:18px}
</style>""",unsafe_allow_html=True)
st.markdown('<div class="hero"><div class="eyebrow">PORTSHIELD AI / IMPORT OPERATIONS</div><h1>Trade document review workbench</h1><p>Find conflicts. Review the evidence. Prepare corrections before submission.</p></div>',unsafe_allow_html=True)
st.caption('LIVE PROTOTYPE v0.2 · Six deterministic checks · Sample/text-PDF mode · AI extraction planned')
fields=['lc_currency','lc_amount','latest_shipment_date','invoice_currency','invoice_total','invoice_quantity','unit_price','packing_quantity','packing_container','bl_container','on_board_date']
base={'lc_currency':'USD','lc_amount':'25000','latest_shipment_date':'2026-10-20','invoice_currency':'USD','invoice_total':'27000','invoice_quantity':'100','unit_price':'250','packing_quantity':'100','packing_container':'ABCD1234567','bl_container':'ABCD1234568','on_board_date':'2026-10-21'}
fixed={**base,'invoice_total':'25000','bl_container':'ABCD1234567'}
with st.sidebar:
    st.title('PortShield AI')
    st.caption('COMMERCIAL DESK')
    st.header('Shipment workspace')
    st.caption('Fictional polymer import • Chattogram')
    scenario=st.selectbox('Sample packet',['Problem shipment','Corrected shipment','Unreadable field'])
    if st.button('Load sample',type='primary') or 'fields' not in st.session_state:
        sample=dict(fixed if scenario=='Corrected shipment' else base)
        if scenario=='Unreadable field':sample['invoice_total']=''
        st.session_state.previous=st.session_state.pop('results',st.session_state.get('previous',[]))
        st.session_state.fields=sample;st.session_state.evidence={k:f'Fictional sample field: {k} = {v}' for k,v in sample.items()}
    st.download_button('Download sample PDFs',(Path(__file__).parent / 'sample_documents.zip').read_bytes(),'portshield-sample-documents.zip','application/zip')
    st.caption('Upload the sample PDFs below to exercise actual text extraction. Other layouts may need manual entry.')
overview,upload,review,actions,about=st.tabs(['Shipment overview','Document intake','Review & evidence','Corrections & report','Scope & roadmap'])
current=audit(st.session_state.fields)
with overview:
    st.markdown('<div class="stagebar">01 Intake → 02 Confirm fields → 03 Review exceptions → 04 Prepare corrections</div>',unsafe_allow_html=True)
    st.subheader('PS-DEMO-001 | Polymer raw material import')
    st.caption('Fictional demonstration case · Destination: Chattogram · No bank or customs approval implied')
    cols=st.columns(3)
    for col,status in zip(cols,['Passed','Review required','Incomplete']):
        col.metric(status,sum(x['status']==status for x in current))
    st.subheader('Cross-document reconciliation')
    d=st.session_state.fields
    def v(k): return d.get(k,'') or 'Not available'
    rows=[
        {'Field':'Currency','L/C':v('lc_currency'),'Invoice':v('invoice_currency'),'Packing list':'—','B/L':'—'},
        {'Field':'Amount / credit limit','L/C':v('lc_amount'),'Invoice':v('invoice_total'),'Packing list':'—','B/L':'—'},
        {'Field':'Quantity (equivalent units)','L/C':'—','Invoice':v('invoice_quantity'),'Packing list':v('packing_quantity'),'B/L':'—'},
        {'Field':'Container','L/C':'—','Invoice':'—','Packing list':v('packing_container'),'B/L':v('bl_container')},
        {'Field':'Shipment date / deadline','L/C':v('latest_shipment_date'),'Invoice':'—','Packing list':'—','B/L':v('on_board_date')},
    ]
    st.dataframe(rows,hide_index=True,use_container_width=True)
    st.caption('Matrix reflects loaded or confirmed fields. Confirm source values in Review & evidence before relying on a result.')
    st.subheader('Exception queue')
    pending=[r for r in current if r['status']!='Passed']
    if pending:st.dataframe(pending,hide_index=True,use_container_width=True)
    else:st.success('No issues detected in the six supported checks. Human review remains required.')
    st.info('Start with the sample packet, or upload the supplied PDFs in Document intake. Change confirmed values, run checks, then open Corrections & report.')
with upload:
    st.subheader('Upload a document packet')
    st.caption('Supported prototype format: text-based PDFs with field labels such as Invoice Total: 25000. Scanned PDFs are not supported yet. Use fictional documents only.')
    files=st.file_uploader('PDF documents',type=['pdf'],accept_multiple_files=True)
    if st.button('Extract uploaded text'):
        extracted={}; evidence={}
        if not files:st.warning('Upload at least one PDF.')
        for f in files or []:
            try:
                reader=PdfReader(io.BytesIO(f.getvalue()))
                if len(reader.pages)>50:st.warning(f'{f.name}: limit 50 pages');continue
                for n,p in enumerate(reader.pages,1):
                    text=p.extract_text() or ''
                    for key in fields:
                        label=key.replace('_',' ')
                        match=re.search(r'(?im)^\s*'+re.escape(label)+r'\s*:\s*([^\n\r]+)',text)
                        if match:
                            value=match.group(1).strip()
                            if key in extracted and extracted[key]!=value:extracted[key]='';evidence[key]='Conflicting extracted values: manual confirmation required'
                            else:extracted[key]=value;evidence[key]=f'{f.name} · page {n} · {match.group(0).strip()}'
            except Exception:st.warning(f'Could not read {f.name}. Please use an unencrypted text PDF.')
        if files:
            st.session_state.previous=st.session_state.pop('results',st.session_state.get('previous',[]))
            st.session_state.fields={k:extracted.get(k,'') for k in fields};st.session_state.evidence=evidence
            st.success(f'Extracted {len(extracted)} labelled fields. Open Review workspace to confirm and run checks.')
with review:
    st.subheader('Review extracted fields')
    st.caption('Amounts use the same currency; quantities use the same unit. The configured amount limit must include any applicable tolerance. No prior credit utilisation is modelled.')
    with st.form('review_form'):
        vals={};cols=st.columns(3)
        for i,k in enumerate(fields):
            with cols[i%3]:vals[k]=st.text_input(k.replace('_',' ').title(),value=st.session_state.fields.get(k,''))
        submitted=st.form_submit_button('Run document checks',type='primary')
    if submitted:
        st.session_state.previous=st.session_state.get('results',st.session_state.get('previous',[]))
        st.session_state.results=audit(vals);st.session_state.fields=vals
    if 'results' in st.session_state:
        results=st.session_state.results
        cols=st.columns(3)
        for col,status in zip(cols,['Passed','Review required','Incomplete']):col.metric(status,sum(x['status']==status for x in results))
        previous={x['check']:x['status'] for x in st.session_state.get('previous',[])}
        resolved=[x['check'] for x in results if x['status']=='Passed' and previous.get(x['check'])=='Review required']
        if resolved:st.success('Resolved since previous run: '+', '.join(resolved))
        for result in results:
            with st.expander(f"{result['status']} — {result['check']}",expanded=result['status']!='Passed'):
                st.write(result['evidence']);st.caption('Evidence refers to confirmed values; edits require reviewer verification against the source.')
        with st.expander('Source extraction evidence'):
            for k,v in st.session_state.evidence.items():st.write(f'**{k}**: {v}')
        report={'prototype':'PortShield v0.2','scope':'Six limited checks; human approval required','fields':st.session_state.fields,'findings':results,'source_evidence':st.session_state.evidence}
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
        }
        lines=['PORTSHIELD | OFFICER REVIEW DRAFT','Fictional demo shipment PS-DEMO-001','']
        for r in st.session_state.results:
            if r['status']=='Passed':continue
            owner,action=recommendations[r['check']]
            if r['status']=='Incomplete':action='Obtain readable source information and confirm missing values before completing this check.'
            with st.expander(r['status']+' | '+r['check'],expanded=True):
                st.write('**Suggested owner:** '+owner)
                st.write('**Evidence:** '+r['evidence'])
                st.write('**Next action:** '+action)
            lines.extend([r['check'],r['evidence'],'Suggested owner: '+owner,'Requested action: '+action,''])
        draft='Subject: Document review - please confirm outstanding items\n\nPlease review the items below against the actual shipment and credit terms. Confirm the appropriate correction or escalation before final submission.\n\n'+'\n'.join(lines)
        st.download_button('Download correction-request draft',draft,'portshield-correction-request.txt','text/plain')
        report={'prototype':'PortShield v0.2','fields':st.session_state.fields,'findings':st.session_state.results,'source_evidence':st.session_state.evidence,'scope':'Six limited checks; human approval required'}
        st.download_button('Download full review data',json.dumps(report,indent=2),'portshield-review.json','application/json')
with about:
    st.subheader('Working today')
    st.write('Sample PDF upload • labelled text extraction • editable fields • six deterministic checks • source text evidence • comparison with previous review • downloadable JSON report')
    st.subheader('Next milestones')
    st.write('AI extraction for varied layouts; scanned-document handling; PDF evidence viewer; versioned correction uploads; expert-reviewed rules and evaluation dataset.')
    st.caption('No financial savings, accuracy percentage or regulatory certification is claimed. Uploaded files are processed in the app session; do not upload confidential trade documents to this public prototype.')
