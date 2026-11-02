# 香港官方道路網與路段車速：工程交接（2026-11-02）

**結論：幾何建置成功；歷史路段車速確實可由官方存檔下載；用於恢復預測的空間特徵仍為 NO-GO。** 完整來源與重現命令：[英文實驗紀錄](official_network_pilot.md)。

- 復用本機 484,207,756-byte 官方 `CENTERLINE.gml`，未重新下載。串流處理 36,525 條道路、48,080 條方向弧、29,705 個端點；以 `INTERSECTION` 和 `TURN` 標示候選連接，跨線及不同高程不會僅因交叉而連接。輸出：`data/local/network-full/v1/{geometry,arcs,transitions}/tile=.../`。Linux 峰值 RSS 300,544 KiB，運行 59.28 秒。來源 SHA-256 `4fad0303e65c759ac7abe8eea3920b3ffcfcd5149c978fa9540bf032933a32c2`；候選連接未經人工核證。
- 官方存檔 `irnAvgSpeed-all.xml` 在 2023-05-15 及 2026-09-15 各抽一個 **真實** 中午快照，官方日清單分別有 720 與 528 個版本。2023 快照 SHA-256 `fdeed8f75587c3c97072f55b144a027e8d1432f2f3dee3422f7c808dd34c24b5`，4,198 筆有效速度，其中 4,181 個 ID 與現時幾何精確相同；2026 快照 SHA-256 `0007acb1eee0defd9eae89802c61cbeeacc3950de1c2eaf2dfd20c536c1785f0`，4,458 筆有效速度，其中 4,437 個 ID 相同。換算全網 **ID 重合** 分別約 11.447% 和 12.148%，不是歷史可用或導航覆蓋率。
- 兩份 XML 的 `irn_version=20221210`，目前道路檔為 2026-10 版；ID 相同不足以證明歷史幾何一致。存檔擷取時間也未證明當時公眾已可取得，故**批准的模型特徵為零**。無速度的道路保留缺失，無插值或限速替代。處理後速度可能由目標原始偵測器推算，不能當獨立觀測。
- 原始來源、HTTP 狀態、日期、SHA-256 及失敗紀錄在 `data/local/processed-pilot/v1/http/*.meta.json`、`pilot.json`；覆蓋報告在 `data/local/processed-pilot/coverage.json`。現有環境沒有 2023–2026 長窗事件檔，也沒有 Streamlit/PyDeck/Plotly，事件上下游、補足原始偵測器缺口、分折覆蓋及實際瀏覽器呈現**尚未驗證**。沒有重新訓練模型。
- `uv sync --locked`、`uv run --locked pytest` 已執行；詳細測試數和限制見英文紀錄。下一步先核實歷史道路版本及車速發布時間，人工審核連接，再載入已發布的長窗資料量測事件覆蓋；若仍不足，維持 NO-GO。

Git 狀態：原工作目錄已有未提交的 README、API、前端等修改；PR #11 已合併至 `origin/main`，現有分支另有與主線重疊的舊實驗提交。**未清除、覆寫或提交原有修改；不要把舊實驗檔重新放進 PR。**
