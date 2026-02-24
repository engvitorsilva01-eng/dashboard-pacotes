import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Painel de Pacotes", layout="wide")

# ====== CONFIG ======
ARQ = "CONTROLE_LOGISTICO_FORMATADO_COM_FORMULAS.xlsx"
ABA = "PACOTES"

# ====== TOPO ======
st.title("📦 Painel de Pacotes — Controle Logístico")
st.caption(
    "✅ Este painel mostra o **status dos pacotes** e o **tempo desde o envio**.\n\n"
    "➡️ Use o **filtro à esquerda** para ver apenas *Recebidos* ou *Em trânsito*.\n\n"
    "ℹ️ **Dias desde envio** = dias corridos desde a **Data do envio**."
)

# Hora de atualização (visual)
st.markdown(f"🕒 **Atualizado em:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

st.divider()

# ====== LEITURA ======
@st.cache_data(ttl=60)
def carregar_excel():
    df = pd.read_excel(ARQ, sheet_name=ABA)
    df.columns = [str(c).strip() for c in df.columns]
    return df

df = carregar_excel()

# Converter datas (se existirem)
for col in ["Data do pedido", "Data do envio", "Data de recebimento"]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

# Checagem de colunas (evita quebrar o app)
necessarias = ["Pacote", "Status", "Dias desde envio"]
faltando = [c for c in necessarias if c not in df.columns]
if faltando:
    st.error("⚠️ A planilha está sem estas colunas na aba PACOTES: " + ", ".join(faltando))
    st.stop()

# ====== FILTRO ======
st.sidebar.header("Filtro")
status_lista = ["Todos"] + sorted(df["Status"].dropna().unique().tolist())
status = st.sidebar.selectbox("Status", status_lista)

df_f = df.copy() if status == "Todos" else df[df["Status"] == status].copy()

# ====== MÉTRICAS ======
c1, c2, c3, c4 = st.columns(4)

total = len(df_f)
recebidos = int((df_f["Status"] == "Recebido").sum())
em_transito = int((df_f["Status"] == "Em trânsito").sum())
media_dias = round(float(df_f["Dias desde envio"].mean()), 1) if total else 0

c1.metric("📦 Total de pacotes", total)
c2.metric("✅ Recebidos", recebidos)
c3.metric("🚚 Em trânsito", em_transito)
c4.metric("⏱️ Média (dias desde envio)", media_dias)

st.divider()

# ====== FAIXAS MAIS CLARAS ======
def faixa_humana(d):
    if pd.isna(d):
        return "Sem data"
    try:
        d = int(d)
    except:
        return "Sem data"
    if d <= 5:
        return "Até 5 dias"
    if d <= 10:
        return "6 a 10 dias"
    if d <= 20:
        return "11 a 20 dias"
    return "Mais de 20 dias"

df_plot = df_f.copy()
df_plot["Faixa de dias"] = df_plot["Dias desde envio"].apply(faixa_humana)

ordem = ["Até 5 dias", "6 a 10 dias", "11 a 20 dias", "Mais de 20 dias", "Sem data"]
dist = df_plot["Faixa de dias"].value_counts().reindex(ordem, fill_value=0)

colA, colB = st.columns([1, 1])

with colA:
    st.subheader("📊 Quantos pacotes por faixa de dias (desde envio)")
    st.bar_chart(dist)

# ====== TOP DEMORADOS (ENXUTO + CORES) ======
def cor_status(v):
    v = str(v).strip().lower()
    if v == "recebido":
        return "background-color: #d4edda; color: #155724;"  # verde claro
    if v == "em trânsito" or v == "em transito":
        return "background-color: #fff3cd; color: #856404;"  # amarelo claro
    return "background-color: #f8d7da; color: #721c24;"      # vermelho claro (outros)

with colB:
    st.subheader("⏳ Top 20 mais demorados (dias desde envio)")

    # Colunas mais importantes (se existirem)
    colunas_top = [c for c in ["Pacote", "Status", "Dias desde envio", "Data do envio"] if c in df_f.columns]

    top = (
        df_f.sort_values("Dias desde envio", ascending=False)
        .loc[:, colunas_top]
        .head(20)
        .copy()
    )

    # Formatar datas para leitura
    if "Data do envio" in top.columns:
        top["Data do envio"] = pd.to_datetime(top["Data do envio"], errors="coerce").dt.strftime("%d/%m/%Y")

    # Estilo com cor no Status
    if "Status" in top.columns:
        styler = top.style.applymap(cor_status, subset=["Status"])
        st.dataframe(styler, use_container_width=True)
    else:
        st.dataframe(top, use_container_width=True)

st.divider()

# ====== EXPORTAR ======
st.subheader("📥 Exportar relatório")
nome_filtro = "Todos" if status == "Todos" else f"Status_{status}".replace(" ", "_")
csv = df_f.to_csv(index=False).encode("utf-8")

st.download_button(
    f"⬇️ Baixar relatório (CSV) — {status}",
    data=csv,
    file_name=f"pacotes_{nome_filtro}.csv",
    mime="text/csv",
)
