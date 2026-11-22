# ทองคำไทย · แดชบอร์ดกลยุทธ์ Swing

วิเคราะห์ราคาทองคำแท่ง 96.5% (สมาคมค้าทองคำ) ด้วยการวิเคราะห์ทางเทคนิค ข่าว และการทดสอบย้อนหลังแบบ walk-forward
มีหน้าเว็บภาษาไทย และหน้าสรุปบน Xteink X4 (แอป **Gold**)

## ออนไลน์ (ไม่ต้องเปิดโน้ตบุ๊ก)
หน้าเว็บ: https://terachaiy.github.io/thai-gold-dashboard/
GitHub Actions ([.github/workflows/gold.yml](.github/workflows/gold.yml)) รัน `export_static.py` ทุก 30 นาที
ช่วง 08:00–19:00 น. และ 06:15 น. (เวลาไทย) แล้วเผยแพร่ขึ้น GitHub Pages ถ้ารอบไหนล้มเหลว หน้าเว็บจะแสดงข้อมูลชุดล่าสุดที่สำเร็จ
ประวัติข่าวและราคาเก็บใน Actions cache · GitHub จะหยุด schedule ถ้า repo ไม่มีความเคลื่อนไหว 60 วัน
(จะได้อีเมลเตือน กด Enable ในหน้า Actions ได้)

ส่งโค้ดที่แก้ใน workspace ขึ้น GitHub (commit ก่อน): `gold\publish.ps1`
สคริปต์จะเปลี่ยนอีเมลผู้เขียนเป็น no-reply ของ GitHub เพื่อไม่ให้อีเมลจริงเป็นสาธารณะ

## รันบนโน้ตบุ๊ก (ทางเลือก)
```
cd gold
python -m venv .venv
.venv\Scripts\python -m pip install pandas numpy requests yfinance feedparser fastapi uvicorn beautifulsoup4 lxml
.venv\Scripts\python run_backtest.py      # ทดสอบย้อนหลัง ~1 นาที (รันใหม่เดือนละครั้งพอ)
.venv\Scripts\python server.py            # เปิด http://localhost:8765
```
**เปิดอัตโนมัติตอนเข้าใช้ Windows:** `gold\install-autostart.ps1` (ยกเลิก: `-Remove`) เซิร์ฟเวอร์จะรันแบบไม่มีหน้าต่าง
บันทึก log ที่ `gold\data\server.log` และรัน backtest ใหม่เองเมื่อผลเก่ากว่า 30 วัน

เซิร์ฟเวอร์อัปเดตราคาและข่าวทุก 15 นาที และเปิดรับจากทุกเครื่องในวง LAN เพื่อให้ X4 อ่าน `/api/x4` ได้
(Windows อาจถามให้อนุญาต Python ผ่าน firewall ให้กดอนุญาตสำหรับ Private network)

## X4
- แอป Gold อ่านที่อยู่จาก `/apps/gold/server.txt` บน SD การ์ด
  (ค่าเริ่มต้น `https://terachaiy.github.io/thai-gold-dashboard`) ถ้าจะใช้โน้ตบุ๊กแทน ให้ใส่ `http://<IP>:8765`
- ข้อมูลล่าสุดถูกเก็บไว้ที่ `/apps/gold/latest.json` จึงเปิดดูได้แม้ไม่มีเน็ต ปุ่ม Confirm = รีเฟรช

## โครงสร้าง
| ไฟล์ | หน้าที่ |
|---|---|
| `goldapp/data.py` | ราคาสดจากสมาคมฯ และราคาทองไทยย้อนหลัง (XAU/USD × USD/THB × 0.965 × 15.244/31.1035 × ค่าพรีเมียม) |
| `goldapp/indicators.py` | EMA, RSI, ATR, ADX, MACD, Bollinger, แนวรับ/แนวต้าน |
| `goldapp/strategies.py` | กลยุทธ์ซื้ออย่างเดียว: EMA, Donchian, RSI, ADX regime |
| `goldapp/backtest.py` | backtester หักต้นทุน 0.4%/รอบ, ส่งคำสั่งช้า 1 วัน, walk-forward 5 ปี/1 ปี |
| `goldapp/news.py` | ข่าวจาก RSS + ให้คะแนนด้วยคำสำคัญไทย/อังกฤษ (ไม่ใช้ API key) |
| `goldapp/analysis.py` | สรุปมุมมอง: Donchian 45%, แนวโน้ม 25%, RSI 15%, ข่าว 15% |
| `server.py`, `web/index.html` | เซิร์ฟเวอร์และหน้าเว็บ |

ข้อมูลนี้เป็นการวิเคราะห์ ไม่ใช่คำแนะนำการลงทุน ผลในอดีตไม่รับประกันอนาคต
