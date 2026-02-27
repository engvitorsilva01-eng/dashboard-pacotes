import streamlit as st
import pandas as pd
import numpy as np
import unicodedata
from datetime import date

# =========================
# Config
# =========================
st.set_page_config(page_title="Painel de Pacotes", page_icon="📦", layout="wide")

ARQUIVO_EXCEL = "CONTROLE_LOGISTICO_FORMATADO_COM_FORMULAS.xlsx"
DIAS_ALERTA = 40  # alerta a partir de 40 dias

# =========================
# Estilo (objetivo / público)
# =========================
st.markdown(
    """
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1200px; }

.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
@media (max-width: 900px) { .kpi-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 520px) { .kpi-grid { grid-template-columns: 1fr; } }

.kpi-card {
  border: 1px solid rgba(250,250,250,0.12);
  border-radius: 14px;
  padding: 14px 16px;
  background: rgba(255,255,255,0.03);
}
.kpi-title { font-size: 0.85rem; opacity: 0.75; margin-bottom: 4px; }
.kpi-value { font-size: 1.6rem; font-weight: 750; line-height: 1.2; }

.row-card {
  border: 1px solid rgba(250,250,250,0.12);
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 10px;
  background: rgba(255,255,255,0.02);
}
.row-top { display:flex; justify-content:space-between; align-items:center; gap:12px; }
.badge {
  padding: 4px 10px; border-radius: 999px; font-size: 0.82rem;
  border: 1px solid rgba(250,250,250,0.18);
  opacity: 0.95;
  white-space: nowrap;
}
.badge-warn { border-color: rgba(255, 180, 60, 0.65); }
.small { font-size: 0.88rem; opacity: 0.78; margin-top: 6px; }
hr { opacity: 0.15; }
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Helpers
# =========================
def safe_str(x) -> str:
    if pd.isna(x) or x is None:
        return ""
    return str(x).strip()

def _norm_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = " ".join(s.split())
    return s

def suggest_column(columns, keywords):
    """Sugere uma coluna baseada em palavras-chave."""
    cols_norm = {c: _norm_text(c) for c in columns}
    for c, cn in cols_norm.items():
        if any(k in cn for k in keywords):
            return c
    return None

def to_date_series(series: pd.Series) -> pd.Series:
    s = pd.to_datetime(series, errors="coerce", dayfirst=True)
    return s.dt.date

def kpi_card(title: str, value: str):
    st.markdown(
        f"""
<div class="kpi-card">
  <div class="kpi-title">{title}</div>
  <div class="kpi-value">{value}</div>
</div>
""",
        unsafe_allow_html=True,
    )

def compute_status(row: pd.Series, col_status: str | None, col_receb: str | None) -> str:
    # Se tem data de recebimento => RECEBIDO
    if col_receb and pd.notna(row.get(col_receb)):
        return "RECEBIDO"

    # Se o texto do status indicar recebido/entregue => RECEBIDO
    if col_status:
        v = _norm_text(row.get(col_status))
        if any(k in v for k in ["recebid", "entreg", "finaliz", "conclu", "chegou"]):
            return "RECEBIDO"

    return "EM TRANSITO"

def calc_dias_espera(row: pd.Series, col_envio: str | None, hoje: date) -> float:
    if row.get("STATUS_PUBLICO") != "EM TRANSITO":
        return np.nan
    if not col_envio:
        return np.nan
    d0 = row.get(col_envio)
    if pd.isna(d0) or d0 is None:
        return np.nan
    try:
        return float((hoje - d0).days)
    except Exception:
        return np.nan

# =========================
# Header
# =========================
st.title("📦 Painel Público de Pacotes")
hoje = date.today()
st.caption(f"📅 Atualizado em: {hoje.strftime('%d/%m/%Y')}")

# =========================
# Carregar Excel (com escolha de aba)
# =========================
try:
    xls = pd.ExcelFile(ARQUIVO_EXCEL)
except FileNotFoundError:
    st.error(
        f"Arquivo **{ARQUIVO_EXCEL}** não encontrado.\n\n"
        "✅ Coloque a planilha na **raiz do repositório** (mesma pasta do app.py)."
    )
    st.stop()
except Exception as e:
    st.error(f"Não consegui abrir a planilha. Erro: {e}")
    st.stop()

with st.sidebar:
    st.header("⚙️ Configuração")
    sheet = st.selectbox("Escolha a aba (sheet) correta", xls.sheet_names, index=0)
    st.markdown("---")
    st.caption("Se os dados ficaram errados, normalmente é porque a aba ou as colunas escolhidas não são as certas.")

df_raw = pd.read_excel(ARQUIVO_EXCEL, sheet_name=sheet, engine="openpyxl")
df_raw = df_raw.dropna(how="all")

if df_raw.empty:
    st.warning("Essa aba está vazia. Selecione outra aba no menu lateral.")
    st.stop()

columns = list(df_raw.columns)

# =========================
# Mapeamento manual de colunas (para nunca errar)
# =========================
# Sugestões automáticas (pra facilitar)
sug_codigo = suggest_column(columns, ["codigo", "código", "rastreamento", "tracking", "awb", "pedido", "id"])
sug_status = suggest_column(columns, ["status", "situacao", "situação"])
sug_envio  = suggest_column(columns, ["data envio", "envio", "postagem", "data postagem", "despacho"])
sug_receb  = suggest_column(columns, ["data recebimento", "recebimento", "entrega", "recebido", "entregue"])

with st.sidebar:
    st.subheader("Mapear colunas")
    col_codigo = st.selectbox("Coluna do CÓDIGO", options=columns, index=columns.index(sug_codigo) if sug_codigo in columns else 0)
    col_envio  = st.selectbox("Coluna DATA DE ENVIO/POSTAGEM", options=["(não tenho)"] + columns, index=(["(não tenho)"] + columns).index(sug_envio) if sug_envio in columns else 0)
    col_receb  = st.selectbox("Coluna DATA DE RECEBIMENTO", options=["(não tenho)"] + columns, index=(["(não tenho)"] + columns).index(sug_receb) if sug_receb in columns else 0)
    col_status = st.selectbox("Coluna STATUS (texto)", options=["(não tenho)"] + columns, index=(["(não tenho)"] + columns).index(sug_status) if sug_status in columns else 0)

# Resolver "(não tenho)"
col_envio  = None if col_envio == "(não tenho)" else col_envio
col_receb  = None if col_receb == "(não tenho)" else col_receb
col_status = None if col_status == "(não tenho)" else col_status

st.subheader("👀 Prévia da base (para conferir se está certo)")
st.dataframe(df_raw.head(8), use_container_width=True, hide_index=True)

# =========================
# Preparar dados (sem inventar colunas)
# =========================
df = df_raw.copy()

# Código como texto
df[col_codigo] = df[col_codigo].astype(str).str.strip()

# Datas
if col_envio:
    df[col_envio] = to_date_series(df[col_envio])
if col_receb:
    df[col_receb] = to_date_series(df[col_receb])

# Status público + dias
df["STATUS_PUBLICO"] = df.apply(lambda r: compute_status(r, col_status, col_receb), axis=1)
df["DIAS_EM_ESPERA"] = df.apply(lambda r: calc_dias_espera(r, col_envio, hoje), axis=1)

# =========================
# KPIs
# =========================
total = int(len(df))
em_transito = int((df["STATUS_PUBLICO"] == "EM TRANSITO").sum())
recebidos = int((df["STATUS_PUBLICO"] == "RECEBIDO").sum())

espera = df.loc[df["STATUS_PUBLICO"] == "EM TRANSITO", "DIAS_EM_ESPERA"].dropna()
media_espera = int(round(float(espera.mean()))) if len(espera) else 0
max_espera = int(float(espera.max())) if len(espera) else 0

st.markdown('<div class="kpi-grid">', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
with c1: kpi_card("📦 Total", f"{total}")
with c2: kpi_card("🚚 Em trânsito", f"{em_transito}")
with c3: kpi_card("✅ Recebidos", f"{recebidos}")
with c4: kpi_card("⏳ Espera (média / máximo)", f"{media_espera}d / {max_espera}d")
st.markdown("</div>", unsafe_allow_html=True)

# =========================
# Busca / filtro (objetivo)
# =========================
st.divider()
left, right = st.columns([2, 1])

with left:
    busca = st.text_input("🔎 Buscar por código (ou parte do código)", placeholder="Ex: LB123, BR, 2026...")
with right:
    filtro_status = st.selectbox("Filtrar", ["Todos", "Em trânsito", "Recebidos"], index=0)

f = df.copy()
if busca.strip():
    f = f[f[col_codigo].astype(str).str.contains(busca.strip(), case=False, na=False)]

if filtro_status == "Em trânsito":
    f = f[f["STATUS_PUBLICO"] == "EM TRANSITO"]
elif filtro_status == "Recebidos":
    f = f[f["STATUS_PUBLICO"] == "RECEBIDO"]

# =========================
# Em trânsito (principal)
# =========================
st.divider()
st.subheader("⏳ Em trânsito (mais antigos primeiro)")
st.caption("O principal aqui é: **quantos dias o pacote está em espera**.")

em_df = df[df["STATUS_PUBLICO"] == "EM TRANSITO"].copy()
em_df = em_df.sort_values(by="DIAS_EM_ESPERA", ascending=False)

limite = st.slider("Quantidade para mostrar", min_value=10, max_value=120, value=30, step=10)

if em_df.empty:
    st.info("Nenhum pacote em trânsito encontrado.")
else:
    for _, r in em_df.head(limite).iterrows():
        codigo = safe_str(r.get(col_codigo))
        dias = r.get("DIAS_EM_ESPERA")
        dias_txt = "—" if pd.isna(dias) else f"{int(dias)} dias"

        envio_txt = ""
        if col_envio and pd.notna(r.get(col_envio)):
            d = r.get(col_envio)
            envio_txt = d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d)

        warn = (not pd.isna(dias)) and int(dias) >= DIAS_ALERTA
        badge_class = "badge badge-warn" if warn else "badge"
        badge_text = f"⚠️ ATENÇÃO ({DIAS_ALERTA}+ dias)" if warn else "Em trânsito"
        extra = f" • 📮 Postado em: <b>{envio_txt}</b>" if envio_txt else ""

        st.markdown(
            f"""
<div class="row-card">
  <div class="row-top">
    <div><b>📦 {codigo}</b></div>
    <div class="{badge_class}">🚚 {badge_text}</div>
  </div>
  <div class="small">⏳ Espera: <b>{dias_txt}</b>{extra}</div>
</div>
""",
            unsafe_allow_html=True,
        )

# =========================
# Resultado da busca / filtro
# =========================
st.divider()
st.subheader("📌 Resultado da busca / filtro")

if f.empty:
    st.info("Nada para mostrar com esse filtro/busca.")
else:
    max_cards = 50
    count = 0

    for _, r in f.iterrows():
        if count >= max_cards:
            st.caption(f"Mostrando os primeiros {max_cards}. Refine a busca para ver menos.")
            break

        codigo = safe_str(r.get(col_codigo))
        status = safe_str(r.get("STATUS_PUBLICO"))

        if status == "RECEBIDO":
            rec_txt = "—"
            if col_receb and pd.notna(r.get(col_receb)):
                d = r.get(col_receb)
                rec_txt = d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d)

            st.markdown(
                f"""
<div class="row-card">
  <div class="row-top">
    <div><b>📦 {codigo}</b></div>
    <div class="badge">✅ Recebido</div>
  </div>
  <div class="small">📅 Data de recebimento: <b>{rec_txt}</b></div>
</div>
""",
                unsafe_allow_html=True,
            )
        else:
            dias = r.get("DIAS_EM_ESPERA")
            dias_txt = "—" if pd.isna(dias) else f"{int(dias)} dias"
            warn = (not pd.isna(dias)) and int(dias) >= DIAS_ALERTA
            badge_class = "badge badge-warn" if warn else "badge"
            badge_text = f"⚠️ ATENÇÃO ({DIAS_ALERTA}+ dias)" if warn else "Em trânsito"

            st.markdown(
                f"""
<div class="row-card">
  <div class="row-top">
    <div><b>📦 {codigo}</b></div>
    <div class="{badge_class}">🚚 {badge_text}</div>
  </div>
  <div class="small">⏳ Espera: <b>{dias_txt}</b></div>
</div>
""",
                unsafe_allow_html=True,
            )

        count += 1

# =========================
# Diagnóstico
# =========================
with st.expander("⚙️ Diagnóstico (para manutenção)", expanded=False):
    st.write("**Arquivo:**", ARQUIVO_EXCEL)
    st.write("**Aba usada:**", sheet)
    st.write("**Mapeamento escolhido:**")
    st.json(
        {
            "codigo": col_codigo,
            "data_envio": col_envio,
            "data_recebimento": col_receb,
            "status_texto": col_status,
        }
    )
    if not col_envio:
        st.warning("Sem coluna de DATA DE ENVIO/POSTAGEM: DIAS EM ESPERA pode ficar vazio.")
