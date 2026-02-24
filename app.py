import streamlit as st
import pandas as pd

st.set_page_config(page_title="Pacotes - Logística", layout="wide")
st.title("📦 Dashboard - Controle Logístico")

ARQ = "CONTROLE_LOGISTICO_FORMATADO_COM_FORMULAS.xlsx"
ABA = "PACOTES"

@st.cache_data
def carregar():
    df = pd.read_excel(ARQ, sheet_name=ABA)
    df.columns = [str(c).strip() for c in df.columns]
    return df

df = carregar()

# Garantir datas (caso alguma esteja como texto)
for col in ["Data do pedido", "Data do envio", "Data de recebimento"]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

# Filtro
st.sidebar.header("Filtro")
status_lista = ["Todos"] + sorted(df["Status"].dropna().unique().tolist())
status = st.sidebar.selectbox("Status", status_lista)

df_f = df.copy() if status == "Todos" else df[df["Status"] == status].copy()

# Métricas
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total", len(df_f))
c2.metric("Recebidos", int((df_f["Status"] == "Recebido").sum()))
c3.metric("Em trânsito", int((df_f["Status"] == "Em trânsito").sum()))
c4.metric("Média (dias desde envio)", round(df_f["Dias desde envio"].mean(), 1) if len(df_f) else 0)

st.divider()

# Distribuição por faixa
def faixa(d):
    if pd.isna(d): return "Sem dado"
    d = int(d)
    if d <= 5: return "0–5"
    if d <= 10: return "6–10"
    if d <= 20: return "11–20"
    return "21+"

df_plot = df_f.copy()
df_plot["Faixa"] = df_plot["Dias desde envio"].apply(faixa)
dist = df_plot["Faixa"].value_counts().reindex(["0–5","6–10","11–20","21+","Sem dado"], fill_value=0)

colA, colB = st.columns([1, 1])

with colA:
    st.subheader("Distribuição (Dias desde envio)")
    st.bar_chart(dist)

with colB:
    st.subheader("Top mais demorados (Dias desde envio)")
    top = df_f.sort_values("Dias desde envio", ascending=False)[
        ["Pacote", "Status", "Dias desde envio", "Data do envio", "Data de recebimento"]
    ].head(20)
    st.dataframe(top, use_container_width=True)

st.subheader("Tabela completa")
st.dataframe(df_f, use_container_width=True)

# Download CSV
csv = df_f.to_csv(index=False).encode("utf-8")

st.download_button("⬇️ Baixar CSV (filtrado)", csv, "pacotes_filtrados.csv", "text/csv")
