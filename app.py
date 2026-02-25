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
DT_PEDIDO_COL = "Data do pedido"
DT_ENVIO_COL = "Data do envio"
DT_RECEB_COL = "Data de recebimento"

CORREIOS_URL = "https://rastreamento.correios.com.br/app/index.php?objetos="
CACHE_TTL = 20

ALERTA_DIAS = 40  # <- depois de 40 dias: ATENÇÃO

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
    if "trâns" in s or "transit" in s or "transito" in s:
        return "Em trânsito"
    if s:
        return str(s).strip().title()
    return "Sem status"

def status_bolinha(stt: str) -> str:
    if stt == "Em trânsito":
        return "🟡 Em trânsito"
    if stt == "Recebido":
        return "🟢 Recebido"
    if stt == "Sem status":
        return "⚪ Sem status"
    return f"🔵 {stt}"

@st.cache_data(ttl=CACHE_TTL)
def carregar_dados() -> pd.DataFrame:
    try:
        df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, engine="openpyxl")
    except Exception as e:
        st.error("Não consegui abrir a planilha (.xlsx).")
        st.code(str(e))
        st.info(f"Confirme se o arquivo está na raiz do repositório com o nome: {FILE_PATH}")
        st.stop()

    df.columns = [str(c).strip() for c in df.columns]

    # datas SEM horas
    for c in [DT_PEDIDO_COL, DT_ENVIO_COL, DT_RECEB_COL]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce").dt.date

    # rastreio + link
    if TRACK_COL in df.columns:
        df[TRACK_COL] = df[TRACK_COL].apply(limpar_codigo)
        df["Rastreio (URL)"] = df[TRACK_COL].apply(lambda x: CORREIOS_URL + x if x else "")

    # status padronizado + bolinha
    if STATUS_COL in df.columns:
        df["Status (padronizado)"] = df[STATUS_COL].apply(normalizar_status)
    else:
        df["Status (padronizado)"] = "Sem status"

    df["Status"] = df["Status (padronizado)"].apply(status_bolinha)

    # dias desde envio até hoje
    hoje = date.today()
    if DT_ENVIO_COL in df.columns:
        def calc_dias_envio(d):
            if d is None or pd.isna(d):
                return None
            try:
                return (hoje - d).days
            except Exception:
                return None
        df["Dias desde envio"] = df[DT_ENVIO_COL].apply(calc_dias_envio)
    else:
        df["Dias desde envio"] = None

    return df

def limpar_cache():
    carregar_dados.clear()

def mask_busca(df: pd.DataFrame, term: str) -> pd.Series:
    term = term.strip().lower()
    if not term:
        return pd.Series([True] * len(df), index=df.index)
    m = pd.Series(False, index=df.index)
    for col in df.columns:
        if df[col].dtype == "object":
            m = m | df[col].fillna("").astype(str).str.lower().str.contains(term, regex=False)
    return m

# ========= UI =========
st.title(APP_TITLE)
st.caption(f"📅 Data da atualização: {date.today().strftime('%d/%m/%Y')}")

top1, top2, top3 = st.columns([1, 1, 2])
with top1:
    if st.button("🔄 Atualizar agora"):
        limpar_cache()
        st.rerun()
with top2:
    st.caption(f"Atualiza automaticamente: ~{CACHE_TTL}s")
with top3:
    st.caption("Atualize como sempre: suba o .xlsx no GitHub.")

df = carregar_dados()

# ========= FILTROS =========
st.sidebar.header("Filtros")
status_opts = sorted(df["Status (padronizado)"].dropna().unique().tolist())
status_sel = st.sidebar.multiselect("Status", options=status_opts, default=status_opts)
somente_sem_rastreio = st.sidebar.checkbox("Somente sem rastreio", value=False)
busca = st.sidebar.text_input("Buscar", "")

fdf = df.copy()
fdf = fdf[fdf["Status (padronizado)"].isin(status_sel)]

if somente_sem_rastreio and TRACK_COL in fdf.columns:
    fdf = fdf[fdf[TRACK_COL].fillna("").astype(str).str.strip() == ""]

fdf = fdf[mask_busca(fdf, busca)]

# ========= RESUMO =========
st.subheader("Resumo")

total = len(fdf)
em_transito = int((fdf["Status (padronizado)"] == "Em trânsito").sum())
recebidos = int((fdf["Status (padronizado)"] == "Recebido").sum())
sem_rastreio = int((fdf.get(TRACK_COL, pd.Series([""] * len(fdf))).fillna("").astype(str).str.strip() == "").sum())

media_dias = None
max_dias = None
emt_series = fdf[(fdf["Status (padronizado)"] == "Em trânsito")]["Dias desde envio"].dropna()
if len(emt_series) > 0:
    media_dias = float(emt_series.mean())
    max_dias = int(emt_series.max())

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Pacotes registrados", total)
c2.metric("🟡 Em trânsito", em_transito)
c3.metric("🟢 Recebidos", recebidos)
c4.metric("Sem rastreio", sem_rastreio)
c5.metric("Média dias (em trânsito)", "-" if media_dias is None else f"{media_dias:.1f}")
c6.metric("Maior tempo (em trânsito)", "-" if max_dias is None else f"{max_dias} dias")

# ========= ATENÇÃO 40+ DIAS =========
st.subheader("⚠️ Atenção")

atencao = fdf[
    (fdf["Status (padronizado)"] == "Em trânsito")
    & (fdf["Dias desde envio"].notna())
    & (fdf["Dias desde envio"] >= ALERTA_DIAS)
].copy()

if len(atencao) == 0:
    st.success(f"Nenhum pacote em trânsito com {ALERTA_DIAS}+ dias desde o envio ✅")
else:
    st.error(f"⚠️ ATENÇÃO: {len(atencao)} pacote(s) com {ALERTA_DIAS}+ dias em trânsito!")

    cols_alerta = [c for c in [PACOTE_COL, TRACK_COL, DT_ENVIO_COL, "Dias desde envio"] if c in atencao.columns]
    atencao = atencao.sort_values("Dias desde envio", ascending=False)
    st.dataframe(atencao[cols_alerta], use_container_width=True)

# ========= TOP 5 MAIS ANTIGOS EM TRÂNSITO =========
st.subheader("Top 5 mais antigos em trânsito")

top5 = fdf[
    (fdf["Status (padronizado)"] == "Em trânsito")
    & (fdf["Dias desde envio"].notna())
].copy()

if len(top5) == 0:
    st.info("Nenhum pacote em trânsito com data de envio preenchida.")
else:
    top5 = top5.sort_values("Dias desde envio", ascending=False).head(5)
    cols_top = []
    for c in [PACOTE_COL, TRACK_COL, DT_ENVIO_COL, "Dias desde envio"]:
        if c in top5.columns:
            cols_top.append(c)

    # adiciona link direto
    if "Rastreio (URL)" in top5.columns:
        top5["Rastrear"] = top5["Rastreio (URL)"]
        cols_top.append("Rastrear")

    # Tabela com link (se suportado)
    if hasattr(st, "data_editor") and hasattr(st, "column_config") and hasattr(st.column_config, "LinkColumn"):
        cfg = {}
        if "Rastrear" in top5.columns:
            cfg["Rastrear"] = st.column_config.LinkColumn("Rastrear (Correios)", display_text="Abrir")
        st.data_editor(
            top5[cols_top],
            use_container_width=True,
            hide_index=True,
            disabled=True,
            column_config=cfg
        )
    else:
        st.dataframe(top5[cols_top], use_container_width=True)

# ========= RASTREIO RÁPIDO =========
st.subheader("Rastreio (abrir e copiar)")

if TRACK_COL in fdf.columns:
    codigos = [c for c in fdf[TRACK_COL].dropna().unique().tolist() if str(c).strip()]
    if codigos:
        code_sel = st.selectbox("Selecione um código", codigos)
        link = CORREIOS_URL + str(code_sel)
        st.markdown(f"➡️ **Abrir rastreio:** [{code_sel}]({link})")
        st.code(link)
    else:
        st.info("Nenhum código disponível com os filtros atuais.")
else:
    st.info("Coluna de rastreio não encontrada.")

# ========= LISTA =========
st.subheader("Lista (clara)")

cols_principais = []
for c in [PACOTE_COL, "Status", TRACK_COL, DT_PEDIDO_COL, DT_ENVIO_COL, "Dias desde envio", DT_RECEB_COL]:
    if c in fdf.columns:
        cols_principais.append(c)

mostrar_link = st.checkbox("Mostrar link do rastreio na lista completa", value=False)
view = fdf[cols_principais].copy() if cols_principais else fdf.copy()

if mostrar_link and "Rastreio (URL)" in fdf.columns:
    view["Rastrear"] = fdf["Rastreio (URL)"]
    if hasattr(st, "data_editor") and hasattr(st, "column_config") and hasattr(st.column_config, "LinkColumn"):
        st.data_editor(
            view.assign(Rastrear=view["Rastrear"]),
            use_container_width=True,
            hide_index=True,
            disabled=True,
            column_config={"Rastrear": st.column_config.LinkColumn("Rastrear (Correios)", display_text="Abrir")},
        )
    else:
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
