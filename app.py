import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Pacotes — Dias em Espera", layout="wide")

ARQ = "CONTROLE_LOGISTICO_FORMATADO_COM_FORMULAS.xlsx"
ABA = "PACOTES"

st.title("📦 Painel de Pacotes — Dias em Espera")
st.caption("**Dias em espera** = dias corridos desde a **Data do envio**. Use os filtros para refinar.")
st.markdown(f"🕒 **Atualizado em:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
st.divider()

@st.cache_data(ttl=60)
def carregar_excel():
    df = pd.read_excel(ARQ, sheet_name=ABA)
    df.columns = [str(c).strip() for c in df.columns]
    return df

df = carregar_excel()

# Datas
for col in ["Data do pedido", "Data do envio", "Data de recebimento"]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

# Checagem mínima
necessarias = ["Pacote", "Status", "Dias desde envio"]
faltando = [c for c in necessarias if c not in df.columns]
if faltando:
    st.error("⚠️ Faltam colunas na aba PACOTES: " + ", ".join(faltando))
    st.stop()

# Renomear para ficar didático
df = df.rename(columns={"Dias desde envio": "Dias em espera"})

def faixa_humana(d):
    if pd.isna(d): return "Sem data"
    try:
        d = int(d)
    except:
        return "Sem data"
    if d <= 5: return "Até 5 dias"
    if d <= 10: return "6 a 10 dias"
    if d <= 20: return "11 a 20 dias"
    return "21+ dias"

df["Faixa"] = df["Dias em espera"].apply(faixa_humana)

# ===== FILTROS =====
st.sidebar.header("Filtros")
status_lista = ["Todos"] + sorted(df["Status"].dropna().unique().tolist())
status = st.sidebar.selectbox("Status", status_lista)

faixas_ordem = ["Todas", "Até 5 dias", "6 a 10 dias", "11 a 20 dias", "21+ dias", "Sem data"]
faixa = st.sidebar.selectbox("Faixa de dias", faixas_ordem)

df_f = df.copy()
if status != "Todos":
    df_f = df_f[df_f["Status"] == status]
if faixa != "Todas":
    df_f = df_f[df_f["Faixa"] == faixa]

# ===== CONTADORES (BEM VISÍVEIS) =====
total = len(df_f)
qtd_recebidos = int((df_f["Status"] == "Recebido").sum())
qtd_transito = int((df_f["Status"] == "Em trânsito").sum())

# ===== INDICADORES PRINCIPAIS =====
max_dias = int(df_f["Dias em espera"].max()) if total and df_f["Dias em espera"].notna().any() else 0
media_dias = round(float(df_f["Dias em espera"].mean()), 1) if total else 0

pacote_top = "-"
if total and df_f["Dias em espera"].notna().any():
    pacote_top = str(df_f.sort_values("Dias em espera", ascending=False).iloc[0]["Pacote"])

qtd_21 = int((df_f["Faixa"] == "21+ dias").sum())

# Linha 1 (o que você pediu: recebidos e em trânsito)
a1, a2, a3 = st.columns(3)
a1.metric("📦 Total de pacotes", total)
a2.metric("✅ Recebidos", qtd_recebidos)
a3.metric("🚚 Em trânsito", qtd_transito)

# Linha 2 (tempo de espera)
b1, b2, b3, b4 = st.columns(4)
b1.metric("⏱️ Maior espera (dias)", max_dias)
b2.metric("🏷️ Pacote mais atrasado", pacote_top)
b3.metric("📈 Média (dias)", media_dias)
b4.metric("🔥 Pacotes 21+ dias", qtd_21)

st.divider()

# ===== GRÁFICO =====
st.subheader("📊 Quantos pacotes por faixa de dias em espera")
ordem = ["Até 5 dias", "6 a 10 dias", "11 a 20 dias", "21+ dias", "Sem data"]
dist = df_f["Faixa"].value_counts().reindex(ordem, fill_value=0)
st.bar_chart(dist)

st.divider()

# ===== RANKING PRINCIPAL =====
st.subheader("🏆 Ranking — pacotes com mais dias em espera")

cols_rank = [c for c in ["Pacote", "Status", "Dias em espera", "Data do envio", "Data de recebimento"] if c in df_f.columns]
rank = df_f.sort_values("Dias em espera", ascending=False)[cols_rank].head(50).copy()

# Formatar datas
if "Data do envio" in rank.columns:
    rank["Data do envio"] = pd.to_datetime(rank["Data do envio"], errors="coerce").dt.strftime("%d/%m/%Y")
if "Data de recebimento" in rank.columns:
    rank["Data de recebimento"] = pd.to_datetime(rank["Data de recebimento"], errors="coerce").dt.strftime("%d/%m/%Y")

st.dataframe(rank, use_container_width=True)

st.divider()

# ===== EXPORTAR =====
st.subheader("📥 Exportar relatório")
csv = df_f.drop(columns=["Faixa"], errors="ignore").to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Baixar CSV", csv, "relatorio_pacotes.csv", "text/csv")
