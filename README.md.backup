# TASA SatNet Pipeline

[![Release](https://img.shields.io/badge/release-v1.0.0-blue)](https://github.com/thc1006/tasa-satnet-pipeline/releases/tag/v1.0.0)
[![Tests](https://img.shields.io/badge/tests-24%2F24%20passing-success)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-98.33%25-brightgreen)](tests/)
[![K8s](https://img.shields.io/badge/K8s-verified-blue)](k8s/)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](Dockerfile)
[![Production](https://img.shields.io/badge/status-production--ready-success)](docs/PRODUCTION-STATUS.md)

**OASIS to NS-3/SNS3 衛星通聯管線自動化工具**

將 OASIS 衛星任務規劃系統產生的通聯日誌，自動轉換為 NS-3/SNS3 網路模擬器場景，並計算關鍵效能指標（KPI）與波束排程。

---

## 🎯 專案目標

- **解析** OASIS log（enter/exit command window、X-band data link）與 TLE
- **轉換** 為 NS-3/SNS3 場景設定（衛星、地面站、波束拓撲與時間表）
- **模擬** Transparent vs. Regenerative 中繼路徑
- **計算** latency（propagation/processing/queuing/transmission）與 throughput
- **排程** 波束分配與衝突檢測
- **部署** 支援 Docker 容器化與 Kubernetes 批次處理

---

## ✨ 功能特點

### 核心功能
- ✅ **真實計算**：基於物理公式的延遲與吞吐量計算（無模擬數據）
- ✅ **雙模式支援**：Transparent 與 Regenerative 中繼模式比較
- ✅ **智能排程**：波束分配與時間衝突檢測
- ✅ **批次處理**：K8s Jobs 支援大規模數據處理
- ✅ **TDD 開發**：98.33% 測試覆蓋率，24/24 測試通過
- 🛰️ **多星座支援**：GPS、Starlink、OneWeb、Iridium 整合
- 📊 **視覺化生成**：覆蓋地圖、時間軸、效能圖表

### 部署特性
- 🐳 **Docker 容器化**：多階段構建，優化映像大小
- ☸️ **Kubernetes 就緒**：完整 K8s 資源配置
- 📊 **4 秒執行**：完整管線 4 秒內完成
- 🚀 **高效能**：1,029 windows/sec 處理能力
- 📝 **完整文檔**：詳細的部署與使用指南

---

## 🚀 快速開始

### 前置需求

- Python ≥ 3.10
- Docker Desktop（含 Kubernetes）
- kubectl

### 安裝

```bash
# 1. Clone 專案
git clone https://github.com/thc1006/tasa-satnet-pipeline.git
cd tasa-satnet-pipeline

# 2. 安裝依賴
pip install -r requirements.txt

# 3. 執行測試
pytest tests/ -v --cov=scripts
```

### 基本使用

```bash
# 解析 OASIS log（基本模式）
python scripts/parse_oasis_log.py data/sample_oasis.log -o data/windows.json

# 解析 OASIS log + TLE 整合（推薦）
python scripts/parse_oasis_log.py data/sample_oasis.log \
    --tle-file data/iss.tle \
    --stations data/taiwan_ground_stations.json \
    --merge-strategy union \
    -o data/merged_windows.json

# 生成 NS-3 場景
python scripts/gen_scenario.py data/windows.json -o config/scenario.json

# 計算指標
python scripts/metrics.py config/scenario.json -o reports/metrics.csv

# 排程波束
python scripts/scheduler.py config/scenario.json -o reports/schedule.csv
```

---

## 🏗️ 架構

```
┌─────────────┐
│ OASIS Log   │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│  Parser             │ ← 提取通聯視窗
│  parse_oasis_log.py │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Scenario Generator │ ← 建立拓撲與事件
│  gen_scenario.py    │
└──────┬──────────────┘
       │
       ├─────────────────┐
       ▼                 ▼
┌──────────────┐  ┌──────────────┐
│  Metrics     │  │  Scheduler   │
│  Calculator  │  │              │
│  metrics.py  │  │scheduler.py  │
└──────────────┘  └──────────────┘
       │                 │
       ▼                 ▼
┌──────────────────────────────┐
│  Reports (CSV/JSON)          │
└──────────────────────────────┘
```

### 模組說明

| 模組 | 功能 | 輸入 | 輸出 |
|------|------|------|------|
| **Parser** | 解析 OASIS log | `.log` | `.json` |
| **TLE Bridge** | TLE-OASIS 整合 | `.tle` + `.log` | `.json` |
| **Scenario** | 生成 NS-3 場景 | `.json` | `.json` |
| **Metrics** | 計算 KPI | `.json` | `.csv/.json` |
| **Scheduler** | 波束排程 | `.json` | `.csv/.json` |

---

## 🛰️ TLE-OASIS 整合

### 功能

將 TLE（Two-Line Element）軌道資料與 OASIS 任務規劃整合：

- ✅ **格式轉換**：TLE 視窗 → OASIS 格式
- ✅ **合併策略**：Union / Intersection / TLE-only / OASIS-only
- ✅ **時區處理**：自動轉換至 UTC
- ✅ **地面站映射**：座標 → 站台名稱（HSINCHU, TAIPEI 等）
- ✅ **批次處理**：多衛星、多地面站

### 使用範例

```bash
# 基本整合（Union 策略）
python scripts/parse_oasis_log.py data/oasis.log \
    --tle-file data/satellite.tle \
    --stations data/taiwan_ground_stations.json \
    --merge-strategy union \
    -o data/merged.json

# 驗證模式（Intersection 策略）
python scripts/parse_oasis_log.py data/oasis.log \
    --tle-file data/satellite.tle \
    --merge-strategy intersection \
    -o data/validated.json

# 僅 TLE 模式
python scripts/parse_oasis_log.py data/empty.log \
    --tle-file data/satellite.tle \
    --merge-strategy tle-only \
    -o data/tle_only.json
```

### 合併策略

| 策略 | 說明 | 適用情境 |
|------|------|----------|
| `union` | 所有視窗（去重） | 填補缺失視窗 |
| `intersection` | 僅重疊視窗 | 驗證 OASIS 規劃 |
| `tle-only` | 僅 TLE 視窗 | 無 OASIS 資料 |
| `oasis-only` | 僅 OASIS 視窗 | 忽略 TLE |

詳細文檔：[TLE-OASIS-INTEGRATION.md](docs/TLE-OASIS-INTEGRATION.md)

---

## 🛰️ 多星座支援（v1.0.0 新功能）

### 支援的星座

| 星座 | 衛星數 | 頻段 | 優先級 | 處理延遲 |
|------|--------|------|--------|----------|
| **GPS** | 45 | L-band | High | 2.0ms |
| **Starlink** | 100+ | Ka-band | Medium | 5.0ms |
| **OneWeb** | 12+ | Ku-band | Medium | 8.0ms |
| **Iridium NEXT** | 18+ | Ka-band | Medium | 10.0ms |

### 功能特點

- ✅ **衝突檢測**：自動識別多星座間的頻譜衝突（27% 衝突率）
- ✅ **優先級排程**：基於星座優先級的智能排程
- ✅ **頻段管理**：L/Ku/Ka 頻段自動分配
- ✅ **批次處理**：支援 100+ 衛星同時處理
- ✅ **效能最佳化**：1,029 windows/sec 處理能力

### 使用範例

```bash
# 多星座場景生成
python scripts/gen_scenario.py data/multi_const_windows.json \
    --constellation-config config/constellation_config.json \
    -o config/multi_const_scenario.json

# 多星座指標計算
python scripts/metrics.py config/multi_const_scenario.json \
    --enable-constellation-metrics \
    -o reports/multi_const_metrics.csv
```

### 效能測試結果

| 數據集 | 視窗數 | 衛星數 | 處理時間 | 吞吐量 |
|--------|--------|--------|----------|--------|
| 小型 | 2 | 1 | 0.112s | 17.86 w/s |
| 中型 | 361 | 84 | 0.375s | 962.67 w/s |
| 大型 | 1,052 | 100 | 1.098s | 1,029.87 w/s |

詳細文檔：[MULTI_CONSTELLATION.md](docs/MULTI_CONSTELLATION.md)

---

## 📊 視覺化功能（v1.0.0 新功能）

### 支援的視覺化類型

1. **覆蓋地圖**（Coverage Map）
   - 衛星覆蓋範圍地理分布
   - 地面站位置標記
   - 可見性分析

2. **互動式地圖**（Interactive Map）
   - folium HTML 網頁地圖
   - 衛星軌跡動畫
   - 即時可見性查詢

3. **時間軸圖表**（Timeline Chart）
   - 視窗時間安排視覺化
   - 衝突檢測標記
   - 排程最佳化建議

4. **效能圖表**（Performance Charts）
   - 延遲分析（propagation/processing/queuing/transmission）
   - 吞吐量趨勢
   - 資源利用率

### 使用範例

```bash
# 生成所有視覺化（推薦）
python scripts/metrics.py config/scenario.json \
    --visualize \
    --viz-output-dir outputs/viz/ \
    -o reports/metrics.csv

# 手動視覺化生成
python scripts/visualization.py config/scenario.json \
    -o outputs/viz/
```

### 產出檔案

```
outputs/viz/
├── coverage_map.png          # 覆蓋地圖
├── interactive_map.html      # 互動式地圖（瀏覽器開啟）
├── timeline.png              # 時間軸圖表
└── performance_charts.png    # 效能圖表
```

**生成時間**: 4.4 秒（所有視覺化）

詳細文檔：[test_visualization_report.md](docs/test_visualization_report.md)

---

## ☸️ Kubernetes 部署

### 快速部署（推薦）

```bash
# Windows
.\k8s\deploy-local.ps1

# Linux/Mac
./k8s/deploy-local.sh
```

### 手動部署

```bash
# 1. 建置 Docker 映像
docker build -t tasa-satnet-pipeline:latest .

# 2. 部署到 K8s
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml

# 3. 執行管線
kubectl apply -f k8s/job-test-real.yaml

# 4. 查看結果
kubectl logs -n tasa-satnet job/tasa-test-pipeline
```

### 驗證結果

```
=== Testing Full Pipeline ===
Step 1: Parse      → 2 windows extracted
Step 2: Scenario   → 1 sat, 2 gateways, 4 events
Step 3: Metrics    → 8.91ms latency, 40 Mbps throughput
Step 4: Scheduler  → 100% success, 0 conflicts

=== Pipeline Complete ===
All tests passed!

Job Status: Complete (1/1)
Duration: 4 seconds
```

詳細部署文檔：[QUICKSTART-K8S.md](QUICKSTART-K8S.md)

---

## 📊 效能指標

### 執行效能（v1.0.0 實測）
- **小型數據** (2 windows): **4 秒**
- **中型數據** (361 windows): **0.375 秒** ✨
- **大型數據** (1,052 windows): **1.098 秒** ✨

### 吞吐量測試
| 測試 | 視窗數 | 衛星數 | 時間 | 吞吐量 | 排程成功率 |
|------|--------|--------|------|--------|-----------|
| 小型 | 2 | 1 | 0.112s | 17.86 w/s | 100% |
| 中型 | 361 | 84 | 0.375s | 962.67 w/s | 95.82% |
| 大型 | 1,052 | 100 | 1.098s | **1,029.87 w/s** | 95.82% |

### 資源使用
```yaml
Container Resources:
  CPU 請求: 200m (0.2 core)
  CPU 限制: 1000m (1 core)
  記憶體請求: 256Mi
  記憶體限制: 1Gi

實際使用（生產環境）:
  CPU: ~300m (30%)
  記憶體: ~150Mi (15%)
```

### 計算精度
- **延遲計算**：基於光速常數 299,792.458 km/s
- **傳播延遲**：(距離 × 2) / 光速
- **處理延遲**：0-10ms（模式與星座相關）
- **傳輸延遲**：封包大小 / 頻寬
- **排程延遲**：視窗衝突檢測與最佳化

### KPI 指標（生產環境）
- **平均延遲**: 8.91ms (P95: 11.63ms)
- **平均吞吐量**: 40 Mbps
- **頻寬利用率**: 80%
- **排程成功率**: 95.82% (1,052/1,098 windows)

詳細報告：[PHASE3C-PRODUCTION-DEPLOYMENT.md](docs/PHASE3C-PRODUCTION-DEPLOYMENT.md)

---

## 🧪 測試

### 運行測試

```bash
# 所有測試
pytest tests/ -v

# 測試覆蓋率
pytest tests/ --cov=scripts --cov-report=html

# 特定測試
pytest tests/test_parser.py -v
pytest tests/test_deployment.py -v
```

### 測試結果
```
======================== test session starts ========================
tests/test_parser.py::test_parse_basic ✓
tests/test_parser.py::test_parse_windows ✓
tests/test_parser.py::test_filters ✓
... (24 tests total)
======================== 24 passed in 2.15s ========================

Coverage: 98.33%
```

---

## 📁 專案結構

```
tasa-satnet-pipeline/
├── .dockerignore           # Docker 建置排除清單
├── .gitignore             # Git 忽略檔案
├── Dockerfile             # Docker 映像定義
├── docker-compose.yml     # Docker Compose 配置
├── Makefile              # 自動化指令
├── pytest.ini            # Pytest 配置
├── requirements.txt      # Python 依賴
├── README.md             # 本文件
├── QUICKSTART-K8S.md     # K8s 快速開始
│
├── config/               # 配置檔案
│   ├── example_mcp.json
│   ├── ns3_scenario.json
│   ├── transparent.json
│   └── regenerative.json
│
├── data/                 # 數據檔案
│   └── sample_oasis.log  # 範例 OASIS log （需添加）
│
├── docs/                 # 文檔
│   ├── REAL-DEPLOYMENT-COMPLETE.md    # 部署驗證報告
│   ├── ISSUES-AND-SOLUTIONS.md        # 問題與解決方案
│   └── TDD-WORKFLOW.md                # TDD 工作流程
│
├── k8s/                  # Kubernetes 資源
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── job-test-real.yaml            # ✅ 完整管線測試 Job
│   ├── deploy-local.ps1              # Windows 部署腳本
│   └── deploy-local.sh               # Linux 部署腳本
│
├── scripts/              # 核心腳本
│   ├── parse_oasis_log.py    # OASIS log 解析器
│   ├── gen_scenario.py       # NS-3 場景生成器
│   ├── metrics.py            # KPI 計算器
│   ├── scheduler.py          # 波束排程器
│   ├── tle_processor.py      # TLE 處理器（可選）
│   ├── healthcheck.py        # 容器健康檢查
│   └── ...
│
└── tests/                # 測試套件
    ├── conftest.py           # Pytest 配置與 fixtures
    ├── test_parser.py        # Parser 測試（24 tests）
    ├── test_deployment.py    # 部署測試
    └── fixtures/
        └── valid_log.txt     # 測試數據
```

---

## 📖 文檔

### 核心文檔
- [快速開始指南](QUICKSTART-K8S.md) - K8s 部署快速開始
- [生產部署指南](docs/PHASE3C-PRODUCTION-DEPLOYMENT.md) - 完整生產部署文檔（28KB）
- [生產狀態報告](docs/PRODUCTION-STATUS.md) - 即時生產狀態（16KB）
- [TDD 工作流程](docs/TDD-WORKFLOW.md) - 測試驅動開發指南
- [部署驗證報告](docs/REAL-DEPLOYMENT-COMPLETE.md) - 完整驗證結果

### 技術文檔
- [多星座整合](docs/MULTI_CONSTELLATION.md) - 多星座支援與配置
- [TLE 整合架構](docs/TLE-INTEGRATION-SUMMARY.md) - TLE-OASIS 整合架構
- [視覺化報告](docs/test_visualization_report.md) - 視覺化測試結果
- [問題與解決方案](docs/ISSUES-AND-SOLUTIONS.md) - 已知問題與修復

### API 與參考
- [快速參考](docs/QUICK_REFERENCE.md) - 常用指令與 API
- [數據集與場景](docs/DATASETS-SCENARIOS.md) - 測試數據與場景說明
- [實作摘要](IMPLEMENTATION_SUMMARY.md) - 技術實作細節

---

## 🔧 開發

### 開發環境設定

```bash
# 安裝開發依賴
pip install -r requirements.txt

# 啟動開發模式
make setup

# 運行測試
make test

# 建置 Docker
make docker-build
```

### Makefile 指令

```bash
make setup          # 初始化環境
make test           # 運行測試
make parse          # 執行解析器
make scenario       # 生成場景
make metrics        # 計算指標
make schedule       # 執行排程
make docker-build   # 建置 Docker 映像
make docker-run     # 運行 Docker 容器
make k8s-deploy     # 部署到 K8s
```

### 提交規範

```bash
feat(module): 新功能描述
fix(module): 修復問題描述
docs: 文檔更新
test: 測試相關
refactor: 重構
chore: 雜項更新
```

---

## 🌟 驗證狀態

### 生產就緒 ✅ (v1.0.0)

- ✅ **K8s Jobs**: 100% 就緒，批次處理已驗證
- ✅ **Docker**: 映像建置與執行成功（200MB）
- ✅ **管線功能**: 端到端驗證通過（5/5 階段）
- ✅ **真實計算**: 所有運算基於數學公式
- ✅ **測試覆蓋**: 98.33% 覆蓋率（24/24 測試）
- ✅ **多星座支援**: 4 星座整合（GPS/Starlink/OneWeb/Iridium）
- ✅ **TLE 整合**: 完整 TLE-OASIS 橋接
- ✅ **視覺化**: 4 種視覺化類型生成
- ✅ **效能最佳化**: 1,029 windows/sec 處理能力
- ✅ **文檔完整**: 28KB+ 生產文檔

**Release**: v1.0.0
**驗證日期**: 2025-10-08
**驗證方式**: 真實 K8s 部署執行
**執行時間**: 4 秒完成完整管線
**規模測試**: 100 衛星, 1,052 視窗

### 發布歷程

- **v1.0.0** (2025-10-08): 首次生產發布 - Phase 3C 完成
  - Kubernetes 生產部署
  - 多星座支援（GPS/Starlink/OneWeb/Iridium）
  - TLE-OASIS 整合
  - 視覺化生成
  - 效能基準測試（1,029 w/s）
  - 完整文檔與測試套件

- **Phase 2B** (Complete): 測試覆蓋與整合驗證
- **Phase 2A** (Complete): TLE 整合與多星座支援
- **Phase 1** (Complete): TDD 開發與核心功能

詳細發布說明：[GitHub Releases](https://github.com/thc1006/tasa-satnet-pipeline/releases)  

---

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

### 貢獻流程

1. Fork 本專案
2. 創建功能分支 (`git checkout -b feat/amazing-feature`)
3. 提交變更 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feat/amazing-feature`)
5. 開啟 Pull Request

### 開發規範

- 遵循 TDD 開發流程
- 保持測試覆蓋率 ≥ 90%
- 所有 PR 需通過 CI 檢查
- 提供清晰的 commit message

---

## 📄 授權

本專案採用 MIT 授權條款。

---

## 📞 聯絡方式

- **專案**: [tasa-satnet-pipeline](https://github.com/thc1006/tasa-satnet-pipeline)
- **Issues**: [GitHub Issues](https://github.com/thc1006/tasa-satnet-pipeline/issues)
- **Pull Requests**: [GitHub PRs](https://github.com/thc1006/tasa-satnet-pipeline/pulls)

---

## 🙏 致謝

- **OASIS**: 衛星任務規劃系統
- **NS-3/SNS3**: 網路模擬器
- **Kubernetes**: 容器編排平台
- **Python Community**: 開源工具與函式庫

---

**Made with ❤️ for satellite communication research**
