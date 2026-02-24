import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Painel de Pacotes", layout="wide")

APP_TITLE = "📦 Painel de Pacotes (sem senha)"
TRACK_COL = "Código de Rastreio"
CLIENT_COL = "Cliente"
STATUS_COL = "Status"
CORREIOS_URL = "https://rastreamento.correios.com.br/app/index.php?objetos="
CACHE_TTL = 60

def limpar_codigo(valor) -> str:
    if pd.isna(valor):
        return ""
    s = str(valor).strip().upper()
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s

@st.cache_data(ttl=CACHE_TTL)
def carregar_dados() -> pd.DataFrame:
    csv_url = st.secrets.get("CSV_URL", "").strip()
    try:
        if csv_url:
            df = pd.read_csv(csv_url, sep=None, engine="python", encoding="utf-8-sig")
        else:
            df = pd.read_csv("pacotes.csv", sep=None, engine="python", encoding="utf-8-sig")
    except Exception as e:
        st.error("Não consegui ler os dados.")
        st.code(str(e))
        st.info("Se usa planilha: configure o Secrets CSV_URL. Se usa arquivo: confirme que existe pacotes.csv no repo.")
        st.stop()

    df.columns = [c.strip() for c in df.columns]

    if TRACK_COL in df.columns:
        df[TRACK_COL] = df[TRACK_COL].apply(limpar_codigo)
        df["Rastreio (URL)"] = df[TRACK_COL].apply(lambda x: CORREIOS_URL + x if x else "")
    else:
        st.warning(f"Não achei a coluna '{TRACK_COL}'. Colunas encontradas: {list(df.columns)}")

    return df

def limpar_cache():
    carregar_dados.clear()

st.title(APP_TITLE)

c1, c2 = st.columns([1, 3])
with c1:
    if st.button("🔄 Atualizar agora"):
        limpar_cache()
        st.rerun()
with c2:
    st.caption("Sem senha: qualquer pessoa com o link acessa.")

df = carregar_dados()

st.subheader("Filtros")
f1, f2, f3 = st.columns(3)

clientes = ["Todos"]
if CLIENT_COL in df.columns:
    clientes += sorted(df[CLIENT_COL].dropna().unique().tolist())

status_list = ["Todos"]
if STATUS_COL in df.columns:
    status_list += sorted(df[STATUS_COL].dropna().unique().tolist())

with f1:
    cliente_sel = st.selectbox("Cliente", clientes)
with f2:
    status_sel = st.selectbox("Status", status_list)
with f3:
    busca = st.text_input("Buscar (qualquer campo)", "")

fdf = df.copy()

if cliente_sel != "Todos" and CLIENT_COL in fdf.columns:
    fdf = fdf[fdf[CLIENT_COL] == cliente_sel]

if status_sel != "Todos" and STATUS_COL in fdf.columns:
    fdf = fdf[fdf[STATUS_COL] == status_sel]

if busca.strip():
    term = busca.strip().lower()
    mask = False
    for c in fdf.columns:
        if fdf[c].dtype == "object":
            mask = mask | fdf[c].fillna("").astype(str).str.lower().str.contains(term, regex=False)
    fdf = fdf[mask]

st.subheader("Abrir rastreio rápido")
if TRACK_COL in fdf.columns:
    codigos = [c for c in fdf[TRACK_COL].dropna().unique().tolist() if str(c).strip()]
    if codigos:
        code_sel = st.selectbox("Selecione um código", codigos)
        st.markdown(f"➡️ Clique aqui: [{code_sel}]({CORREIOS_URL + str(code_sel)})")
    else:
        st.info("Nenhum código de rastreio no filtro atual.")
else:
    st.info("Coluna de rastreio não encontrada.")

st.subheader("Lista")
st.dataframe(fdf, use_container_width=True)

st.download_button(
    "⬇️ Baixar CSV (com filtros)",
    data=fdf.to_csv(index=False).encode("utf-8"),
    file_name="pacotes_filtrados.csv",
    mime="text/csv"
)
