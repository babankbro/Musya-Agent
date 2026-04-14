"""
Script to create and upload sample documents to MinIO for testing Citation & Evidence Agent.
Creates realistic sample documents with proper structure for testing.
"""

import sys
from pathlib import Path
from io import BytesIO

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.minio_client import get_minio_client
from src.config import get_settings
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_sample_text_document(filename: str, content: str) -> BytesIO:
    """Create a simple text document."""
    return BytesIO(content.encode('utf-8'))


def upload_sample_documents():
    """Upload sample documents to MinIO for testing."""
    settings = get_settings()
    client = get_minio_client()
    
    logger.info("=" * 60)
    logger.info("Preparing Sample Documents for Citation & Evidence Testing")
    logger.info("=" * 60)
    
    # Sample documents with structured content
    documents = {
        "accident/road_safety_policy_2025.txt": """
นโยบายความปลอดภัยทางถนน พ.ศ. 2568

หน้า 1
บทที่ 1: บทนำ
นโยบายความปลอดภัยทางถนนฉบับนี้จัดทำขึ้นเพื่อลดอัตราการเสียชีวิตจากอุบัติเหตุทางถนน
โดยมีเป้าหมายลดการเสียชีวิตลง 50% ภายในปี 2568

หน้า 2
มาตรา 1.1: วัตถุประสงค์
1. ลดอัตราการเสียชีวิตจากอุบัติเหตุทางถนน
2. เพิ่มความปลอดภัยสำหรับผู้ใช้รถใช้ถนน
3. ปรับปรุงโครงสร้างพื้นฐานด้านความปลอดภัย

หน้า 3
บทที่ 2: สถานการณ์ปัจจุบัน
มาตรา 2.1: สถิติอุบัติเหตุปี 2567
จากข้อมูลกรมทางหลวง พบว่าในปี 2567 มีผู้เสียชีวิตจากอุบัติเหตุทางถนนทั้งสิ้น 15,234 ราย
เพิ่มขึ้น 8.5% จากปีก่อนหน้า

หน้า 4
มาตรา 2.2: พื้นที่เสี่ยง
จังหวัดที่มีอัตราอุบัติเหตุสูงสุด 5 อันดับแรก ได้แก่:
1. เชียงใหม่ - 1,245 ราย
2. นครราชสีมา - 1,123 ราย
3. ขอนแก่น - 1,089 ราย
4. อุบลราชธานี - 987 ราย
5. สงขลา - 945 ราย

หน้า 5
บทที่ 3: มาตรการป้องกัน
มาตรา 3.1: มาตรการด้านวิศวกรรม
1. ปรับปรุงจุดเสี่ยงบนทางหลวง 500 จุด
2. ติดตั้งไฟส่องสว่างเพิ่มเติม 2,000 จุด
3. ปรับปรุงป้ายจราจรให้ชัดเจนยิ่งขึ้น

หน้า 6
มาตรา 3.2: มาตรการด้านการบังคับใช้กฎหมาย
เพิ่มการตรวจจับการฝ่าฝืนกฎจราจร โดยเฉพาะ:
- การขับขี่เร็วเกินกำหนด
- การขับขี่ในสภาพเมาสุรา
- การไม่สวมหมวกนิรภัย

หน้า 7
บทที่ 4: งบประมาณและแผนดำเนินการ
มาตรา 4.1: งบประมาณ
จัดสรรงบประมาณทั้งสิ้น 5,000 ล้านบาท แบ่งเป็น:
- ด้านวิศวกรรม: 3,000 ล้านบาท
- ด้านการบังคับใช้กฎหมาย: 1,000 ล้านบาท
- ด้านการประชาสัมพันธ์: 1,000 ล้านบาท

หน้า 8
มาตรา 4.2: กำหนดการ
ไตรมาสที่ 1/2568: เริ่มดำเนินการปรับปรุงจุดเสี่ยง
ไตรมาสที่ 2/2568: เพิ่มการตรวจจับการฝ่าฝืน
ไตรมาสที่ 3/2568: ประเมินผลและปรับปรุง
ไตรมาสที่ 4/2568: รายงานผลการดำเนินงาน
""",

        "accident/accident_statistics_2024.txt": """
รายงานสถิติอุบัติเหตุทางถนน ปี 2567

หน้า 1
บทสรุปผู้บริหาร
รายงานฉบับนี้นำเสนอสถิติอุบัติเหตุทางถนนในประเทศไทยประจำปี 2567
โดยรวบรวมข้อมูลจากกรมทางหลวง สำนักงานตำรวจแห่งชาติ และกระทรวงสาธารณสุข

หน้า 2
บทที่ 1: ภาพรวมสถิติ
มาตรา 1.1: จำนวนอุบัติเหตุทั้งหมด
ปี 2567 มีอุบัติเหตุทางถนนทั้งสิ้น 234,567 ครั้ง
เพิ่มขึ้น 5.2% จากปี 2566 ที่มี 223,012 ครั้ง

หน้า 3
มาตรา 1.2: ผู้เสียชีวิตและบาดเจ็บ
- ผู้เสียชีวิต: 15,234 ราย (เพิ่มขึ้น 8.5%)
- บาดเจ็บสาหัส: 45,678 ราย (เพิ่มขึ้น 6.3%)
- บาดเจ็บเล็กน้อย: 123,456 ราย (เพิ่มขึ้น 4.1%)

หน้า 4
บทที่ 2: การวิเคราะห์ตามพื้นที่
มาตรา 2.1: ภาคเหนือ
จังหวัดเชียงใหม่มีอุบัติเหตุสูงสุดในภาคเหนือ 1,245 ราย
สาเหตุหลักมาจากการขับขี่เร็วเกินกำหนดบนเส้นทางภูเขา

หน้า 5
มาตรา 2.2: ภาคตะวันออกเฉียงเหนือ
นครราชสีมามีอุบัติเหตุสูงสุด 1,123 ราย
ส่วนใหญ่เกิดบนทางหลวงสายหลัก โดยเฉพาะช่วงเทศกาล

หน้า 6
บทที่ 3: การวิเคราะห์ตามช่วงเวลา
มาตรา 3.1: การกระจายตามเดือน
เดือนที่มีอุบัติเหตุสูงสุด:
1. เมษายน (สงกรานต์): 25,678 ครั้ง
2. ธันวาคม (ปีใหม่): 23,456 ครั้ง
3. กรกฎาคม (เข้าพรรษา): 21,234 ครั้ง

หน้า 7
มาตรา 3.2: การกระจายตามช่วงเวลาในวัน
ช่วงเวลาที่มีอุบัติเหตุสูงสุด:
- 17:00-19:00 น. (เลิกงาน): 35% ของอุบัติเหตุทั้งหมด
- 06:00-08:00 น. (ไปทำงาน): 25%
- 22:00-02:00 น. (กลางคืน): 20%

หน้า 8
บทที่ 4: สาเหตุของอุบัติเหตุ
มาตรา 4.1: สาเหตุหลัก
1. ขับรถเร็วเกินกำหนด: 45%
2. ขับรถในสภาพเมาสุรา: 25%
3. ไม่ปฏิบัติตามสัญญาณจราจร: 15%
4. ง่วงนอน/เผลอสติ: 10%
5. สภาพรถไม่พร้อม: 5%

หน้า 9
บทที่ 5: ข้อเสนอแนะ
มาตรา 5.1: มาตรการเร่งด่วน
1. เพิ่มการตรวจจับความเร็วด้วยกล้อง
2. เข้มงวดการตรวจวัดแอลกอฮอล์
3. ปรับปรุงจุดเสี่ยงให้ปลอดภัยยิ่งขึ้น
4. รณรงค์ประชาสัมพันธ์อย่างต่อเนื่อง
""",

        "mental_health/mental_health_guidelines.txt": """
แนวทางการดูแลสุขภาพจิต พ.ศ. 2568

หน้า 1
บทนำ
แนวทางฉบับนี้จัดทำขึ้นเพื่อเป็นแนวทางในการดูแลสุขภาพจิตของประชาชน
โดยเฉพาะในสถานการณ์วิกฤติและภาวะความเครียด

หน้า 2
บทที่ 1: หลักการพื้นฐาน
มาตรา 1.1: ความสำคัญของสุขภาพจิต
สุขภาพจิตเป็นส่วนสำคัญของสุขภาพโดยรวม
การดูแลสุขภาพจิตที่ดีช่วยเพิ่มคุณภาพชีวิตและประสิทธิภาพในการทำงาน

หน้า 3
มาตรา 1.2: กลุ่มเสี่ยง
กลุ่มที่ควรได้รับการดูแลเป็นพิเศษ:
1. ผู้ประสบภาวะวิกฤติ (อุบัติเหตุ, ภัยพิบัติ)
2. ผู้สูงอายุที่อยู่คนเดียว
3. เด็กและเยาวชนที่มีปัญหาครอบครัว
4. ผู้ที่มีประวัติโรคจิตเวช

หน้า 4
บทที่ 2: การประเมินสุขภาพจิต
มาตรา 2.1: เครื่องมือประเมิน
ใช้แบบประเมิน DASS-21 (Depression Anxiety Stress Scale)
เพื่อคัดกรองภาวะซึมเศร้า วิตกกังวล และความเครียด

หน้า 5
มาตรา 2.2: เกณฑ์การประเมิน
คะแนน 0-9: ปกติ
คะแนน 10-20: เล็กน้อย
คะแนน 21-30: ปานกลาง
คะแนน 31+: รุนแรง (ควรพบจิตแพทย์)
""",

        "nutrition/nutrition_standards.txt": """
มาตรฐานโภชนาการ พ.ศ. 2568

หน้า 1
บทนำ
มาตรฐานโภชนาการฉบับนี้กำหนดแนวทางการบริโภคอาหาร
เพื่อสุขภาพที่ดีของประชาชนไทยทุกช่วงวัย

หน้า 2
บทที่ 1: ความต้องการพลังงาน
มาตรา 1.1: ตามช่วงวัย
- เด็ก 1-3 ปี: 1,000-1,400 แคลอรี/วัน
- เด็ก 4-8 ปี: 1,400-1,800 แคลอรี/วัน
- วัยรุ่น: 2,000-2,800 แคลอรี/วัน
- ผู้ใหญ่: 1,800-2,400 แคลอรี/วัน
- ผู้สูงอายุ: 1,600-2,000 แคลอรี/วัน

หน้า 3
บทที่ 2: สัดส่วนสารอาหาร
มาตรา 2.1: คาร์โบไฮเดรต
ควรได้รับ 45-65% ของพลังงานทั้งหมด
เน้นคาร์โบไฮเดรตเชิงซ้อนจากธัญพืชไม่ขัดสี

หน้า 4
มาตรา 2.2: โปรตีน
ควรได้รับ 10-35% ของพลังงานทั้งหมด
เน้นโปรตีนจากพืช ปลา และเนื้อไม่ติดมัน
"""
    }
    
    # Ensure bucket exists
    try:
        if not client.bucket_exists(settings.MINIO_BUCKET):
            client.make_bucket(settings.MINIO_BUCKET)
            logger.info(f"✅ Created bucket: {settings.MINIO_BUCKET}")
        else:
            logger.info(f"✅ Bucket exists: {settings.MINIO_BUCKET}")
    except Exception as e:
        logger.error(f"❌ Failed to create bucket: {e}")
        return 0

    uploaded_count = 0
    
    for object_name, content in documents.items():
        try:
            data = create_sample_text_document(object_name, content)
            data.seek(0)
            
            client.put_object(
                settings.MINIO_BUCKET,
                object_name,
                data,
                length=len(content.encode('utf-8')),
                content_type='text/plain; charset=utf-8'
            )
            
            logger.info(f"✅ Uploaded: {object_name} ({len(content)} bytes)")
            uploaded_count += 1
            
        except Exception as e:
            logger.error(f"❌ Failed to upload {object_name}: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info(f"Upload Complete: {uploaded_count}/{len(documents)} documents")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("1. Run ingestion: curl -X POST http://localhost:8000/api/ingest")
    logger.info("2. Verify in ChromaDB: Check collection count")
    logger.info("3. Test search: Use the test UI or search_documents tool")
    
    return uploaded_count


def main():
    """Main function."""
    logger.info("\n🔍 Sample Document Preparation for Citation & Evidence Testing\n")
    
    try:
        count = upload_sample_documents()
        
        if count > 0:
            logger.info("\n✅ Sample documents ready for testing!")
            return True
        else:
            logger.error("\n❌ No documents were uploaded")
            return False
            
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
