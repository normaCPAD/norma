"""Shareable NORMA demo. Deploy on Streamlit Cloud or a Hugging Face Space:

    pip install streamlit norma-dq
    streamlit run examples/streamlit_app.py

Upload a CSV -> discover constraints -> see errors vs rare-but-valid -> export to your stack.
"""
import pandas as pd
import streamlit as st

from norma.core.table import Table
from norma.models import DiscreteCPAD, RoutedCPAD
from norma.modeling.report import build_model
from norma.export import export, FORMATS

st.set_page_config(page_title="NORMA", layout="wide")
st.title("NORMA — discover the rules in your data")
st.caption("Learn denial constraints, detect errors (not just rare values), export anywhere.")

uploaded = st.file_uploader("Upload a CSV", type=["csv"])
col1, col2 = st.columns(2)
learner = col1.selectbox("Learner", ["discrete (fast)", "routed (complete)"])
top = col2.slider("Top violations to show", 5, 50, 20)

if uploaded is not None:
    df = pd.read_csv(uploaded, dtype=str)
    st.write(f"**{len(df)}** rows × **{len(df.columns)}** columns")
    table = Table.from_pandas(df)
    model = (RoutedCPAD() if learner.startswith("routed") else DiscreteCPAD(max_lhs=2)).fit(table)
    report = build_model(table, model, top_anomalies=top)

    st.components.v1.html(report._repr_html_(), height=600, scrolling=True)

    st.subheader("Export the discovered constraints")
    fmt = st.selectbox("Format", FORMATS)
    for name, content in export(report, fmt, kinds=table.kinds).items():
        st.download_button(f"⬇ {name}", content, file_name=name, key=name)
else:
    st.info("Upload a CSV to start. Try a dirty table where one column follows another "
            "(e.g. country → continent) with a few wrong values.")
