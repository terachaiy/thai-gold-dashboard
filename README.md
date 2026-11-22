# ทองคำไทย · แดชบอร์ดกลยุทธ์ Swing

วิเคราะห์ราคาทองคำแท่ง 96.5% (สมาคมค้าทองคำ) ด้วยการวิเคราะห์ทางเทคนิค ข่าว และการทดสอบย้อนหลังแบบ walk-forward
มีหน้าเว็บภาษาไทย และหน้าสรุปบน Xteink X4 (แอป **Gold**)

## เริ่มใช้งาน
```
cd gold
python -m venv .venv
.venv\Scripts\python -m pip install pandas numpy requests yfinance feedparser fastapi uvicorn beautifulsoup4 lxml
.venv\Scripts\python run_backtest.py      # ทดสอบย้อนหลัง ~1 นาที (รันใหม่เดือนละครั้งพอ)
.venv\Scripts\python server.py            # เปิด http://localhost:8765
```
เซิร์ฟเวอร์อัปเดตราคาและข่าวทุก 15 นาที และเปิดรับจากทุกเครื่องในวง LAN เพื่อให้ X4 อ่าน `/api/x4` ได้
(Windows อาจถามให้อนุญาต Python ผ่าน firewall ให้กดอนุญาตสำหรับ Private network)

## X4
- แอป Gold อ่านที่อยู่เซิร์ฟเวอร์จาก `/apps/gold/server.txt` บน SD การ์ด (ค่าเริ่มต้น `http://172.20.10.3:8765`)
  ถ้า IP ของโน้ตบุ๊กเปลี่ยน ให้แก้ไฟล์นี้ผ่าน File Transfer
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
