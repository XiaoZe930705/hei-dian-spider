# 黑點網站爬蟲

這是一個自動化爬蟲工具，用於定期爬取 https://hei-dian.com.tw/ 網站。

## 功能特點

- ✅ 每30分鐘自動爬取一次網站
- ✅ 專注於 SEO 相關數據提取
- ✅ 自動保存爬取數據為 JSON 格式
- ✅ 完整的日誌記錄
- ✅ 錯誤處理和重試機制
- ✅ 模擬瀏覽器請求標頭

## 安裝步驟

1. 確保已安裝 Python 3.7 或更高版本

2. 安裝依賴套件：
```bash
pip install -r requirements.txt
```

## 使用方法

### 方法一：直接運行 Python 腳本

```bash
python spider.py
```

爬蟲會立即執行一次爬取，然後每30分鐘自動執行一次。

### 方法二：使用 Windows 任務計劃程序（推薦）

1. 創建一個批次檔 `run_spider.bat`：
```batch
@echo off
cd /d "C:\Users\aa098\OneDrive\Web-Crawler\hei-dian-spider"
python spider.py
```

2. 在 Windows 任務計劃程序中設定：
   - 觸發條件：每30分鐘執行一次
   - 操作：執行 `run_spider.bat`

## 輸出說明

- **日誌文件**: `spider.log` - 記錄所有爬取活動和錯誤
- **數據文件**: `data/hei_dian_YYYYMMDD_HHMMSS.json` - 每次爬取的數據

## 數據格式

每次爬取的數據包含以下 SEO 相關資訊：
- `timestamp`: 爬取時間
- `url`: 目標網址
- `status_code`: HTTP 狀態碼
- `title`: 網頁標題
- `content_length`: HTML 內容長度
- `meta_description`: Meta 描述標籤
- `meta_keywords`: Meta 關鍵字標籤
- `canonical_url`: Canonical URL
- `h1_tags`: 所有 H1 標題標籤
- `h2_tags`: H2 標題標籤（最多20個）
- `h3_tags`: H3 標題標籤（最多20個）
- `links`: 網頁中的連結列表（最多100個）
- `link_count`: 連結總數
- `text_content_length`: 純文字內容長度
- `text_preview`: 文字內容預覽（前500字元）

## 停止爬蟲

在終端機中按 `Ctrl+C` 即可停止爬蟲。

## 注意事項

- 請遵守網站的 robots.txt 和使用條款
- 建議設定合理的爬取頻率，避免對伺服器造成負擔
- 數據會保存在 `data/` 目錄中，請定期清理舊數據

## 自訂設定

如需修改爬取頻率，請編輯 `spider.py` 中的以下行：
```python
schedule.every(30).minutes.do(run_scheduled_crawl)
```

可選的時間間隔：
- `schedule.every(15).minutes.do(...)` - 每15分鐘
- `schedule.every(1).hour.do(...)` - 每小時
- `schedule.every(2).hours.do(...)` - 每2小時

