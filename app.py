import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

# =========================
# Config
# =========================
st.set_page_config(page_title="Status dos Pacotes", page_icon="📦", layout="centered")

ARQUIVO_EXCEL = "CONTROLE_LOGISTICO_FORMATADO_COM_FORMULAS.xlsx"
SHEET_PACOTES = "PACOTES"
SHEET_ITENS = "ITENS"

DIAS_ALERTA = 40
MAX_RESULTADOS_BUSCA = 20

# =========================
# CSS (mobile + didático)
# =========================
st.markdown(
    """
<style>
.block-container { padding-top: 0.9rem; padding-bottom: 1.6rem; max-width: 860px; }
h1 { font-size: 1.45rem !important; margin-bottom: 0.2rem; }
h2 { font-size: 1.15rem !important; }
h3 { font-size: 1.05rem !important; }

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
.small { font-size: 0.90rem; opacity: 0.83; margin-top: 6px; line-height: 1.35; }
hr { opacity: 0.12; }
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Helpers
# =========================
def safe_str(x) -> str:
    if x is None:
        return ""
    if isinstance(x, float) and np.isnan(x):
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


def public_status(row) -> str:
    # Se tem data de recebimento -> Recebido
    if pd.notna(row.get("Data de recebimento")):
        return "Recebido"

    # Se status textual indicar recebido/entregue -> Recebido
    s = safe_str(row.get("Status")).lower()
    if any(k in s for k in ["recebid", "entreg"]):
        return "Recebido"

    return "Em trânsito"


def dias_em_espera(row, today: date) -> float:
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


def correios_link(codigo: str) -> str | None:
    codigo = safe_str(codigo)
    if not codigo or codigo.lower() == "nan":
        return None
    return f"https://rastreamento.correios.com.br/app/index.php?objeto={codigo}"


def render_card_pacote(
    pacote: str,
    codigo: str,
    status: str,
    dias: float | None,
    data_envio,
    data_receb,
    show_button: bool = True,
):
    # Badge
    if status == "Recebido":
        badge_class = "badge badge-ok"
        badge_text = "✅ Recebido"
    else:
        warn = (dias is not None) and (not pd.isna(dias)) and int(dias) >= DIAS_ALERTA
        badge_class = "badge badge-warn" if warn else "badge"
        badge_text = f"⚠️ {DIAS_ALERTA}+ dias" if warn else "🚚 Em trânsito"

    # Linhas
    dias_txt = "—" if (dias is None or pd.isna(dias)) else f"{int(dias)} dias"

    envio_txt = ""
    if pd.notna(data_envio):
        envio_txt = data_envio.strftime("%d/%m/%Y") if hasattr(data_envio, "strftime") else str(data_envio)

    receb_txt = ""
    if pd.notna(data_receb):
        receb_txt = data_receb.strftime("%d/%m/%Y") if hasattr(data_receb, "strftime") else str(data_receb)

    # Card principal
    if status == "Recebido":
        line = f"📅 Recebido em: <b>{receb_txt or '—'}</b>"
    else:
        extra = f" • 📮 Enviado: <b>{envio_txt}</b>" if envio_txt else ""
        line = f"⏳ Dias em espera: <b>{dias_txt}</b>{extra}"

    st.markdown(
        f"""
<div class="card">
  <div class="card-top">
    <div><b>Pacote {pacote}</b><br><span class="small">Código: {codigo}</span></div>
    <div class="{badge_class}">{badge_text}</div>
  </div>
  <div class="small">{line}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    # Botão de rastreio (opcional)
    if show_button:
        link = correios_link(codigo)
        if link:
            st.link_button("📍 Rastrear nos Correios", link, use_container_width=True)


@st.cache_data(show_spinner=False)
def load_data():
    xls = pd.ExcelFile(ARQUIVO_EXCEL)
    if SHEET_PACOTES not in xls.sheet_names:
        raise ValueError(f"Aba '{SHEET_PACOTES}' não encontrada. Abas: {xls.sheet_names}")
    if SHEET_ITENS not in xls.sheet_names:
        raise ValueError(f"Aba '{SHEET_ITENS}' não encontrada. Abas: {xls.sheet_names}")

    pac = pd.read_excel(ARQUIVO_EXCEL, sheet_name=SHEET_PACOTES, engine="openpyxl").dropna(how="all")
    it = pd.read_excel(ARQUIVO_EXCEL, sheet_name=SHEET_ITENS, engine="openpyxl").dropna(how="all")

    # Checagem de colunas essenciais
    required_pac = ["Pacote", "Código de Rastreio", "Data do pedido", "Data do envio", "Data de recebimento", "Status"]
    required_it = ["Pacote", "Código de Rastreio", "Camisa", "Tamanho", "Qtd", "Cliente"]
    for c in required_pac:
        if c not in pac.columns:
            raise ValueError(f"Coluna '{c}' não encontrada em {SHEET_PACOTES}. Colunas: {list(pac.columns)}")
    for c in required_it:
        if c not in it.columns:
            raise ValueError(f"Coluna '{c}' não encontrada em {SHEET_ITENS}. Colunas: {list(it.columns)}")

    # Tipos
    pac["Pacote"] = pac["Pacote"].apply(
        lambda x: safe_str(int(x)) if isinstance(x, (int, float)) and pd.notna(x) else safe_str(x)
    )
    pac["Código de Rastreio"] = pac["Código de Rastreio"].astype(str).str.strip()

    it["Pacote"] = it["Pacote"].apply(lambda x: safe_str(x))
    it["Código de Rastreio"] = it["Código de Rastreio"].astype(str).str.strip()

    # Datas
    pac["Data do pedido"] = to_date_series(pac["Data do pedido"])
    pac["Data do envio"] = to_date_series(pac["Data do envio"])
    pac["Data de recebimento"] = to_date_series(pac["Data de recebimento"])

    # Qtd
    it["Qtd"] = pd.to_numeric(it["Qtd"], errors="coerce").fillna(0).astype(int)

    return pac, it


# =========================
# App
# =========================
today = date.today()

st.title("📦 Status dos Pacotes")
st.markdown(f'<div class="caption">📅 Atualizado em: <b>{today.strftime("%d/%m/%Y")}</b></div>', unsafe_allow_html=True)

# Carregar dados
try:
    pacotes, itens = load_data()
except FileNotFoundError:
    st.error(f"Não encontrei **{ARQUIVO_EXCEL}** na pasta do app.")
    st.info("✅ Coloque a planilha na raiz do repositório (mesma pasta do app.py).")
    st.stop()
except Exception as e:
    st.error(f"Erro ao carregar a planilha: {e}")
    st.stop()

# Calcular status e dias
pacotes["Status público"] = pacotes.apply(public_status, axis=1)
pacotes["Dias em espera"] = pacotes.apply(lambda r: dias_em_espera(r, today), axis=1)

# KPIs (direto e didático)
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

with st.expander("📌 Como entender (bem rápido)", expanded=False):
    st.write("• **Em trânsito**: ainda não tem data de recebimento.")
    st.write("• **Dias em espera**: contado desde a data de envio (se faltar, usa a data do pedido).")
    st.write(f"• **Alerta**: aparece quando passar de **{DIAS_ALERTA} dias**.")

st.divider()

# Busca (ação principal)
st.subheader("🔎 Buscar pacote")
q = st.text_input("Digite o número do Pacote ou o Código de Rastreio", placeholder="Ex: 35 ou LZ373185768CN")

# Opções (bem simples)
with st.expander("⚙️ Opções", expanded=False):
    limite = st.selectbox("Quantidade para mostrar", [20, 30, 50, 80, 120], index=1)
    mostrar_camisas = st.toggle("Mostrar camisas do pacote", value=True)

# =========================
# Seção 1: Em trânsito (principal)
# =========================
st.subheader("⏳ Em trânsito (mais antigos primeiro)")
st.caption("Aqui é onde você vê o que está mais atrasado.")

em_df = pacotes[pacotes["Status público"] == "Em trânsito"].copy()
em_df = em_df.sort_values(by="Dias em espera", ascending=False).head(limite)

if em_df.empty:
    st.info("Nenhum pacote em trânsito.")
else:
    for _, r in em_df.iterrows():
        pacote = safe_str(r.get("Pacote"))
        codigo = safe_str(r.get("Código de Rastreio"))
        status = safe_str(r.get("Status público"))
        dias = r.get("Dias em espera")
        d_envio = r.get("Data do envio")
        d_rec = r.get("Data de recebimento")

        render_card_pacote(
            pacote=pacote,
            codigo=codigo,
            status=status,
            dias=dias,
            data_envio=d_envio,
            data_receb=d_rec,
            show_button=True,  # botão Correios aqui
        )

        if mostrar_camisas:
            it = itens[
                (itens["Pacote"].astype(str) == str(pacote))
                | (itens["Código de Rastreio"].astype(str) == str(codigo))
            ].copy()

            if not it.empty:
                it_small = (
                    it.groupby(["Camisa", "Tamanho"], dropna=False)["Qtd"]
                    .sum()
                    .reset_index()
                    .sort_values(by=["Camisa", "Tamanho"])
                )
                with st.expander("👕 Ver camisas deste pacote", expanded=False):
                    st.dataframe(it_small, use_container_width=True, hide_index=True, height=240)

# =========================
# Seção 2: Resultado da busca
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
        res = res.head(MAX_RESULTADOS_BUSCA)
        for _, r in res.iterrows():
            pacote = safe_str(r.get("Pacote"))
            codigo = safe_str(r.get("Código de Rastreio"))
            status = safe_str(r.get("Status público"))
            dias = r.get("Dias em espera")
            d_envio = r.get("Data do envio")
            d_rec = r.get("Data de recebimento")

            render_card_pacote(
                pacote=pacote,
                codigo=codigo,
                status=status,
                dias=dias,
                data_envio=d_envio,
                data_receb=d_rec,
                show_button=True,  # botão Correios também aqui
            )

            if mostrar_camisas:
                it = itens[
                    (itens["Pacote"].astype(str) == str(pacote))
                    | (itens["Código de Rastreio"].astype(str) == str(codigo))
                ].copy()

                if not it.empty:
                    it_small = (
                        it.groupby(["Camisa", "Tamanho"], dropna=False)["Qtd"]
                        .sum()
                        .reset_index()
                        .sort_values(by=["Camisa", "Tamanho"])
                    )
                    with st.expander("👕 Ver camisas deste pacote", expanded=False):
                        st.dataframe(it_small, use_container_width=True, hide_index=True, height=240)

# =========================
# Diagnóstico (fechado)
# =========================
with st.expander("⚙️ Diagnóstico (manutenção)", expanded=False):
    st.write("Arquivo:", ARQUIVO_EXCEL)
    st.write("Abas:", SHEET_PACOTES, "/", SHEET_ITENS)
    st.write("Linhas PACOTES:", len(pacotes))
    st.write("Linhas ITENS:", len(itens))
