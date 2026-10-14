import io,json,re,zipfile
from pathlib import Path
import streamlit as st
from pypdf import PdfReader
from checks import audit

st.set_page_config(page_title='PortShield AI | Document Readiness',page_icon='🛡️',layout='wide')
st.markdown('''<style>.stApp{background:#f5f8fc}h1,h2,h3{color:#102b46}.stButton>button{border-radius:10px}div[data-testid="stMetric"]{background:white;padding:18px;border-radius:12px}</style>''',unsafe_allow_html=True)
st.caption('PORTSHIELD AI  /  SUMMIT PROTOTYPE  /  v0.1')
st.title('Catch document conflicts before submission.')
st.write('Review a sample import packet, inspect its evidence and verify corrections.')
st.info('Working rules prototype using fictional shipments. AI extraction is planned and is not active in this version. This is not bank or customs approval.')
fields=['lc_currency','lc_amount','latest_shipment_date','invoice_currency','invoice_total','invoice_quantity','unit_price','packing_quantity','packing_container','bl_container','on_board_date']
base={'lc_currency':'USD','lc_amount':'25000','latest_shipment_date':'2026-10-20','invoice_currency':'USD','invoice_total':'27000','invoice_quantity':'100','unit_price':'250','packing_quantity':'100','packing_container':'ABCD1234567','bl_container':'ABCD1234568','on_board_date':'2026-10-21'}
fixed={**base,'invoice_total':'25000','bl_container':'ABCD1234567'}
with st.sidebar:
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
review,upload,about=st.tabs(['Review workspace','Upload documents','Scope & roadmap'])
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
    st.subheader('Confirm fields, then run checks')
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
        report={'prototype':'PortShield v0.1','scope':'Six limited checks; human approval required','fields':st.session_state.fields,'findings':results,'source_evidence':st.session_state.evidence}
        st.download_button('Download review report (JSON)',json.dumps(report,indent=2),'portshield-review.json','application/json')
with about:
    st.subheader('Working today')
    st.write('Sample PDF upload • labelled text extraction • editable fields • six deterministic checks • source text evidence • comparison with previous review • downloadable JSON report')
    st.subheader('Next milestones')
    st.write('AI extraction for varied layouts; scanned-document handling; PDF evidence viewer; versioned correction uploads; expert-reviewed rules and evaluation dataset.')
    st.caption('No financial savings, accuracy percentage or regulatory certification is claimed. Uploaded files are processed in the app session; do not upload confidential trade documents to this public prototype.')
