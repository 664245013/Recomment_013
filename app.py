import pandas as pd
import streamlit as st
from neo4j import GraphDatabase

from data import HOTELS, LIKES, PERSONS

st.set_page_config(page_title="Hotel Recommendation System", page_icon="🏨", layout="wide")

REC_QUERY = """
MATCH (t:Person {name: $name})-[:LIKES]->(common:Hotel)<-[:LIKES]-(other:Person)
WHERE other <> t
WITH t, other, count(common) AS shared
MATCH (other)-[:LIKES]->(rec:Hotel)
WHERE NOT (t)-[:LIKES]->(rec)
RETURN rec.name AS hotel,
       count(DISTINCT other) AS voters,
       sum(shared) AS similarity_score,
       collect(DISTINCT other.name) AS recommended_by
ORDER BY similarity_score DESC, voters DESC, hotel
LIMIT $top_n
"""


@st.cache_resource
def get_driver():
    s = st.secrets
    driver = GraphDatabase.driver(s["NEO4J_URI"], auth=(s["NEO4J_USER"], s["NEO4J_PASSWORD"]))
    driver.verify_connectivity()
    return driver


def run(query, **params):
    db = st.secrets.get("NEO4J_DATABASE", "neo4j")
    with get_driver().session(database=db) as session:
        return [r.data() for r in session.run(query, **params)]


def load_sample_data():
    run("MATCH (n) DETACH DELETE n")
    run("UNWIND $xs AS n MERGE (:Person {name: n})", xs=PERSONS)
    run("UNWIND $xs AS n MERGE (:Hotel {name: n})", xs=HOTELS)
    run(
        """UNWIND $pairs AS p
           MATCH (a:Person {name: p[0]}), (h:Hotel {name: p[1]})
           MERGE (a)-[:LIKES]->(h)""",
        pairs=[list(x) for x in LIKES],
    )


def graph_dot(highlight=None, recs=()):
    rows = run("MATCH (p:Person)-[:LIKES]->(h:Hotel) RETURN p.name AS p, h.name AS h")
    lines = ["graph [rankdir=LR]", "node [fontname=Helvetica]"]
    for p in sorted({r["p"] for r in rows}):
        color = "#f59e0b" if p == highlight else "#93c5fd"
        lines.append(f'"{p}" [shape=ellipse, style=filled, fillcolor="{color}"]')
    for h in sorted({r["h"] for r in rows}):
        color = "#86efac" if h in recs else "#e5e7eb"
        lines.append(f'"{h}" [shape=box, style=filled, fillcolor="{color}"]')
    for r in rows:
        lines.append(f'"{r["p"]}" -> "{r["h"]}" [label="LIKES", fontsize=9]')
    return "digraph G {" + "; ".join(lines) + "}"


# ---------- UI ----------
st.title("🏨 Hotel Recommendation System")
st.caption("Streamlit + Neo4j Aura + Cypher · Collaborative Filtering จาก (Person)-[:LIKES]->(Hotel)")

try:
    get_driver()
except Exception as e:
    st.error("เชื่อมต่อ Neo4j Aura ไม่ได้ ตรวจสอบ Secrets (NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD)")
    st.exception(e)
    st.stop()

with st.sidebar:
    st.header("ตั้งค่า")
    if st.button("โหลดข้อมูลตัวอย่าง (ล้างข้อมูลเดิม)", use_container_width=True):
        load_sample_data()
        st.success("โหลดข้อมูลตัวอย่างแล้ว")
    people = [r["name"] for r in run("MATCH (p:Person) RETURN p.name AS name ORDER BY name")]
    if not people:
        st.info("ฐานข้อมูลยังว่าง กดโหลดข้อมูลตัวอย่างก่อน")
        st.stop()
    default = people.index("Pond") if "Pond" in people else 0
    user = st.selectbox("ผู้ใช้เป้าหมาย", people, index=default)
    top_n = st.slider("จำนวนคำแนะนำ", 1, 10, 5)

tab_rec, tab_graph, tab_data, tab_add = st.tabs(["แนะนำโรงแรม", "กราฟ", "ข้อมูล LIKES", "เพิ่ม LIKES"])

with tab_rec:
    liked = [r["h"] for r in run(
        "MATCH (:Person {name:$n})-[:LIKES]->(h:Hotel) RETURN h.name AS h ORDER BY h", n=user)]
    st.subheader(f"{user} ชอบ: " + (", ".join(liked) if liked else "-"))
    recs = run(REC_QUERY, name=user, top_n=top_n)
    if recs:
        df = pd.DataFrame(recs)
        df["recommended_by"] = df["recommended_by"].apply(", ".join)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption("similarity_score = ผลรวมจำนวนโรงแรมที่ชอบร่วมกันของผู้ใช้ที่แนะนำโรงแรมนั้น · "
                   "voters = จำนวนผู้ใช้ที่คล้ายกันที่ชอบโรงแรมนั้น")
    else:
        st.warning("ไม่มีคำแนะนำ (ยังไม่มีผู้ใช้ที่ชอบโรงแรมร่วมกัน หรือไม่มีโรงแรมใหม่ให้แนะนำ)")
    with st.expander("ดู Cypher Query"):
        st.code(REC_QUERY, language="cypher")

with tab_graph:
    st.caption("สีส้ม = ผู้ใช้เป้าหมาย · สีเขียว = โรงแรมที่แนะนำ")
    st.graphviz_chart(graph_dot(user, {r["hotel"] for r in recs}), use_container_width=True)

with tab_data:
    rows = run("""MATCH (p:Person)-[:LIKES]->(h:Hotel)
                  RETURN p.name AS person, collect(h.name) AS liked_hotels ORDER BY person""")
    df = pd.DataFrame(rows)
    df["liked_hotels"] = df["liked_hotels"].apply(lambda xs: ", ".join(sorted(xs)))
    st.dataframe(df, use_container_width=True, hide_index=True)

with tab_add:
    st.write("เพิ่มความสัมพันธ์ LIKES แล้วดูว่าคำแนะนำเปลี่ยนอย่างไร")
    hotels_db = [r["name"] for r in run("MATCH (h:Hotel) RETURN h.name AS name ORDER BY name")]
    c1, c2 = st.columns(2)
    p_sel = c1.selectbox("Person", people, key="add_p")
    h_sel = c2.selectbox("Hotel", hotels_db, key="add_h")
    b1, b2 = st.columns(2)
    if b1.button("เพิ่ม LIKES"):
        run("MATCH (p:Person {name:$p}), (h:Hotel {name:$h}) MERGE (p)-[:LIKES]->(h)", p=p_sel, h=h_sel)
        st.success(f"({p_sel})-[:LIKES]->({h_sel})")
        st.rerun()
    if b2.button("ลบ LIKES"):
        run("MATCH (:Person {name:$p})-[r:LIKES]->(:Hotel {name:$h}) DELETE r", p=p_sel, h=h_sel)
        st.success("ลบแล้ว")
        st.rerun()
