import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

st.set_page_config(page_title="Pacotes - Status", page_icon="📦", layout="centered")

ARQUIVO_EXCEL = "CONTROLE_LOGISTICO_FORMATADO_COM_FORMULAS.xlsx"
SHEET_PACOTES = "PACOTES"
SHEET_ITENS = "ITENS"
DIAS_ALERTA = 40

# =========================
# CSS (limpo e legível no celular)
# =========================
st.markdown(
    """
<style>
.block-container { padding-top: 0.9rem; padding-bottom: 1.6rem; max-width: 860px; }
h1 { font-size: 1.45rem !important; margin-bottom: 0.2rem; }
.caption { opacity: 0.78; font-size: 0.95rem; margin-top: 0.1rem; margin-bottom: 0.8rem; }

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

.card {
  border: 1px solid rgba(250,250,250,0.14);
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 10px;
  background: rgba(255,255,255,0.02);
}
.card-top { display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }
.badge {
  padding: 4px 10px; border-radius: 999px; font-size: 0.78rem;
  border: 1px solid rgba(250,250,250,0.20);
  opacity: 0.95;
  white-space: nowrap;
}
.badge-warn { border-color: rgba(255, 180, 60, 0.70); }
.badge-ok { border-color: rgba(110, 255, 180, 0.35); }
.small { font-size: 0.90rem; opacity: 0.83; margin-top: 6px; line-height: 1.3; }
hr { opacity: 0.12; }
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
    # Se tem data de recebimento -> Recebido
    if pd.notna(row.get("Data de recebimento")):
        return "Recebido"

    # Se status textual indica recebido/entregue -> Recebido
    status_txt = safe_str(row.get("Status")).lower()
    if any(k in status_txt for k in ["recebid", "entreg"]):
        return "Recebido"

    return "Em trânsito"

def calc_days_waiting(row, today: date) -> float:
    # Dias em espera só para "Em trânsito"
    if row.get("Status público") != "Em trânsito":
        return np.nan

    d_envio = row.get("Data do envio")
    d_pedido = row.get("Data do pedido")

    # prioridade: envio; se não tiver, pedido
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

    pac = pd.read_excel(ARQUIVO_EXCEL, sheet_name=SHEET_PACOTES, engine="openpyxl").dropna(how="all")
    it  = pd.read_excel(ARQUIVO_EXCEL, sheet_name=SHEET_ITENS, engine="openpyxl").dropna(how="all")

    # Datas
    pac["Data do pedido"] = to_date_series(pac["Data do pedido"])
    pac["Data do envio"] = to_date_series(pac["Data do envio"])
    pac["Data de recebimento"] = to_date_series(pac["Data de recebimento"])

    # Texto
    pac["Código de Rastreio"] = pac["Código de Rastreio"].astype(str).str.strip()
    it["Código de Rastreio"]  = it["Código de Rastreio"].astype(str).str.strip()

    # Pacote (evita 35.0)
    pac["Pacote"] = pac["Pacote"].apply(
        lambda x: safe_str(int(x)) if isinstance(x, (int, float)) and pd.notna(x) else safe_str(x)
    )
    it["Pacote"] = it["Pacote"].apply(lambda x: safe_str(x))

    return pac, it

# =========================
# App
# =========================
today = date.today()

st.title("📦 Status dos Pacotes")
st.markdown(f'<div class="caption">📅 Atualizado em: <b>{today.strftime("%d/%m/%Y")}</b></div>', unsafe_allow_html=True)

try:
    pacotes, itens = load_data()
except Exception as e:
    st.error(f"Erro ao carregar a planilha: {e}")
    st.stop()

# Colunas públicas e cálculo
pacotes["Status público"] = pacotes.apply(compute_public_status, axis=1)
pacotes["Dias em espera"] = pacotes.apply(lambda r: calc_days_waiting(r, today), axis=1)

# KPIs
total = int(len(pacotes))
em_transito = int((pacotes["Status público"] == "Em trânsito").sum())
recebidos = int((pacotes["Status público"] == "Recebido").sum())

wait = pacotes.loc[pacotes["Status público"] == "Em trânsito", "Dias em espera"].dropna()
media_wait = int(round(float(wait.mean()))) if len(wait) else 0
max_wait = int(float(wait.max())) if len(wait) else 0

st.markdown('<div class="kpi-grid">', unsafe_allow_html=True)
kpi_card("🚚 Em trânsito", f"{em_transito}")
kpi_card("✅ Recebidos", f"{recebidos}")
kpi_card("⏳ Média de espera", f"{media_wait} dias")
kpi_card("🔥 Maior espera", f"{max_wait} dias")
st.markdown("</div>", unsafe_allow_html=True)

# Como entender (didático)
with st.expander("📌 Como ler este painel", expanded=False):
    st.write("1) **Em trânsito**: ainda não tem data de recebimento.")
    st.write("2) **Dias em espera**: contado desde a data de envio (se faltar, usa a data do pedido).")
    st.write(f"3) **Alerta**: aparece quando passar de **{DIAS_ALERTA} dias** em espera.")

st.divider()

# Busca simples (principal ação do cliente)
st.subheader("🔎 Buscar pacote")
q = st.text_input("Digite o número do Pacote ou o Código de Rastreio", placeholder="Ex: 35 ou LZ373185768CN")

# Configs simples (escondidas em expander)
with st.expander("⚙️ Opções", expanded=False):
    limite = st.selectbox("Quantidade para mostrar", [20, 30, 50, 80, 120], index=1)
    mostrar_camisas = st.toggle("Mostrar camisas do pacote", value=True)

# =========================
# 1) Lista principal: Em trânsito (mais antigo primeiro)
# =========================
st.subheader("⏳ Em trânsito (mais antigo primeiro)")

em_df = pacotes[pacotes["Status público"] == "Em trânsito"].copy()
em_df = em_df.sort_values(by="Dias em espera", ascending=False).head(limite)

if em_df.empty:
    st.info("Nenhum pacote em trânsito.")
else:
    for _, r in em_df.iterrows():
        pacote = safe_str(r.get("Pacote"))
        codigo = safe_str(r.get("Código de Rastreio"))
        dias = r.get("Dias em espera")
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
<div class="card">
  <div class="card-top">
    <div><b>Pacote {pacote}</b><br><span class="small">Código: {codigo}</span></div>
    <div class="{badge_class}">{badge_text}</div>
  </div>
  <div class="small">⏳ Dias em espera: <b>{dias_txt}</b>{extra}</div>
</div>
""",
            unsafe_allow_html=True,
        )

# =========================
# 2) Resultado da busca (quando digitar)
# =========================
if q.strip():
    st.divider()
    st.subheader("📌 Resultado da busca")

    qq = q.strip().lower()
    res = pacotes[
        pacotes["Pacote"].astype(str).str.lower().str.contains(qq, na=False)
        | pacotes["Código de Rastreio"].astype(str).str.lower().str.contains(qq, na=False)
    ].copy()

    if res.empty:
        st.info("Nada encontrado com esse pacote/código.")
    else:
        for _, r in res.head(20).iterrows():
            pacote = safe_str(r.get("Pacote"))
            codigo = safe_str(r.get("Código de Rastreio"))
            status = safe_str(r.get("Status público"))

            if status == "Recebido":
                drec = r.get("Data de recebimento")
                rec_txt = "—"
                if pd.notna(drec):
                    rec_txt = drec.strftime("%d/%m/%Y") if hasattr(drec, "strftime") else str(drec)

                st.markdown(
                    f"""
<div class="card">
  <div class="card-top">
    <div><b>Pacote {pacote}</b><br><span class="small">Código: {codigo}</span></div>
    <div class="badge badge-ok">✅ Recebido</div>
  </div>
  <div class="small">📅 Recebido em: <b>{rec_txt}</b></div>
</div>
""",
                    unsafe_allow_html=True,
                )
            else:
                dias = r.get("Dias em espera")
                dias_txt = "—" if pd.isna(dias) else f"{int(dias)} dias"
                warn = (not pd.isna(dias)) and int(dias) >= DIAS_ALERTA
                badge_class = "badge badge-warn" if warn else "badge"
                badge_text = f"⚠️ {DIAS_ALERTA}+ dias" if warn else "Em trânsito"

                st.markdown(
                    f"""
<div class="card">
  <div class="card-top">
    <div><b>Pacote {pacote}</b><br><span class="small">Código: {codigo}</span></div>
    <div class="{badge_class}">🚚 {badge_text}</div>
  </div>
  <div class="small">⏳ Dias em espera: <b>{dias_txt}</b></div>
</div>
""",
                    unsafe_allow_html=True,
                )

            if mostrar_camisas:
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
                        st.dataframe(it_small, use_container_width=True, hide_index=True, height=240)
