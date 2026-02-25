import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st


# ========= CONFIG =========
APP_TITLE = "📦 Painel de Pacotes"
BRAND_NAME = "MVSPORTSAC"
BRAND_HANDLE = "mvsportsac"
LOGO_PATH = "logo.png"  # precisa existir no repo

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
ALERTA_DIAS = 40
TZ = ZoneInfo("America/Fortaleza")


# ========= PAGE CONFIG (sem erro) =========
# Se a logo não existir, o Streamlit pode falhar no page_icon.
# Então checamos e usamos um emoji como fallback.
try:
    st.set_page_config(
        page_title=f"Painel de Pacotes - {BRAND_NAME}",
        layout="wide",
        page_icon=LOGO_PATH,
    )
except Exception:
    st.set_page_config(
        page_title=f"Painel de Pacotes - {BRAND_NAME}",
        layout="wide",
        page_icon="📦",
    )


# ========= FUNÇÕES =========
def hoje_local() -> date:
    return datetime.now(TZ).date()


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

    # Datas SEM horas
    for c in [DT_PEDIDO_COL, DT_ENVIO_COL, DT_RECEB_COL]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce").dt.date

    # Código de rastreio + URL
    if TRACK_COL in df.columns:
        df[TRACK_COL] = df[TRACK_COL].apply(limpar_codigo)
        df["Rastreio (URL)"] = df[TRACK_COL].apply(lambda x: CORREIOS_URL + x if x else "")

    # Status padronizado + bolinha
    if STATUS_COL in df.columns:
        df["Status (padronizado)"] = df[STATUS_COL].apply(normalizar_status)
    else:
        df["Status (padronizado)"] = "Sem status"
    df["Status"] = df["Status (padronizado)"].apply(status_bolinha)

    # Dias desde envio (para em trânsito)
    hoje = hoje_local()

    if DT_ENVIO_COL in df.columns:
        def calc_dias_desde_envio(d):
            if d is None or pd.isna(d):
                return None
            try:
                return (hoje - d).days
            except Exception:
                return None

        df["Dias desde envio"] = df[DT_ENVIO_COL].apply(calc_dias_desde_envio)
    else:
        df["Dias desde envio"] = None

    # Dias do trajeto (APENAS para Recebido)
    df["Dias do trajeto"] = None
    if (DT_ENVIO_COL in df.columns) and (DT_RECEB_COL in df.columns):
        def calc_trajeto(row):
            stt = row.get("Status (padronizado)", "")
            envio = row.get(DT_ENVIO_COL, None)
            receb = row.get(DT_RECEB_COL, None)

            if stt != "Recebido":
                return None
            if envio is None or pd.isna(envio) or receb is None or pd.isna(receb):
                return None
            try:
                return (receb - envio).days
            except Exception:
                return None

        df["Dias do trajeto"] = df.apply(calc_trajeto, axis=1)

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


# ========= UI HEADER (LOGO + TÍTULO) =========
col_logo, col_title = st.columns([1, 6], vertical_alignment="center")

with col_logo:
    try:
        st.image(LOGO_PATH, width=120)
    except Exception:
        st.write("")

with col_title:
    st.title(APP_TITLE)
    st.caption(f"📅 Data da atualização: {hoje_local().strftime('%d/%m/%Y')}")


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
busca = st.sidebar.text_input("Buscar (geral)", "")

fdf = df.copy()
fdf = fdf[fdf["Status (padronizado)"].isin(status_sel)]

if somente_sem_rastreio and TRACK_COL in fdf.columns:
    fdf = fdf[fdf[TRACK_COL].fillna("").astype(str).str.strip() == ""]

fdf = fdf[mask_busca(fdf, busca)]


# ========= RESUMO =========
st.subheader("Resumo")

hoje = hoje_local()
total = len(fdf)
em_transito = int((fdf["Status (padronizado)"] == "Em trânsito").sum())
recebidos_total = int((fdf["Status (padronizado)"] == "Recebido").sum())

recebidos_hoje = 0
if DT_RECEB_COL in fdf.columns:
    recebidos_hoje = int(((fdf["Status (padronizado)"] == "Recebido") & (fdf[DT_RECEB_COL] == hoje)).sum())

sem_rastreio = 0
if TRACK_COL in fdf.columns:
    sem_rastreio = int((fdf[TRACK_COL].fillna("").astype(str).str.strip() == "").sum())

emt = fdf[(fdf["Status (padronizado)"] == "Em trânsito")]["Dias desde envio"].dropna()
media_dias_trans = float(emt.mean()) if len(emt) else None
max_dias_trans = int(emt.max()) if len(emt) else None

traj = fdf[(fdf["Status (padronizado)"] == "Recebido")]["Dias do trajeto"].dropna()
media_traj = float(traj.mean()) if len(traj) else None

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Pacotes registrados", total)
c2.metric("🟡 Em trânsito", em_transito)
c3.metric("🟢 Recebidos (total)", recebidos_total)
c4.metric("📦 Recebidos HOJE", recebidos_hoje)
c5.metric("Média dias (em trânsito)", "-" if media_dias_trans is None else f"{media_dias_trans:.1f}")
c6.metric("Maior tempo (em trânsito)", "-" if max_dias_trans is None else f"{max_dias_trans} dias")

st.caption(f"Sem rastreio: {sem_rastreio}")


# ========= ATENÇÃO =========
st.subheader("⚠️ Atenção (40+ dias em trânsito)")

atencao = fdf[
    (fdf["Status (padronizado)"] == "Em trânsito")
    & (fdf["Dias desde envio"].notna())
    & (fdf["Dias desde envio"] >= ALERTA_DIAS)
].copy()

if len(atencao) == 0:
    st.success(f"Nenhum pacote em trânsito com {ALERTA_DIAS}+ dias ✅")
else:
    st.error(f"⚠️ ATENÇÃO: {len(atencao)} pacote(s) com {ALERTA_DIAS}+ dias em trânsito!")
    cols_alerta = [c for c in [PACOTE_COL, TRACK_COL, DT_ENVIO_COL, "Dias desde envio"] if c in atencao.columns]
    atencao = atencao.sort_values("Dias desde envio", ascending=False)
    st.dataframe(atencao[cols_alerta], use_container_width=True)


# ========= TODOS EM TRÂNSITO =========
st.subheader("📌 Todos os pacotes em trânsito (mais antigos primeiro)")

transito = fdf[(fdf["Status (padronizado)"] == "Em trânsito")].copy()

if len(transito) == 0:
    st.info("Nenhum pacote em trânsito com os filtros atuais.")
else:
    transito["_ord"] = transito["Dias desde envio"].fillna(-1)
    transito = transito.sort_values("_ord", ascending=False).drop(columns=["_ord"])

    cols_trans = [c for c in [PACOTE_COL, TRACK_COL, DT_ENVIO_COL, "Dias desde envio"] if c in transito.columns]
    if "Rastreio (URL)" in transito.columns:
        transito["Rastrear"] = transito["Rastreio (URL)"]
        cols_trans.append("Rastrear")

    if hasattr(st, "data_editor") and hasattr(st, "column_config") and hasattr(st.column_config, "LinkColumn") and "Rastrear" in transito.columns:
        st.data_editor(
            transito[cols_trans],
            use_container_width=True,
            hide_index=True,
            disabled=True,
            column_config={"Rastrear": st.column_config.LinkColumn("Rastrear (Correios)", display_text="Abrir")},
        )
    else:
        st.dataframe(transito[cols_trans], use_container_width=True)


# ========= BUSCAR POR CÓDIGO =========
st.subheader("🔎 Buscar por código de rastreio")

if TRACK_COL in df.columns:
    todos_codigos = df[TRACK_COL].dropna().astype(str).str.strip()
    todos_codigos = [c for c in todos_codigos.unique().tolist() if c]

    colA, colB = st.columns([2, 3])
    with colA:
        code_digitado = st.text_input("Digite o código", "").strip().upper()
    with colB:
        code_sel = st.selectbox("Ou selecione na lista", options=[""] + todos_codigos, index=0)

    code_final = code_digitado if code_digitado else code_sel

    if code_final:
        code_final = re.sub(r"[^A-Z0-9]", "", code_final)
        link = CORREIOS_URL + code_final

        st.markdown(f"➡️ **Abrir rastreio:** [{code_final}]({link})")
        st.code(link)

        achados = df[df[TRACK_COL].fillna("").astype(str).str.upper().str.contains(code_final, regex=False)].copy()

        if len(achados) == 0:
            st.info("Código não encontrado na planilha.")
        else:
            cols_show = [c for c in [PACOTE_COL, "Status", DT_ENVIO_COL, DT_RECEB_COL, "Dias desde envio", "Dias do trajeto"] if c in achados.columns]
            st.dataframe(achados[cols_show], use_container_width=True)
else:
    st.info("Coluna de rastreio não encontrada na planilha.")


# ========= LISTA GERAL =========
st.subheader("Lista (clara)")

cols_principais = [c for c in [PACOTE_COL, "Status", TRACK_COL, DT_PEDIDO_COL, DT_ENVIO_COL, "Dias desde envio", DT_RECEB_COL, "Dias do trajeto"] if c in fdf.columns]
view = fdf[cols_principais].copy() if cols_principais else fdf.copy()

mostrar_link = st.checkbox("Mostrar link do rastreio na lista completa", value=False)
if mostrar_link and "Rastreio (URL)" in fdf.columns:
    view["Rastrear"] = fdf["Rastreio (URL)"]
    if hasattr(st, "data_editor") and hasattr(st, "column_config") and hasattr(st.column_config, "LinkColumn"):
        st.data_editor(
            view,
            use_container_width=True,
            hide_index=True,
            disabled=True,
            column_config={"Rastrear": st.column_config.LinkColumn("Rastrear (Correios)", display_text="Abrir")},
        )
    else:
        st.dataframe(view, use_container_width=True)
else:
    st.dataframe(view, use_container_width=True)


# ========= RODAPÉ =========
st.markdown("---")
st.caption(f"© {BRAND_NAME} • {BRAND_HANDLE}")


# ========= EXPORT =========
st.download_button(
    "⬇️ Baixar CSV (com filtros)",
    data=fdf.to_csv(index=False).encode("utf-8"),
    file_name="pacotes_filtrados.csv",
    mime="text/csv",
)
