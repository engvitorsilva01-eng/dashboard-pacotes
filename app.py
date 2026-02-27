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
def _norm_text(s: str) -> str:
    """Normaliza texto: lower, sem acento, sem espaços duplos."""
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = " ".join(s.split())
    return s

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [ _norm_text(c).replace("/", " ").replace("-", " ") for c in df.columns ]
    return df

def pick_sheet(xls: pd.ExcelFile) -> str:
    """Escolhe uma aba provável. Se falhar, usa a primeira."""
    priority = [
        "controle", "logistico", "logistica", "base", "dados", "painel", "dashboard",
        "planilha", "principal"
    ]
    names = xls.sheet_names
    names_norm = [ _norm_text(n) for n in names ]

    for key in priority:
        for real, norm in zip(names, names_norm):
            if key in norm:
                return real
    return names[0]

def pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Acha coluna por match exato (normalizado) ou por 'contem'."""
    cols = list(df.columns)
    for cand in candidates:
        c = _norm_text(cand)
        if c in cols:
            return c
    for col in cols:
        for cand in candidates:
            if _norm_text(cand) in col:
                return col
    return None

def to_date_series(series: pd.Series) -> pd.Series:
    """Converte para date (sem quebrar)."""
    s = pd.to_datetime(series, errors="coerce", dayfirst=True)
    return s.dt.date

def safe_str(x) -> str:
    if pd.isna(x) or x is None:
        return ""
    return str(x).strip()

def status_publico(row: pd.Series, col_status: str | None, col_receb: str | None) -> str:
    """
    Regras:
    - Se tem data de recebimento => RECEBIDO
    - Senão, se status textual indicar recebido/entregue => RECEBIDO
    - Senão => EM TRANSITO
    """
    if col_receb and pd.notna(row.get(col_receb)):
        return "RECEBIDO"

    if col_status:
        v = _norm_text(row.get(col_status))
        if any(k in v for k in ["recebid", "entreg", "finaliz", "conclu", "chegou"]):
            return "RECEBIDO"

    return "EM TRANSITO"

def calc_dias_espera(row: pd.Series, col_envio: str | None, hoje: date) -> float:
    if row.get("status_publico") != "EM TRANSITO":
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

# =========================
# Carregamento do Excel (robusto)
# =========================
@st.cache_data(show_spinner=False)
def load_excel(path: str):
    xls = pd.ExcelFile(path)
    sheet = pick_sheet(xls)
    df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    df = normalize_columns(df)

    # remove linhas totalmente vazias
    df = df.dropna(how="all")

    return df, sheet, xls.sheet_names

st.title("📦 Painel Público de Pacotes")
hoje = date.today()
st.caption(f"📅 Atualizado em: {hoje.strftime('%d/%m/%Y')}")

try:
    df, sheet_used, all_sheets = load_excel(ARQUIVO_EXCEL)
except FileNotFoundError:
    st.error(
        f"Arquivo **{ARQUIVO_EXCEL}** não foi encontrado na pasta do app.\n\n"
        "✅ Coloque a planilha na **raiz do repositório** (mesma pasta do app.py)."
    )
    st.stop()
except Exception as e:
    st.error(f"Não consegui abrir a planilha. Erro: {e}")
    st.stop()

# =========================
# Detectar colunas
# =========================
col_codigo = pick_col(df, ["codigo", "código", "tracking", "rastreamento", "awb", "id", "pedido", "cod"])
col_status = pick_col(df, ["status", "situacao", "situação"])
col_envio  = pick_col(df, ["data envio", "data de envio", "envio", "postagem", "data postagem", "data de postagem", "despacho"])
col_receb  = pick_col(df, ["data recebimento", "data de recebimento", "recebido em", "entregue em", "data entrega", "data de entrega", "entrega"])

# Se não existir coluna de código, cria uma
if not col_codigo:
    df["codigo"] = np.arange(1, len(df) + 1).astype(str)
    col_codigo = "codigo"

# Garantir código como texto
df[col_codigo] = df[col_codigo].astype(str).str.strip()

# Converter datas (se existirem)
if col_envio:
    df[col_envio] = to_date_series(df[col_envio])
if col_receb:
    df[col_receb] = to_date_series(df[col_receb])

# Status público + dias espera
df["status_publico"] = df.apply(lambda r: status_publico(r, col_status, col_receb), axis=1)
df["dias_em_espera"] = df.apply(lambda r: calc_dias_espera(r, col_envio, hoje), axis=1)

# =========================
# KPIs
# =========================
total = int(len(df))
em_transito = int((df["status_publico"] == "EM TRANSITO").sum())
recebidos = int((df["status_publico"] == "RECEBIDO").sum())

espera = df.loc[df["status_publico"] == "EM TRANSITO", "dias_em_espera"].dropna()
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
# Filtros (simples)
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
    f = f[f["status_publico"] == "EM TRANSITO"]
elif filtro_status == "Recebidos":
    f = f[f["status_publico"] == "RECEBIDO"]

# =========================
# Seção principal: Em trânsito (cards)
# =========================
st.divider()
st.subheader("⏳ Em trânsito (mais antigos primeiro)")
st.caption("Aqui aparece o que importa: **quantos dias o pacote está em espera**.")

em_df = df[df["status_publico"] == "EM TRANSITO"].copy()
em_df = em_df.sort_values(by="dias_em_espera", ascending=False)

limite = st.slider("Quantidade para mostrar", min_value=10, max_value=120, value=30, step=10)

if em_df.empty:
    st.info("Nenhum pacote em trânsito encontrado.")
else:
    for _, r in em_df.head(limite).iterrows():
        codigo = safe_str(r.get(col_codigo))
        dias = r.get("dias_em_espera")
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
# Resultado da busca (objetivo, sem tabelão)
# =========================
st.divider()
st.subheader("📌 Resultado da busca / filtro")

if f.empty:
    st.info("Nada para mostrar com esse filtro/busca.")
else:
    # Mostra em cards (mais amigável pro público)
    # Limita para não virar infinito
    max_cards = 40
    count = 0

    for _, r in f.iterrows():
        if count >= max_cards:
            st.caption(f"Mostrando os primeiros {max_cards}. Refine a busca para ver menos.")
            break

        codigo = safe_str(r.get(col_codigo))
        status = safe_str(r.get("status_publico"))

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
            dias = r.get("dias_em_espera")
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
# Diagnóstico (para você, fechado por padrão)
# =========================
with st.expander("⚙️ Diagnóstico (para manutenção)", expanded=False):
    st.write("**Arquivo:**", ARQUIVO_EXCEL)
    st.write("**Aba usada:**", sheet_used)
    st.write("**Abas encontradas:**", all_sheets)
    st.write("**Colunas detectadas:**")
    st.json(
        {
            "codigo": col_codigo,
            "status (planilha)": col_status,
            "data envio": col_envio,
            "data recebimento": col_receb,
        }
    )

    faltando = []
    if not col_envio:
        faltando.append("Data de envio/postagem (sem isso não calcula DIAS EM ESPERA).")
    if faltando:
        st.warning("Campos não encontrados:\n- " + "\n- ".join(faltando))
