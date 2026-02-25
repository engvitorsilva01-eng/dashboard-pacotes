import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

# =======================
# CONFIG GERAL
# =======================
APP_TITLE = "📦 Painel de Pacotes"
BRAND_NAME = "MVSPORTSAC"
BRAND_HANDLE = "mvsportsac"
LOGO_PATH = "logo.png"  # opcional (se não existir, não quebra)

FILE_PATH = "CONTROLE_LOGISTICO_FORMATADO_COM_FORMULAS.xlsx"
SHEET_PACOTES = "PACOTES"
SHEET_ITENS = "ITENS"

# nomes esperados (iguais aos da sua planilha)
TRACK_COL = "Código de Rastreio"
STATUS_COL = "Status"
PACOTE_COL = "Pacote"
DT_PEDIDO_COL = "Data do pedido"
DT_ENVIO_COL = "Data do envio"
DT_RECEB_COL = "Data de recebimento"

# aba ITENS (esperado)
IT_PACOTE_COL = "Pacote"
IT_CAMISA_COL = "Camisa"
IT_TAM_COL = "Tamanho"
IT_QTD_COL = "Qtd"
IT_CLIENTE_COL = "Cliente"

CORREIOS_URL = "https://rastreamento.correios.com.br/app/index.php?objetos="

CACHE_TTL = 20
ALERTA_DIAS = 40
TZ = ZoneInfo("America/Fortaleza")


# =======================
# PAGE CONFIG (anti-erro)
# =======================
def _set_page_config_safe():
    try:
        st.set_page_config(
            page_title=f"{APP_TITLE} - {BRAND_NAME}",
            layout="wide",
            page_icon=LOGO_PATH,
        )
    except Exception:
        st.set_page_config(
            page_title=f"{APP_TITLE} - {BRAND_NAME}",
            layout="wide",
            page_icon="📦",
        )


_set_page_config_safe()


# =======================
# FUNÇÕES
# =======================
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


def mask_busca_texto(df: pd.DataFrame, term: str) -> pd.Series:
    term = (term or "").strip().lower()
    if not term:
        return pd.Series([True] * len(df), index=df.index)

    m = pd.Series(False, index=df.index)
    for col in df.columns:
        # tenta buscar em tudo (inclusive números/datas convertidos pra str)
        try:
            m = m | df[col].fillna("").astype(str).str.lower().str.contains(term, regex=False)
        except Exception:
            pass
    return m


@st.cache_data(ttl=CACHE_TTL)
def carregar_pacotes() -> pd.DataFrame:
    try:
        df = pd.read_excel(FILE_PATH, sheet_name=SHEET_PACOTES, engine="openpyxl")
    except Exception as e:
        st.error("Não consegui abrir a planilha (.xlsx) / aba PACOTES.")
        st.code(str(e))
        st.info(f"Confira se o arquivo existe na raiz do repo com o nome: {FILE_PATH}")
        st.stop()

    df.columns = [str(c).strip() for c in df.columns]

    # datas SEM horas
    for c in [DT_PEDIDO_COL, DT_ENVIO_COL, DT_RECEB_COL]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce").dt.date

    # rastreio
    if TRACK_COL in df.columns:
        df[TRACK_COL] = df[TRACK_COL].apply(limpar_codigo)
        df["Rastreio (URL)"] = df[TRACK_COL].apply(lambda x: CORREIOS_URL + x if x else "")
    else:
        df[TRACK_COL] = ""
        df["Rastreio (URL)"] = ""

    # status padronizado
    if STATUS_COL in df.columns:
        df["Status (padronizado)"] = df[STATUS_COL].apply(normalizar_status)
    else:
        df["Status (padronizado)"] = "Sem status"

    df["Status"] = df["Status (padronizado)"].apply(status_bolinha)

    # dias desde envio (para trânsito)
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

    # dias do trajeto (somente recebidos)
    df["Dias do trajeto"] = None
    if (DT_ENVIO_COL in df.columns) and (DT_RECEB_COL in df.columns):
        def calc_trajeto(row):
            if row.get("Status (padronizado)", "") != "Recebido":
                return None
            envio = row.get(DT_ENVIO_COL, None)
            receb = row.get(DT_RECEB_COL, None)
            if envio is None or pd.isna(envio) or receb is None or pd.isna(receb):
                return None
            try:
                return (receb - envio).days
            except Exception:
                return None

        df["Dias do trajeto"] = df.apply(calc_trajeto, axis=1)

    return df


@st.cache_data(ttl=CACHE_TTL)
def carregar_itens() -> pd.DataFrame:
    # não quebra se não existir a aba
    try:
        it = pd.read_excel(FILE_PATH, sheet_name=SHEET_ITENS, engine="openpyxl")
        it.columns = [str(c).strip() for c in it.columns]
    except Exception:
        it = pd.DataFrame(columns=[IT_PACOTE_COL, IT_CAMISA_COL, IT_TAM_COL, IT_QTD_COL, IT_CLIENTE_COL])

    # garante colunas mínimas
    for c in [IT_PACOTE_COL, IT_CAMISA_COL, IT_TAM_COL, IT_QTD_COL, IT_CLIENTE_COL]:
        if c not in it.columns:
            it[c] = ""

    # normaliza tipos
    it[IT_PACOTE_COL] = it[IT_PACOTE_COL].fillna("").astype(str).str.strip()
    it[IT_CAMISA_COL] = it[IT_CAMISA_COL].fillna("").astype(str).str.strip()
    it[IT_TAM_COL] = it[IT_TAM_COL].fillna("").astype(str).str.strip()
    it[IT_CLIENTE_COL] = it[IT_CLIENTE_COL].fillna("").astype(str).str.strip()

    # Qtd numérica
    it[IT_QTD_COL] = pd.to_numeric(it[IT_QTD_COL], errors="coerce").fillna(0).astype(int)

    # remove linhas vazias (sem pacote e sem camisa)
    it = it[~((it[IT_PACOTE_COL] == "") & (it[IT_CAMISA_COL] == ""))].copy()

    return it


def limpar_cache():
    carregar_pacotes.clear()
    carregar_itens.clear()


def mostrar_logo_titulo():
    col_logo, col_title = st.columns([1, 6], vertical_alignment="center")
    with col_logo:
        try:
            st.image(LOGO_PATH, width=120)
        except Exception:
            st.write("")
    with col_title:
        st.title(APP_TITLE)
        st.caption(f"📅 Data da atualização: {hoje_local().strftime('%d/%m/%Y')}")


# =======================
# UI
# =======================
mostrar_logo_titulo()

top1, top2, top3 = st.columns([1, 1, 2])
with top1:
    if st.button("🔄 Atualizar agora"):
        limpar_cache()
        st.rerun()
with top2:
    st.caption(f"Atualiza automaticamente: ~{CACHE_TTL}s")
with top3:
    st.caption("Atualize como sempre: suba o .xlsx no GitHub.")


df = carregar_pacotes()
itens = carregar_itens()

# =======================
# FILTROS
# =======================
st.sidebar.header("Filtros")

status_opts = sorted(df["Status (padronizado)"].dropna().unique().tolist())
status_sel = st.sidebar.multiselect("Status", options=status_opts, default=status_opts)

somente_sem_rastreio = st.sidebar.checkbox("Somente sem rastreio", value=False)
busca_geral = st.sidebar.text_input("Buscar (geral)", "")

fdf = df.copy()
fdf = fdf[fdf["Status (padronizado)"].isin(status_sel)]

if somente_sem_rastreio:
    fdf = fdf[fdf[TRACK_COL].fillna("").astype(str).str.strip() == ""]

fdf = fdf[mask_busca_texto(fdf, busca_geral)]


# =======================
# RESUMO
# =======================
st.subheader("Resumo")

hoje = hoje_local()
total = len(fdf)
em_transito = int((fdf["Status (padronizado)"] == "Em trânsito").sum())
recebidos_total = int((fdf["Status (padronizado)"] == "Recebido").sum())

recebidos_hoje = 0
if DT_RECEB_COL in fdf.columns:
    recebidos_hoje = int(((fdf["Status (padronizado)"] == "Recebido") & (fdf[DT_RECEB_COL] == hoje)).sum())

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


# =======================
# ATENÇÃO 40+ DIAS
# =======================
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


# =======================
# TODOS EM TRÂNSITO
# =======================
st.subheader("📌 Todos os pacotes em trânsito (mais antigos primeiro)")

transito = fdf[(fdf["Status (padronizado)"] == "Em trânsito")].copy()

if len(transito) == 0:
    st.info("Nenhum pacote em trânsito com os filtros atuais.")
else:
    transito["_ord"] = transito["Dias desde envio"].fillna(-1)
    transito = transito.sort_values("_ord", ascending=False).drop(columns=["_ord"])

    cols_trans = [c for c in [PACOTE_COL, TRACK_COL, DT_ENVIO_COL, "Dias desde envio"] if c in transito.columns]
    transito["Rastrear"] = transito.get("Rastreio (URL)", "")

    # LinkColumn (se disponível)
    if hasattr(st, "data_editor") and hasattr(st, "column_config") and hasattr(st.column_config, "LinkColumn"):
        st.data_editor(
            transito[cols_trans + (["Rastrear"] if "Rastrear" in transito.columns else [])],
            use_container_width=True,
            hide_index=True,
            disabled=True,
            column_config={
                "Rastrear": st.column_config.LinkColumn("Rastrear", display_text="Abrir")
            } if "Rastrear" in transito.columns else None,
        )
    else:
        st.dataframe(transito[cols_trans], use_container_width=True)


# =======================
# BUSCAR POR CÓDIGO + MOSTRAR ITENS
# =======================
st.subheader("🔎 Buscar por código de rastreio (e ver camisas do pacote)")

todos_codigos = df[TRACK_COL].dropna().astype(str).str.strip().tolist()
todos_codigos = sorted(list({c for c in todos_codigos if c}))

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

    achados = df[df[TRACK_COL].fillna("").astype(str).str.upper() == code_final].copy()
    if len(achados) == 0:
        # tenta contains só pra não falhar se tiver espaço etc
        achados = df[df[TRACK_COL].fillna("").astype(str).str.upper().str.contains(code_final, regex=False)].copy()

    if len(achados) == 0:
        st.info("Código não encontrado na planilha.")
    else:
        cols_show = [c for c in [PACOTE_COL, "Status", DT_ENVIO_COL, DT_RECEB_COL, "Dias desde envio", "Dias do trajeto"] if c in achados.columns]
        st.dataframe(achados[cols_show], use_container_width=True)

        # pega o pacote do primeiro resultado
        if PACOTE_COL in achados.columns:
            pacote_encontrado = str(achados[PACOTE_COL].dropna().astype(str).iloc[0]).strip()
            st.markdown("### 🧾 Camisas dentro deste pacote")

            if pacote_encontrado == "":
                st.info("Este código não tem 'Pacote' preenchido na aba PACOTES.")
            else:
                itens_pacote = itens[itens[IT_PACOTE_COL].astype(str).str.strip() == pacote_encontrado].copy()

                if len(itens_pacote) == 0:
                    st.info("Nenhuma camisa cadastrada para este pacote na aba ITENS.")
                else:
                    cols_it = [c for c in [IT_CAMISA_COL, IT_TAM_COL, IT_QTD_COL, IT_CLIENTE_COL] if c in itens_pacote.columns]
                    st.dataframe(itens_pacote[cols_it], use_container_width=True)

                    total_qtd = int(itens_pacote[IT_QTD_COL].sum()) if IT_QTD_COL in itens_pacote.columns else 0
                    st.caption(f"Total de peças neste pacote: {total_qtd}")


# =======================
# LISTA GERAL
# =======================
st.subheader("Lista (clara)")

cols_principais = [c for c in [PACOTE_COL, "Status", TRACK_COL, DT_PEDIDO_COL, DT_ENVIO_COL, "Dias desde envio", DT_RECEB_COL, "Dias do trajeto"] if c in fdf.columns]
view = fdf[cols_principais].copy() if cols_principais else fdf.copy()

mostrar_link = st.checkbox("Mostrar link do rastreio na lista completa", value=False)
if mostrar_link:
    view["Rastrear"] = fdf.get("Rastreio (URL)", "")
    if hasattr(st, "data_editor") and hasattr(st, "column_config") and hasattr(st.column_config, "LinkColumn"):
        st.data_editor(
            view,
            use_container_width=True,
            hide_index=True,
            disabled=True,
            column_config={"Rastrear": st.column_config.LinkColumn("Rastrear", display_text="Abrir")},
        )
    else:
        st.dataframe(view, use_container_width=True)
else:
    st.dataframe(view, use_container_width=True)


# =======================
# EXPORT + RODAPÉ
# =======================
st.download_button(
    "⬇️ Baixar CSV (com filtros)",
    data=fdf.to_csv(index=False).encode("utf-8"),
    file_name="pacotes_filtrados.csv",
    mime="text/csv",
)

st.markdown("---")
st.caption(f"© {BRAND_NAME} • {BRAND_HANDLE}")
