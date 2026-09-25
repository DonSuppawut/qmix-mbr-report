# ระบบสร้างรายงาน MBR EST (QMix East)

สร้างรายงานผลประกอบการประจำเดือนของ EST จากไฟล์ต้นทาง ด้วยคำสั่งเดียว ได้ 3 ไฟล์ที่ตัวเลขชุดเดียวกัน:

- `out/MBR_EST_<Mon><ปี พ.ศ. 2 หลัก>.html` — รายงานหลัก (10 Section, กราฟ SVG, ฟอนต์ Sarabun ฝังในไฟล์)
- `out/MBR_EST_….xlsx` — ตารางทุกตารางแยกชีทตามหัวข้อย่อย + กราฟ native ของ Excel (copy ไป PowerPoint แล้วแก้ไขได้)
- `out/MBR_EST_….pdf` — A4 แนวตั้ง พิมพ์จาก HTML ด้วย Microsoft Edge

โจทย์และกติกาทั้งหมด: Google Doc "โจทย์สำหรับ Claude Code — สร้างระบบสร้างรายงาน MBR EST" + `QMixMBR.md` v1.8 + `QMixMBR • PROJECT-CONTEXT.md` (ใน `01_PROJECTS/QMixMBR/`) — ข้อตัดสินใจของ Don หลังรายงาน Aug'69 บันทึกไว้ใน PROJECT-CONTEXT ข้อ 4

## ติดตั้ง (ครั้งแรกครั้งเดียว)

```
python -m pip install -r requirements.txt
```

ต้องมี Python 3.12+ และ Microsoft Edge (มากับ Windows) — ถ้าไม่มี Edge ให้รัน `python -m playwright install chromium`
ฟอนต์ Sarabun (OFL) อยู่ใน `assets/` แล้ว — ถ้าเปิด .xlsx บนเครื่องที่ไม่ได้ติดตั้ง Sarabun ตัวเลขจะเหมือนเดิมแต่ Excel จะใช้ฟอนต์อื่นแสดงผล

## ขั้นตอนรายเดือน (ตัวอย่างเดือน ก.ย. 69 = `2026-09`)

1. **วางไฟล์ต้นทางใน `D:\QMix\Account\`** (ชื่อตามรูปแบบเดิม — ตรวจชื่อเดือนให้ตรงทุกครั้ง):
   - `09.26 TVC by Plant by Month.xlsx` (มีชีทเดือนก่อน ๆ อยู่ในไฟล์เดียวกัน — ใช้ทำ LM และ YTD)
   - `รายงานต้นทุน Sep'26 All Area.xlsx` และของ 2 เดือนก่อนหน้า (ใช้ทำ 6.4/6.5 movement 3 เดือน)
   - `09.26 Net Con  (Management).xlsx` และของเดือนก่อน (Section 3)
   - `เตรียมข้อมูล คจ. EST ก.ย. 69.xlsx` (Section 9) — ถ้าชื่อไม่ตรงรูปแบบ ให้ระบุ path ใน `data/inputs/2026-09.json` แบบ `data/inputs/2026-08.json`
2. **ดึง snapshot จากฐานข้อมูล** (ให้ Claude ทำผ่าน MCP `query_eastsales` — สคริปต์ Python เรียก MCP เองไม่ได้):
   `east_plant_pnl_monthly` เดือนนั้น scenario=Actual → `data/snapshots/2026-09/east_plant_pnl_monthly_actual.json`
   และอัปเดต `data/snapshots/east_plants.json` ถ้ามีโรงงานใหม่
3. **การปรับปรุง GL เฉพาะ section** (ถ้า Don สั่ง) → `data/adjustments/2026-09.json` (ดูตัวอย่างของ 2026-08)
4. **ตรวจข้อมูลก่อนสร้างรายงาน:**
   ```
   python validate_month.py 2026-09
   ```
   ต้องผ่านทุกข้อ (reconcile รายงานต้นทุนกับ TVC, ผลรวมรายโรงงาน = ยอด scope, residual Waterfall/Bridge = 0) — ถ้าข้อไหน FAIL ให้หยุดและแจ้ง Don ห้ามเดา
5. **สร้างรายงานรอบแรก** (ยังไม่มีข้อความวิเคราะห์):
   ```
   python build_report.py 2026-09 --no-pdf
   ```
6. **เขียนข้อความวิเคราะห์** `data/narrative/2026-09.json` (ให้ Claude ร่างจากตัวเลขในรายงานรอบแรก แล้ว Don ตรวจ) — คีย์ที่ใช้ดูได้จาก `data/narrative/2026-08.json` เช่น `s1.watch`, `s1.strategy`, `s3.segment_notes`, `s7.cases`, `s10.actions` — ตัวเลขข้อเท็จจริงในรายงานสคริปต์คำนวณเอง ข้อความในไฟล์นี้เป็นความเห็น/กลยุทธ์เท่านั้น
7. **สร้างชุดส่งมอบ:**
   ```
   python build_report.py 2026-09
   ```
8. **ตรวจชุดส่งมอบ:**
   ```
   python tests/check_xlsx.py out/MBR_EST_Sep69.html out/MBR_EST_Sep69.xlsx
   ```
   (ตัวเลขทุกช่องใน .xlsx ต้องตรง HTML, กราฟเป็น native ไม่มีรูปภาพฝัง)

## โครงสร้างโค้ด

| ไฟล์ | หน้าที่ |
|---|---|
| `mbr/tvc.py` | อ่าน TVC by Plant by Month — ตรวจชื่อแถว/หัวคอลัมน์ทุกครั้ง ถ้าไฟล์เปลี่ยนโครงสร้างจะหยุดพร้อมบอกแถวที่ไม่ตรง |
| `mbr/calc.py` | Scorecard, Waterfall AP→Actual (ถึง NPAT), EBITDA Bridge LM→Actual, residual |
| `mbr/plants.py` | ข้อมูลรายโรงงาน (เดือนนี้, LM, AP, YTD จากชีทในไฟล์ TVC เดือนปัจจุบัน) |
| `mbr/vendors.py` | Cartage รายเวนเดอร์จากรายงานต้นทุน (ต้องรวมได้เท่า TVC แถว 164 ไม่งั้นหยุด) |
| `mbr/netcon.py` | ไฟล์ Net Con — Segment (China State = Mega), ลูกค้า, NetCon bucket, Rebate |
| `mbr/forecast.py` | ไฟล์ คจ. ชีท AP26 (รวมยอดจากรายเดือนเอง — คอลัมน์ Total ของไฟล์บางจุดสูตรเสีย) |
| `mbr/report*.py`, `mbr/page.py`, `mbr/svg.py` | สร้าง HTML ทีละ Section + กราฟ SVG |
| `mbr/xlsx_out.py`, `mbr/pdf_out.py` | .xlsx (อ่านตารางจาก HTML ที่สร้างแล้ว + กราฟ native) และ PDF |
| `validate_month.py` | ตรวจข้อมูลต้นทาง |
| `tests/regress_html.py` | เทียบกับรายงาน Aug'69 ที่ส่งจริง (ความต่างที่ทราบสาเหตุ/ที่ Don สั่งเปลี่ยน ระบุไว้ในไฟล์) |
| `data/config/plants.json` | ประเภทโรงงาน/โรงที่ซ่อนใน Section 7–8 — **ยืนยันกับ Don ทุกเดือน** |

## ข้อจำกัดที่รู้แล้ว

- เดือน ม.ค. ยังไม่รองรับ (LM ต้องใช้ไฟล์ TVC ของปีก่อน) และ `validate_month.py` ยังผูกกับปี 2569 (golden values ก.ค. 69)
- ตาราง CCP ที่ใบแจ้งหนี้ไม่มี m³ ยังนับปริมาณเฉพาะที่ระบุในข้อความ GL — รอเปิดสิทธิ์ `east_production_dispatches` (Don อนุมัติหลักการแล้ว ต้องเสนอ SQL ก่อน)
- ข้อความวิเคราะห์ของ ส.ค. 69 คัดจากรายงานเดิม บางจุดอ้างตัวเลขก่อน Don เปลี่ยนกติกา (เช่น Mega 3,410)
- ห้ามเก็บ secret ใด ๆ ในโฟลเดอร์นี้ (ไม่มีการใช้ secret อยู่แล้ว)
