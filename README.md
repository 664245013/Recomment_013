# Hotel Recommendation System

Streamlit + Neo4j Aura + Cypher — ระบบแนะนำโรงแรมด้วย Collaborative Filtering จาก `(Person)-[:LIKES]->(Hotel)`

## โครงสร้าง
```
app.py                       แอป Streamlit
data.py                      ข้อมูลตัวอย่าง (Person / Hotel / LIKES)
requirements.txt
.streamlit/secrets.toml.example
```

## รันในเครื่อง
1. สร้าง Neo4j Aura Free instance แล้วเก็บ URI / username / password
2. `cp .streamlit/secrets.toml.example .streamlit/secrets.toml` แล้วใส่ค่าจริง
3. `pip install -r requirements.txt`
4. `streamlit run app.py`
5. กด **โหลดข้อมูลตัวอย่าง** ที่ sidebar ครั้งแรก

## Deploy: GitHub → Streamlit Community Cloud
1. push โฟลเดอร์นี้ขึ้น GitHub (`secrets.toml` ถูกกันไว้ใน `.gitignore` แล้ว)
2. ไปที่ share.streamlit.io → New app → เลือก repo, branch, main file = `app.py`
3. Advanced settings → **Secrets** → วางค่าจาก `secrets.toml.example` (ใส่ค่าจริง)
4. Deploy

## Cypher หลัก
```cypher
MATCH (t:Person {name:$name})-[:LIKES]->(common:Hotel)<-[:LIKES]-(other:Person)
WHERE other <> t
WITH t, other, count(common) AS shared
MATCH (other)-[:LIKES]->(rec:Hotel)
WHERE NOT (t)-[:LIKES]->(rec)
RETURN rec.name AS hotel, count(DISTINCT other) AS voters, sum(shared) AS similarity_score
ORDER BY similarity_score DESC, voters DESC
```
