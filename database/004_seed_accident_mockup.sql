-- Seed mockup accident data adapted from Chat-/database accident schema
-- Populates: dim_geography, dim_source, dim_road_segment,
--            fact_accident_event, fact_accident_person,
--            mart_accident_summary, mart_accident_hotspot
-- Also creates the legacy 'accident' table from ChatV1 with sample rows

-- ===================================================
-- 1. dim_geography — Thai provinces & districts
-- ===================================================
INSERT INTO dim_geography (province_code, province_name, district_code, district_name, subdistrict_name, latitude, longitude)
VALUES
  ('10', 'กรุงเทพมหานคร', '1001', 'พระนคร', 'พระบรมมหาราชวัง', 13.7563, 100.5018),
  ('10', 'กรุงเทพมหานคร', '1002', 'ดุสิต', 'ดุสิต', 13.7740, 100.5160),
  ('10', 'กรุงเทพมหานคร', '1003', 'หนองจอก', 'กระทุ่มราย', 13.8560, 100.8590),
  ('10', 'กรุงเทพมหานคร', '1004', 'บางรัก', 'มหาพฤฒาราม', 13.7276, 100.5230),
  ('50', 'เชียงใหม่', '5001', 'เมืองเชียงใหม่', 'ศรีภูมิ', 18.7883, 98.9853),
  ('50', 'เชียงใหม่', '5002', 'จอมทอง', 'บ้านหลวง', 18.4167, 98.6667),
  ('50', 'เชียงใหม่', '5003', 'แม่แจ่ม', 'ช่างเคิ่ง', 18.5000, 98.3667),
  ('20', 'ชลบุรี', '2001', 'เมืองชลบุรี', 'บางปลาสร้อย', 13.3611, 100.9847),
  ('20', 'ชลบุรี', '2002', 'บ้านบึง', 'บ้านบึง', 13.3500, 101.1000),
  ('20', 'ชลบุรี', '2003', 'พานทอง', 'พานทอง', 13.4500, 101.0833),
  ('40', 'ขอนแก่น', '4001', 'เมืองขอนแก่น', 'ในเมือง', 16.4322, 102.8236),
  ('40', 'ขอนแก่น', '4002', 'บ้านฝาง', 'บ้านฝาง', 16.5500, 102.7167),
  ('90', 'สงขลา', '9001', 'เมืองสงขลา', 'บ่อยาง', 7.1896, 100.5945),
  ('90', 'สงขลา', '9002', 'หาดใหญ่', 'หาดใหญ่', 7.0058, 100.4737),
  ('21', 'ระยอง', '2101', 'เมืองระยอง', 'ท่าประดู่', 12.6814, 101.2814),
  ('30', 'นครราชสีมา', '3001', 'เมืองนครราชสีมา', 'ในเมือง', 14.9799, 102.0977),
  ('30', 'นครราชสีมา', '3002', 'ปากช่อง', 'ปากช่อง', 14.7128, 101.4162),
  ('70', 'ราชบุรี', '7001', 'เมืองราชบุรี', 'หน้าเมือง', 13.5363, 99.8174),
  ('80', 'นครศรีธรรมราช', '8001', 'เมืองนครศรีธรรมราช', 'ในเมือง', 8.4304, 99.9631),
  ('60', 'นครสวรรค์', '6001', 'เมืองนครสวรรค์', 'ปากน้ำโพ', 15.7047, 100.1367)
ON CONFLICT DO NOTHING;

-- ===================================================
-- 2. dim_source — data sources
-- ===================================================
INSERT INTO dim_source (source_name, source_type, owner_org, update_frequency, quality_level)
VALUES
  ('กรมทางหลวง', 'database', 'กระทรวงคมนาคม', 'monthly', 'high'),
  ('สำนักงานตำรวจแห่งชาติ', 'database', 'สำนักงานตำรวจแห่งชาติ', 'monthly', 'high'),
  ('กรมป้องกันและบรรเทาสาธารณภัย', 'database', 'กระทรวงมหาดไทย', 'monthly', 'medium'),
  ('สสส. รายงานอุบัติเหตุ', 'report', 'สสส.', 'quarterly', 'high')
ON CONFLICT DO NOTHING;

-- ===================================================
-- 3. dim_road_segment — road segments
-- ===================================================
INSERT INTO dim_road_segment (road_name, road_type, lane_count, curvature_type, slope_type, speed_limit, surface_type, risk_flag)
VALUES
  ('ถนนพหลโยธิน', 'ทางหลวงแผ่นดิน', 4, 'ตรง', 'ราบ', 90, 'แอสฟัลต์', false),
  ('ถนนมิตรภาพ', 'ทางหลวงแผ่นดิน', 4, 'ตรง', 'ราบ', 90, 'แอสฟัลต์', true),
  ('ถนนสุขุมวิท', 'ทางหลวงแผ่นดิน', 6, 'ตรง', 'ราบ', 80, 'แอสฟัลต์', true),
  ('ถนนเพชรเกษม', 'ทางหลวงแผ่นดิน', 4, 'โค้งเล็กน้อย', 'ราบ', 90, 'แอสฟัลต์', false),
  ('ทางหลวงหมายเลข 11', 'ทางหลวงแผ่นดิน', 4, 'โค้งมาก', 'ลาดชัน', 80, 'แอสฟัลต์', true),
  ('ทางหลวงหมายเลข 304', 'ทางหลวงแผ่นดิน', 2, 'โค้งมาก', 'ลาดชัน', 60, 'แอสฟัลต์', true),
  ('ถนนวิภาวดีรังสิต', 'ทางหลวงพิเศษ', 8, 'ตรง', 'ราบ', 100, 'แอสฟัลต์', false),
  ('ถนนรามอินทรา', 'ทางหลวงแผ่นดิน', 6, 'ตรง', 'ราบ', 80, 'แอสฟัลต์', false),
  ('ทางหลวงชนบท นม.1020', 'ทางหลวงชนบท', 2, 'โค้งเล็กน้อย', 'ราบ', 60, 'ลาดยาง', true),
  ('ทางหลวงชนบท ชม.3029', 'ทางหลวงชนบท', 2, 'โค้งมาก', 'ลาดชัน', 40, 'ลาดยาง', true);

-- ===================================================
-- 4. fact_accident_event — 200 accident events (2024-2025)
-- ===================================================
-- We use generate_series with randomized data
DO $$
DECLARE
  geo_ids BIGINT[];
  road_ids BIGINT[];
  src_ids BIGINT[];
  weather_arr TEXT[] := ARRAY['แจ่มใส', 'ฝนตก', 'มีหมอก', 'ครึ้มฟ้าครึ้มฝน', 'ฝนตกหนัก'];
  road_cond_arr TEXT[] := ARRAY['แห้ง', 'เปียก', 'ลื่น', 'ชำรุด', 'มีน้ำท่วมขัง'];
  light_arr TEXT[] := ARRAY['กลางวัน', 'กลางคืนมีไฟส่องสว่าง', 'กลางคืนไม่มีไฟ', 'รุ่งสาง/พลบค่ำ'];
  acc_type_arr TEXT[] := ARRAY['ชนท้าย', 'ชนประสานงา', 'ชนด้านข้าง', 'ชนคนเดินเท้า', 'พลิกคว่ำ', 'ตกถนน', 'เฉี่ยวชน', 'ชนสิ่งกีดขวาง'];
  severity_arr TEXT[] := ARRAY['เล็กน้อย', 'ปานกลาง', 'รุนแรง', 'เสียชีวิต'];
  vehicle_arr TEXT[] := ARRAY['รถจักรยานยนต์', 'รถยนต์ส่วนบุคคล', 'รถปิคอัพ', 'รถบรรทุก', 'รถตู้', 'รถโดยสาร', 'รถสามล้อเครื่อง'];
  i INT;
  g_id BIGINT;
  r_id BIGINT;
  s_id BIGINT;
  ev_dt TIMESTAMP;
  sev TEXT;
  inj INT;
  dth INT;
BEGIN
  SELECT array_agg(geography_id) INTO geo_ids FROM dim_geography;
  SELECT array_agg(road_segment_id) INTO road_ids FROM dim_road_segment;
  SELECT array_agg(source_id) INTO src_ids FROM dim_source;

  FOR i IN 1..200 LOOP
    g_id := geo_ids[1 + floor(random() * array_length(geo_ids, 1))::INT];
    r_id := road_ids[1 + floor(random() * array_length(road_ids, 1))::INT];
    s_id := src_ids[1 + floor(random() * array_length(src_ids, 1))::INT];
    ev_dt := '2024-01-01'::TIMESTAMP + (random() * 730)::INT * INTERVAL '1 day'
             + (floor(random() * 24))::INT * INTERVAL '1 hour'
             + (floor(random() * 60))::INT * INTERVAL '1 minute';
    sev := severity_arr[1 + floor(random() * 4)::INT];
    inj := CASE WHEN sev = 'เล็กน้อย' THEN floor(random()*2)::INT
                WHEN sev = 'ปานกลาง' THEN 1 + floor(random()*3)::INT
                WHEN sev = 'รุนแรง' THEN 2 + floor(random()*5)::INT
                ELSE floor(random()*2)::INT END;
    dth := CASE WHEN sev = 'เสียชีวิต' THEN 1 + floor(random()*3)::INT ELSE 0 END;

    INSERT INTO fact_accident_event
      (event_datetime, geography_id, road_segment_id, weather_condition, road_condition,
       light_condition, accident_type, severity_level, vehicle_type, injured_count, death_count, source_id)
    VALUES (
      ev_dt, g_id, r_id,
      weather_arr[1 + floor(random() * 5)::INT],
      road_cond_arr[1 + floor(random() * 5)::INT],
      light_arr[1 + floor(random() * 4)::INT],
      acc_type_arr[1 + floor(random() * 8)::INT],
      sev,
      vehicle_arr[1 + floor(random() * 7)::INT],
      inj, dth, s_id
    );
  END LOOP;
END $$;

-- ===================================================
-- 5. fact_accident_person — 2-3 persons per event sample
-- ===================================================
DO $$
DECLARE
  acc RECORD;
  n_persons INT;
  j INT;
  roles TEXT[] := ARRAY['ผู้ขับขี่', 'ผู้โดยสาร', 'คนเดินเท้า'];
  injury_lvls TEXT[] := ARRAY['ไม่บาดเจ็บ', 'บาดเจ็บเล็กน้อย', 'บาดเจ็บสาหัส', 'เสียชีวิต'];
  sexes TEXT[] := ARRAY['ชาย', 'หญิง'];
BEGIN
  FOR acc IN SELECT accident_id, severity_level FROM fact_accident_event LIMIT 100 LOOP
    n_persons := 1 + floor(random() * 3)::INT;
    FOR j IN 1..n_persons LOOP
      INSERT INTO fact_accident_person
        (accident_id, age, sex, role_in_event, injury_level, helmet_used, seatbelt_used)
      VALUES (
        acc.accident_id,
        15 + floor(random() * 55)::INT,
        sexes[1 + floor(random() * 2)::INT],
        roles[1 + floor(random() * 3)::INT],
        CASE WHEN acc.severity_level = 'เสียชีวิต' AND j = 1 THEN 'เสียชีวิต'
             ELSE injury_lvls[1 + floor(random() * 4)::INT] END,
        random() > 0.4,
        random() > 0.3
      );
    END LOOP;
  END LOOP;
END $$;

-- ===================================================
-- 6. mart_accident_summary — monthly aggregation
-- ===================================================
INSERT INTO mart_accident_summary (year_no, month_no, geography_id, accident_count, injured_count, death_count, high_risk_timeband, dominant_road_cond)
SELECT
  EXTRACT(YEAR FROM e.event_datetime)::INT AS year_no,
  EXTRACT(MONTH FROM e.event_datetime)::INT AS month_no,
  e.geography_id,
  COUNT(*) AS accident_count,
  SUM(e.injured_count) AS injured_count,
  SUM(e.death_count) AS death_count,
  MODE() WITHIN GROUP (ORDER BY
    CASE
      WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 0 AND 5 THEN 'ดึก (00-06)'
      WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 6 AND 11 THEN 'เช้า (06-12)'
      WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 12 AND 17 THEN 'บ่าย (12-18)'
      ELSE 'ค่ำ (18-24)'
    END
  ) AS high_risk_timeband,
  MODE() WITHIN GROUP (ORDER BY e.road_condition) AS dominant_road_cond
FROM fact_accident_event e
GROUP BY year_no, month_no, e.geography_id
ORDER BY year_no, month_no;

-- ===================================================
-- 7. mart_accident_hotspot — hotspot scoring
-- ===================================================
INSERT INTO mart_accident_hotspot (geography_id, road_segment_id, accident_count, injured_count, death_count, hotspot_score, dominant_timeband)
SELECT
  e.geography_id,
  e.road_segment_id,
  COUNT(*) AS accident_count,
  SUM(e.injured_count) AS injured_count,
  SUM(e.death_count) AS death_count,
  ROUND((COUNT(*)::DECIMAL * 1.0 + SUM(e.injured_count) * 2.0 + SUM(e.death_count) * 5.0), 2) AS hotspot_score,
  MODE() WITHIN GROUP (ORDER BY
    CASE
      WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 0 AND 5 THEN 'ดึก (00-06)'
      WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 6 AND 11 THEN 'เช้า (06-12)'
      WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 12 AND 17 THEN 'บ่าย (12-18)'
      ELSE 'ค่ำ (18-24)'
    END
  ) AS dominant_timeband
FROM fact_accident_event e
GROUP BY e.geography_id, e.road_segment_id
ORDER BY hotspot_score DESC;

-- ===================================================
-- 8. Legacy 'accident' table (matching Chat-/database schema)
-- ===================================================
CREATE TABLE IF NOT EXISTS accident (
  id SERIAL PRIMARY KEY,
  "ปีที่เกิดเหตุ" INTEGER,
  "วันที่เกิดเหตุ" VARCHAR(50),
  "เวลา" VARCHAR(50),
  "วันที่รายงาน" VARCHAR(50),
  "เวลาที่รายงาน" VARCHAR(50),
  ACC_CODE BIGINT,
  "หน่วยงาน" VARCHAR(100),
  "สายทางหน่วยงาน" VARCHAR(100),
  "รหัสสายทาง" VARCHAR(50),
  "สายทาง" TEXT,
  KM DOUBLE PRECISION,
  "จังหวัด" VARCHAR(100),
  "รถคันที่1" TEXT,
  "บริเวณที่เกิดเหตุ" TEXT,
  "มูลเหตุสันนิษฐาน" TEXT,
  "ลักษณะการเกิดเหตุ" TEXT,
  "สภาพอากาศ" VARCHAR(100),
  LATITUDE DOUBLE PRECISION,
  LONGITUDE DOUBLE PRECISION,
  "รถที่เกิดเหตุ" INTEGER,
  "รถและคนที่เกิดเหตุ" INTEGER,
  "รถจักรยานยนต์" INTEGER,
  "รถสามล้อเครื่อง" INTEGER,
  "รถยนต์นั่งส่วนบุคคล" INTEGER,
  "รถตู้" INTEGER,
  "รถปิคอัพโดยสาร" INTEGER,
  "รถโดยสารมากกว่า4ล้อ" INTEGER,
  "รถปิคอัพบรรทุก4ล้อ" INTEGER,
  "รถบรรทุก6ล้อ" INTEGER,
  "รถบรรทุกไม่เกิน10ล้อ" INTEGER,
  "รถบรรทุกมากกว่า10ล้อ" INTEGER,
  "รถอีแต๋น" INTEGER,
  "รถอื่นๆ" INTEGER,
  "คนเดินเท้า" INTEGER,
  "ผู้เสียชีวิต" INTEGER,
  "ผู้บาดเจ็บสาหัส" INTEGER,
  "ผู้บาดเจ็บเล็กน้อย" INTEGER,
  "รวมจำนวนผู้บาดเจ็บ" INTEGER
);

-- Insert 50 realistic legacy accident rows
DO $$
DECLARE
  provinces TEXT[] := ARRAY['กรุงเทพมหานคร','เชียงใหม่','ชลบุรี','ขอนแก่น','สงขลา','ระยอง','นครราชสีมา','ราชบุรี','นครศรีธรรมราช','นครสวรรค์'];
  agencies TEXT[] := ARRAY['แขวงทางหลวง','สำนักทางหลวง','แขวงทางหลวงชนบท'];
  roads TEXT[] := ARRAY['ถนนพหลโยธิน','ถนนมิตรภาพ','ถนนสุขุมวิท','ถนนเพชรเกษม','ทางหลวง 11','ทางหลวง 304','ถนนวิภาวดีรังสิต','ถนนรามอินทรา'];
  causes TEXT[] := ARRAY['ขับรถเร็วเกินกำหนด','หลับใน','เมาสุรา','ตัดหน้ากระชั้นชิด','ฝ่าสัญญาณไฟแดง','ขับรถย้อนศร','ไม่รักษาระยะห่าง','สภาพถนนชำรุด'];
  patterns TEXT[] := ARRAY['ชนท้าย','ชนประสานงา','เฉี่ยวชน','พลิกคว่ำ','ชนด้านข้าง','ชนคนเดินเท้า','ตกถนน'];
  weathers TEXT[] := ARRAY['แจ่มใส','ฝนตก','มีหมอก','ครึ้มฟ้าครึ้มฝน'];
  lats DOUBLE PRECISION[] := ARRAY[13.75,18.79,13.36,16.43,7.19,12.68,14.98,13.54,8.43,15.70];
  lons DOUBLE PRECISION[] := ARRAY[100.50,98.99,100.98,102.82,100.59,101.28,102.10,99.82,99.96,100.14];
  i INT;
  prov_idx INT;
  yr INT;
  dt TEXT;
  tm TEXT;
  dead INT;
  serious INT;
  minor INT;
BEGIN
  FOR i IN 1..50 LOOP
    prov_idx := 1 + floor(random() * 10)::INT;
    yr := 2567 + floor(random() * 2)::INT;  -- Thai Buddhist year
    dt := (1 + floor(random()*28))::TEXT || '/' || (1 + floor(random()*12))::TEXT || '/' || yr::TEXT;
    tm := lpad((floor(random()*24))::TEXT, 2, '0') || ':' || lpad((floor(random()*60))::TEXT, 2, '0');
    dead := CASE WHEN random() < 0.15 THEN 1 + floor(random()*2)::INT ELSE 0 END;
    serious := floor(random()*3)::INT;
    minor := floor(random()*5)::INT;

    INSERT INTO accident (
      "ปีที่เกิดเหตุ", "วันที่เกิดเหตุ", "เวลา", "วันที่รายงาน", "เวลาที่รายงาน",
      ACC_CODE, "หน่วยงาน", "สายทางหน่วยงาน", "รหัสสายทาง", "สายทาง", KM,
      "จังหวัด", "รถคันที่1", "บริเวณที่เกิดเหตุ", "มูลเหตุสันนิษฐาน",
      "ลักษณะการเกิดเหตุ", "สภาพอากาศ",
      LATITUDE, LONGITUDE,
      "รถที่เกิดเหตุ", "รถและคนที่เกิดเหตุ",
      "รถจักรยานยนต์", "รถสามล้อเครื่อง", "รถยนต์นั่งส่วนบุคคล",
      "รถตู้", "รถปิคอัพโดยสาร", "รถโดยสารมากกว่า4ล้อ",
      "รถปิคอัพบรรทุก4ล้อ", "รถบรรทุก6ล้อ", "รถบรรทุกไม่เกิน10ล้อ",
      "รถบรรทุกมากกว่า10ล้อ", "รถอีแต๋น", "รถอื่นๆ", "คนเดินเท้า",
      "ผู้เสียชีวิต", "ผู้บาดเจ็บสาหัส", "ผู้บาดเจ็บเล็กน้อย", "รวมจำนวนผู้บาดเจ็บ"
    ) VALUES (
      yr, dt, tm, dt, tm,
      1000000 + i, agencies[1 + floor(random()*3)::INT],
      roads[1 + floor(random()*8)::INT] || ' (' || provinces[prov_idx] || ')',
      'R' || lpad((floor(random()*9999))::TEXT, 4, '0'),
      roads[1 + floor(random()*8)::INT],
      round((random()*500)::NUMERIC, 1),
      provinces[prov_idx],
      'รถจักรยานยนต์',
      'ทางตรง กม.' || round((random()*500)::NUMERIC, 1),
      causes[1 + floor(random()*8)::INT],
      patterns[1 + floor(random()*7)::INT],
      weathers[1 + floor(random()*4)::INT],
      lats[prov_idx] + (random()-0.5)*0.1,
      lons[prov_idx] + (random()-0.5)*0.1,
      1 + floor(random()*3)::INT,
      2 + floor(random()*5)::INT,
      CASE WHEN random() < 0.5 THEN 1 ELSE 0 END,
      CASE WHEN random() < 0.1 THEN 1 ELSE 0 END,
      CASE WHEN random() < 0.3 THEN 1 ELSE 0 END,
      CASE WHEN random() < 0.1 THEN 1 ELSE 0 END,
      CASE WHEN random() < 0.2 THEN 1 ELSE 0 END,
      CASE WHEN random() < 0.05 THEN 1 ELSE 0 END,
      CASE WHEN random() < 0.2 THEN 1 ELSE 0 END,
      CASE WHEN random() < 0.1 THEN 1 ELSE 0 END,
      CASE WHEN random() < 0.1 THEN 1 ELSE 0 END,
      CASE WHEN random() < 0.05 THEN 1 ELSE 0 END,
      CASE WHEN random() < 0.05 THEN 1 ELSE 0 END,
      CASE WHEN random() < 0.05 THEN 1 ELSE 0 END,
      CASE WHEN random() < 0.15 THEN 1 ELSE 0 END,
      dead, serious, minor, serious + minor
    );
  END LOOP;
END $$;
