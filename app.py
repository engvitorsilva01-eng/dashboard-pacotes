import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

st.set_page_config(page_title="Painel de Pacotes", page_icon="📦", layout="wide")

ARQUIVO_EXCEL = "CONTROLE_LOGISTICO_FORMATADO_COM_FORMULAS.xlsx"
SHEET_PACOTES = "PACOTES"
SHEET_ITENS = "ITENS"
DIAS_ALERTA = 40  # alerta após 40 dias em trânsito


# =========================
# CSS (visual objetivo)
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
.kpi-value { font-size: 1.6rem; font-weight: 780; line-height: 1.2; }

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
.caption { opacity: 0.75; font-size: 0.9rem; }
hr { opacity: 0.15; }
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
    """
    Regra:
    - Se tem Data de recebimento -> RECEBIDO
    - Senão, se Status contém 'receb'/'entreg' -> RECEBIDO
    - Senão -> EM TRANSITO
    """
    receb = row.get("Data de recebimento")
    if pd.notna(receb):
        return "RECEBIDO"

    status = safe_str(row.get("Status")).lower()
    if any(k in status for k in ["recebid", "entreg"]):
        return "RECEBIDO"

    return "EM TRANSITO"


def calc_days_waiting(row, today: date) -> float:
    """
    Dias em espera (somente em trânsito):
    prioridade: Data do envio; se não tiver, usa Data do pedido.
    """
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
    itens = pd.read_excel(ARQUIVO_EXCEL, sheet_name=SHEET_ITENS, engine="openpyxl").dropna(how="all")

    # Garantir que colunas esperadas existam
    required_pac = [
        "Pacote", "Código de Rastreio", "Data do pedido", "Data do envio",
        "Data de recebimento", "Status"
    ]
    for c in required_pac:
        if c not in pac.columns:
            raise ValueError(f"Coluna '{c}' não encontrada em {SHEET_PACOTES}. Colunas: {list(pac.columns)}")

    required_itens = ["Pacote", "Código de Rastreio", "Camisa", "Tamanho", "Qtd", "Cliente"]
    for c in required_itens:
        if c not in itens.columns:
            raise ValueError(f"Coluna '{c}' não encontrada em {SHEET_ITENS}. Colunas: {list(itens.columns)}")

    # Tipos
    pac["Código de Rastreio"] = pac["Código de Rastreio"].astype(str).str.strip()
    itens["Código de Rastreio"] = itens["Código de Rastreio"].astype(str).str.strip()

    # Datas
    pac["Data do pedido"] = to_date_series(pac["Data do pedido"])
    pac["Data do envio"] = to_date_series(pac["Data do envio"])
    pac["Data de recebimento"] = to_date_series(pac["Data de recebimento"])

    # Normalizar "Pacote" (alguns podem vir float)
    pac["Pacote"] = pac["Pacote"].apply(lambda x: safe_str(int(x)) if isinstance(x, (int, float)) and pd.notna(x) else safe_str(x))
    itens["Pacote"] = itens["Pacote"].apply(lambda x: safe_str(x))

    return pac, itens


# =========================
# App
# =========================
st.title("📦 Painel Público de Pacotes")
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

# Status público + dias em espera
pacotes["STATUS_PUBLICO"] = pacotes.apply(compute_public_status, axis=1)
pacotes["DIAS_EM_ESPERA"] = pacotes.apply(lambda r: calc_days_waiting(r, today), axis=1)

# KPIs
total = int(len(pacotes))
em_transito = int((pacotes["STATUS_PUBLICO"] == "EM TRANSITO").sum())
recebidos = int((pacotes["STATUS_PUBLICO"] == "RECEBIDO").sum())

wait_series = pacotes.loc[pacotes["STATUS_PUBLICO"] == "EM TRANSITO", "DIAS_EM_ESPERA"].dropna()
media_wait = int(round(float(wait_series.mean()))) if len(wait_series) else 0
max_wait = int(float(wait_series.max())) if len(wait_series) else 0

st.markdown('<div class="kpi-grid">', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
with c1: kpi_card("📦 Total", f"{total}")
with c2: kpi_card("🚚 Em trânsito", f"{em_transito}")
with c3: kpi_card("✅ Recebidos", f"{recebidos}")
with c4: kpi_card("⏳ Espera (média / máximo)", f"{media_wait}d / {max_wait}d")
st.markdown("</div>", unsafe_allow_html=True)

# Filtros
st.divider()
colA, colB, colC = st.columns([2, 1, 1])
with colA:
    q = st.text_input("🔎 Buscar por Pacote ou Código de Rastreio", placeholder="Ex: 35, LZ373185768CN...")
with colB:
    filtro = st.selectbox("Filtrar", ["Todos", "Em trânsito", "Recebidos"], index=0)
with colC:
    limite = st.selectbox("Mostrar", [20, 30, 50, 80, 120], index=1)

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

# Seção principal: Em trânsito (sempre em destaque)
st.divider()
st.subheader("⏳ Em trânsito — mais antigos primeiro")
st.caption("A informação principal é: **quantos dias está em espera**.")

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
        badge_text = f"⚠️ ATENÇÃO ({DIAS_ALERTA}+ dias)" if warn else "Em trânsito"

        extra = f" • 📮 Enviado: <b>{envio_txt}</b>" if envio_txt else ""

        st.markdown(
            f"""
<div class="row-card">
  <div class="row-top">
    <div><b>📦 Pacote {pacote}</b>{f" — <span class='small'>Código: {codigo}</span>" if codigo else ""}</div>
    <div class="{badge_class}">🚚 {badge_text}</div>
  </div>
  <div class="small">⏳ Espera: <b>{dias_txt}</b>{extra}</div>
</div>
""",
            unsafe_allow_html=True,
        )

# Resultado da busca/filtro (cards + itens do pacote)
st.divider()
st.subheader("📌 Resultado da busca / filtro")

if df.empty:
    st.info("Nada para mostrar com esse filtro/busca.")
else:
    df_show = df.copy()

    # Ordenação: se estiver em trânsito, prioriza mais antigos
    df_show["__ord"] = df_show["DIAS_EM_ESPERA"].fillna(-1)
    df_show = df_show.sort_values(by=["STATUS_PUBLICO", "__ord"], ascending=[True, False]).drop(columns="__ord")
    df_show = df_show.head(limite)

    mostrar_itens = st.toggle("Mostrar camisas dentro do pacote (aba ITENS)", value=True)

    for _, r in df_show.iterrows():
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
    <div><b>📦 Pacote {pacote}</b>{f" — <span class='small'>Código: {codigo}</span>" if codigo else ""}</div>
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
            badge_text = f"⚠️ ATENÇÃO ({DIAS_ALERTA}+ dias)" if warn else "Em trânsito"

            st.markdown(
                f"""
<div class="row-card">
  <div class="row-top">
    <div><b>📦 Pacote {pacote}</b>{f" — <span class='small'>Código: {codigo}</span>" if codigo else ""}</div>
    <div class="{badge_class}">🚚 {badge_text}</div>
  </div>
  <div class="small">⏳ Espera: <b>{dias_txt}</b></div>
</div>
""",
                unsafe_allow_html=True,
            )

        if mostrar_itens:
            # Procurar itens por Pacote OU por Código de Rastreio
            it = itens[
                (itens["Pacote"].astype(str) == str(pacote))
                | (itens["Código de Rastreio"].astype(str) == str(codigo))
            ].copy()

            if not it.empty:
                # Enxuto: agrupar por camisa+tamanho+cliente
                it["Qtd"] = pd.to_numeric(it["Qtd"], errors="coerce").fillna(0).astype(int)
                it_small = (
                    it.groupby(["Camisa", "Tamanho", "Cliente"], dropna=False)["Qtd"]
                    .sum()
                    .reset_index()
                    .sort_values(by=["Camisa", "Tamanho"])
                )

                st.dataframe(
                    it_small,
                    use_container_width=True,
                    hide_index=True
                )

# Diagnóstico (fechado)
with st.expander("⚙️ Diagnóstico (para manutenção)", expanded=False):
    st.write("Arquivo:", ARQUIVO_EXCEL)
    st.write("Abas usadas:", SHEET_PACOTES, "e", SHEET_ITENS)
    st.write("Colunas PACOTES:", list(pacotes.columns))
    st.write("Colunas ITENS:", list(itens.columns))
