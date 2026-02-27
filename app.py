import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

st.set_page_config(page_title="Painel de Pacotes", page_icon="📦", layout="centered")

ARQUIVO_EXCEL = "CONTROLE_LOGISTICO_FORMATADO_COM_FORMULAS.xlsx"
SHEET_PACOTES = "PACOTES"
SHEET_ITENS = "ITENS"
DIAS_ALERTA = 40

# =========================
# CSS (mobile first)
# =========================
st.markdown(
    """
<style>
/* Mobile-first: centralizado, mais espaçado e legível */
.block-container { padding-top: 0.9rem; padding-bottom: 1.6rem; max-width: 860px; }
h1 { font-size: 1.35rem !important; }
h2 { font-size: 1.15rem !important; }
h3 { font-size: 1.05rem !important; }

/* KPIs em 2 colunas no celular */
.kpi-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
@media (min-width: 900px) { .kpi-grid { grid-template-columns: repeat(4, 1fr); } }

.kpi-card {
  border: 1px solid rgba(250,250,250,0.14);
  border-radius: 14px;
  padding: 12px 14px;
  background: rgba(255,255,255,0.03);
}
.kpi-title { font-size: 0.82rem; opacity: 0.78; margin-bottom: 2px; }
.kpi-value { font-size: 1.35rem; font-weight: 800; line-height: 1.2; }

/* Cards de pacotes */
.row-card {
  border: 1px solid rgba(250,250,250,0.14);
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 10px;
  background: rgba(255,255,255,0.02);
}
.row-top { display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }
.badge {
  padding: 4px 10px; border-radius: 999px; font-size: 0.78rem;
  border: 1px solid rgba(250,250,250,0.20);
  opacity: 0.95;
  white-space: nowrap;
}
.badge-warn { border-color: rgba(255, 180, 60, 0.70); }
.small { font-size: 0.86rem; opacity: 0.80; margin-top: 6px; }
.caption { opacity: 0.78; font-size: 0.92rem; }
hr { opacity: 0.12; }

/* Deixa expanders mais "tocáveis" */
details summary { font-size: 0.95rem; }
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Helpers
# =========================
def safe_str(x) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    return str(x).strip()

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

def compute_public_status(row) -> str:
    receb = row.get("Data de recebimento")
    if pd.notna(receb):
        return "RECEBIDO"
    status = safe_str(row.get("Status")).lower()
    if any(k in status for k in ["recebid", "entreg"]):
        return "RECEBIDO"
    return "EM TRANSITO"

def calc_days_waiting(row, today: date) -> float:
    if row.get("STATUS_PUBLICO") != "EM TRANSITO":
        return np.nan
    d_envio = row.get("Data do envio")
    d_pedido = row.get("Data do pedido")
    d0 = d_envio if pd.notna(d_envio) else d_pedido
    if pd.isna(d0) or d0 is None:
        return np.nan
    try:
        return float((today - d0).days)
    except Exception:
        return np.nan

@st.cache_data(show_spinner=False)
def load_data():
    xls = pd.ExcelFile(ARQUIVO_EXCEL)

    if SHEET_PACOTES not in xls.sheet_names:
        raise ValueError(f"Aba '{SHEET_PACOTES}' não existe. Abas: {xls.sheet_names}")
    if SHEET_ITENS not in xls.sheet_names:
        raise ValueError(f"Aba '{SHEET_ITENS}' não existe. Abas: {xls.sheet_names}")

    pac = pd.read_excel(ARQUIVO_EXCEL, sheet_name=SHEET_PACOTES, engine="openpyxl").dropna(how="all")
    it = pd.read_excel(ARQUIVO_EXCEL, sheet_name=SHEET_ITENS, engine="openpyxl").dropna(how="all")

    # Checagens
    required_pac = ["Pacote", "Código de Rastreio", "Data do pedido", "Data do envio", "Data de recebimento", "Status"]
    required_it = ["Pacote", "Código de Rastreio", "Camisa", "Tamanho", "Qtd", "Cliente"]

    for c in required_pac:
        if c not in pac.columns:
            raise ValueError(f"Coluna '{c}' não encontrada em {SHEET_PACOTES}. Colunas: {list(pac.columns)}")
    for c in required_it:
        if c not in it.columns:
            raise ValueError(f"Coluna '{c}' não encontrada em {SHEET_ITENS}. Colunas: {list(it.columns)}")

    # Tipos
    pac["Código de Rastreio"] = pac["Código de Rastreio"].astype(str).str.strip()
    it["Código de Rastreio"] = it["Código de Rastreio"].astype(str).str.strip()

    pac["Data do pedido"] = to_date_series(pac["Data do pedido"])
    pac["Data do envio"] = to_date_series(pac["Data do envio"])
    pac["Data de recebimento"] = to_date_series(pac["Data de recebimento"])

    pac["Pacote"] = pac["Pacote"].apply(
        lambda x: safe_str(int(x)) if isinstance(x, (int, float)) and pd.notna(x) else safe_str(x)
    )
    it["Pacote"] = it["Pacote"].apply(lambda x: safe_str(x))

    return pac, it

# =========================
# App
# =========================
st.title("📦 Painel de Pacotes")
today = date.today()
st.markdown(f'<div class="caption">📅 Atualizado em: <b>{today.strftime("%d/%m/%Y")}</b></div>', unsafe_allow_html=True)

try:
    pacotes, itens = load_data()
except FileNotFoundError:
    st.error(f"Não achei o arquivo **{ARQUIVO_EXCEL}** na pasta do app.")
    st.info("✅ Coloque a planilha na raiz do repositório (mesma pasta do app.py).")
    st.stop()
except Exception as e:
    st.error(f"Erro ao carregar planilha: {e}")
    st.stop()

pacotes["STATUS_PUBLICO"] = pacotes.apply(compute_public_status, axis=1)
pacotes["DIAS_EM_ESPERA"] = pacotes.apply(lambda r: calc_days_waiting(r, today), axis=1)

total = int(len(pacotes))
em_transito = int((pacotes["STATUS_PUBLICO"] == "EM TRANSITO").sum())
recebidos = int((pacotes["STATUS_PUBLICO"] == "RECEBIDO").sum())

wait_series = pacotes.loc[pacotes["STATUS_PUBLICO"] == "EM TRANSITO", "DIAS_EM_ESPERA"].dropna()
media_wait = int(round(float(wait_series.mean()))) if len(wait_series) else 0
max_wait = int(float(wait_series.max())) if len(wait_series) else 0

st.markdown('<div class="kpi-grid">', unsafe_allow_html=True)
kpi_card("📦 Total", f"{total}")
kpi_card("🚚 Em trânsito", f"{em_transito}")
kpi_card("✅ Recebidos", f"{recebidos}")
kpi_card("⏳ Espera (média / máximo)", f"{media_wait}d / {max_wait}d")
st.markdown("</div>", unsafe_allow_html=True)

# =========================
# Filtros (em expander: melhor no celular)
# =========================
st.divider()

with st.expander("🔎 Buscar e Filtrar", expanded=True):
    q = st.text_input("Buscar por Pacote ou Código de Rastreio", placeholder="Ex: 35 ou LZ373185768CN")
    filtro = st.selectbox("Status", ["Todos", "Em trânsito", "Recebidos"], index=0)
    limite = st.selectbox("Quantidade para mostrar", [20, 30, 50, 80, 120], index=1)
    mostrar_itens = st.toggle("Mostrar camisas do pacote (ITENS)", value=True)

# =========================
# Seção 1: Em trânsito (principal no celular)
# =========================
st.subheader("⏳ Em trânsito")
st.caption("Ordem: mais antigos primeiro. O principal é **Dias em espera**.")

em_df = pacotes[pacotes["STATUS_PUBLICO"] == "EM TRANSITO"].copy()
em_df = em_df.sort_values(by="DIAS_EM_ESPERA", ascending=False).head(limite)

if em_df.empty:
    st.info("Nenhum pacote em trânsito encontrado.")
else:
    for _, r in em_df.iterrows():
        pacote = safe_str(r.get("Pacote"))
        codigo = safe_str(r.get("Código de Rastreio"))
        dias = r.get("DIAS_EM_ESPERA")
        dias_txt = "—" if pd.isna(dias) else f"{int(dias)} dias"

        d_envio = r.get("Data do envio")
        envio_txt = ""
        if pd.notna(d_envio):
            envio_txt = d_envio.strftime("%d/%m/%Y") if hasattr(d_envio, "strftime") else str(d_envio)

        warn = (not pd.isna(dias)) and int(dias) >= DIAS_ALERTA
        badge_class = "badge badge-warn" if warn else "badge"
        badge_text = f"⚠️ {DIAS_ALERTA}+ dias" if warn else "Em trânsito"

        extra = f" • 📮 Enviado: <b>{envio_txt}</b>" if envio_txt else ""

        st.markdown(
            f"""
<div class="row-card">
  <div class="row-top">
    <div><b>📦 Pacote {pacote}</b><br><span class="small">Código: {codigo}</span></div>
    <div class="{badge_class}">🚚 {badge_text}</div>
  </div>
  <div class="small">⏳ Dias em espera: <b>{dias_txt}</b>{extra}</div>
</div>
""",
            unsafe_allow_html=True,
        )

# =========================
# Seção 2: Resultado da busca/filtro (mobile friendly)
# =========================
st.divider()
st.subheader("📌 Resultado")

df = pacotes.copy()

if q.strip():
    qq = q.strip().lower()
    df = df[
        df["Pacote"].astype(str).str.lower().str.contains(qq, na=False)
        | df["Código de Rastreio"].astype(str).str.lower().str.contains(qq, na=False)
    ]

if filtro == "Em trânsito":
    df = df[df["STATUS_PUBLICO"] == "EM TRANSITO"]
elif filtro == "Recebidos":
    df = df[df["STATUS_PUBLICO"] == "RECEBIDO"]

df = df.head(limite)

if df.empty:
    st.info("Nada encontrado com esse filtro/busca.")
else:
    for _, r in df.iterrows():
        pacote = safe_str(r.get("Pacote"))
        codigo = safe_str(r.get("Código de Rastreio"))
        status = safe_str(r.get("STATUS_PUBLICO"))

        if status == "RECEBIDO":
            drec = r.get("Data de recebimento")
            rec_txt = "—"
            if pd.notna(drec):
                rec_txt = drec.strftime("%d/%m/%Y") if hasattr(drec, "strftime") else str(drec)

            st.markdown(
                f"""
<div class="row-card">
  <div class="row-top">
    <div><b>📦 Pacote {pacote}</b><br><span class="small">Código: {codigo}</span></div>
    <div class="badge">✅ Recebido</div>
  </div>
  <div class="small">📅 Recebido em: <b>{rec_txt}</b></div>
</div>
""",
                unsafe_allow_html=True,
            )

        else:
            dias = r.get("DIAS_EM_ESPERA")
            dias_txt = "—" if pd.isna(dias) else f"{int(dias)} dias"
            warn = (not pd.isna(dias)) and int(dias) >= DIAS_ALERTA
            badge_class = "badge badge-warn" if warn else "badge"
            badge_text = f"⚠️ {DIAS_ALERTA}+ dias" if warn else "Em trânsito"

            st.markdown(
                f"""
<div class="row-card">
  <div class="row-top">
    <div><b>📦 Pacote {pacote}</b><br><span class="small">Código: {codigo}</span></div>
    <div class="{badge_class}">🚚 {badge_text}</div>
  </div>
  <div class="small">⏳ Dias em espera: <b>{dias_txt}</b></div>
</div>
""",
                unsafe_allow_html=True,
            )

        # Itens (camisas) -> em expander: perfeito no celular
        if mostrar_itens:
            it = itens[
                (itens["Pacote"].astype(str) == str(pacote))
                | (itens["Código de Rastreio"].astype(str) == str(codigo))
            ].copy()

            if not it.empty:
                it["Qtd"] = pd.to_numeric(it["Qtd"], errors="coerce").fillna(0).astype(int)

                it_small = (
                    it.groupby(["Camisa", "Tamanho"], dropna=False)["Qtd"]
                    .sum()
                    .reset_index()
                    .sort_values(by=["Camisa", "Tamanho"])
                )

                with st.expander("👕 Ver camisas deste pacote", expanded=False):
                    # Em celular, tabela pequena com altura fixa
                    st.dataframe(it_small, use_container_width=True, hide_index=True, height=240)

# =========================
# Diagnóstico (fechado)
# =========================
with st.expander("⚙️ Diagnóstico (manutenção)", expanded=False):
    st.write("Arquivo:", ARQUIVO_EXCEL)
    st.write("Abas:", SHEET_PACOTES, "/", SHEET_ITENS)
    st.write("Linhas PACOTES:", len(pacotes))
    st.write("Linhas ITENS:", len(itens))
