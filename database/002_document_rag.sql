-- Document RAG and Indicator Catalog schema

-- Document registry for RAG
CREATE TABLE IF NOT EXISTS document_registry (
    document_id BIGSERIAL PRIMARY KEY,
    title VARCHAR(500),
    topic VARCHAR(100),
    document_type VARCHAR(100),
    source_id BIGINT REFERENCES dim_source(source_id),
    effective_date DATE,
    version_no VARCHAR(50),
    status VARCHAR(50) DEFAULT 'active',
    uploaded_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_doc_topic ON document_registry(topic);

-- Document chunks for RAG (metadata mirror of ChromaDB)
-- REMOVED by migration 014: ChromaDB replaced by pgvector (migration 011).
-- Chunk text + vectors are now stored in document_embeddings.
-- CREATE TABLE statement kept here for history only — table is DROPPED by 014.
-- CREATE TABLE IF NOT EXISTS document_chunks ( ... )

-- Indicator catalog
CREATE TABLE IF NOT EXISTS indicator_catalog (
    indicator_id BIGSERIAL PRIMARY KEY,
    topic VARCHAR(100) NOT NULL,
    indicator_code VARCHAR(100) NOT NULL,
    indicator_name VARCHAR(255) NOT NULL,
    definition TEXT,
    unit_name VARCHAR(100),
    preferred_chart VARCHAR(100),
    report_section VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_indicator_topic ON indicator_catalog(topic);

-- Seed accident indicators
INSERT INTO indicator_catalog (topic, indicator_code, indicator_name, definition, unit_name, preferred_chart, report_section) VALUES
('accident', 'ACC-001', 'จำนวนอุบัติเหตุ', 'จำนวนครั้งของอุบัติเหตุทางถนนทั้งหมด', 'ครั้ง', 'line', 'สถานการณ์ปัจจุบัน'),
('accident', 'ACC-002', 'จำนวนผู้บาดเจ็บ', 'จำนวนผู้ได้รับบาดเจ็บจากอุบัติเหตุ', 'คน', 'line', 'สถานการณ์ปัจจุบัน'),
('accident', 'ACC-003', 'จำนวนผู้เสียชีวิต', 'จำนวนผู้เสียชีวิตจากอุบัติเหตุ', 'คน', 'line', 'สถานการณ์ปัจจุบัน'),
('accident', 'ACC-004', 'อัตราการเสียชีวิตต่อแสนประชากร', 'จำนวนผู้เสียชีวิตต่อประชากร 100,000 คน', 'ต่อแสนประชากร', 'bar', 'ตัวชี้วัดสำคัญ'),
('accident', 'ACC-005', 'คะแนนจุดเสี่ยง', 'คะแนนความเสี่ยงของจุดที่เกิดอุบัติเหตุซ้ำ', 'คะแนน', 'ranked_bar', 'การวิเคราะห์เชิงลึก'),
('accident', 'ACC-006', 'ช่วงเวลาเสี่ยงสูง', 'ช่วงเวลาที่มีอุบัติเหตุมากที่สุด', 'ช่วงเวลา', 'bar', 'การวิเคราะห์เชิงลึก')
ON CONFLICT DO NOTHING;
