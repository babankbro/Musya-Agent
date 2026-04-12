![](media/image1.png){width="7.255208880139983in" height="4.836805555555555in"}

**คำอธิบายสถาปัตยกรรมระบบ Agentic AI and RAG in Musya AI**

**Musya AI** เป็นแพลตฟอร์มสำหรับค้นหา วิเคราะห์ สังเคราะห์ และจัดทำเอกสารแผนสุขภาพอัตโนมัติ โดยออกแบบบนแนวคิด **Agentic AI ร่วมกับ Retrieval-Augmented Generation (RAG)** เพื่อให้ระบบสามารถดึงข้อมูลจากทั้งเอกสารและฐานข้อมูลเชิงโครงสร้างมาประกอบการวิเคราะห์อย่างมีที่มาที่ตรวจสอบย้อนกลับได้ รองรับการใช้งานในโดเมนหลัก **3** ด้าน ได้แก่ **อุบัติเหตุ สุขภาพจิต และโภชนาการที่เชื่อมโยงกับโรคเรื้อรัง** พร้อมรองรับการแสดงผลรายงานผ่านเว็บและการส่งออกเป็นไฟล์ **DOCX**

สถาปัตยกรรมของระบบประกอบด้วย **6** ชั้นหลัก ได้แก่ **Web Frontend, Backend API, AI Agent Layer, RAG/Data Layer, Report Engine และ Observability & Governance** โดยทำงานเชื่อมต่อกันเป็นลำดับตั้งแต่ผู้ใช้ระบุโจทย์ ไปจนถึงการสร้างรายงานฉบับสมบูรณ์ ระบบรองรับผู้ใช้งาน **2** กลุ่ม คือ **General User** สำหรับสั่งค้นหา ดูผลลัพธ์ **preview** รายงาน และดาวน์โหลดเอกสาร และ **Admin User** สำหรับอัปโหลดเอกสาร ข้อมูลสถิติ และข้อมูลสุขภาพเข้าสู่ระบบ รวมถึงจัดการ **metadata** สิทธิ์การเข้าถึง และกระบวนการเตรียมข้อมูลก่อนนำเข้า เช่น **validation, mapping** และ **re-indexing** เพื่อให้ข้อมูลพร้อมสำหรับการค้นคืนและวิเคราะห์ในขั้นถัดไป

ในส่วนของ **Web Frontend** ระบบรองรับการ **login, dashboard,** การตั้งคำถามหรือระบุโจทย์**,** การ **preview** รายงาน**,** การดูกราฟและตาราง และการดาวน์โหลดไฟล์ **DOCX** โดยเป็นจุดเชื่อมต่อระหว่างผู้ใช้กับระบบประมวลผลทั้งหมด ขณะที่ **Backend API** ทำหน้าที่เป็นศูนย์กลางในการควบคุม **workflow, authentication, authorization, routing, orchestration** และการเชื่อมต่อบริการภายในระบบ เพื่อให้ทุกโมดูลทำงานร่วมกันได้อย่างเป็นระบบและปลอดภัย

แกนหลักของระบบคือ **AI Agent Layer** ซึ่งออกแบบให้มี **Orchestrator** ทำงานร่วมกับ **specialist agents** หลายตัว ได้แก่ **Request Interpreter, Planner, Retrieval Agent, Citation & Evidence Agent, Domain Analyst Agents, Report Writer/Report Generator** และ **Review & Compliance Agent** โดยแต่ละ **agent** มีบทบาทเฉพาะ เช่น ตีความโจทย์ วางแผนการดึงข้อมูล ค้นข้อมูลจาก **RAG** และฐานข้อมูล วิเคราะห์เชิงโดเมน จัดการแหล่งอ้างอิง และเรียบเรียงผลลัพธ์เป็นรายงานที่มีโครงสร้างมาตรฐาน ทั้งนี้ระบบรองรับการทำงานแบบ **workflow/state management** เพื่อให้สามารถจัดการงานหลายขั้นตอน การอนุมัติ และการติดตามสถานะของงานได้อย่างต่อเนื่อง

สำหรับ **RAG/Data Layer** ระบบใช้แนวทางแบบ **hybrid** โดยแบ่งเป็น **2** ส่วนสำคัญ คือ **Document RAG** และ **Database RAG** ส่วน **Document RAG** ใช้สำหรับค้นคืนข้อมูลจากเอกสาร เช่น นโยบาย รายงาน คู่มือ และเอกสารวิชาการ ผ่านกระบวนการ **ingest, chunking, embedding** และ **semantic search** บน **vector store** ขณะที่ **Database RAG** ใช้สำหรับเข้าถึงข้อมูลสุขภาพเชิงโครงสร้างผ่าน **query tools** และ **analytic mart** ที่ออกแบบให้ปลอดภัยและเหมาะกับการวิเคราะห์ เช่น การสรุปตัวชี้วัด การเปรียบเทียบเชิงพื้นที่ และการวิเคราะห์แนวโน้มตามช่วงเวลา โดย **agent** จะไม่เข้าถึง **raw tables** โดยตรง แต่เรียกผ่าน **tools/API** ที่ควบคุมขอบเขตการใช้งานไว้ชัดเจน

ฐานข้อมูลของระบบออกแบบให้สอดคล้องกับทั้ง **3** โดเมน ได้แก่ **Accident DB, Mental Health DB และ Nutrition & Chronic Disease DB** พร้อม **shared master data** เช่น **geography, time, population group, facility, source** และ **indicator catalog** เพื่อให้การวิเคราะห์ข้ามโดเมนทำได้ในโครงสร้างเดียวกัน นอกจากนี้ยังมี **evidence registry และ citation schema** สำหรับผูกข้อความ ตาราง และกราฟกับแหล่งข้อมูลต้นทาง เพื่อให้เอกสารทุกฉบับสามารถ **trace** ย้อนกลับได้ถึงหลักฐานที่ใช้จริง ซึ่งเป็นองค์ประกอบสำคัญสำหรับงานรายงานด้านสุขภาพและงานเชิงนโยบาย

ผลลัพธ์จากการค้นคืนและวิเคราะห์จะถูกส่งต่อไปยัง **Report Engine** ซึ่งทำหน้าที่สร้างตาราง กราฟ ข้อความสรุป และเอกสารฉบับสมบูรณ์ โดยรองรับทั้งการ **render** เพื่อ **preview** บนเว็บและการ **export** เป็น **DOCX** ตาม **template** มาตรฐานของรายงาน ระบบยังรองรับ **source note** และ **references** อัตโนมัติ เพื่อให้รายงานที่สร้างขึ้นมีความพร้อมใช้งานทั้งในเชิงบริหาร วิชาการ และการจัดทำ **proposal** หรือแผนสุขภาพในระดับองค์กร

ในด้านการกำกับดูแล ระบบมีชั้น **Observability & Governance** สำหรับ **tracing, evaluation, audit logs** และ **data lineage** เพื่อให้สามารถตรวจสอบย้อนหลังได้ว่า **agent** ใช้ข้อมูลจากแหล่งใด เรียกใช้เครื่องมือใด และสร้างข้อสรุปบนหลักฐานใด กลไกนี้ช่วยเพิ่มความโปร่งใส ลดความเสี่ยงจากการสรุปเกินข้อมูล และสนับสนุนการควบคุมคุณภาพของรายงาน โดยเฉพาะในหัวข้อที่มีความอ่อนไหว เช่น สุขภาพจิต ซึ่งอาจต้องมี **review** จากมนุษย์ก่อนเผยแพร่หรือใช้งานอย่างเป็นทางการ

โดยสรุป **Musya AI** เป็นสถาปัตยกรรมที่รวม **Web Platform + Agentic AI + Document RAG + Database RAG + Reporting + Governance** เข้าไว้ในระบบเดียว เพื่อให้สามารถเปลี่ยนข้อมูลกระจัดกระจายจากเอกสารและฐานข้อมูลให้กลายเป็นรายงานสุขภาพที่เป็นระบบ มีแหล่งอ้างอิง ตรวจสอบย้อนหลังได้ และพร้อมใช้งานจริงทั้งบนเว็บและในรูปแบบเอกสารทางการ

**เอกสารออกแบบระบบเวอร์ชันสมบูรณ์**

**AI Agent System สำหรับสร้างเอกสารแผนสุขภาพ**

ครอบคลุมหัวข้อ: อุบัติเหตุ • สุขภาพจิต • โภชนาการที่เชื่อมโยงกับโรคเรื้อรัง

  **องค์ประกอบหลัก**   **รายละเอียด**
  -------------------- --------------------------------------------------------------------
  Database Schema      โครงข้อมูลกลาง + schema รายโดเมน + schema สำหรับ citation/evidence
  Agent Workflow       บทบาทของ agent แต่ละตัว ตั้งแต่รับโจทย์จนสร้างรายงาน
  Citation Flow        การผูกหลักฐานกับข้อความ ตาราง และกราฟ เพื่อ trace แหล่งอ้างอิง
  Report Template      แม่แบบรายงานสำหรับ web preview และส่งออก DOCX

*เอกสารฉบับนี้จัดทำเพื่อใช้ประกอบ proposal และใช้คุยรายละเอียดกับทีมพัฒนา*

# 1. บทสรุปผู้บริหาร

ระบบที่เสนอเป็น AI Agent System สำหรับค้นหา วิเคราะห์ สังเคราะห์ และสร้างเอกสารแผนสุขภาพจากทั้งเอกสารและฐานข้อมูลเชิงโครงสร้าง โดยรองรับการทำงานแบบ RAG, การสร้างตารางและกราฟอัตโนมัติ, การอ้างอิงแหล่งข้อมูลแบบ trace ได้ และการแสดงผลทั้งบนเว็บและในรูปแบบไฟล์ DOCX.

-   โดเมนข้อมูลหลัก 3 ด้าน ได้แก่ อุบัติเหตุ สุขภาพจิต และโภชนาการที่เชื่อมโยงกับโรคเรื้อรังหรือโรคที่เกิดจากพฤติกรรมการกิน

-   สถาปัตยกรรมข้อมูลเป็นแบบ hybrid: Document RAG + Database RAG + analytic mart + evidence registry

-   สถาปัตยกรรม agent ใช้ Orchestrator ควบคุมงานร่วมกับ specialist agents เช่น Retrieval, Citation, Domain Analyst, Chart/Table, Report Writer และ Review

-   ผลลัพธ์สุดท้ายต้องสามารถ preview บนเว็บ พร้อมดาวน์โหลดเป็น DOCX โดยยังคง metadata ของแหล่งอ้างอิงได้

# 2. วัตถุประสงค์และขอบเขต

-   สร้างระบบค้นข้อมูลจากเอกสารและฐานข้อมูลด้วยแนวทาง RAG เพื่อใช้ในการวิเคราะห์เชิงนโยบายและแผนสุขภาพ

-   สร้าง workflow สำหรับเรียบเรียงรายงานที่มีโครงสร้างมาตรฐาน พร้อมตาราง กราฟ และบทสรุปผู้บริหาร

-   กำหนด database schema และ agent workflow ที่รองรับ 3 โดเมนหลักในโครงเดียวกัน

-   เพิ่มกลไก citation/evidence ที่เชื่อมโยงข้อความ ตาราง และกราฟกับแหล่งข้อมูลต้นทาง

-   รองรับการใช้งานจริงผ่าน web preview และการส่งออกเป็นไฟล์ DOCX

# 3. ภาพรวมสถาปัตยกรรมระบบ

  **ชั้นระบบ**            **หน้าที่หลัก**                                           **องค์ประกอบสำคัญ**
  ----------------------- --------------------------------------------------------- -----------------------------------------------------
  Frontend Web            รับโจทย์ แสดง preview เอกสาร เรียกดูประวัติและดาวน์โหลด   Form, report preview, chart viewer, download DOCX
  Backend API             ควบคุม workflow, security, job orchestration, session     REST/Graph API, auth, job queue, audit log
  AI Agent Layer          วางแผนงาน ค้นข้อมูล วิเคราะห์ เขียนรายงาน ตรวจคุณภาพ      Orchestrator + specialist agents
  RAG / Data Layer        ค้นจากเอกสารและฐานข้อมูลที่จัดรูปสำหรับการวิเคราะห์       Vector store, analytic mart, metadata registry
  Reporting Layer         สร้างตาราง กราฟ และเอกสารฉบับสมบูรณ์                      Chart engine, template engine, DOCX renderer
  Evidence & Governance   จัดการ citation, traceability, review, compliance         Evidence registry, citation linker, review workflow

# 4. Database Schema

ฐานข้อมูลออกแบบเป็น 4 กลุ่ม ได้แก่ shared core schema, domain schema, analytic mart และ citation/evidence schema โดย agent จะเข้าถึงข้อมูลผ่าน tool/API ที่ควบคุมขอบเขต ไม่ query raw table โดยตรง.

## 4.1 Shared Core Schema

  **ตาราง**              **บทบาท**                                                 **ฟิลด์หลักตัวอย่าง**
  ---------------------- --------------------------------------------------------- ------------------------------------------------------------
  dim_geography          เก็บโครงสร้างพื้นที่เพื่อใช้ร่วมกันทุกโดเมน               province, district, subdistrict, latitude, longitude
  dim_time               เก็บมิติด้านเวลาเพื่อวิเคราะห์รายวัน รายเดือน รายไตรมาส   full_date, month_no, quarter_no, year_no, hour_no
  dim_population_group   อธิบายกลุ่มประชากรหรือกลุ่มเปราะบาง                       age_group, sex, occupation_group, vulnerable_group
  dim_facility           อธิบายสถานพยาบาลหรือหน่วยบริการ                           facility_code, facility_name, facility_type, service_level
  dim_source             บันทึกเจ้าของข้อมูลและระดับความเชื่อถือ                   source_name, source_type, owner_org, quality_level
  document_registry      ทะเบียนเอกสารที่เข้า Document RAG                         title, topic, effective_date, version_no, status
  document_chunks        หน่วยข้อความสำหรับ retrieval และ citation                 chunk_text, chunk_order, embedding_ref, page_ref
  indicator_catalog      คลังตัวชี้วัดและนิยามมาตรฐาน                              indicator_code, definition, unit_name, preferred_chart

## 4.2 Domain Schema: อุบัติเหตุ

  **ตาราง**               **หน้าที่**                                 **ตัวอย่างข้อมูลสำคัญ**
  ----------------------- ------------------------------------------- ----------------------------------------------------------------------------------------------------------------
  fact_accident_event     เก็บเหตุการณ์อุบัติเหตุรายเหตุ              event_datetime, road_segment_id, weather_condition, road_condition, severity_level, injured_count, death_count
  fact_accident_person    เก็บข้อมูลผู้ประสบเหตุรายบุคคลในเชิงสถิติ   age, sex, role_in_event, injury_level, helmet_used, seatbelt_used
  dim_road_segment        เก็บรายละเอียดถนนและสภาพทางกายภาพ           road_name, lane_count, curvature_type, speed_limit, surface_type, risk_flag
  mart_accident_summary   สรุปความถี่และผลกระทบตามเวลา/พื้นที่        accident_count, injured_count, death_count, high_risk_timeband
  mart_accident_hotspot   จัดอันดับจุดเสี่ยงและคะแนน hotspot          hotspot_score, dominant_timeband, road_segment_id

## 4.3 Domain Schema: สุขภาพจิต

  **ตาราง**                      **หน้าที่**                                        **ตัวอย่างข้อมูลสำคัญ**
  ------------------------------ -------------------------------------------------- -----------------------------------------------------------------------------
  fact_mental_health_visit       เก็บการเข้ารับบริการสุขภาพจิต                      visit_date, diagnosis_group, referral_flag, wait_time_days, service_channel
  fact_suicide_indicator         เก็บตัวชี้วัดการฆ่าตัวตายระดับพื้นที่และช่วงเวลา   suicide_case_count, population_base, suicide_rate
  fact_mental_service_capacity   เก็บศักยภาพของหน่วยบริการ                          psychiatrist_count, psychologist_count, nurse_count, service_slot_count
  mart_mental_health_access      สรุปการใช้บริการและภาระงาน                         service_use_rate, new_case_count, referral_rate, avg_wait_time_days
  mart_mental_health_risk_gap    เชื่อม risk กับช่องว่างบริการ                      suicide_rate, service_use_rate, capacity_score, care_gap_score

## 4.4 Domain Schema: โภชนาการ + โรคเรื้อรัง

โดเมนนี้ออกแบบให้เห็นความสัมพันธ์จากพฤติกรรมการกิน → ภาวะโภชนาการ → ความเสี่ยงทางคลินิก → ภาระโรคเรื้อรัง เพื่อใช้จัดทำแผนที่มีเหตุผลเชิงหลักฐาน.

  **ตาราง**                           **หน้าที่**                                          **ตัวอย่างข้อมูลสำคัญ**
  ----------------------------------- ---------------------------------------------------- --------------------------------------------------------------------------
  dim_disease                         กลุ่มโรคเรื้อรัง/โรคที่เกี่ยวข้องกับอาหาร            disease_group, diet_related_flag, chronic_flag
  fact_nutrition_assessment           เก็บข้อมูลภาวะโภชนาการรายหน่วยข้อมูล                 height_cm, weight_kg, bmi, bmi_category, waist_cm
  fact_food_consumption               เก็บ consumption pattern และพฤติกรรมเสี่ยง           fruit_intake_freq, sugary_drink_freq, fast_food_freq, sodium_risk_flag
  fact_clinical_risk_profile          เก็บตัวชี้วัดคลินิกที่สะท้อนความเสี่ยง               hba1c, systolic_bp, ldl, triglyceride, egfr
  fact_chronic_disease_case           เก็บภาระโรคเรื้อรังในระดับพื้นที่/หน่วยบริการ        prevalence_rate, incidence_rate, admission_count
  fact_nutrition_intervention         เก็บข้อมูลมาตรการหรือโครงการด้านโภชนาการ             target_group, intervention_type, coverage_rate
  mart_nutrition_status               สรุปสถานะ BMI และภาวะโภชนาการ                        avg_bmi, underweight_pct, overweight_pct, obesity_pct
  mart_consumption_risk               สรุปพฤติกรรมการกินเสี่ยงในระดับพื้นที่               high_sugar_pct, high_sodium_pct, high_fastfood_pct, unhealthy_diet_score
  mart_diet_related_disease_summary   สรุปอัตราโรคที่สัมพันธ์กับการกิน                     diabetes_rate, hypertension_rate, dyslipidemia_rate, ckd_rate
  mart_nutrition_disease_link         ตารางเชื่อม consumption pattern กับ burden disease   unhealthy_diet_score, avg_bmi, diabetes_rate, diet_disease_risk_score

## 4.5 Citation / Evidence Schema

  **ตาราง**                 **หน้าที่**                                       **ฟิลด์หลักตัวอย่าง**
  ------------------------- ------------------------------------------------- ------------------------------------------------------------------------------------------------
  evidence_registry         ทะเบียนหลักฐานที่มาจากเอกสาร ฐานข้อมูล หรือ API   evidence_type, source_ref, section_label, page_ref, query_signature, extracted_at, trust_level
  report_citation           ผูก evidence เข้ากับรายงานและสร้างรหัส citation   citation_code, citation_type, bibliography_text
  report_section_citation   เชื่อม citation เข้ากับข้อความหรือ section        section_id, linked_text_snippet, claim_type, evidence_strength
  report_object_citation    เชื่อม citation เข้ากับกราฟและตาราง               object_type, object_id, citation_id

## 4.6 API / Tool Layer ที่ Agent ใช้งาน

  **กลุ่มเครื่องมือ**   **ตัวอย่าง tool/API**
  --------------------- ---------------------------------------------------------------------------------------------------------------------
  Common Tools          search_documents(), get_indicator_catalog(), get_report_template(), get_geography_profile()
  Accident Tools        get_accident_summary(), get_accident_hotspots(), get_accident_time_distribution(), get_road_condition_risk()
  Mental Health Tools   get_mental_service_utilization(), get_suicide_rate(), get_service_capacity_gap(), get_mental_risk_groups()
  Nutrition Tools       get_bmi_distribution(), get_consumption_pattern(), get_diet_related_disease_summary(), get_nutrition_disease_link()
  Citation Tools        build_document_evidence(), build_database_evidence(), link_citation_to_section(), compile_reference_list()
  Reporting Tools       generate_chart(), generate_table(), render_report_preview(), export_docx()

# 5. Agent Workflow

สถาปัตยกรรม agent แนะนำเป็น 1 Orchestrator ร่วมกับ specialist agents โดยทุก agent ใช้ output schema กลางเพื่อลดความซับซ้อนในการรวมรายงานและการ debug.

## 5.1 โครงสร้าง Agent

  **Agent**                   **หน้าที่หลัก**                                                        **ผลลัพธ์ที่คาดหวัง**
  --------------------------- ---------------------------------------------------------------------- ------------------------------------------------------------
  Request Interpreter Agent   ตีความโจทย์ ระบุหัวข้อ ช่วงเวลา พื้นที่ และรูปแบบรายงาน                normalized request payload
  Planner Agent               วาง outline รายงานและรายการข้อมูลที่ต้องใช้                            report plan, required data, task list
  Retrieval Agent             ค้นข้อมูลจาก Document RAG, Database RAG และ indicator catalog          facts, indicators, citations metadata, data frames
  Citation & Evidence Agent   สร้าง evidence package และ citation code ผูกกับข้อความ กราฟ และตาราง   evidence registry entries, citation map, reference list
  Domain Analyst Agent        วิเคราะห์เชิงโดเมน แยกเป็น accident / mental health / nutrition        key findings, risk groups, priority areas, recommendations
  Chart & Table Agent         เลือกประเภทกราฟและออกแบบตาราง                                          chart specs, table specs
  Report Writer Agent         เรียบเรียงเนื้อหาเป็นรายงานภาษาไทยเชิงทางการ                           executive summary, section drafts, recommendations
  Review & Compliance Agent   ตรวจความครบถ้วน ความน่าเชื่อถือ และ coverage ของ citation              approval status, issues list, citation gaps

## 5.2 ลำดับการทำงานแบบ end-to-end

1.  ผู้ใช้กรอกคำขอ ระบุหัวข้อ พื้นที่ ช่วงเวลา และประเภทรายงานบนหน้าเว็บ

2.  Request Interpreter Agent แปลงคำขอเป็น structured payload และส่งให้ Planner

3.  Planner Agent สร้างโครงร่างรายงาน กำหนด section และรายการข้อมูลที่ต้องใช้ในแต่ละส่วน

4.  Retrieval Agent เรียก Document RAG, Database tools และตัวชี้วัดมาตรฐาน เพื่อดึง facts พร้อม metadata ของแหล่งข้อมูล

5.  Citation & Evidence Agent ลงทะเบียนหลักฐาน สร้าง citation code และผูก fact แต่ละข้อเข้ากับแหล่งอ้างอิง

6.  Domain Analyst Agent วิเคราะห์และสรุปประเด็นสำคัญเฉพาะโดเมน โดยใช้เฉพาะข้อมูลที่มี evidence รองรับ

7.  Chart & Table Agent เลือกชนิดกราฟและออกแบบตารางจากข้อมูลที่วิเคราะห์ได้

8.  Report Writer Agent สร้างรายงานฉบับร่าง พร้อมใส่ inline citation หรือ source note ใน section, chart และ table

9.  Review & Compliance Agent ตรวจความครบถ้วนของเนื้อหา ตัวเลข และ coverage ของ citation ก่อนอนุมัติ

10. Reporting Layer render เป็น web preview และ export เป็นไฟล์ DOCX สำหรับดาวน์โหลด

## 5.3 กฎการทำงานที่แนะนำ

-   Agent ทุกตัวส่งผลลัพธ์ใน schema กลางเพื่อให้ orchestration ง่าย

-   ข้อความที่เป็นข้อเท็จจริงเชิงตัวเลขต้องมาจาก evidence ที่ลงทะเบียนแล้วเท่านั้น

-   หาก retrieval พบข้อมูลขัดกันหลายแหล่ง ต้องส่งต่อให้ Review & Compliance Agent ตัดสินใจ

-   สุขภาพจิตควรมี human review ก่อนเผยแพร่หรือส่งออกเป็นรายงานทางการ

-   ไม่เปิดสิทธิ์ให้ agent เขียนหรือปรับข้อมูลฐานข้อมูลต้นทางโดยตรง

# 6. Citation Flow และการจัดการแหล่งอ้างอิง

Citation Flow เป็นแกนสำคัญของระบบ เพราะรายงานแผนสุขภาพต้องตรวจสอบย้อนกลับได้ทั้งในระดับข้อความ ตาราง และกราฟ โดยอาศัย Citation & Evidence Agent เป็นตัวกลางระหว่าง Retrieval, Writer และ Review.

## 6.1 แหล่งข้อมูลที่ต้องรองรับ

  **ประเภทแหล่งข้อมูล**     **รายละเอียด metadata ที่ต้องเก็บ**                                                         **ตัวอย่างการอ้างอิง**
  ------------------------- ------------------------------------------------------------------------------------------- ----------------------------------------
  Document Citation         title, topic, section_label, page_ref, chunk_id, source_org, effective_date, version_no     คู่มือ/นโยบาย/รายงานวิชาการ หน้า X
  Database Citation         table/view name, query parameters, geography, time range, extraction timestamp, owner_org   mart_xxx, จังหวัด Y, ช่วงเวลา Z
  API / External Citation   endpoint name, request parameter, retrieved_at, response signature                          ข้อมูลจาก service ภายนอกที่ผูกเข้าระบบ

## 6.2 Citation Flow แบบลำดับงาน

11. Retrieval Agent ดึง facts พร้อม metadata ของแหล่งข้อมูลต้นทาง

12. Citation & Evidence Agent แปลงผล retrieval เป็น evidence package และบันทึกลง evidence_registry

13. สร้าง citation code เช่น C-001, C-002 สำหรับใช้ในรายงานและส่งออก DOCX

14. เชื่อม citation เข้ากับ section text, chart และ table ผ่าน report_section_citation / report_object_citation

15. Report Writer เรียกใช้ citation map เพื่อแทรก inline citation หรือ source note ตามรูปแบบของ template

16. Review & Compliance ตรวจว่าทุกข้อสรุปหลัก ทุกกราฟ และทุกตารางมี source note หรือ inline citation ครบ

17. ระบบ compile reference list อัตโนมัติและแสดงท้ายรายงาน

## 6.3 กฎ Citation ที่ควรกำหนดในระบบ

-   ข้อสรุปเชิงตัวเลขทุกข้อ ต้องมี citation

-   กราฟและตารางทุกชิ้น ต้องมี source note ที่ trace กลับไปยัง evidence ได้

-   ข้อเสนอเชิงนโยบายที่อ้างอิงหลักฐานเชิงประจักษ์ ควรมี reference supporting basis

-   หากไม่มีหลักฐานเพียงพอ ระบบต้องระบุว่า insufficient evidence แทนการสรุปเกินข้อมูล

-   reference list ท้ายรายงานต้องมาจาก evidence ที่ถูกใช้จริงในเนื้อหาเท่านั้น

## 6.4 Output schema กลางของรายงาน

  **field**                **คำอธิบาย**
  ------------------------ ---------------------------------------------------------------
  document_title           ชื่อรายงาน
  report_type              ประเภทรายงาน เช่น แผนสุขภาพระดับจังหวัด
  topic_list               หัวข้อที่อยู่ในรายงาน เช่น accident, mental_health, nutrition
  time_range / geography   ช่วงเวลาข้อมูลและพื้นที่เป้าหมาย
  executive_summary        บทสรุปผู้บริหาร
  sections\[\]             แต่ละ section มี text, charts, tables, citations
  recommendations\[\]      ข้อเสนอเชิงมาตรการ
  references\[\]           รายการอ้างอิงท้ายรายงาน

# 7. Report Template

Report Template ต้องรองรับทั้ง web preview และ DOCX โดยใช้โครงสร้างกลางเดียวกัน แล้วแยกการ render ตามช่องทางปลายทางเพื่อลดภาระของ agent และรักษาความสม่ำเสมอของเอกสาร.

## 7.1 Template กลางของรายงาน

  **ลำดับ**   **หัวข้อหลัก**                **สาระสำคัญที่ควรมี**
  ----------- ----------------------------- --------------------------------------------------------------------------
  1           หน้าปก                        ชื่อเอกสาร พื้นที่ ช่วงเวลา หน่วยงาน และวันที่สร้าง
  2           บทสรุปผู้บริหาร               สถานการณ์เด่น พื้นที่/กลุ่มเสี่ยง และข้อเสนอสำคัญ
  3           วัตถุประสงค์ของแผน            เหตุผลในการจัดทำ เป้าหมาย และขอบเขตข้อมูล
  4           แหล่งข้อมูลและวิธีวิเคราะห์   ชุดข้อมูลที่ใช้ ช่วงเวลา วิธีวิเคราะห์ และข้อจำกัดของข้อมูล
  5           สถานการณ์ปัจจุบัน             ตัวชี้วัดหลัก แนวโน้มย้อนหลัง การเปรียบเทียบเชิงพื้นที่
  6           การวิเคราะห์เชิงลึก           ปัจจัยเสี่ยง กลุ่มเป้าหมาย จุดเสี่ยง/ช่องว่างบริการ พร้อมหลักฐานสนับสนุน
  7           ข้อเสนอเชิงมาตรการ            ระยะสั้น ระยะกลาง ระยะยาว พร้อมหน่วยงานเจ้าภาพ
  8           แผนดำเนินงาน                  กิจกรรม กลุ่มเป้าหมาย พื้นที่เป้าหมาย ระยะเวลา และ KPI
  9           ภาคผนวก                       ตาราง กราฟ รายละเอียดตัวชี้วัด และ references

## 7.2 Template เฉพาะโดเมน

  **โดเมน**                **หัวข้อย่อยสำคัญ**                                                                                     **กราฟ/ตารางที่แนะนำ**
  ------------------------ ------------------------------------------------------------------------------------------------------- -----------------------------------------------------------------------------------
  อุบัติเหตุ               ความถี่ จุดเสี่ยง เวลาเสี่ยง สภาพถนน กลุ่มผู้ประสบเหตุ                                                  line trend, hotspot ranking table, time heatmap, road-condition risk table
  สุขภาพจิต                อัตราการเข้ารับบริการ suicide rate การเข้าถึงบริการ service gap กลุ่มเสี่ยง                             line trend, area comparison bar, service gap table, risk group table
  โภชนาการ + โรคเรื้อรัง   BMI distribution, consumption pattern, burden disease, linkage กับเบาหวาน/ความดัน/ไขมัน/โรคอ้วน/โรคไต   stacked BMI chart, grouped diet-risk chart, disease trend line, risk matrix table

## 7.3 แนวการเขียนที่ Report Writer ควรใช้

-   ย่อหน้าเชิงสถานการณ์: อธิบายแนวโน้ม ขนาดปัญหา และพื้นที่/กลุ่มเสี่ยงโดยอ้างอิงตัวเลข

-   ย่อหน้าเชิงความเชื่อมโยง: อธิบายความสัมพันธ์ระหว่างปัจจัยกับผลลัพธ์อย่างระมัดระวัง ไม่สรุปเหตุและผลเกินกว่าหลักฐาน

-   ย่อหน้าเชิงข้อเสนอ: เสนอแนวทางระยะสั้น กลาง ยาว โดยผูกกับหลักฐานและกลุ่มเป้าหมายที่ชัดเจน

-   ทุก section ควรมี citation ครบและแยกให้ชัดระหว่างข้อเท็จจริง ข้อสังเกต และข้อเสนอเชิงนโยบาย

# 8. Deliverables และข้อเสนอเชิงการพัฒนา

  **Deliverable**                 **รายละเอียด**
  ------------------------------- ------------------------------------------------------------------------------
  1\. Data Foundation             shared schema, domain schema, analytic mart และ metadata/evidence schema
  2\. Agent Orchestration         workflow สำหรับ Request → Retrieval → Citation → Analysis → Writing → Review
  3\. Reporting Engine            web preview, chart/table generation, DOCX export
  4\. Governance & Traceability   citation registry, audit log, review workflow, quality rules
  5\. Template Pack               template รายงานกลางและ template เฉพาะโดเมน 3 ชุด

## 8.1 ข้อเสนอการเริ่มพัฒนา

1\. Phase 1: ทำ shared schema, document registry, accident mart และ report engine สำหรับรายงานโดเมนเดียว

2\. Phase 2: เพิ่มสุขภาพจิต พร้อม review/compliance และ citation coverage check ที่เข้มขึ้น

3\. Phase 3: เพิ่มโภชนาการที่เชื่อมโรคเรื้อรัง พร้อม nutrition-disease linkage mart และ comparative report

4\. Phase 4: ขยายสู่ production ด้วย monitoring, audit trail, role-based access และ template หลายรูปแบบ

# 9. สรุปสำหรับใช้ใน proposal

ระบบที่เสนอเป็นแพลตฟอร์ม AI Agent สำหรับสร้างเอกสารแผนสุขภาพที่เชื่อถือได้ โดยวางฐานข้อมูลให้รองรับทั้ง Document RAG และ Database RAG, ออกแบบ agent เป็นลำดับงานที่ตรวจสอบได้, เพิ่ม Citation Flow เพื่อ trace หลักฐานตลอดกระบวนการ และกำหนด report template ที่นำไปใช้ทั้งบนเว็บและในไฟล์ DOCX ได้จริง. แนวทางนี้ช่วยให้ทีมพัฒนามีกรอบการทำงานที่ชัดเจน ลดความเสี่ยงด้านคุณภาพข้อมูล และทำให้เอกสารที่สร้างขึ้นพร้อมใช้งานในบริบท proposal, policy planning และรายงานเชิงบริหาร.

ได้ครับ ด้านล่างคือฉบับ **ปรับหัวข้อรายงาน + ออกแบบฐานข้อมูล + ออกแบบ agent** ให้สอดคล้องกับ 3 โดเมนนี้โดยตรง

-   **อุบัติเหตุ**: ความถี่, จุดเสี่ยง, เวลา, สภาพถนน

-   **สุขภาพจิต**: อัตราการเข้ารับบริการ, suicide rate, กลุ่มเสี่ยง, การเข้าถึงบริการ

-   **โภชนาการ**: BMI, consumption pattern, กลุ่มเป้าหมาย, พฤติกรรมเสี่ยง

ผมออกแบบให้ใช้ได้กับระบบ **RAG + Database + AI Agent + Report Generator** ในโครงเดียวกัน

**1) ปรับหัวข้อรายงานให้สอดคล้อง**

**1.1 โครงหัวข้อหลักร่วมของทุกแผนสุขภาพ**

เพื่อให้ระบบเขียนรายงานได้เป็นมาตรฐานเดียวกัน ควรกำหนดหัวข้อกลางแบบนี้

1.  บทสรุปผู้บริหาร

2.  สถานการณ์ปัจจุบัน

3.  ตัวชี้วัดสำคัญ

4.  การวิเคราะห์เชิงพื้นที่ / เชิงเวลา / เชิงกลุ่มประชากร

5.  ปัจจัยเสี่ยงและสาเหตุที่เกี่ยวข้อง

6.  กลุ่มเป้าหมายสำคัญ

7.  ข้อเสนอเชิงนโยบาย / มาตรการ

8.  แผนดำเนินงาน

9.  ตัวชี้วัดติดตามผล

10. ภาคผนวก: ตาราง, กราฟ, แหล่งข้อมูลอ้างอิง

**1.2 หัวข้อเฉพาะด้าน "อุบัติเหตุ"**

**หมวดวิเคราะห์ที่ควรมี**

1.  ภาพรวมสถานการณ์อุบัติเหตุ

2.  ความถี่การเกิดอุบัติเหตุ

3.  การกระจายตามช่วงเวลา

4.  จุดเสี่ยง / พื้นที่เสี่ยงสูง

5.  ปัจจัยแวดล้อมที่เกี่ยวข้อง

6.  สภาพถนนและลักษณะทางกายภาพ

7.  ประเภทยานพาหนะ / ผู้ประสบเหตุ / กลุ่มอายุ

8.  แนวโน้มเปรียบเทียบรายเดือน / รายปี

9.  ข้อเสนอป้องกันและลดความเสี่ยง

**ตัวชี้วัดหลัก**

-   จำนวนเหตุ

-   อัตราเกิดเหตุ ต่อประชากร

-   ช่วงเวลาที่เกิดเหตุสูงสุด

-   จุดเสี่ยงสูงสุด

-   ประเภทถนน / สภาพถนน / สภาพอากาศ

-   จำนวนบาดเจ็บ / เสียชีวิต

-   กลุ่มอายุหรือประเภทยานพาหนะที่มีความเสี่ยงสูง

**1.3 หัวข้อเฉพาะด้าน "สุขภาพจิต"**

**หมวดวิเคราะห์ที่ควรมี**

1.  ภาพรวมสถานการณ์สุขภาพจิต

2.  อัตราการเข้ารับบริการ

3.  suicide rate ในระดับพื้นที่ / ช่วงเวลา / กลุ่มประชากร

4.  การเข้าถึงบริการและความครอบคลุม

5.  กลุ่มเปราะบางหรือกลุ่มเสี่ยง

6.  ปัจจัยทางสังคมและเศรษฐกิจที่เกี่ยวข้อง

7.  แนวโน้มการใช้บริการและภาระงานบริการ

8.  ช่องว่างของระบบบริการ

9.  ข้อเสนอเชิงป้องกัน ส่งเสริม และเฝ้าระวัง

**ตัวชี้วัดหลัก**

-   อัตราการเข้ารับบริการสุขภาพจิต

-   จำนวนผู้รับบริการรายใหม่ / รายเก่า

-   suicide rate ต่อประชากร

-   อัตราการส่งต่อ

-   ระยะเวลารอรับบริการ

-   พื้นที่ที่เข้าถึงบริการต่ำ

-   กลุ่มอายุ / เพศ / กลุ่มเสี่ยงสำคัญ

สำหรับหัวข้อนี้ ระบบควรใช้เพื่อ **วิเคราะห์เชิงนโยบายและวางแผนบริการ** ไม่ควรสร้างคำแนะนำเชิงวินิจฉัยหรือเฉพาะบุคคล

**1.4 หัวข้อเฉพาะด้าน "โภชนาการ"**

**หมวดวิเคราะห์ที่ควรมี**

1.  ภาพรวมภาวะโภชนาการ

2.  BMI และสถานะทางโภชนาการ

3.  consumption pattern / รูปแบบการบริโภค

4.  กลุ่มเสี่ยงด้านโภชนาการ

5.  พฤติกรรมการบริโภคที่สัมพันธ์กับความเสี่ยง

6.  การเปรียบเทียบตามช่วงวัย / พื้นที่ / โรงเรียน / ชุมชน

7.  แนวโน้มตัวชี้วัดโภชนาการ

8.  ปัจจัยแวดล้อมด้านอาหาร

9.  ข้อเสนอส่งเสริมโภชนาการที่เหมาะสม

**ตัวชี้วัดหลัก**

-   BMI เฉลี่ย

-   สัดส่วนผอม / ปกติ / น้ำหนักเกิน / อ้วน

-   consumption pattern เช่น หวาน มัน เค็ม ผัก ผลไม้

-   ความถี่การบริโภคอาหารบางประเภท

-   กลุ่มอายุหรือพื้นที่ที่มีความเสี่ยง

-   แนวโน้มเปรียบเทียบรายเวลา

**2) ออกแบบฐานข้อมูลให้สอดคล้อง**

ผมแนะนำให้ใช้แนวคิด **Hybrid Database Design**\
คือมีทั้ง

-   **Operational / Raw tables** สำหรับเก็บข้อมูลต้นทาง

-   **Analytic tables / Data mart** สำหรับ query เร็วเพื่อ agent สร้างรายงาน

-   **Metadata / Evidence tables** สำหรับ RAG และการอ้างอิง

**2.1 โครงสร้างฐานข้อมูลกลาง**

ควรมีตารางกลางใช้ร่วมกันทุกโดเมน

**Master / Dimension Tables**

-   dim_geography

    -   geography_id

    -   country

    -   province

    -   district

    -   subdistrict

    -   latitude

    -   longitude

-   dim_time

    -   time_id

    -   date

    -   day

    -   week

    -   month

    -   quarter

    -   year

    -   hour

-   dim_population_group

    -   group_id

    -   age_group

    -   sex

    -   occupation

    -   vulnerable_group

-   dim_facility

    -   facility_id

    -   facility_name

    -   facility_type

    -   geography_id

-   dim_source

    -   source_id

    -   source_name

    -   source_type

    -   update_frequency

    -   owner_org

**Shared Metadata Tables**

-   document_registry

    -   document_id

    -   title

    -   document_type

    -   topic

    -   source_id

    -   uploaded_at

    -   effective_date

    -   status

-   document_chunks

    -   chunk_id

    -   document_id

    -   chunk_text

    -   chunk_order

    -   embedding_ref

    -   keywords

-   indicator_catalog

    -   indicator_id

    -   topic

    -   indicator_name

    -   definition

    -   unit

    -   chart_default

    -   report_section

**2.2 ฐานข้อมูลด้านอุบัติเหตุ**

**Raw / Fact Tables**

-   fact_accident_event

    -   accident_id

    -   event_datetime

    -   geography_id

    -   road_id

    -   weather_condition

    -   road_condition

    -   light_condition

    -   accident_type

    -   severity_level

    -   vehicle_type

    -   injured_count

    -   death_count

    -   source_id

-   fact_accident_person

    -   person_event_id

    -   accident_id

    -   age

    -   sex

    -   role_in_event

    -   injury_level

    -   helmet_used

    -   seatbelt_used

-   dim_road_segment

    -   road_id

    -   road_name

    -   road_type

    -   lane_count

    -   curvature_type

    -   slope_type

    -   speed_limit

    -   surface_type

    -   risk_flag

**Analytic Tables**

-   mart_accident_summary_by_time

    -   month

    -   year

    -   geography_id

    -   accident_count

    -   injured_count

    -   death_count

-   mart_accident_hotspot

    -   hotspot_id

    -   geography_id

    -   road_id

    -   accident_count

    -   severity_score

    -   top_time_window

    -   dominant_condition

**สิ่งที่ agent query บ่อย**

-   พื้นที่เกิดเหตุสูงสุด

-   ช่วงเวลาเสี่ยง

-   ถนนหรือจุดเสี่ยง

-   ความสัมพันธ์ระหว่างสภาพถนนกับความถี่การเกิดเหตุ

**2.3 ฐานข้อมูลด้านสุขภาพจิต**

**Raw / Fact Tables**

-   fact_mental_health_visit

    -   visit_id

    -   visit_date

    -   facility_id

    -   geography_id

    -   patient_group_id

    -   visit_type

    -   diagnosis_group

    -   referral_flag

    -   wait_time_days

    -   service_channel

    -   source_id

-   fact_suicide_indicator

    -   record_id

    -   record_date

    -   geography_id

    -   age_group

    -   sex

    -   suicide_case_count

    -   population_base

    -   suicide_rate

-   fact_mental_health_service_capacity

    -   capacity_id

    -   facility_id

    -   month

    -   year

    -   psychiatrist_count

    -   psychologist_count

    -   nurse_count

    -   service_slot_count

**Analytic Tables**

-   mart_mental_health_service_access

    -   month

    -   year

    -   geography_id

    -   service_use_rate

    -   new_case_count

    -   referral_rate

    -   avg_wait_time

-   mart_mental_health_risk_area

    -   geography_id

    -   month

    -   year

    -   suicide_rate

    -   service_use_rate

    -   care_gap_score

**สิ่งที่ agent query บ่อย**

-   พื้นที่ที่มี suicide rate สูง

-   พื้นที่ที่เข้าถึงบริการต่ำ

-   แนวโน้มการเข้ารับบริการ

-   ความสัมพันธ์ระหว่าง service capacity กับ service utilization

**2.4 ฐานข้อมูลด้านโภชนาการ**

**Raw / Fact Tables**

-   fact_nutrition_assessment

    -   assessment_id

    -   assessment_date

    -   geography_id

    -   facility_id

    -   age_group

    -   sex

    -   height_cm

    -   weight_kg

    -   bmi

    -   bmi_category

    -   source_id

-   fact_food_consumption

    -   consumption_id

    -   survey_date

    -   geography_id

    -   group_id

    -   meal_frequency

    -   fruit_intake_freq

    -   vegetable_intake_freq

    -   sugary_drink_freq

    -   fast_food_freq

    -   snack_freq

    -   sodium_risk_flag

-   fact_nutrition_program

    -   program_id

    -   geography_id

    -   target_group

    -   intervention_type

    -   start_date

    -   end_date

    -   coverage_rate

**Analytic Tables**

-   mart_bmi_summary

    -   month

    -   year

    -   geography_id

    -   avg_bmi

    -   underweight_pct

    -   normal_pct

    -   overweight_pct

    -   obesity_pct

-   mart_consumption_pattern

    -   month

    -   year

    -   geography_id

    -   healthy_score

    -   sugary_drink_risk_pct

    -   low_vegfruit_pct

    -   high_fastfood_pct

**สิ่งที่ agent query บ่อย**

-   BMI distribution

-   กลุ่มอายุที่มีน้ำหนักเกินสูง

-   พื้นที่ที่มีพฤติกรรมบริโภคเสี่ยง

-   แนวโน้ม consumption pattern

**3) ออกแบบ Agent ให้สอดคล้องกับฐานข้อมูลและงานรายงาน**

ผมแนะนำเป็น **6 agent หลัก** โดยมี 1 ตัวคุม flow และ 5 ตัวทำงานเฉพาะด้าน

**3.1 Orchestrator Agent**

หน้าที่:

-   รับคำขอจากผู้ใช้

-   แยกว่าโจทย์เป็นเรื่องอุบัติเหตุ / สุขภาพจิต / โภชนาการ หรือหลายเรื่อง

-   เลือก workflow

-   สั่ง domain agent ที่เกี่ยวข้อง

-   รวมผลลัพธ์เป็นรายงานเดียว

input:

-   prompt จากผู้ใช้

-   ช่วงเวลา

-   พื้นที่

-   ประเภทเอกสาร

output:

-   report plan

-   task list

-   final structured report payload

**3.2 Retrieval Agent**

หน้าที่:

-   ค้นข้อมูลจาก Document RAG

-   ค้นข้อมูลจาก Database RAG

-   ดึง evidence ที่เกี่ยวข้อง

-   จัดอันดับความน่าเชื่อถือของข้อมูล

tools:

-   search_documents(topic, query)

-   query_accident_mart(filters)

-   query_mental_health_mart(filters)

-   query_nutrition_mart(filters)

-   get_indicator_definition(indicator_name)

output:

-   evidence package

-   cited facts

-   candidate indicators

**3.3 Domain Analyst Agents**

แยก 3 ตัว

**Accident Analyst Agent**

หน้าที่:

-   วิเคราะห์ความถี่

-   หา hotspot

-   วิเคราะห์เวลาและสภาพถนน

-   สรุปข้อเสนอป้องกัน

**Mental Health Analyst Agent**

หน้าที่:

-   วิเคราะห์ service utilization

-   วิเคราะห์ suicide rate เชิงพื้นที่และเวลา

-   หาช่องว่างบริการ

-   สรุปข้อเสนอเชิงระบบบริการ

**Nutrition Analyst Agent**

หน้าที่:

-   วิเคราะห์ BMI distribution

-   วิเคราะห์ consumption pattern

-   ระบุกลุ่มเสี่ยง

-   สรุปแนวทางส่งเสริมสุขภาพ

output ของทุกตัวควรเหมือนกัน:

-   key findings

-   supporting metrics

-   chart suggestions

-   policy recommendations

**3.4 Chart & Table Agent**

หน้าที่:

-   เลือกว่าข้อมูลไหนควรเป็นกราฟ

-   สร้าง spec สำหรับกราฟและตาราง

-   ส่งข้อมูลให้ report engine

ตัวอย่าง logic:

-   แนวโน้มรายเดือน → line chart

-   เปรียบเทียบจังหวัด → bar chart

-   BMI category → stacked bar / pie

-   hotspot accidents → heatmap / ranked table

-   service coverage gap → comparison table

output:

-   chart_spec\[\]

-   table_spec\[\]

**3.5 Report Writer Agent**

หน้าที่:

-   นำผลวิเคราะห์มาเรียบเรียงเป็นภาษาไทยทางการ

-   เติมหัวข้อให้ครบตาม template

-   เขียนบทสรุปผู้บริหาร

-   สร้างข้อความเชื่อมโยงระหว่างข้อมูล

output schema ที่แนะนำ:

-   title

-   executive_summary

-   sections

-   recommendations

-   appendix

-   references

**3.6 Review & Compliance Agent**

หน้าที่:

-   ตรวจว่ามีข้อมูลอ้างอิงครบหรือไม่

-   ตรวจว่าใช้ตัวชี้วัดถูกโดเมน

-   ตรวจว่าไม่สรุปเกินข้อมูล

-   ตรวจความเสี่ยงด้านเนื้อหา โดยเฉพาะหัวข้อสุขภาพจิต

-   ตรวจความครบถ้วนก่อน export

rules สำคัญ:

-   ถ้าไม่มี evidence ห้ามเขียนข้อสรุปเชิงยืนยัน

-   ถ้าข้อมูลขัดแย้งกัน ให้ flag review

-   ถ้าเป็นสุขภาพจิต ให้แสดงเชิงระบบ ไม่ใช่รายบุคคล

**4) ความสัมพันธ์ระหว่างหัวข้อ ฐานข้อมูล และ agent**

**4.1 อุบัติเหตุ**

หัวข้อรายงาน:

-   ความถี่

-   จุดเสี่ยง

-   เวลา

-   สภาพถนน

ฐานข้อมูลหลัก:

-   fact_accident_event

-   dim_road_segment

-   mart_accident_summary_by_time

-   mart_accident_hotspot

agent หลัก:

-   Retrieval Agent

-   Accident Analyst Agent

-   Chart & Table Agent

-   Report Writer Agent

กราฟที่เหมาะ:

-   line chart แนวโน้ม

-   bar chart จุดเสี่ยง

-   heatmap เวลาเกิดเหตุ

-   ranked table สภาพถนนกับความเสี่ยง

**4.2 สุขภาพจิต**

หัวข้อรายงาน:

-   อัตราการเข้ารับบริการ

-   suicide rate

-   การเข้าถึงบริการ

-   กลุ่มเสี่ยง

ฐานข้อมูลหลัก:

-   fact_mental_health_visit

-   fact_suicide_indicator

-   fact_mental_health_service_capacity

-   mart_mental_health_service_access

agent หลัก:

-   Retrieval Agent

-   Mental Health Analyst Agent

-   Chart & Table Agent

-   Review & Compliance Agent

กราฟที่เหมาะ:

-   line chart service utilization

-   bar chart เปรียบเทียบพื้นที่

-   table ช่องว่างบริการ

-   trend chart suicide rate

**4.3 โภชนาการ**

หัวข้อรายงาน:

-   BMI

-   consumption pattern

-   พฤติกรรมเสี่ยง

-   กลุ่มเป้าหมาย

ฐานข้อมูลหลัก:

-   fact_nutrition_assessment

-   fact_food_consumption

-   mart_bmi_summary

-   mart_consumption_pattern

agent หลัก:

-   Retrieval Agent

-   Nutrition Analyst Agent

-   Chart & Table Agent

-   Report Writer Agent

กราฟที่เหมาะ:

-   stacked bar BMI category

-   line chart แนวโน้ม BMI

-   bar chart consumption risk

-   comparison table กลุ่มอายุ / พื้นที่

**5) โครง API / Tool ที่ควรมีให้ agent ใช้**

เพื่อให้ agent ทำงานแม่น ควรไม่เปิดฐานข้อมูลกว้างเกินไป แต่ทำ tool แบบมีขอบเขต

**Tool กลาง**

-   search_policy_docs(topic, keywords)

-   get_indicator_catalog(topic)

-   get_report_template(report_type)

**Tool ด้านอุบัติเหตุ**

-   get_accident_summary(start_date, end_date, geography)

-   get_accident_hotspots(start_date, end_date, geography)

-   get_accident_time_distribution(start_date, end_date, geography)

-   get_road_condition_risk(start_date, end_date, geography)

**Tool ด้านสุขภาพจิต**

-   get_mental_service_utilization(start_date, end_date, geography)

-   get_suicide_rate(start_date, end_date, geography)

-   get_service_capacity_gap(start_date, end_date, geography)

**Tool ด้านโภชนาการ**

-   get_bmi_distribution(start_date, end_date, geography, age_group)

-   get_consumption_pattern(start_date, end_date, geography, target_group)

-   get_nutrition_risk_groups(start_date, end_date, geography)

**Tool สำหรับรายงาน**

-   generate_chart(spec)

-   generate_table(spec)

-   render_report_preview(payload)

-   export_docx(payload)

**6) โครง output กลางของระบบ**

แนะนำให้ทุก agent ส่งผลใน schema เดียวกัน เพื่อให้รวมรายงานได้ง่าย

{\
\"topic\": \"accident \| mental_health \| nutrition\",\
\"report_title\": \"\",\
\"time_range\": \"\",\
\"geography\": \"\",\
\"key_findings\": \[\],\
\"indicators\": \[\],\
\"charts\": \[\],\
\"tables\": \[\],\
\"recommendations\": \[\],\
\"evidence_refs\": \[\]\
}

จากนั้น Orchestrator ค่อยรวมเป็นเอกสารสุดท้าย

{\
\"document_title\": \"\",\
\"executive_summary\": \"\",\
\"sections\": \[\],\
\"tables\": \[\],\
\"charts\": \[\],\
\"references\": \[\],\
\"download_formats\": \[\"web\", \"docx\"\]\
}

**7) ข้อเสนอที่ควรใช้จริง**

ถ้าจะทำให้ระบบนิ่งและขยายง่าย ผมแนะนำแบบนี้

**ระยะเริ่มต้น**

-   ใช้ 3 domain แยกกันก่อน

-   ใช้ analytic marts มากกว่า query raw table ตรง

-   ใช้ single orchestrator + domain analyst

**ระยะขยาย**

-   เพิ่ม comparative report ข้าม 3 โดเมน

-   เพิ่ม dashboard บนเว็บ

-   เพิ่ม template หลายแบบ เช่น รายงานผู้บริหาร / รายงานเชิงวิชาการ / แผนปฏิบัติการ

**ระยะ production**

-   มี review ก่อน export ทุกฉบับ

-   เก็บ trace ว่าใช้ข้อมูลจากไหน

-   บังคับ citation ทุกข้อสรุปสำคัญ

ถ้าต้องการ ผมแปลงสิ่งนี้ต่อให้เป็น **เอกสารออกแบบระบบทางการ** โดยจัดเป็น 3 ส่วนชัด ๆ คือ\
**1. Database Schema, 2. Agent Workflow, 3. Report Template** ให้พร้อมใช้ใน proposal หรือคุยกับทีม dev ได้เลย

ปรับเรื่องโภชนการใช้เกี่ยวข้องกับโรคเรื้อรัง เเละโรคที่เกิดจากกินอื่นๆ 1. Database Schema, 2. Agent Workflow, 3. Report Template ให้พร้อมใช้ใน proposal หรือคุยกับทีม dev ได้เลย เเละ หรือคุยกับทีม dev ได้เลย

Thought for 16s

ได้ครับ ด้านล่างคือฉบับ **พร้อมใช้ใน proposal / ใช้คุยกับทีม dev ได้เลย** โดยผมปรับหัวข้อ **โภชนาการ** ให้เชื่อมกับ **โรคเรื้อรัง** และ **โรคที่สัมพันธ์กับพฤติกรรมการกิน** แล้ว

เอกสารนี้แบ่งเป็น 3 ส่วนตามที่ต้องการ:

1.  **Database Schema**

2.  **Agent Workflow**

3.  **Report Template**

**เอกสารออกแบบระบบ AI Agent สำหรับสร้างเอกสารแผนสุขภาพ**

**ขอบเขตหัวข้อ**

ระบบรองรับการสร้างเอกสารแผนสุขภาพ 3 ด้าน

-   **อุบัติเหตุ**: ความถี่, จุดเสี่ยง, เวลา, สภาพถนน, ปัจจัยเสี่ยงเชิงพื้นที่

-   **สุขภาพจิต**: อัตราการเข้ารับบริการ, suicide rate, การเข้าถึงบริการ, กลุ่มเสี่ยง

-   **โภชนาการและโรคที่เกี่ยวข้องกับการกิน**: BMI, consumption pattern, เบาหวาน, ความดันโลหิตสูง, ไขมันในเลือดสูง, โรคอ้วน, โรคไตเรื้อรัง, และโรคอื่นที่สัมพันธ์กับพฤติกรรมการบริโภค

**1) Database Schema**

**1.1 แนวคิดการออกแบบฐานข้อมูล**

แนะนำให้ใช้โครงแบบ **Hybrid Architecture**

-   **Operational / Raw Data** เก็บข้อมูลต้นทาง

-   **Analytic Mart** สำหรับ query เพื่อวิเคราะห์และทำรายงาน

-   **Document / RAG Metadata** สำหรับเอกสาร นโยบาย งานวิจัย คู่มือ และแหล่งอ้างอิง

เป้าหมายคือให้ AI Agent ไม่ query ข้อมูลดิบมั่ว ๆ แต่ใช้ **tool/API** ที่อิงกับ mart หรือ curated view เป็นหลัก

**1.2 Shared Core Schema**

ใช้ร่วมกันทุกโดเมน

**A. พื้นที่**

dim_geography (\
geography_id bigint primary key,\
country_code varchar(10),\
province_code varchar(20),\
province_name varchar(255),\
district_code varchar(20),\
district_name varchar(255),\
subdistrict_code varchar(20),\
subdistrict_name varchar(255),\
latitude decimal(10,6),\
longitude decimal(10,6)\
)

**B. เวลา**

dim_time (\
time_id bigint primary key,\
full_date date,\
day_of_week varchar(20),\
week_no int,\
month_no int,\
month_name varchar(20),\
quarter_no int,\
year_no int,\
hour_no int\
)

**C. กลุ่มประชากร**

dim_population_group (\
group_id bigint primary key,\
age_group varchar(100),\
sex varchar(20),\
occupation_group varchar(100),\
vulnerable_group varchar(255)\
)

**D. สถานพยาบาล / หน่วยบริการ**

dim_facility (\
facility_id bigint primary key,\
facility_code varchar(50),\
facility_name varchar(255),\
facility_type varchar(100),\
geography_id bigint,\
service_level varchar(100)\
)

**E. แหล่งข้อมูล**

dim_source (\
source_id bigint primary key,\
source_name varchar(255),\
source_type varchar(100),\
owner_org varchar(255),\
update_frequency varchar(50),\
quality_level varchar(50)\
)

**F. เอกสารสำหรับ RAG**

document_registry (\
document_id bigint primary key,\
title varchar(500),\
topic varchar(100),\
document_type varchar(100),\
source_id bigint,\
effective_date date,\
version_no varchar(50),\
status varchar(50),\
uploaded_at timestamp\
)

document_chunks (\
chunk_id bigint primary key,\
document_id bigint,\
chunk_order int,\
chunk_text text,\
keywords text,\
embedding_ref varchar(255),\
page_ref varchar(50)\
)

**G. ตัวชี้วัดกลาง**

indicator_catalog (\
indicator_id bigint primary key,\
topic varchar(100),\
indicator_code varchar(100),\
indicator_name varchar(255),\
definition text,\
unit_name varchar(100),\
preferred_chart varchar(100),\
report_section varchar(100)\
)

**1.3 Domain Schema: อุบัติเหตุ**

**ข้อมูลเหตุการณ์**

fact_accident_event (\
accident_id bigint primary key,\
event_datetime timestamp,\
geography_id bigint,\
road_segment_id bigint,\
weather_condition varchar(100),\
road_condition varchar(100),\
light_condition varchar(100),\
accident_type varchar(100),\
severity_level varchar(50),\
vehicle_type varchar(100),\
injured_count int,\
death_count int,\
source_id bigint\
)

**ข้อมูลผู้ประสบเหตุ**

fact_accident_person (\
person_event_id bigint primary key,\
accident_id bigint,\
age int,\
sex varchar(20),\
role_in_event varchar(100),\
injury_level varchar(100),\
helmet_used boolean,\
seatbelt_used boolean\
)

**ข้อมูลถนน**

dim_road_segment (\
road_segment_id bigint primary key,\
road_name varchar(255),\
road_type varchar(100),\
lane_count int,\
curvature_type varchar(100),\
slope_type varchar(100),\
speed_limit int,\
surface_type varchar(100),\
risk_flag boolean\
)

**Mart สำหรับรายงาน**

mart_accident_summary (\
year_no int,\
month_no int,\
geography_id bigint,\
accident_count int,\
injured_count int,\
death_count int,\
high_risk_timeband varchar(100),\
dominant_road_cond varchar(100)\
)

mart_accident_hotspot (\
hotspot_id bigint primary key,\
geography_id bigint,\
road_segment_id bigint,\
accident_count int,\
injured_count int,\
death_count int,\
hotspot_score decimal(10,2),\
dominant_timeband varchar(100)\
)

**1.4 Domain Schema: สุขภาพจิต**

**การเข้ารับบริการ**

fact_mental_health_visit (\
visit_id bigint primary key,\
visit_date date,\
facility_id bigint,\
geography_id bigint,\
group_id bigint,\
visit_type varchar(100),\
diagnosis_group varchar(100),\
referral_flag boolean,\
wait_time_days int,\
service_channel varchar(100),\
source_id bigint\
)

**ตัวชี้วัดการฆ่าตัวตาย**

fact_suicide_indicator (\
record_id bigint primary key,\
record_date date,\
geography_id bigint,\
age_group varchar(100),\
sex varchar(20),\
suicide_case_count int,\
population_base int,\
suicide_rate decimal(10,4),\
source_id bigint\
)

**ศักยภาพบริการ**

fact_mental_service_capacity (\
capacity_id bigint primary key,\
facility_id bigint,\
month_no int,\
year_no int,\
psychiatrist_count int,\
psychologist_count int,\
nurse_count int,\
service_slot_count int\
)

**Mart สำหรับรายงาน**

mart_mental_health_access (\
year_no int,\
month_no int,\
geography_id bigint,\
service_use_rate decimal(10,4),\
new_case_count int,\
repeat_case_count int,\
referral_rate decimal(10,4),\
avg_wait_time_days decimal(10,2)\
)

mart_mental_health_risk_gap (\
year_no int,\
month_no int,\
geography_id bigint,\
suicide_rate decimal(10,4),\
service_use_rate decimal(10,4),\
capacity_score decimal(10,2),\
care_gap_score decimal(10,2)\
)

**1.5 Domain Schema: โภชนาการ + โรคเรื้อรัง/โรคจากพฤติกรรมการกิน**

ตรงนี้ผมปรับใหม่ให้เชื่อม **พฤติกรรมการกิน → ภาวะโภชนาการ → โรคเรื้อรัง**

**กลุ่มโรค**

dim_disease (\
disease_id bigint primary key,\
disease_code varchar(50),\
disease_name varchar(255),\
disease_group varchar(100),\
diet_related_flag boolean,\
chronic_flag boolean\
)

ตัวอย่าง disease_group:

-   diabetes

-   hypertension

-   dyslipidemia

-   obesity

-   chronic_kidney_disease

-   cardiovascular_risk

-   metabolic_syndrome

**ข้อมูลประเมินโภชนาการ**

fact_nutrition_assessment (\
assessment_id bigint primary key,\
assessment_date date,\
geography_id bigint,\
facility_id bigint,\
group_id bigint,\
height_cm decimal(10,2),\
weight_kg decimal(10,2),\
bmi decimal(10,2),\
bmi_category varchar(50),\
waist_cm decimal(10,2),\
source_id bigint\
)

**ข้อมูลพฤติกรรมการบริโภค**

fact_food_consumption (\
consumption_id bigint primary key,\
survey_date date,\
geography_id bigint,\
group_id bigint,\
meal_frequency decimal(10,2),\
fruit_intake_freq decimal(10,2),\
vegetable_intake_freq decimal(10,2),\
sugary_drink_freq decimal(10,2),\
fast_food_freq decimal(10,2),\
processed_food_freq decimal(10,2),\
snack_freq decimal(10,2),\
sodium_risk_flag boolean,\
sugar_risk_flag boolean,\
fat_risk_flag boolean,\
source_id bigint\
)

**ข้อมูลโรคเรื้อรัง**

fact_chronic_disease_case (\
disease_case_id bigint primary key,\
record_date date,\
geography_id bigint,\
facility_id bigint,\
group_id bigint,\
disease_id bigint,\
case_count int,\
prevalence_rate decimal(10,4),\
incidence_rate decimal(10,4),\
admission_count int,\
source_id bigint\
)

**ข้อมูลผลตรวจสุขภาพเชิงคลินิก**

fact_clinical_risk_profile (\
risk_profile_id bigint primary key,\
record_date date,\
geography_id bigint,\
facility_id bigint,\
group_id bigint,\
fasting_blood_sugar decimal(10,2),\
hba1c decimal(10,2),\
systolic_bp decimal(10,2),\
diastolic_bp decimal(10,2),\
total_cholesterol decimal(10,2),\
ldl decimal(10,2),\
hdl decimal(10,2),\
triglyceride decimal(10,2),\
egfr decimal(10,2),\
source_id bigint\
)

**โครงการ/มาตรการ**

fact_nutrition_intervention (\
intervention_id bigint primary key,\
geography_id bigint,\
target_group varchar(255),\
intervention_type varchar(255),\
start_date date,\
end_date date,\
coverage_rate decimal(10,2),\
owner_org varchar(255)\
)

**Mart สำหรับรายงาน**

mart_nutrition_status (\
year_no int,\
month_no int,\
geography_id bigint,\
avg_bmi decimal(10,2),\
underweight_pct decimal(10,2),\
normal_pct decimal(10,2),\
overweight_pct decimal(10,2),\
obesity_pct decimal(10,2)\
)

mart_consumption_risk (\
year_no int,\
month_no int,\
geography_id bigint,\
low_vegfruit_pct decimal(10,2),\
high_sugar_pct decimal(10,2),\
high_sodium_pct decimal(10,2),\
high_fastfood_pct decimal(10,2),\
unhealthy_diet_score decimal(10,2)\
)

mart_diet_related_disease_summary (\
year_no int,\
month_no int,\
geography_id bigint,\
diabetes_rate decimal(10,4),\
hypertension_rate decimal(10,4),\
dyslipidemia_rate decimal(10,4),\
obesity_rate decimal(10,4),\
ckd_rate decimal(10,4),\
metabolic_risk_score decimal(10,2)\
)

mart_nutrition_disease_link (\
year_no int,\
month_no int,\
geography_id bigint,\
unhealthy_diet_score decimal(10,2),\
avg_bmi decimal(10,2),\
diabetes_rate decimal(10,4),\
hypertension_rate decimal(10,4),\
diet_disease_risk_score decimal(10,2)\
)

**สิ่งที่ระบบตอบได้จาก schema นี้**

-   พื้นที่ที่มี BMI สูงและเบาหวานสูงร่วมกัน

-   กลุ่มที่มีพฤติกรรมกินเสี่ยงสูง

-   ความสัมพันธ์เชิงแนวโน้มระหว่าง consumption pattern กับโรคเรื้อรัง

-   พื้นที่ที่ควรเร่งมาตรการลดหวาน มัน เค็ม

**1.6 Tool/API Layer ที่ Agent ควรเรียก**

ไม่ควรให้ agent ยิง SQL ตรง ควรมี API ชัดเจน

**Common Tools**

search_documents(topic, keywords, time_range)\
get_indicator_catalog(topic)\
get_report_template(report_type)\
get_geography_profile(geography_id)

**Accident Tools**

get_accident_summary(start_date, end_date, geography)\
get_accident_hotspots(start_date, end_date, geography)\
get_accident_time_distribution(start_date, end_date, geography)\
get_road_condition_risk(start_date, end_date, geography)

**Mental Health Tools**

get_mental_service_utilization(start_date, end_date, geography)\
get_suicide_rate(start_date, end_date, geography)\
get_service_capacity_gap(start_date, end_date, geography)\
get_mental_risk_groups(start_date, end_date, geography)

**Nutrition Tools**

get_bmi_distribution(start_date, end_date, geography, age_group)\
get_consumption_pattern(start_date, end_date, geography, target_group)\
get_diet_related_disease_summary(start_date, end_date, geography)\
get_nutrition_disease_link(start_date, end_date, geography)\
get_high_risk_nutrition_groups(start_date, end_date, geography)

**Reporting Tools**

generate_chart(chart_spec)\
generate_table(table_spec)\
render_report_preview(report_payload)\
export_docx(report_payload)

**2) Agent Workflow**

**2.1 Agent Architecture**

แนะนำแบบ **1 Orchestrator + 6 Specialist Agents**

1.  **Request Interpreter Agent**

2.  **Planner Agent**

3.  **Retrieval Agent**

4.  **Domain Analyst Agent**

5.  **Chart & Table Agent**

6.  **Report Writer Agent**

7.  **Review & Compliance Agent**

ถ้าต้องการลดความซับซ้อนช่วงแรก สามารถรวมข้อ 1 และ 2 เป็นตัวเดียวได้

**2.2 บทบาทของแต่ละ Agent**

**1. Request Interpreter Agent**

หน้าที่:

-   อ่านคำขอผู้ใช้

-   แยกว่าเป็นหัวข้อใด

-   สกัด parameter เช่น ช่วงเวลา พื้นที่ กลุ่มประชากร ประเภทรายงาน

ตัวอย่าง output:

{\
\"topics\": \[\"nutrition\"\],\
\"geography\": \"จังหวัด A\",\
\"time_range\": \"2025-01 ถึง 2025-12\",\
\"report_type\": \"แผนสุขภาพระดับจังหวัด\",\
\"focus\": \[\"BMI\", \"consumption pattern\", \"เบาหวาน\", \"ความดันโลหิตสูง\"\]\
}

**2. Planner Agent**

หน้าที่:

-   แปลงคำขอเป็นโครงร่างรายงาน

-   กำหนดว่าแต่ละ section ต้องใช้ข้อมูลอะไร

-   สั่งงาน retrieval และ analysis ตามลำดับ

ตัวอย่าง output:

{\
\"outline\": \[\
\"บทสรุปผู้บริหาร\",\
\"สถานการณ์ปัจจุบัน\",\
\"ตัวชี้วัดสำคัญ\",\
\"การวิเคราะห์เชิงพื้นที่\",\
\"ปัจจัยเสี่ยง\",\
\"ข้อเสนอเชิงมาตรการ\"\
\],\
\"required_data\": \[\
\"mart_nutrition_status\",\
\"mart_consumption_risk\",\
\"mart_diet_related_disease_summary\",\
\"policy_docs\"\
\]\
}

**3. Retrieval Agent**

หน้าที่:

-   ดึงข้อมูลจาก Document RAG

-   ดึงข้อมูลจาก mart/API

-   คืนค่าเป็น evidence package พร้อม metadata

output:

{\
\"facts\": \[\],\
\"indicators\": \[\],\
\"citations\": \[\],\
\"data_frames\": \[\]\
}

กฎ:

-   ถ้าไม่มีข้อมูลเชิงปริมาณ ห้ามสร้างข้อสรุปเชิงยืนยัน

-   ถ้ามีข้อมูลหลายแหล่งขัดกัน ให้ติด flag ส่ง review

**4. Domain Analyst Agent**

มี 3 ตัวตามหัวข้อ

**4.1 Accident Analyst**

วิเคราะห์:

-   แนวโน้มความถี่

-   จุดเสี่ยง

-   เวลาเสี่ยง

-   ความสัมพันธ์กับสภาพถนน

**4.2 Mental Health Analyst**

วิเคราะห์:

-   การเข้าถึงบริการ

-   suicide rate

-   service gap

-   กลุ่มเสี่ยง

**4.3 Nutrition & Chronic Disease Analyst**

วิเคราะห์:

-   BMI distribution

-   consumption pattern

-   กลุ่มเสี่ยงด้านการกิน

-   แนวโน้มเบาหวาน/ความดัน/ไขมัน/โรคอ้วน/โรคไต

-   ความเชื่อมโยงระหว่างพฤติกรรมกินกับภาระโรค

output กลาง:

{\
\"key_findings\": \[\],\
\"risk_groups\": \[\],\
\"priority_areas\": \[\],\
\"recommended_actions\": \[\],\
\"chart_candidates\": \[\],\
\"table_candidates\": \[\]\
}

**5. Chart & Table Agent**

หน้าที่:

-   เลือกชนิดกราฟและตารางที่เหมาะสม

-   สร้าง spec ให้ frontend / reporting engine

logic ตัวอย่าง:

-   แนวโน้มรายเดือน → line chart

-   เปรียบเทียบหลายพื้นที่ → bar chart

-   BMI category → stacked bar

-   disease burden by area → ranked bar

-   consumption pattern → grouped bar / score table

-   hotspot accidents → map layer / ranked table

output:

{\
\"charts\": \[\
{\
\"chart_type\": \"line\",\
\"title\": \"แนวโน้มอัตราเบาหวาน\",\
\"x\": \"month\",\
\"y\": \"diabetes_rate\"\
}\
\],\
\"tables\": \[\
{\
\"table_name\": \"พื้นที่เสี่ยงสูง\",\
\"columns\": \[\"พื้นที่\", \"คะแนนความเสี่ยง\", \"ปัจจัยหลัก\"\]\
}\
\]\
}

**6. Report Writer Agent**

หน้าที่:

-   เขียนเนื้อหาแบบภาษาทางการ

-   เรียบเรียงจาก evidence และ analysis

-   สรุปให้เหมาะกับแผนสุขภาพหรือรายงานเชิงบริหาร

ข้อกำหนด:

-   ต้องอ้างอิง evidence ทุกข้อสรุปสำคัญ

-   ต้องแยก "ข้อเท็จจริง" กับ "ข้อเสนอเชิงนโยบาย"

-   ต้องเขียนตาม template ที่กำหนด

**7. Review & Compliance Agent**

หน้าที่:

-   ตรวจความครบถ้วน

-   ตรวจความสมเหตุสมผลของตัวเลข

-   ตรวจว่าใช้ indicator ถูกหัวข้อ

-   ตรวจว่าไม่มีการสรุปเกินหลักฐาน

-   ตรวจ policy ด้านเนื้อหาสุขภาพ โดยเฉพาะสุขภาพจิต

ผลลัพธ์:

{\
\"status\": \"approved \| revision_required\",\
\"issues\": \[\],\
\"missing_sections\": \[\],\
\"citation_gaps\": \[\]\
}

**2.3 Workflow ตั้งแต่รับคำขอถึง DOCX**

ลำดับแนะนำ

**Step 1 รับคำขอ**

ผู้ใช้ระบุหัวข้อ เช่น\
"สร้างแผนสุขภาพด้านโภชนาการและโรคเรื้อรังของจังหวัด X ช่วงปี 2025"

**Step 2 ตีความโจทย์**

Request Interpreter แยกหัวข้อ พื้นที่ ช่วงเวลา และรูปแบบเอกสาร

**Step 3 วางแผนรายงาน**

Planner กำหนด outline และรายการข้อมูลที่ต้องใช้

**Step 4 ดึงข้อมูล**

Retrieval Agent เรียก

-   document RAG

-   database mart

-   indicator catalog

**Step 5 วิเคราะห์รายหัวข้อ**

Domain Analyst สังเคราะห์ประเด็นสำคัญ

**Step 6 สร้างตารางและกราฟ**

Chart & Table Agent สร้าง spec

**Step 7 เขียนรายงาน**

Report Writer รวมข้อมูลเป็นร่างเอกสาร

**Step 8 ตรวจคุณภาพ**

Review & Compliance ตรวจเนื้อหา ตัวเลข และ citation

**Step 9 สร้างผลลัพธ์**

-   preview บนเว็บ

-   export เป็น DOCX

**2.4 Output Schema กลาง**

ใช้ schema กลางตัวเดียว แล้วค่อย render เป็น web/docx

{\
\"document_title\": \"\",\
\"report_type\": \"\",\
\"topic_list\": \[\],\
\"time_range\": \"\",\
\"geography\": \"\",\
\"executive_summary\": \"\",\
\"sections\": \[\
{\
\"section_title\": \"\",\
\"section_text\": \"\",\
\"tables\": \[\],\
\"charts\": \[\],\
\"citations\": \[\]\
}\
\],\
\"recommendations\": \[\],\
\"references\": \[\],\
\"appendix\": \[\]\
}

**3) Report Template**

ด้านล่างคือ template พร้อมใช้สำหรับ proposal และสำหรับกำหนด output ของระบบ

**3.1 Template กลางของเอกสารแผนสุขภาพ**

**หน้าปก**

-   ชื่อเอกสาร

-   พื้นที่

-   ช่วงเวลา

-   หน่วยงาน

-   วันที่สร้างเอกสาร

**1. บทสรุปผู้บริหาร**

สรุปสาระสำคัญ

-   สถานการณ์เด่น

-   พื้นที่/กลุ่มเสี่ยง

-   ประเด็นเร่งด่วน

-   ข้อเสนอหลัก

**2. วัตถุประสงค์ของแผน**

-   เหตุผลในการจัดทำ

-   เป้าหมายของแผน

-   ขอบเขตข้อมูลที่ใช้

**3. แหล่งข้อมูลและวิธีวิเคราะห์**

-   แหล่งข้อมูลเอกสาร

-   แหล่งข้อมูลฐานข้อมูล

-   ช่วงเวลาข้อมูล

-   ข้อจำกัดของข้อมูล

-   วิธีวิเคราะห์โดยสรุป

**4. สถานการณ์ปัจจุบัน**

-   ภาพรวมตัวชี้วัดสำคัญ

-   แนวโน้มย้อนหลัง

-   เปรียบเทียบเชิงพื้นที่

-   ตารางและกราฟประกอบ

**5. การวิเคราะห์เชิงลึก**

-   วิเคราะห์ตามหัวข้อหลัก

-   จุดเสี่ยง / กลุ่มเสี่ยง / ปัจจัยสำคัญ

-   ความเชื่อมโยงของข้อมูล

-   หลักฐานสนับสนุน

**6. ประเด็นปัญหาและช่องว่าง**

-   ช่องว่างของข้อมูล

-   ช่องว่างของบริการ

-   ช่องว่างของมาตรการ

-   ประเด็นที่ควรติดตาม

**7. ข้อเสนอเชิงมาตรการ**

-   มาตรการระยะสั้น

-   มาตรการระยะกลาง

-   มาตรการระยะยาว

-   หน่วยงานหลัก/หน่วยงานร่วม

**8. แผนดำเนินงาน**

-   กิจกรรม

-   กลุ่มเป้าหมาย

-   พื้นที่เป้าหมาย

-   ระยะเวลา

-   ตัวชี้วัดผลสำเร็จ

**9. ตัวชี้วัดติดตามผล**

-   ตัวชี้วัดผลลัพธ์

-   ตัวชี้วัดกระบวนการ

-   ความถี่ในการติดตาม

**10. ภาคผนวก**

-   ตารางสรุป

-   กราฟ

-   รายละเอียดตัวชี้วัด

-   เอกสารอ้างอิง

**3.2 Template เฉพาะ: อุบัติเหตุ**

**หัวข้อย่อยที่ควรมี**

-   ภาพรวมสถานการณ์อุบัติเหตุ

-   ความถี่การเกิดเหตุ

-   จุดเสี่ยงสูงสุด

-   ช่วงเวลาเสี่ยง

-   ความสัมพันธ์กับสภาพถนน/สภาพแวดล้อม

-   กลุ่มผู้ประสบเหตุสำคัญ

-   ข้อเสนอป้องกันเชิงพื้นที่

**กราฟ/ตารางที่ควรมี**

-   กราฟแนวโน้มจำนวนอุบัติเหตุรายเดือน

-   ตาราง 10 จุดเสี่ยงสูงสุด

-   กราฟช่วงเวลาเกิดเหตุ

-   ตารางสภาพถนนที่สัมพันธ์กับเหตุรุนแรง

**3.3 Template เฉพาะ: สุขภาพจิต**

**หัวข้อย่อยที่ควรมี**

-   ภาพรวมการเข้ารับบริการ

-   แนวโน้ม service utilization

-   suicide rate รายพื้นที่/รายช่วงเวลา

-   พื้นที่ที่มี service gap

-   กลุ่มเสี่ยงและกลุ่มเปราะบาง

-   ข้อเสนอพัฒนาระบบบริการและการเฝ้าระวัง

**กราฟ/ตารางที่ควรมี**

-   กราฟแนวโน้มอัตราการเข้ารับบริการ

-   กราฟเปรียบเทียบ suicide rate รายพื้นที่

-   ตารางช่องว่างระหว่างความต้องการกับศักยภาพบริการ

-   ตารางกลุ่มเสี่ยงสำคัญ

**3.4 Template เฉพาะ: โภชนาการ + โรคเรื้อรัง**

**หัวข้อย่อยที่ควรมี**

-   ภาพรวมภาวะโภชนาการ

-   BMI และการกระจายของกลุ่มน้ำหนัก

-   consumption pattern และพฤติกรรมการกินเสี่ยง

-   สถานการณ์โรคเรื้อรังที่เกี่ยวข้องกับการบริโภค

-   การเชื่อมโยงระหว่างพฤติกรรมกินกับภาระโรค

-   พื้นที่เสี่ยง / กลุ่มเสี่ยง / กลุ่มเป้าหมาย

-   ข้อเสนอส่งเสริมโภชนาการและลดโรคเรื้อรัง

**ตัวอย่างโรคที่เน้นในรายงาน**

-   เบาหวาน

-   ความดันโลหิตสูง

-   ไขมันในเลือดสูง

-   โรคอ้วน

-   โรคไตเรื้อรัง

-   ความเสี่ยงโรคหัวใจและหลอดเลือด

**กราฟ/ตารางที่ควรมี**

-   stacked bar: BMI category

-   line chart: แนวโน้มอัตราเบาหวาน/ความดัน

-   grouped bar: รูปแบบการบริโภคในแต่ละพื้นที่

-   table: กลุ่มเสี่ยงด้านพฤติกรรมกิน

-   matrix table: พื้นที่ที่มี unhealthy diet สูง + burden disease สูง

**3.5 โครงสร้างข้อความที่ Report Writer ควรเขียน**

เพื่อให้เอกสารสม่ำเสมอ ควรมี pattern การเขียนแบบนี้

**Pattern 1: รายงานสถานการณ์**

"จากข้อมูลช่วง \[เวลา\] พบว่า \[ตัวชี้วัดหลัก\] มีแนวโน้ม \[เพิ่มขึ้น/ลดลง/ทรงตัว\] โดยพื้นที่ที่มีค่าความเสี่ยงสูง ได้แก่ \[พื้นที่\] และกลุ่มที่ได้รับผลกระทบสำคัญคือ \[กลุ่ม\]"

**Pattern 2: รายงานความเชื่อมโยง**

"เมื่อพิจารณาร่วมกับข้อมูล \[แหล่งข้อมูล\] พบความสัมพันธ์เชิงแนวโน้มระหว่าง \[ปัจจัย\] กับ \[ผลลัพธ์\] ซึ่งสะท้อนถึงความจำเป็นในการดำเนินมาตรการ \[มาตรการ\]"

**Pattern 3: รายงานข้อเสนอ**

"ข้อเสนอสำคัญในระยะ \[สั้น/กลาง/ยาว\] คือ \[มาตรการ\] โดยควรให้ความสำคัญกับพื้นที่ \[พื้นที่\] และกลุ่มเป้าหมาย \[กลุ่ม\] เป็นลำดับแรก"

**3.6 Deliverables ที่ใส่ใน Proposal ได้เลย**

ระบบควรส่งมอบผลลัพธ์อย่างน้อยดังนี้

-   ระบบค้นข้อมูลจาก Document RAG และ Database RAG

-   ระบบ AI Agent สำหรับวิเคราะห์ 3 หัวข้อสุขภาพ

-   ระบบสร้างตารางและกราฟอัตโนมัติ

-   ระบบสร้างรายงาน preview บนเว็บ

-   ระบบ export รายงานเป็น DOCX

-   ระบบเก็บประวัติรายงานและแหล่งอ้างอิง

-   ชุด template รายงานอย่างน้อย 3 แบบตามโดเมน

**3.7 ข้อเสนอเชิงพัฒนา**

ถ้าจะเริ่มทำจริงให้คุมงานง่าย แนะนำลำดับนี้

**Phase 1**

-   ทำ schema กลาง

-   ทำ accident + report engine ก่อน

**Phase 2**

-   เพิ่ม mental health

-   เพิ่ม review/compliance ที่เข้มขึ้น

**Phase 3**

-   เพิ่ม nutrition + chronic disease linkage

-   เพิ่ม comparative report ข้ามโดเมน

ถ้าต้องการ ผมจัดต่อให้เป็น **เอกสาร Proposal ฉบับสมบูรณ์** ในรูปแบบทางการ มีหัวข้อ\
**บทนำ / วัตถุประสงค์ / ขอบเขต / สถาปัตยกรรมระบบ / roadmap / deliverables / งวดงาน** ได้ทันทีครับ

เพิ่ม Agent การทำ Citation เเหล่งข้อมูล ซึ่งเกี่ยวข้องกับ การค้นข้อมูลเเละทำรายงาน

Thought for 5s

ได้ครับ ควรเพิ่ม **Citation Agent** เป็น agent เฉพาะอีก 1 ตัว เพราะงานนี้มีทั้ง **ค้นข้อมูลจาก RAG/ฐานข้อมูล** และ **สร้างรายงานทางสุขภาพ** ซึ่งต้องระบุที่มาของข้อมูลให้ตรวจสอบย้อนกลับได้

ด้านล่างคือฉบับปรับเพิ่มให้เอาไปคุยกับทีม dev ได้เลย

**เพิ่ม Agent: Citation & Evidence Agent**

**บทบาท**

Citation & Evidence Agent ทำหน้าที่จัดการ **แหล่งอ้างอิง, หลักฐาน, การเชื่อมโยง citation กับข้อความในรายงาน** และตรวจสอบว่าเนื้อหาทุกข้อสรุปสำคัญมีที่มารองรับ

Agent นี้อยู่กึ่งกลางระหว่าง

-   **Retrieval Agent** ที่ค้นข้อมูล

-   **Report Writer Agent** ที่เขียนรายงาน

-   **Review & Compliance Agent** ที่ตรวจความครบถ้วน

ดังนั้นมันไม่ใช่แค่ "ใส่อ้างอิงท้ายรายงาน" แต่เป็นตัวควบคุม **evidence traceability** ตลอด flow

**1) เพิ่มส่วนใน Agent Architecture**

จากเดิม

1.  Request Interpreter Agent

2.  Planner Agent

3.  Retrieval Agent

4.  Domain Analyst Agent

5.  Chart & Table Agent

6.  Report Writer Agent

7.  Review & Compliance Agent

ให้ปรับเป็น

1.  Request Interpreter Agent

2.  Planner Agent

3.  Retrieval Agent

4.  **Citation & Evidence Agent**

5.  Domain Analyst Agent

6.  Chart & Table Agent

7.  Report Writer Agent

8.  Review & Compliance Agent

**2) หน้าที่ของ Citation & Evidence Agent**

**2.1 หน้าที่หลัก**

1.  รับผลลัพธ์จาก Retrieval Agent

2.  แปลงข้อมูลที่ค้นมาให้อยู่ในรูป **evidence package**

3.  สร้าง citation ID สำหรับแต่ละข้อเท็จจริง

4.  เชื่อมโยงข้อความในรายงานกับแหล่งข้อมูลต้นทาง

5.  แยกประเภทแหล่งข้อมูล เช่น เอกสาร, ตารางฐานข้อมูล, policy, statistical source

6.  ตรวจว่าข้อสรุปใด "มีหลักฐานรองรับ" หรือ "ยังไม่มีหลักฐานพอ"

7.  สร้าง reference list สำหรับท้ายรายงาน

8.  ส่งข้อมูลให้ Review Agent ตรวจต่อ

**2.2 สิ่งที่ต้องรองรับ**

Citation Agent ต้องรองรับแหล่งข้อมูล 2 กลุ่มหลัก

**A. Document Citation**

เช่น

-   นโยบาย

-   คู่มือ

-   งานวิจัย

-   รายงานวิชาการ

-   เอกสาร PDF / DOCX

ตัวอย่างข้อมูลที่ต้องเก็บ

-   document title

-   section / heading

-   page number

-   paragraph / chunk

-   source organization

-   publication date

-   document version

**B. Database Citation**

เช่น

-   ตารางสถิติอุบัติเหตุ

-   ตารางอัตราเข้ารับบริการสุขภาพจิต

-   ตาราง BMI / chronic disease summary

ตัวอย่างข้อมูลที่ต้องเก็บ

-   database/table name

-   query tool name

-   parameter ที่ใช้ query

-   time range

-   geography filter

-   extraction timestamp

-   source owner

**3) เพิ่ม Database Schema สำหรับ Citation**

ควรเพิ่ม schema กลางสำหรับ evidence และ citation โดยเฉพาะ

**3.1 ตารางหลักฐาน**

evidence_registry (\
evidence_id bigint primary key,\
evidence_type varchar(50), \-- document \| database \| api\
topic varchar(100),\
source_id bigint,\
source_ref varchar(255), \-- document_id หรือ table/view name\
title varchar(500),\
section_label varchar(255),\
page_ref varchar(50),\
chunk_id bigint,\
query_signature text,\
geography_id bigint,\
start_date date,\
end_date date,\
extracted_at timestamp,\
extracted_by_agent varchar(100),\
trust_level varchar(50),\
note text\
)

**3.2 ตาราง citation ต่อรายงาน**

report_citation (\
citation_id bigint primary key,\
report_id bigint,\
evidence_id bigint,\
citation_code varchar(50), \-- เช่น C-001, C-002\
citation_type varchar(50), \-- inline \| table \| chart \| appendix\
citation_text text,\
bibliography_text text,\
created_at timestamp\
)

**3.3 ตารางเชื่อม citation กับ section**

report_section_citation (\
section_citation_id bigint primary key,\
report_id bigint,\
section_id bigint,\
citation_id bigint,\
linked_text_snippet text,\
claim_type varchar(100), \-- finding \| statistic \| recommendation_basis\
evidence_strength varchar(50) \-- high \| medium \| low\
)

**3.4 ตารางเชื่อม citation กับกราฟ/ตาราง**

report_object_citation (\
object_citation_id bigint primary key,\
report_id bigint,\
object_type varchar(50), \-- chart \| table\
object_id varchar(100),\
citation_id bigint,\
note text\
)

**4) ปรับ Tool/API Layer ให้รองรับ Citation**

ควรเพิ่ม tools สำหรับ Citation Agent โดยเฉพาะ

**4.1 Citation Tools**

build_document_evidence(document_id, chunk_id)\
build_database_evidence(table_name, query_params, extract_time)\
generate_citation_code(report_id)\
link_citation_to_section(report_id, section_id, evidence_id, claim_type)\
link_citation_to_chart(report_id, chart_id, evidence_id)\
link_citation_to_table(report_id, table_id, evidence_id)\
compile_reference_list(report_id)\
validate_citation_coverage(report_id)

**4.2 Retrieval Tools ที่ต้องส่ง metadata มากขึ้น**

จากเดิม Retrieval Agent ไม่ควรส่งแค่ data หรือ facts แต่ต้องส่ง

-   source

-   section/page/chunk

-   query condition

-   time range

-   extraction timestamp

-   confidence/trust level

ตัวอย่าง output จาก retrieval:

{\
\"fact\": \"อัตราการเข้ารับบริการสุขภาพจิตเพิ่มขึ้นในปี 2025\",\
\"value\": 12.4,\
\"unit\": \"ต่อประชากร 1,000 คน\",\
\"source_type\": \"database\",\
\"source_ref\": \"mart_mental_health_access\",\
\"query_params\": {\
\"geography\": \"จังหวัด A\",\
\"year\": 2025\
},\
\"extracted_at\": \"2026-04-06T10:00:00\"\
}

**5) ปรับ Workflow ให้มี Citation Flow**

**Workflow ใหม่**

**Step 1 รับคำขอ**

ผู้ใช้ระบุหัวข้อ พื้นที่ ช่วงเวลา และรูปแบบรายงาน

**Step 2 ตีความโจทย์**

Request Interpreter แยกหัวข้อและ parameter

**Step 3 วางแผนรายงาน**

Planner กำหนด outline และข้อมูลที่ต้องใช้

**Step 4 ค้นข้อมูล**

Retrieval Agent ดึงข้อมูลจาก

-   Document RAG

-   Database mart

-   Policy/reference docs

**Step 5 สร้างหลักฐานอ้างอิง**

**Citation & Evidence Agent**

-   รับผล retrieval

-   ลงทะเบียน evidence

-   สร้าง citation code

-   ผูก fact แต่ละรายการกับแหล่งข้อมูล

**Step 6 วิเคราะห์**

Domain Analyst ใช้เฉพาะข้อมูลที่มี evidence รองรับ

**Step 7 สร้างตารางและกราฟ**

Chart & Table Agent สร้าง spec และแนบ citation ให้แต่ละ chart/table

**Step 8 เขียนรายงาน**

Report Writer เขียนรายงานพร้อม inline citation หรือ section citation

**Step 9 ตรวจคุณภาพ**

Review & Compliance Agent ตรวจว่า

-   ทุกข้อสรุปสำคัญมี citation

-   ทุก chart/table มี source

-   references ท้ายรายงานครบ

**Step 10 ส่งออกผลลัพธ์**

-   preview บนเว็บ

-   export DOCX พร้อม references

**6) Output ของ Citation & Evidence Agent**

ควรมี schema กลางแบบนี้

{\
\"evidences\": \[\
{\
\"evidence_id\": \"EV-001\",\
\"source_type\": \"document\",\
\"title\": \"รายงานสถานการณ์สุขภาพจังหวัด\",\
\"page_ref\": \"12\",\
\"chunk_ref\": \"CH-145\",\
\"claim_supported\": \[\
\"พื้นที่ A มีอัตราอุบัติเหตุสูง\"\
\],\
\"trust_level\": \"high\"\
},\
{\
\"evidence_id\": \"EV-002\",\
\"source_type\": \"database\",\
\"source_ref\": \"mart_accident_hotspot\",\
\"query_params\": {\
\"province\": \"A\",\
\"year\": 2025\
},\
\"claim_supported\": \[\
\"จุดเสี่ยงหลักอยู่บนถนนสาย X\"\
\],\
\"trust_level\": \"high\"\
}\
\],\
\"citations\": \[\
{\
\"citation_code\": \"C-001\",\
\"evidence_id\": \"EV-001\",\
\"citation_text\": \"รายงานสถานการณ์สุขภาพจังหวัด, หน้า 12\"\
},\
{\
\"citation_code\": \"C-002\",\
\"evidence_id\": \"EV-002\",\
\"citation_text\": \"ฐานข้อมูล mart_accident_hotspot, จังหวัด A, ปี 2025\"\
}\
\]\
}

**7) ปรับ Output Schema กลางของรายงาน**

จากเดิม report payload ให้เพิ่ม citation field ในแต่ละ section

{\
\"document_title\": \"\",\
\"report_type\": \"\",\
\"topic_list\": \[\],\
\"time_range\": \"\",\
\"geography\": \"\",\
\"executive_summary\": \"\",\
\"sections\": \[\
{\
\"section_title\": \"\",\
\"section_text\": \"\",\
\"tables\": \[\],\
\"charts\": \[\],\
\"citations\": \[\]\
}\
\],\
\"recommendations\": \[\],\
\"references\": \[\]\
}

**กติกา**

-   section_text ต้องผูกกับ citation อย่างน้อย 1 แหล่ง หากมีข้อเท็จจริงเชิงยืนยัน

-   tables และ charts ต้องมี source note ทุกชิ้น

-   references เป็นรายการรวมท้ายรายงาน

**8) ปรับ Report Template ให้รองรับ Citation**

**8.1 ในเนื้อหารายงาน**

แต่ละ section ควรมีการอ้างอิงแบบใดแบบหนึ่ง

-   inline citation

-   footnote citation

-   source note ใต้กราฟ/ตาราง

ตัวอย่าง

-   "จากข้อมูลปี 2025 พบว่าอัตราเบาหวานมีแนวโน้มเพิ่มขึ้นใน 3 อำเภอหลัก \[C-014\]"

-   "พื้นที่เสี่ยงอุบัติเหตุสูงสุดคือเขต X \[C-002\]\[C-005\]"

**8.2 ใต้ตาราง/กราฟ**

ตัวอย่าง

-   แหล่งข้อมูล: mart_nutrition_status, จังหวัด A, ปี 2025 \[C-031\]

-   แหล่งข้อมูล: รายงานสำรวจพฤติกรรมการบริโภค 2025, หน้า 18 \[C-044\]

**8.3 ท้ายรายงาน**

เพิ่มหัวข้อ

**เอกสารอ้างอิง / References**

รวบรวม bibliography ทั้งหมดจาก Citation Agent โดยจัดรูปแบบมาตรฐานเดียวกัน

**9) กฎที่ทีม dev ควรใช้**

**กฎสำคัญ**

1.  ข้อสรุปเชิงตัวเลขทุกข้อ ต้องมี citation

2.  ตารางทุกตาราง ต้องมี source note

3.  กราฟทุกกราฟ ต้องมี source note

4.  ข้อเสนอเชิงนโยบาย ควรผูกกับ evidence ที่รองรับ

5.  ถ้า retrieval ไม่พบหลักฐานพอ ระบบต้อง flag ว่า "insufficient evidence"

6.  ถ้ามีข้อมูลขัดกันหลายแหล่ง Citation Agent ต้องเก็บครบและส่งให้ Review Agent ตัดสิน

**10) ประโยชน์ของการเพิ่ม Citation Agent**

การเพิ่ม agent นี้จะช่วยให้ระบบ:

-   ตรวจสอบย้อนกลับได้

-   ลด hallucination ในรายงาน

-   แยก "ข้อเท็จจริง" ออกจาก "การตีความ"

-   รองรับงาน proposal / policy / รายงานสุขภาพที่ต้องมีความน่าเชื่อถือ

-   ทำ DOCX และ web preview ที่มี references ครบ
