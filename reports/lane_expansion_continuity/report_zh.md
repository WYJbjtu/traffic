# 2023 年一月完整參考與 96 車道延伸：實測交接（暫定；非模型結果）

## 已量測（來源是官方原始車道快照）

- 以既有 `configs/long_window.json` 的一月第一週規則**凍結** 426 個一方向一車道候選，沒有使用後期觀測挑選車道。原始前 24 個車道 ID、**完整一月 85 百分位參考速度及參考箱數**，逐項與已發表 24 車道結果一致。
- 僅重用一份 2023 年 1 月官方 `rawSpeedVol-all.xml` 每月 ZIP（`https://app.data.gov.hk/v1/historical-archive/get-file?url=https%3A%2F%2Fresource.data.one.gov.hk%2Ftd%2Ftraffic-detectors%2FrawSpeedVol-all.xml&time=20230101`），原始 1,136,915,260 bytes；SHA-256 `e9dede47f76807f674d26ca78a6832361e01073f51a09ddb2e1fd489d1794dc0`，41,330 個快照。原始檔 `data/local/lane-expansion/source/raw/202301/raw_202301.zip` 保持不變；HTTP 206、ETag、逐段請求與校驗見同目錄 `.meta.json`、`range_requests.jsonl`、`archive_check.json`。前三十一日參考結果在 **ignored** 的 `data/local/lane-expansion/january426/v1/full_january_reference.parquet`（SHA-256 `f34b16ce590e3a6ae3c35477b2aa7d74c5ae3337315d78900285d32aeb0f88f4`），每車道每日品質及所有輸出校驗在 `reference_manifest.json`。
- 依原有方法：每個車道的「可用、正流量、速度大於 0」五分鐘速度箱、觀測時間及可用時間均早於 2023-02-01 HKT；≥300 箱，以第 85 百分位計算。**426/426 全部通過完整一月要求**（最少 2,929 箱，參考速度中位數 81 km/h）。這不是 2023–2026 年持續穩定性證明。
- 一月品質比首週差：426 候選合計 **1,330 車道日全無觀測**；其中 2023-01-16/17/18/24 各有至少 317/426 條缺日。96 車道的其中四日全部缺失（384 車道日）；一月 96 車道平均有效 30 秒車速覆蓋率 **71.75%**、可用五分鐘箱 **74.54%**（首週五分鐘為 98.83%）。五分鐘「可用」僅需 10 個 30 秒時段中的 ≥2 個正流量有效時段，故兩個覆蓋率**不可互換**。完整一月品質見 `january_scenarios.csv`、`january_reference.csv` 及 ignored 的 `january_lane_day.parquet`。
- 同月首週和全月 85 百分位參考比較：差值中位數 0 km/h、絕對差第 90 百分位 1 km/h；這只是**一月內**品質診斷，不代表長期漂移，亦不會作驗證／測試期重新擬合。

| 預先定義隊列 | 車道／偵測器 | 現行元數據地區數 | 一月有效 30 秒平均 | 一月可用 5 分鐘平均 | 一月全缺車道日 | 新恢復事件數 |
|---|---:|---:|---:|---:|---:|---|
| 原 24 | 24/24 | 6 | 71.24% | 74.48% | 96 | 沿用既有 7,597；未重新計數 |
| 原 ID 順序 48 | 48/48 | 7 | 71.17% | 74.15% | 192 | 未量測 |
| 原 ID 順序 96 | 96/96 | 12 | 71.75% | 74.54% | 384 | 未量測 |
| 首週合格全部 | 426/426 | 18 | 76.44% | 79.55% | 1,330 | 未量測 |
| 現行地區輪流 96（僅方案） | 96/96 | 18 | 72.58% | 75.04% | 364 | 未量測 |

## 2023–2026 連續性：**尚未可量測**

對 2023-01 至 2026-09 的 45 個每月官方原始 ZIP 做本機完整性清單：**1 個已驗證（2023-01）；其餘 44 個不在本環境**。清單 `archive_inventory.csv` 的缺失月份是**來源缺失**，不是車道覆蓋率 0。也沒有完整 2026-10-01 邊界 ZIP。檢查了此 repo `data/local/`、已掛載 Windows D:/E: 的常見團隊資料目錄、C:/Users 常見目錄；未找到其餘原始檔。2023–2026 train／validation／test 的新增 402 車道每月覆蓋率、停用與身份／方向變化、長缺口、速度漂移及新事件／標籤數**均為未量測**。`reports/long_window/coverage_detector_month.csv` 只覆蓋原 24 偵測器，不可移植到 96 或 426。

現時地理資料只來自官方**現行**偵測器元數據（`https://static.data.gov.hk/td/traffic-data-strategic-major-roads/info/traffic_speed_volume_occ_info.csv`；SHA-256 `f30818ec94984c024f0188e2e45139ac684c4636aae7906561e227f01407423d`）；現行地點是否適用於 2023 年仍須核對。距離 ≤250 米的 426 站點候選對 **196** 對，其中 ID 順序 96 車道內 **29** 對；並非核准上／下游道路連接、不同來源獨立觀測或事件空間覆蓋。另一個已觀測之處理後道路速度快照只有兩個日期；不可當作車道速度、流量或標籤補值。官方 `CENTERLINE` 現版道路 36,525 段／48,080 方向弧及 `irn_version` 歷史相容性未核實。**空間 ablation 仍 NO-GO。**

## 在持有原始 47 GB ZIP 的隊員機器上重現（不重新下載）

使用原始 ZIP 與對應 `raw/YYYYMM/archive_check.json`、`raw/YYYYMM/raw_YYYYMM.zip.meta.json`、`metadata/archive_inventory.json{,.meta.json}`（以及 `raw/20261001-boundary/archive_check.json` 所指 ZIP）；從 repo 根目錄執行：

```text
uv sync --locked
uv run --locked python -m scripts.scan_expanded_archives --source-root D:/HK_Traffic_Recovery_Long_Window --inventory D:/HK_Traffic_Recovery_Long_Window/metadata/archive_inventory.json --output D:/HK_Traffic_Recovery_Long_Window/expansion/archive_inventory-v1.csv
uv run --locked python -m scripts.validate_january_references --root D:/HK_Traffic_Recovery_Long_Window --output D:/HK_Traffic_Recovery_Long_Window/expansion/january426-v1 --workers 2
uv run --locked python -m scripts.profile_expanded_archives --source-root D:/HK_Traffic_Recovery_Long_Window --inventory D:/HK_Traffic_Recovery_Long_Window/metadata/archive_inventory.json --january-reference D:/HK_Traffic_Recovery_Long_Window/expansion/january426-v1 --output D:/HK_Traffic_Recovery_Long_Window/expansion/continuity426-v1 --workers 2
uv run --locked python -m scripts.label_expanded_96 --profile-root D:/HK_Traffic_Recovery_Long_Window/expansion/continuity426-v1 --january-reference D:/HK_Traffic_Recovery_Long_Window/expansion/january426-v1 --config configs/long_window_96_candidate.json --output D:/HK_Traffic_Recovery_Long_Window/expansion/pilot96-id-order-v1
uv run --locked pytest
```

示例 D: 路徑僅表示**隊員自己指定的根目錄**，不是程式內硬編碼。`profile_expanded_archives` 需先通過 45 個月逐檔 SHA-256 及十月邊界檢查；缺任何一檔會**在處理前停止**。來源壞檔／補齊與傳輸需依原始 SHA-256 核實，不能以已發表僅 24 站的 prepared Release 代替。連續性處理相當龐大，以上完整四年步驟目前**只驗證了缺檔時拒絕執行**，未作真實端到端成功聲稱。隊員可只傳遞檢查後的輕量報告及 SHA-256 清單；需合併四年原始車道資料時先核對全部 45 ZIP 和原始來源時間，不應透過 Git 提交大型資料。

現環境可獨立重現已完成的一月結果（單月 ZIP 路徑見上）：

```text
uv run --locked python -m scripts.validate_january_references --root data/local/lane-expansion/source --output data/local/lane-expansion/january426/NEW_VERSION --workers 2
uv run --locked python -m scripts.report_expanded_january --january data/local/lane-expansion/january426/NEW_VERSION --output reports/lane_expansion_continuity_NEW_VERSION
```

以上所有擴充結果與已發表 24 車道、7,597 個事件分開；沒有插值、改標籤、重訓模型或修改舊輸出。
