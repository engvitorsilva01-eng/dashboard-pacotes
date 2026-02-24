import re
import pandas as pd
import streamlit as st

# Auto refresh (opcional). Se não tiver a lib, o app funciona sem auto refresh.
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

st.set_page_config(page_title="Painel de Pacotes", layout="wide")

# =========================
# CONFIG
# =========================
APP_TITLE = "📦 Painel de Pacotes"
DEFAULT_TTL_SECONDS = 60            # atualiza dados no cache a cada X segundos
AUTOREFRESH_EVERY_SECONDS = 60      # recarrega a tela a cada X segundos (opcional)

# =========================
# DADOS
# =========================
DATA_MODE = "csv_local"  # "csv_local" ou "csv_url"
CSV_LOCAL_PATH = "pacotes.csv"
CSV_URL = "https://SEU-LINK-CSV-AQUI"

# =========================
# COLUNAS (como está na planilha)
# =========================
CLIENT_COL = "Cliente"
STATUS_COL = "Status"
TRACK_COL = "Código de Rastreio"   # <- você confirmou esse nome

CORREIOS_TRACK_URL = "https://rastreamento.correios.com.br/app/index.php?objetos="

# =========================
# FUNÇÕES
# =========================
def limpar_codigo_rastreio(valor) -> str:
    if pd.isna(valor):
        return ""
    s = str(valor).strip().upper()
    s = re.sub(r"[^A-Z0-9]", "", s)  # remove espaços, hífen, etc.
    return s

@st.cache_data(ttl=DEFAULT_TTL_SECONDS)
def load_data() -> pd.DataFrame:
    if DATA_MODE == "csv_url":
        df = pd.read_csv(CSV_URL)
    else:
        # se der problema com acento, use: pd.read_csv(CSV_LOCAL_PATH, encoding="utf-8-sig")
        df = pd.read_csv(CSV_LOCAL_PATH)

    df.columns = [c.strip() for c in df.columns]

    # Coluna de link clicável do rastreio
    if TRACK_COL in df.columns:
        df[TRACK_COL] = df[TRACK_COL].apply(limpar_codigo_rastreio)
        df["Rastreio (link)"] = df[TRACK_COL].apply(
            lambda code: (CORREIOS_TRACK_URL + code) if code else ""
        )

    return df

def clear_cache():
    load_data.clear()

def build_search_mask(df: pd.DataFrame, term: str) -> pd.Series:
    term = term.strip().lower()
    if not term:
        return pd.Series([True] * len(df), index=df.index)

    mask = pd.Series([False] * len(df), index=df.index)
    for col in df.columns:
        if df[col].dtype == "object":
            mask = mask | df[col].fillna("").astype(str).str.lower().str.contains(term, regex=False)
    return mask

def get_query_params():
    # Compatibilidade com versões diferentes do Streamlit
    try:
        qp = st.query_params  # versões novas
        return {k: str(v) for k, v in qp.items()}
    except Exception:
        qp = st.experimental_get_query_params()  # versões antigas
        # qp vem como dict[str, list[str]]
        return {k: (v[0] if isinstance(v, list) and v else str(v)) for k, v in qp.items()}

# =========================
# UI
# =========================
st.title(APP_TITLE)

# Auto refresh (opcional)
if st_autorefresh is not None:
    st_autorefresh(interval=AUTOREFRESH_EVERY_SECONDS * 1000, key="auto_refresh")

top1, top2, top3 = st.columns([1, 1, 2])
with top1:
    if st.button("🔄 Atualizar agora"):
        clear_cache()
        st.rerun()
with top2:
    st.caption(f"Cache dados: {DEFAULT_TTL_SECONDS}s")
with top3:
    st.caption("Clique no código de rastreio para abrir o site.")

df = load_data()
qp = get_query_params()

# =========================
# FILTROS
# =========================
st.subheader("Filtros")
c1, c2, c3, c4 = st.columns(4)

clientes = ["Todos"]
if CLIENT_COL in df.columns:
    clientes += sorted([x for x in df[CLIENT_COL].dropna().unique()])

status_list = ["Todos"]
if STATUS_COL in df.columns:
    status_list += sorted([x for x in df[STATUS_COL].dropna().unique()])

# ✅ Opcional: se você mandar pro cliente um link com ?cliente=NOME,
# ele já abre filtrado (não é “segurança”, mas facilita).
cliente_forcado = qp.get("cliente", "").strip()
status_forcado = qp.get("status", "").strip()

with c1:
    if cliente_forcado and CLIENT_COL in df.columns:
        cliente_sel = cliente_forcado
        st.text_input("Cliente (fixo pelo link)", value=cliente_sel, disabled=True)
    else:
        cliente_sel = st.selectbox("Cliente", clientes)

with c2:
    if status_forcado and STATUS_COL in df.columns:
        status_sel = status_forcado
        st.text_input("Status (fixo pelo link)", value=status_sel, disabled=True)
    else:
        status_sel = st.selectbox("Status", status_list)

with c3:
    busca = st.text_input("Buscar (qualquer campo)", qp.get("busca", ""))

with c4:
    cols_default = [c for c in df.columns if c != "Rastreio (link)"]
    prefer = [CLIENT_COL, "Pedido", TRACK_COL, STATUS_COL]
    prefer = [p for p in prefer if p in cols_default]
    rest = [c for c in cols_default if c not in prefer]
    cols_default = prefer + rest

    show_cols = st.multiselect(
        "Colunas para exibir",
        options=[c for c in df.columns if c != "Rastreio (link)"],
        default=cols_default[:8] if len(cols_default) > 8 else cols_default
    )

fdf = df.copy()

if cliente_sel != "Todos" and CLIENT_COL in fdf.columns:
    fdf = fdf[fdf[CLIENT_COL] == cliente_sel]

if status_sel != "Todos" and STATUS_COL in fdf.columns:
    fdf = fdf[fdf[STATUS_COL] == status_sel]

fdf = fdf[build_search_mask(fdf, busca)]

# =========================
# RESUMO
# =========================
st.subheader("Resumo")
m1, m2, m3, m4 = st.columns(4)

total = len(fdf)
m1.metric("Total (com filtros)", total)

if STATUS_COL in fdf.columns:
    entregues = fdf[STATUS_COL].astype(str).str.lower().str.contains("entreg", na=False).sum()
    transito = fdf[STATUS_COL].astype(str).str.lower().str.contains("transit|enviado|rota", na=False).sum()
    outros = total - entregues - transito
    m2.metric("Entregues", int(entregues))
    m3.metric("Em trânsito", int(transito))
    m4.metric("Outros", int(outros))
else:
    m2.metric("Entregues", "-")
    m3.metric("Em trânsito", "-")
    m4.metric("Outros", "-")

# =========================
# TABELA (código clicável)
# =========================
st.subheader("Lista")

if not show_cols:
    show_cols = [c for c in fdf.columns if c != "Rastreio (link)"]

table_df = fdf.copy()
column_config = {}

# Torna a coluna "Código de Rastreio" clicável
if "Rastreio (link)" in table_df.columns and TRACK_COL in table_df.columns:
    table_df["Código (clique)"] = table_df["Rastreio (link)"]

    display_cols = []
    for c in show_cols:
        if c == TRACK_COL:
            display_cols.append("Código (clique)")
        else:
            if c in table_df.columns:
                display_cols.append(c)

    if "Código (clique)" not in display_cols:
        display_cols.insert(0, "Código (clique)")

    column_config["Código (clique)"] = st.column_config.LinkColumn(
        "Código de Rastreio (clique)",
        display_text=r".*objetos=([A-Z0-9]+)$"
    )
else:
    display_cols = show_cols

st.data_editor(
    table_df[display_cols],
    use_container_width=True,
    hide_index=True,
    disabled=True,
    column_config=column_config
)

# =========================
# EXPORT
# =========================
st.download_button(
    "⬇️ Baixar CSV (com filtros)",
    data=fdf.to_csv(index=False).encode("utf-8"),
    file_name="pacotes_filtrados.csv",
    mime="text/csv"
)
