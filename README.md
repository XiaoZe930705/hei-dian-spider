# 黑點網站爬蟲（hei-dian-spider）

定期爬取 https://hei-dian.com.tw/  （或你指定的站點），抓取站內多頁，輸出 SEO 稽核報告（JSON + PDF），並可選擇保存原始 HTML 方便除錯與比對。

## 功能

- 站內多頁爬取（BFS 深度/頁數可控）
- SEO 稽核：title、meta description、canonical、H1、薄內容/CSR 風險、狀態碼等
- 資安（OWASP Top 10 啟發式）：依 HTTP 標頭 + HTML 訊號給分與統計（非完整弱掃）
- 輸出稽核報告：JSON + PDF（同時保留 HTML 報告）
- 可選保存每次抓到的原始 HTML（方便判斷是否 CSR/JS 渲染）
- 日誌輸出到 `spider.log`
- 針對 `Content-Encoding: br` 提供可選 brotli 解壓支援

## 環境需求

- Python 3.7+
- 安裝套件：`pip install -r requirements.txt`
- （可選）若站點回應使用 `br` 壓縮：`pip install brotli`
- 產生 PDF：需本機已安裝 Microsoft Edge 或 Google Chrome（用 headless 列印）

## 快速開始

```bash
pip install -r requirements.txt
python spider.py
```

停止：在終端機按 `Ctrl+C`。

## 站內多頁 + SEO 稽核（建議用法）

只跑一次並輸出稽核報表（JSON + PDF）：

```bash
python spider.py --once --max-pages 60 --max-depth 3
```

預設行為：啟動會先跑 1 次，之後每天 `03:00` 再跑 1 次（可用 `--interval-days` / `--daily-at` 調整）。

常用參數：

- `--url https://example.com/`：起始網址
- `--max-pages 200`：最多抓幾頁
- `--max-depth 3`：最多跟隨幾層連結
- `--delay 0.5`：每次請求間隔（秒）
- `--no-save-html`：不保存原始 HTML

## 專案結構（模組化）

- `spider.py`：CLI 入口（參數解析、排程）
- `spider_core/`：核心模組
  - `crawler.py`：站內爬取 + 稽核流程
  - `audit.py`：SEO 欄位抽取與 issue 判斷
  - `http_client.py`：抓取 HTML、PDF 輸出（Edge/Chrome headless）
  - `security.py`：OWASP Top 10 啟發式資安評分
  - `url_utils.py` / `parsing.py` / `reporting.py` / `config.py`

## 排程方式（Windows）

專案已提供 `run_spider.bat`，可直接用於 Windows 任務排程器。

- 觸發：每天一次（建議）或依需求調整
- 動作：執行 `run_spider.bat`

## 輸出檔案

- `spider.log`：爬取過程與錯誤資訊
- `data/seo_audit_YYYYMMDD_HHMMSS.json`：站內多頁 SEO 稽核（含每頁 issues 與摘要）
- `data/seo_audit_YYYYMMDD_HHMMSS.html`：稽核報告 HTML（用於產生 PDF，也可自行開啟檢視）
- `data/seo_audit_YYYYMMDD_HHMMSS.pdf`：稽核報告 PDF（由 Edge/Chrome headless 列印產生）
- `data/html/YYYYMMDD_HHMMSS/`：本次爬取保存的原始 HTML（最多 `--save-html-limit` 頁）

## JSON 欄位說明

每頁常用欄位（實際以輸出為準）：

- `timestamp`：爬取時間（ISO 格式）
- `url` / `final_url`：目標 URL / 追隨 redirect 後的最終 URL
- `status_code`：HTTP 狀態碼
- `content_type` / `content_encoding`：回應標頭資訊
- `title`：網頁標題
- `content_length`：HTML 長度（字元數）
- `meta_description` / `meta_keywords`
- `canonical_url`
- `h1_tags` / `h2_tags` / `h3_tags`：標題文字陣列（H2/H3 會截到最多 20 個）
- `links` / `link_count`：連結清單（最多 100 個）與總數
- `text_content_length` / `text_preview`：可見文字長度與前 500 字預覽
- `security_score` / `security_grade`：資安分數與等級（啟發式）
- `security.findings`：發現項目（如缺 HSTS/CSP、混合內容、cookie flags 等）

## 自訂設定

- 預設目標網址：`spider_core/config.py` 的 `TARGET_URL`
- 排程：執行時用 `--interval-days` / `--daily-at` 調整
- 報告輸出：`data/` 資料夾

## 注意事項

- 請遵守目標網站的 robots.txt 與使用條款，並控制頻率避免造成負擔
- 報告中的部分 404（例如 `/cdn-cgi/l/email-protection`）可能來自 Cloudflare 防護機制，非站內真實內容頁
