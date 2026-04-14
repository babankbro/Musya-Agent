# Quick Start: Citation & Evidence Agent Testing

## 🚀 Fast Track (5 Minutes)

### Step 1: Run Setup Verification (2 min)

```powershell
# From Agent directory
python scripts/test_citation_setup.py
```

**Expected:** All tests pass ✅

### Step 2: Upload Sample Documents (1 min)

```powershell
python scripts/prepare_sample_documents.py
```

**Expected:** 4 documents uploaded to MinIO

### Step 3: Start Server (1 min)

```powershell
python -m uvicorn src.main:app --reload --port 8000
```

**Expected:** Server running on http://localhost:8000

### Step 4: Ingest Documents (30 sec)

```powershell
# In another terminal
curl -X POST http://localhost:8000/api/ingest
```

**Expected:** Returns chunk count

### Step 5: Open Test UI (30 sec)

Open browser: **http://localhost:8000/static/citation_test_ui.html**

---

## 🧪 Quick Tests

### Test 1: Basic Chat with Citations

1. Go to **💬 Chat Test** tab
2. Enter: `สถิติอุบัติเหตุจังหวัดเชียงใหม่ปี 2025`
3. Click **Send to Agent Pipeline**

**Verify:**
- ✅ Citations appear (C-001, C-002, etc.)
- ✅ Evidence count > 0
- ✅ Coverage score > 0

### Test 2: Evidence API

1. Copy an `evidence_id` from chat response
2. Go to **📚 Evidence API** tab
3. Paste evidence ID and click **Get Evidence**

**Verify:**
- ✅ Returns evidence details
- ✅ Has `open_url` link
- ✅ Trust level shown

### Test 3: Document Opening

1. From evidence details, note document ID
2. Enter document ID in **Open Document** section
3. Click **Open Document**

**Verify:**
- ✅ Document opens in new tab

---

## 📊 What You Should See

### Chat Response Structure

```json
{
  "content": "...",
  "citations": [
    {
      "citation_code": "C-001",
      "source_ref": "road_safety_policy_2025.txt",
      "citation_text": "นโยบายความปลอดภัยทางถนน พ.ศ. 2568, หน้า 4",
      "evidence_id": "EV-001",
      "open_url": "/api/documents/open/1?page=4"
    }
  ],
  "metadata": {
    "agent_count": 7,
    "total_evidence": 5,
    "coverage_score": 0.85,
    "pipeline": "phase1_accident_with_citation"
  }
}
```

### Evidence Item

```json
{
  "evidence_id": "EV-001",
  "evidence_type": "document",
  "source_ref": "road_safety_policy_2025.txt",
  "title": "นโยบายความปลอดภัยทางถนน พ.ศ. 2568",
  "page_ref": "4",
  "section_label": "มาตรา 2.2",
  "trust_level": "high",
  "open_url": "/api/documents/open/1?page=4"
}
```

---

## 🔧 Troubleshooting

### Server won't start
```powershell
# Check if port 8000 is in use
netstat -ano | findstr :8000

# Kill process if needed
taskkill /PID <PID> /F
```

### No citations in response
```powershell
# Check if migration ran
python scripts/test_citation_setup.py

# Check evidence table
psql -d musya_agent -c "SELECT COUNT(*) FROM evidence_registry;"
```

### MinIO connection fails
```powershell
# Verify MinIO is running
curl http://localhost:9000/minio/health/live

# Check .env file has correct credentials
```

### No documents found
```powershell
# Re-upload samples
python scripts/prepare_sample_documents.py

# Re-ingest
curl -X POST http://localhost:8000/api/ingest
```

---

## 📚 Full Documentation

For detailed testing guide: `doc/CITATION_TESTING_GUIDE.md`

For architecture details: `doc/CITATION_EVIDENCE_AGENT.md`

---

## ✅ Success Checklist

- [ ] Setup script passes all tests
- [ ] Sample documents uploaded (4 files)
- [ ] Server starts without errors
- [ ] Documents ingested into ChromaDB
- [ ] Test UI loads successfully
- [ ] Chat returns citations
- [ ] Evidence API works
- [ ] Documents can be opened
- [ ] Coverage score > 0.7

---

## 🎯 Sample Test Messages

```
สถิติอุบัติเหตุจังหวัดเชียงใหม่ปี 2025
แนวโน้มอุบัติเหตุทางถนนในภาคเหนือ
นโยบายความปลอดภัยทางถนนล่าสุด
เปรียบเทียบอัตราการเสียชีวิตจากอุบัติเหตุระหว่างปี 2023-2025
มาตรการป้องกันอุบัติเหตุที่มีประสิทธิภาพ
จุดเสี่ยงอุบัติเหตุในพื้นที่ภาคเหนือ
```

---

**Last Updated:** 2025-01-27  
**Estimated Time:** 5-10 minutes  
**Status:** Ready to Test
