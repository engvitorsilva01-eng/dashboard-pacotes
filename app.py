import re
import pandas as pd
import streamlit as st

# Auto refresh (opcional). Se não tiver a lib, o app continua sem auto refresh.
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

st.set_page_config(page_title="Painel de Pacotes", layout="wide")

# =========================
# CONFIG GERAL
# =========================
APP_TITLE = "📦 Painel de Pacotes"
DEFAULT_TTL_SECONDS = 60            # recarrega os dados a cada X segundos (cache)
AUTOREFRESH_EVERY_SECONDS = 60      # recarrega a tela a cada X segundos (opcional)

# =========================
# DADOS: escolha a fonte
# =========================
DATA_MODE = "csv_local"  # "csv_local" ou "csv_url"

CSV_LOCAL_PATH = "pacotes.csv"
CSV_URL = "https://SEU-LINK-CSV-AQUI"

# =========================
# COLUNAS (ajuste conforme sua planilha)
# =========================
CLIENT_COL = "Cliente"
STATUS_COL = "Status"

# ✅ Nome exato informado por você:
TRACK_COL = "Código de Rastreio"

# Link oficial de rastreio (abre já com o código)
CORREIOS_TRACK_URL = "https://rastreamento.correios.com.br/app/index.php?objetos="

# =========================
# FUNÇÕES
# =========================
def limpar_codigo_rastreio(valor) -> str:
    """Remove espaços, hífens e qualquer caractere que não seja A-Z/0-9."""
    if pd.isna(valor):
        return ""
    s = str(valor).strip().upper()
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s

def login_gate() -> bool:
    """Login simples com 1 senha em st.secrets['APP_PASSWORD']."""
    st.sidebar.header("🔒 Acesso")
    if "authed" not in st.session_state:
        st.session_state.authed = False

    if st.session_state.authed:
        st.sidebar.success("Acesso liberado")
        if st.sidebar.button("Sair"):
            st.session_state.authed = False
            st.rerun()
        return True

    pwd = st.sidebar.text_input("Senha", type="password")
    if st.sidebar.button("Entrar"):
        real_pwd = st.secrets.get("APP_PASSWORD", "")
        if pwd and real_pwd and pwd == real_pwd:
            st.session_state.authed = True
            st.rerun()
        else:
            st.sidebar.error("Senha incorreta.")
    return False

@st.cache_data(ttl=DEFAULT_TTL_SECONDS)
def load_data() -> pd.DataFrame:
    """Carrega CSV e cria coluna de link clicável para rastreio."""
    if DATA_MODE == "csv_url":
        df = pd.read_csv(CSV_URL)
    else:
        # Se der erro de acento/encoding, troque para: encoding="utf-8-sig"
        df = pd.read_csv(CSV_LOCAL_PATH)

    df.columns = [c.strip() for c in df.columns]

    # Cria a coluna de link clicável (se existir coluna de rastreio)
    if TRACK_COL in df.columns:
        df[TRACK_COL] = df[TRACK_COL].apply(limpar_codigo_rastreio)
        df["Rastreio (link)"] = df[TRACK_COL].apply(
            lambda code: (CORREIOS_TRACK_URL + code) if code else ""
        )

    return df

def clear_cache():
    load_data.clear()

def build_search_mask(df: pd.DataFrame, term: str) -> pd.Series:
    """Cria máscara de busca em colunas texto."""
    term = term.strip().lower()
    if not term:
        return pd.Series([True] * len(df), index=df.index)

    mask = pd.Series([False] * len(df), index=df.index)
    for col in df.columns:
        if df[col].dtype == "object":
            mask = mask | df[col].fillna("").astype(str).str.lower().str.contains(term, regex=False)
    return mask

# =========================
# UI
# =========================
st.title(APP_TITLE)

# Auto refresh (opcional)
if st_autorefresh is not None:
    st_autorefresh(interval=AUTOREFRESH_EVERY_SECONDS * 1000, key="auto_refresh")

if not login_gate():
    st.stop()

top1, top2, top3, top4 = st.columns([1, 1, 1, 2])
with top1:
    if st.button("🔄 Atualizar agora"):
        clear_cache()
        st.rerun()
with top2:
    st.caption(f"Cache dados: {DEFAULT_TTL_SECONDS}s")
with top3:
    st.caption(f"Auto refresh: {AUTOREFRESH_EVERY_SECONDS}s" if st_autorefresh else "Auto refresh: desativado")
with top4:
    st.caption("Dica: clique no código de rastreio para abrir o site.")

df = load_data()

# =========================
# FILTROS
# =========================
st.subheader("Filtros")
c1, c2, c3, c4 = st.columns(4)

# Cliente
clientes = ["Todos"]
if CLIENT_COL in df.columns:
    clientes += sorted([x for x in df[CLIENT_COL].dropna().unique()])

# Status
status_list = ["Todos"]
if STATUS_COL in df.columns:
    status_list += sorted([x for x in df[STATUS_COL].dropna().unique()])

with c1:
    cliente_sel = st.selectbox("Cliente", clientes)
with c2:
    status_sel = st.selectbox("Status", status_list)
with c3:
    busca = st.text_input("Buscar (qualquer campo)", "")
with c4:
    cols_default = list(df.columns)
    # Prioriza mostrar campos comuns no começo
    prefer = [CLIENT_COL, "Pedido", TRACK_COL, STATUS_COL]
    prefer = [p for p in prefer if p in cols_default]
    rest = [c for c in cols_default if c not in prefer and c != "Rastreio (link)"]
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

mask_busca = build_search_mask(fdf, busca)
fdf = fdf[mask_busca]

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

# Se existir rastreio, a própria coluna "Código de Rastreio" vira clicável
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
        display_text=r".*objetos=([A-Z0-9]+)$"  # mostra só o código, mas clica no link
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
