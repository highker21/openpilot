# Jetlink 0.8.10 → 0.8.13 更新說明

> 分支：`dp0111jetlink-0813`（基於 herizon1054/openpilot `dp0111jetlink` 84acc0c）
> 上游：zoompilot/jetlink `af9df78`（v0.8.13）；比對基準 `3d4f671`（v0.8.10）

## 做法

`jetlink_repo/jetlink` 以三方合併更新：基準 = 上游 v0.8.10，一邊 = 本分支（含 dp 修改），另一邊 = 上游 v0.8.13。
dp 這層（`dragonpilot/jetlink_adapter` 等）不需要改：API 仍是 3，介面只多了選用欄位 `Keys.select`（預設 None）。

## 上游 0.8.11–0.8.13 帶進來的

- 在 comma 或 App 選的模型兩邊共用，不用各自重新下載（0.8.11）
- 可以用 ONNX 雜湊指定模型（0.8.12）
- 在 comma 選的大模型不會再跳回前一個（0.8.13）
- 進度多一個 `download` 階段（Jetson 自己下載模型）

## 保留的 dp 修改

| 檔案 | 修改 |
| --- | --- |
| `comma/lending.py` | `SERVER_FIELDS` 取聯集：上游的 `pick`、`fetches` 加上 dp 的 `loaded`、`cached_models` |
| `comma/owner.py`、`openpilot/settings.py` | 不供電給手機（沒動） |
| `openpilot/joining.py` | keepalive 失敗快速重連（沒動） |
| `openpilot/model_cache.py`、`models.py` 的 `cache_lock` | 刪除已下載模型（保留） |
| `openpilot/link.py` | 跟隨外部裝置：跟隨時沿用 dp 的作法；不跟隨時走上游新的 `adopt()` 流程。跟隨時 `ensure` 不帶 comma 的 ref、`fetch=False` |
| `openpilot/provision.py` | `provision()` 改用上游先 hello 的順序，dp 的跟隨判斷改讀這次 hello（不再多送一次 hello）；`run()` 先做 dp 的跟隨判斷，再做上游的「伺服器有新選擇」判斷 |

## 新增的 dp 修改（因應 0.8.13）

- `openpilot/models.py` `default_chosen_at()`：0.8.13 把「清空模型欄位」當成「選了預設模型」，會在 hello 裡把預設模型送給手機，讓手機換掉自己選的模型。dp 清空欄位的意思是「跟隨外部裝置」，所以跟隨時一律回 None。

## 驗證（無實機）

- 上游測試（合併後套件，Python 3.12）：`tests/openpilot` 663 通過、3 略過。
- 其餘測試：4 項失敗都是預期內：lending 兩項多記 `loaded`/`cached_models`、owner 不供電給手機、`jetlink-root.sh` 沒有執行權限（本分支原本就是 100644，以 `sudo -n bash` 執行）。另外 3 項在原版 0.8.13 也同樣失敗（測試環境缺檔）。
- `tools/jetlink/test_port.py`：更新前後都是同樣 2 項錯誤（`test_mici_hud_draw_path`、`test_old_and_new_memoryview_api`），沒有新增。
- **尚未在 comma 實機上測試。** 請先停車確認連線、切換大模型，再上路。外部裝置（Jetson / App）也要更新到 0.8.13。
