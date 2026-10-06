import streamlit as st


def aplicar_diseno():
    st.markdown("""<style>
    :root {color-scheme: light;}
    .stApp {background:#fff; color:#202020;}
    [data-testid="stSidebar"] {background:#f5f3ee; border-right:1px solid #e7e0d4;}
    .block-container {max-width:1280px; padding-top:2.4rem; padding-bottom:3rem;}
    h1,h2,h3 {color:#202020; letter-spacing:-.025em;}
    h1 {font-weight:700;}
    [data-testid="stMetric"] {background:#faf9f6; border:1px solid #e8e2d7; border-radius:14px; padding:1rem 1.2rem;}
    [data-testid="stMetric"] {border-top:3px solid #ac915e;}
    [data-testid="stSidebar"] [role="radiogroup"] {gap:.35rem;}
    [data-testid="stSidebar"] [role="radiogroup"] label {padding:.65rem .8rem; border-radius:9px;}
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {background:#eae3d5; color:#5f4824;}
    [data-testid="stExpander"] {border:1px solid #e8e2d7; border-radius:12px; background:#fff;}
    .stButton button,.stDownloadButton button {border-radius:9px; min-height:2.8rem;}
    button[kind="primary"],button[kind="primaryFormSubmit"] {background:#92713d; border-color:#92713d; color:white;}
    button[kind="primary"]:hover {background:#785c31; border-color:#785c31; color:white;}
    [data-testid="stAlert"] {border-radius:10px;}
    [data-testid="stAlert"][data-baseweb="notification"] {background:#f5f3ee; color:#4a453c;}
    .portada-anclaje {background:linear-gradient(115deg,#f8f6f1,#fff); border:1px solid #e7e0d4; border-radius:18px; padding:1.6rem 1.8rem; margin:1rem 0 1.4rem;}
    .portada-anclaje h2 {margin:0 0 .5rem; font-size:1.6rem;}
    .portada-anclaje p {color:#6b655a; max-width:760px; margin:0; line-height:1.65;}
    .portada-etapas {display:flex; flex-wrap:wrap; gap:.7rem; margin-top:1.2rem;}
    .portada-etapas span {border:1px solid #e2d8c7; border-radius:24px; padding:.35rem .8rem; color:#735b32; font-size:.8rem; background:#fff;}
    .marca-anclaje {font-size:.78rem; letter-spacing:.22em; color:#85683c; font-weight:700; margin-bottom:.7rem;}
    .intro-anclaje {border-bottom:1px solid #e7e0d4; padding-bottom:1rem; margin-bottom:1rem; color:#6b655a;}
    </style>""", unsafe_allow_html=True)
    st.markdown('<div class="marca-anclaje">ANCLAJE / EVIDENCIA Y TRAZABILIDAD</div>', unsafe_allow_html=True)


def mostrar_portada():
    st.markdown('''<div class="portada-anclaje">
    <h2>De tus documentos a una respuesta con respaldo.</h2>
    <p>Un espacio para organizar fuentes, comprobar afirmaciones y construir la evidencia de tu investigación. Empieza con tus documentos y avanza a tu ritmo.</p>
    <div class="portada-etapas"><span>01 / Organiza tus fuentes</span><span>02 / Consulta y contrasta</span><span>03 / Documenta la evidencia</span></div>
    </div>''', unsafe_allow_html=True)


def destacar_accion(key):
    # Los identificadores proceden exclusivamente del mapa de acciones de la app.
    st.markdown(f'''<style>
    .st-key-{key} button:not(:disabled) {{
        border:2px solid #92713d;
        box-shadow:0 0 0 4px #92713d20;
        font-weight:650;
    }}
    </style>''', unsafe_allow_html=True)
