
#  YOLO + MediaPipe 跌倒偵測系統

## 🧩 系統架構

本系統由三個主要組件組成：

1. **`sender.py`**（執行於樹莓派）：
   - 透過 USB 攝影機擷取即時影像
   - 將影像壓縮為 JPEG 後透過 TCP 傳送至虛擬機（後端）

2. **`backend_server.py`**（執行於虛擬機）：
   - 接收來自樹莓派的影像並進行儲存與分析
   - 呼叫 YOLOv8 + MediaPipe 模型進行跌倒判斷
   - 提供即時影像與跌倒狀態的網頁顯示（Flask）

3. **`fall_detection.py`**：
   - 使用 YOLO 模型偵測人
   - 使用 MediaPipe Pose 擷取關鍵點
   - 評估人體姿勢計算 `fall_score`
   - 判定是否跌倒（如超過設定閾值）

## 🗂️ 專案結構

```
.
├── sender.py               # 樹莓派端程式：擷取與傳送攝影機影像
├── backend_server.py       # 虛擬機端程式：接收影像、提供前端頁面與 API
├── fall_detection.py       # 影像分析模組：YOLO + MediaPipe + 跌倒判斷
└── yolov8n.pt              # 預訓練 YOLOv8 模型檔（需自行放置）
```

## 🔧 安裝套件

### 後端（Ubuntu 虛擬機）

```bash
pip install flask opencv-python numpy ultralytics mediapipe
```

### 樹莓派端（Sender）

```bash
pip install opencv-python
```

## 🚀 啟動方式

### 1. 樹莓派端：`sender.py`

```bash
python3 sender.py
```

請確認 `SERVER_IP` 為虛擬機的 Tailscale IP（如 `100.77.77.70`）

### 2. 虛擬機端：`backend_server.py`

```bash
python3 backend_server.py
```

執行後會啟動 Flask 網頁伺服器與 Socket 接收器

## 🌐 查看即時影像與跌倒狀態

- 開啟瀏覽器輸入：
  
  ```
  http://<虛擬機 Tailscale IP>:5000
  ```

- 頁面內容包括：
  - 樹莓派傳送來的即時影像
  - `Fall Score` 與偵測邊框
  - 即時更新的跌倒狀態文字提示

## ⚠️ 跌倒判斷邏輯

- **評分項目：**
  1. 頭部與腳踝的高度差
  2. 軀幹傾斜角度
  3. 腿部垂直角度

- **綜合評分 (`fall_score`)**：
  ```text
  fall_score = 0.4 * 頭部 + 0.4 * 軀幹 + 0.2 * 腿部
  ```

- **跌倒閾值**：
  - 若 `fall_score > 0.5`，即視為發生跌倒

## 📦 資源準備

- 確保下載並放置 `yolov8n.pt` 模型到指定位置：
  ```
  /home/tku-im-sd/backend_project/yolov8n.pt
  ```
- 若需替換模型路徑，請在 `fall_detection.py` 修改 `YOLO_MODEL_PATH`

## 📌 其他說明

- 此系統使用 JPEG 串流方式傳遞影像（非 RTSP/MJPEG），適用於局域網與 Tailscale 虛擬網路
- 若要延伸功能（如紀錄跌倒時間、連接資料庫等），可修改 `fall_warning` 為日誌或觸發 API
