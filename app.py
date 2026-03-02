import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

# =========================================================
# 1) CONFIGURAÇÕES (mexer aqui é fácil)
# =========================================================
ARQUIVO_EXCEL = "CONTROLE_LOGISTICO_FORMATADO_COM_FORMULAS.xlsx"
SHEET_PACOTES = "PACOTES"
SHEET_ITENS = "ITENS"

DIAS_ALERTA = 40           # a partir de quantos dias mostra alerta
LIMITE_PADRAO = 30         # quantos pacotes mostrar por padrão

st.set_page_config(page_title="Painel de Rastreamento", page_icon="📦", layout="centered")


# =========================================================
# 2) ESTILO (visual)
# =========================================================
st.markdown("""
<style>
#MainMenu{visibility:hidden;} footer{visibility:hidden;} header{visibility:hidden;}
.block-container{padding-top:.9rem; padding-bottom:1.6rem; max-width:860px;}
.caption{opacity:.8; font-size:.95rem; margin:.1rem 0 .9rem 0;}

.kpi-grid{display:grid; grid-template-columns:repeat(2,1fr); gap:10px;}
@media (min-width:900px){.kpi-grid{grid-template-columns:repeat(4,1fr);}}
.kpi-card{border:1px solid rgba(250,250,250,.12); border-radius:16px; padding:12px 14px;
background:rgba(255,255,255,.03);}
.kpi-title{font-size:.82rem; opacity:.78; margin-bottom:2px;}
.kpi-value{font-size:1.35rem; font-weight:850; line-height:1.2;}

.card{border:1px solid rgba(250,250,250,.12); border-radius:16px; padding:14px; margin-bottom:10px;
background:linear-gradient(180deg, rgba(255,255,255,.035), rgba(255,255,255,.02));
box-shadow:0 8px 20px rgba(0,0,0,.18);}
.card-top{display:flex; justify-content:space-between; align-items:flex-start; gap:10px;}
.badge{padding:4px 10px; border-radius:999px; font-size:.78rem;
border:1px solid rgba(250,250,250,.20); opacity:.95; white-space:nowrap;}
.badge-warn{border-color:rgba(255,180,60,.72);}
.badge-ok{border-color:rgba(110,255,180,180,.20);}
.small{font-size:.90rem; opacity:.88; margin-top:6px; line-height:1.35;}
hr{opacity:.12;}
</style>
""", unsafe_allow_html=True)


# =========================================================
# 3) FUNÇÕES PEQUENAS (pra entender fácil)
# =========================================================
def safe_str(x) -> str:
    """Converte para texto sem 'nan' e sem espaços."""
    if x is None:
        return ""
    if isinstance(x, float) and np.isnan(x):
        return ""
    s = str(x).strip()
    return "" if s.lower() == "nan" else s


def correios_link(codigo: str) -> str | None:
    """Monta link dos Correios para o código."""
    codigo = safe_str(codigo)
    if not codigo:
        return None
    return f"https://rastreamento.correios.com.br/app/index.php?objeto={codigo}"


def kpi_card(title: str, value: str):
    st.markdown(f"""
<div class="kpi-card">
  <div class="kpi-title">{title}</div>
  <div class="kpi-value">{value}</div>
</div>
""", unsafe_allow_html=True)


def render_card(pacote, codigo, status, dias_espera, data_envio, data_receb):
    """Mostra um card (bonito) com botão de rastreio."""
    status = safe_str(status)

    if status.lower().startswith("receb"):
        badge_class, badge_text = "badge badge-ok", "✅ Recebido"
        rec = "—"
        if pd.notna(data_receb):
            rec = data_receb.strftime("%d/%m/%Y") if hasattr(data_receb, "strftime") else str(data_receb)
        line = f"📅 Recebido em: <b>{rec}</b>"
    else:
        # Em trânsito
        warn = pd.notna(dias_espera) and int(dias_espera) >= DIAS_ALERTA
        badge_class = "badge badge-warn" if warn else "badge"
        badge_text = f"⚠️ {DIAS_ALERTA}+ dias" if warn else "🚚 Em trânsito"

        dias_txt = "—" if pd.isna(dias_espera) else f"{int(dias_espera)} dias"

        env = ""
        if pd.notna(data_envio):
            env = data_envio.strftime("%d/%m/%Y") if hasattr(data_envio, "strftime") else str(data_envio)

        extra = f" • 📮 Enviado: <b>{env}</b>" if env else ""
        line = f"⏳ Dias em espera: <b>{dias_txt}</b>{extra}"

    st.markdown(f"""
<div class="card">
  <div class="card-top">
    <div><b>Pacote {pacote}</b><br><span class="small">Código: {codigo}</span></div>
    <div class="{badge_class}">{badge_text}</div>
  </div>
  <div class="small">{line}</div>
</div>
""", unsafe_allow_html=True)

    link = correios_link(codigo)
    if link:
        st.link_button("📍 Abrir rastreio", link, use_container_width=True)


@st.cache_data(show_spinner=False)
def load_data():
    """Carrega PACOTES e ITENS e garante tipos básicos."""
    pac = pd.read_excel(ARQUIVO_EXCEL, sheet_name=SHEET_PACOTES, engine="openpyxl").dropna(how="all")
    it = pd.read_excel(ARQUIVO_EXCEL, sheet_name=SHEET_ITENS, engine="openpyxl").dropna(how="all")

    # Ajustes pra ficar limpo no app
    pac["Pacote"] = pac["Pacote"].apply(lambda x: safe_str(int(x)) if isinstance(x, (int, float)) and pd.notna(x) else safe_str(x))
    pac["Código de Rastreio"] = pac["Código de Rastreio"].apply(safe_str)
    it["Pacote"] = it["Pacote"].apply(safe_str)
    it["Código de Rastreio"] = it["Código de Rastreio"].apply(safe_str)

    # Qtd como número inteiro
    it["Qtd"] = pd.to_numeric(it["Qtd"], errors="coerce").fillna(0).astype(int)

    return pac, it


def prepare_pacotes(pacotes: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara as colunas que o painel usa.
    IMPORTANTE: a sua planilha já tem 'Dias desde envio' e 'Dias desde pedido'
    então a gente usa isso (mais confiável).
    """
    df = pacotes.copy()

    # Status público: se tiver Data de recebimento ou Status=Recebido
    df["Status público"] = df["Status"].apply(lambda s: "Recebido" if str(s).lower().startswith("receb") else "Em trânsito")
    # Se tiver data de recebimento, garante Recebido
    df.loc[pd.notna(df["Data de recebimento"]), "Status público"] = "Recebido"

    # Dias em espera: usa a coluna pronta "Dias desde envio"
    # Se faltar envio, usa "Dias desde pedido"
    df["Dias em espera"] = df["Dias desde envio"]
    df.loc[df["Dias em espera"].isna(), "Dias em espera"] = df["Dias desde pedido"]

    # Só faz sentido para Em trânsito
    df.loc[df["Status público"] == "Recebido", "Dias em espera"] = np.nan

    return df


def itens_do_pacote(itens: pd.DataFrame, pacote: str, codigo: str) -> pd.DataFrame:
    """Puxa e resume as camisas do pacote, agrupando Camisa + Tamanho."""
    it = itens[(itens["Pacote"] == str(pacote)) | (itens["Código de Rastreio"] == str(codigo))].copy()
    if it.empty:
        return it
    resumo = (
        it.groupby(["Camisa", "Tamanho"], dropna=False)["Qtd"]
        .sum()
        .reset_index()
        .sort_values(by=["Camisa", "Tamanho"])
    )
    return resumo


# =========================================================
# 4) APP (TELAS)
# =========================================================
today = date.today()

st.markdown("""
<div style="font-size:1.35rem;font-weight:900;line-height:1.1;">📦 Painel de Rastreamento</div>
<div style="opacity:.78;margin-top:4px;">Consulte o pacote e rastreie em 1 clique.</div>
""", unsafe_allow_html=True)
st.markdown(f'<div class="caption">📅 Atualizado em: <b>{today.strftime("%d/%m/%Y")}</b></div>', unsafe_allow_html=True)

try:
    pacotes_raw, itens_raw = load_data()
except Exception as e:
    st.error(f"Erro ao carregar planilha: {e}")
    st.stop()

pacotes = prepare_pacotes(pacotes_raw)

# KPIs (objetivo)
em_transito = int((pacotes["Status público"] == "Em trânsito").sum())
recebidos = int((pacotes["Status público"] == "Recebido").sum())

wait = pacotes.loc[pacotes["Status público"] == "Em trânsito", "Dias em espera"].dropna()
media_wait = int(round(float(wait.mean()))) if len(wait) else 0
max_wait = int(float(wait.max())) if len(wait) else 0

st.markdown('<div class="kpi-grid">', unsafe_allow_html=True)
kpi_card("🚚 Em trânsito", str(em_transito))
kpi_card("✅ Recebidos", str(recebidos))
kpi_card("⏳ Média", f"{media_wait} dias")
kpi_card("🔥 Maior atraso", f"{max_wait} dias")
st.markdown("</div>", unsafe_allow_html=True)

with st.expander("ℹ️ Entenda em 10 segundos", expanded=False):
    st.write("• **Em trânsito**: ainda não tem data de recebimento.")
    st.write("• **Dias em espera**: vem da sua planilha (Dias desde envio / Dias desde pedido).")
    st.write(f"• **Alerta**: aparece após **{DIAS_ALERTA} dias**.")

st.divider()

tab1, tab2 = st.tabs(["🔎 Consultar", "⏳ Em trânsito"])

# ---- Tela 1: Consultar
with tab1:
    st.subheader("Consultar pacote")
    q = st.text_input("Pacote ou código", placeholder="Ex: 35 ou LZ373185768CN", label_visibility="collapsed")
    mostrar_camisas = st.toggle("Mostrar camisas do pacote", value=True)

    if not q.strip():
        st.info("Digite um **Pacote** ou **Código** acima para consultar.")
    else:
        qq = q.strip().lower()
        res = pacotes[
            pacotes["Pacote"].astype(str).str.lower().str.contains(qq, na=False) |
            pacotes["Código de Rastreio"].astype(str).str.lower().str.contains(qq, na=False)
        ].copy()

        if res.empty:
            st.warning("Nada encontrado.")
        else:
            for _, r in res.head(20).iterrows():
                pacote = safe_str(r["Pacote"])
                codigo = safe_str(r["Código de Rastreio"])
                render_card(
                    pacote=pacote,
                    codigo=codigo,
                    status=r["Status público"],
                    dias_espera=r["Dias em espera"],
                    data_envio=r["Data do envio"],
                    data_receb=r["Data de recebimento"],
                )

                if mostrar_camisas:
                    resumo = itens_do_pacote(itens_raw, pacote, codigo)
                    if not resumo.empty:
                        with st.expander("👕 Ver camisas", expanded=False):
                            st.dataframe(resumo, use_container_width=True, hide_index=True, height=240)

# ---- Tela 2: Em trânsito
with tab2:
    st.subheader("Em trânsito (mais atrasados primeiro)")
    limite = st.selectbox("Quantidade", [20, 30, 50, 80, 120], index=1)

    em = pacotes[pacotes["Status público"] == "Em trânsito"].copy()
    em = em.sort_values(by="Dias em espera", ascending=False).head(limite)

    if em.empty:
        st.info("Nenhum pacote em trânsito.")
    else:
        for _, r in em.iterrows():
            render_card(
                pacote=safe_str(r["Pacote"]),
                codigo=safe_str(r["Código de Rastreio"]),
                status=r["Status público"],
                dias_espera=r["Dias em espera"],
                data_envio=r["Data do envio"],
                data_receb=r["Data de recebimento"],
            )

st.divider()
st.caption("Painel público • Dados atualizados conforme planilha de controle")
