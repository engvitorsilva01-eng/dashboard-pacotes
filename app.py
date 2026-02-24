import re
from datetime import date
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Painel de Pacotes", layout="wide")

# ========= CONFIG =========
APP_TITLE = "📦 Painel de Pacotes"
FILE_PATH = "CONTROLE_LOGISTICO_FORMATADO_COM_FORMULAS.xlsx"
SHEET_NAME = "PACOTES"

TRACK_COL = "Código de Rastreio"
STATUS_COL = "Status"
PACOTE_COL = "Pacote"
DT_ENVIO_COL = "Data do envio"
DT_RECEB_COL = "Data de recebimento"
DT_PEDIDO_COL = "Data do pedido"

CORREIOS_URL = "https://rastreamento.correios.com.br/app/index.php?objetos="
CACHE_TTL = 20  # atualiza rápido depois que você subir o .xlsx

# ========= FUNÇÕES =========
def limpar_codigo(valor) -> str:
    if pd.isna(valor):
        return ""
    s = str(valor).strip().upper()
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s

def normalizar_status(s):
    s = "" if pd.isna(s) else str(s).strip().lower()
    if "receb" in s or "entreg" in s:
        return "Recebido"
    if "trâns" in s or "transit" in s:
        return "Em trânsito"
    if s:
        return str(s).strip().title()
    return "Sem status"

@st.cache_data(ttl=CACHE_TTL)
def carregar_dados() -> pd.DataFrame:
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]

    # garante datas como datetime
    for c in [DT_ENVIO_COL, DT_RECEB_COL, DT_PEDIDO_COL]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    # rastreio
    if TRACK_COL in df.columns:
        df[TRACK_COL] = df[TRACK_COL].apply(limpar_codigo)
        df["Rastreio (URL)"] = df[TRACK_COL].apply(lambda x: CORREIOS_URL + x if x else "")

    # status padronizado
    if STATUS_COL in df.columns:
        df["Status (padronizado)"] = df[STATUS_COL].apply(normalizar_status)
    else:
        df["Status (padronizado)"] = "Sem status"

    # dias desde envio (até hoje)
    hoje = pd.Timestamp(date.today())
    if DT_ENVIO_COL in df.columns:
        df["Dias desde envio (hoje)"] = (hoje - df[DT_ENVIO_COL]).dt.days
    else:
        df["Dias desde envio (hoje)"] = pd.NA

    return df

def limpar_cache():
    carregar_dados.clear()

# ========= HEADER =========
st.title(APP_TITLE)
st.caption(
    "Atualize do mesmo jeito de sempre: substitua o arquivo .xlsx no GitHub. "
    "O painel reflete automaticamente (ou clique em **Atualizar agora**)."
)

top1, top2, top3 = st.columns([1, 1, 2])
with top1:
    if st.button("🔄 Atualizar agora"):
        limpar_cache()
        st.rerun()
with top2:
    st.caption(f"Atualização automática: ~{CACHE_TTL}s")
with top3:
    st.caption("Clique no código de rastreio para abrir no site dos Correios.")

df = carregar_dados()

# ========= SIDEBAR (filtros fáceis) =========
st.sidebar.header("Filtros")

status_opts = sorted(df["Status (padronizado)"].dropna().unique().tolist())
status_sel = st.sidebar.multiselect(
    "Status",
    options=status_opts,
    default=status_opts
)

somente_sem_rastreio = st.sidebar.checkbox("Somente sem rastreio", value=False)
busca = st.sidebar.text_input("Buscar (qualquer campo)", "")

# aplica filtros
fdf = df.copy()
fdf = fdf[fdf["Status (padronizado)"].isin(status_sel)]

if somente_sem_rastreio and TRACK_COL in fdf.columns:
    fdf = fdf[fdf[TRACK_COL].fillna("").astype(str).str.strip() == ""]

if busca.strip():
    term = busca.strip().lower()
    mask = pd.Series(False, index=fdf.index)
    for c in fdf.columns:
        if fdf[c].dtype == "object":
            mask = mask | fdf[c].fillna("").astype(str).str.lower().str.contains(term, regex=False)
    fdf = fdf[mask]

# ========= CARDS / RESUMO =========
st.subheader("Resumo")

total = len(fdf)
em_transito = int((fdf["Status (padronizado)"] == "Em trânsito").sum())
recebidos = int((fdf["Status (padronizado)"] == "Recebido").sum())
sem_rastreio = int((fdf.get(TRACK_COL, pd.Series([""]*len(fdf))).fillna("").astype(str).str.strip() == "").sum())

# média de dias desde envio só para "Em trânsito"
media_dias_envio = None
if "Dias desde envio (hoje)" in fdf.columns:
    emt = fdf[fdf["Status (padronizado)"] == "Em trânsito"]["Dias desde envio (hoje)"]
    emt = emt.dropna()
    if len(emt) > 0:
        media_dias_envio = float(emt.mean())

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Pacotes registrados", total)
c2.metric("Em trânsito", em_transito)
c3.metric("Recebidos", recebidos)
c4.metric("Sem rastreio", sem_rastreio)
c5.metric("Média dias desde envio (em trânsito)", "-" if media_dias_envio is None else f"{media_dias_envio:.1f} dias")

# ========= RASTREIO RÁPIDO =========
st.subheader("Rastreio")
if TRACK_COL in fdf.columns:
    codigos = [c for c in fdf[TRACK_COL].dropna().unique().tolist() if str(c).strip()]
    if codigos:
        code_sel = st.selectbox("Selecione um código para abrir", codigos)
        link = CORREIOS_URL + str(code_sel)
        st.markdown(f"➡️ **Abrir rastreio:** [{code_sel}]({link})")
        st.caption("Dica: copie o link abaixo se precisar mandar no WhatsApp:")
        st.code(link)
    else:
        st.info("Nenhum código de rastreio disponível com os filtros atuais.")

# ========= TABELA “LIMPA” =========
st.subheader("Lista (clara e fácil de entender)")

# escolhe só as colunas principais (se existirem)
cols = []
for c in [PACOTE_COL, "Status (padronizado)", TRACK_COL, DT_PEDIDO_COL, DT_ENVIO_COL, "Dias desde envio (hoje)", DT_RECEB_COL]:
    if c in fdf.columns:
        cols.append(c)

# adiciona coluna de link por último (opcional)
if "Rastreio (URL)" in fdf.columns:
    cols.append("Rastreio (URL)")

view = fdf[cols].copy() if cols else fdf.copy()

# Deixa o link mais “usável” (sem poluir)
if "Rastreio (URL)" in view.columns and TRACK_COL in view.columns:
    # Mostrar o link mas com texto "Rastrear"
    view["Rastrear"] = view["Rastreio (URL)"]
    view = view.drop(columns=["Rastreio (URL)"])

    if hasattr(st, "data_editor") and hasattr(st, "column_config") and hasattr(st.column_config, "LinkColumn"):
        st.data_editor(
            view,
            use_container_width=True,
            hide_index=True,
            disabled=True,
            column_config={
                "Rastrear": st.column_config.LinkColumn("Rastrear (Correios)", display_text="Abrir"),
            },
        )
    else:
        # fallback compatível
        st.dataframe(view, use_container_width=True)
else:
    st.dataframe(view, use_container_width=True)

# ========= EXPORT =========
st.download_button(
    "⬇️ Baixar CSV (com filtros)",
    data=fdf.to_csv(index=False).encode("utf-8"),
    file_name="pacotes_filtrados.csv",
    mime="text/csv"
)
