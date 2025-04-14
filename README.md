
#  YOLO + MediaPipe 跌倒偵測系統

## 🧩 系統架構

本系統由三個主要組件組成：

### 1. **`sender.py`**（執行於樹莓派）：
   - 透過 USB 攝影機擷取即時影像
   - 將影像壓縮為 JPEG 後透過 TCP 傳送至虛擬機（後端）

### 2. **`backend_server.py`**（執行於虛擬機）：
   - 接收來自樹莓派的影像並進行儲存與分析
   - 呼叫 YOLOv8 + MediaPipe 模型進行跌倒判斷
   - 提供即時影像與跌倒狀態的網頁顯示（Flask）
     
### Socket 程式設計
- **TCP Socket 傳輸:**  
  利用 Python 的 `socket` 模組建立點對點連線。樹莓派端在傳輸影像前，先以固定長度（4 bytes）的方式傳送資料大小，再傳送實際的 JPEG 影像資料。  
- **錯誤處理與重試機制:**  
  當連線或資料傳輸中斷，程式能立即釋放相關資源並重試連線，確保整個系統具有高度的容錯性與連續性。

### Flask 與多執行緒
- **Flask Web 伺服器:**  
  虛擬機端建立簡單的 HTTP 伺服器，用於即時影像串流與網頁前端顯示。  
- **多執行緒處理:**  
  結合 Python `threading` 模組，讓 Socket 伺服器與 Flask 服務能夠並行運作；使用 threading Lock 保護全域影像資料，防止資料競爭與不一致性問題。

### 設定覆蓋網路 (Tailscale)
- Tailscale 提供了一種簡單且安全的方式在多個裝置之間建立覆蓋網路，讓跨網段通訊更為便捷。

### 3. **`fall_detection.py`**：
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

### YOLO 物件偵測

- **作用：**
  - 利用 YOLO v8 模型檢測影像中是否存在「person」，並鎖定目標區域。
  - 檢測結果會回傳各類物件的標籤與邊界框資訊。

- **使用方式：**
  - 輸入完整影像，模型返回所有檢測到的物件及其邊界框（例如：x1, y1, x2, y2）。
  - 在跌倒偵測中，當判定目標為「person」時，從該區域裁切影像以進行後續的關鍵點提取。

### MediaPipe Pose 姿勢估算

- **作用：**
  - 在 YOLO 檢測到的「person」區域內使用 MediaPipe Pose 提取人體的主要關鍵點（landmarks）。

- **使用方式：**
  - 對裁切後的人物圖像進行顏色空間轉換，輸入 MediaPipe 模型。
  - 取得的 landmarks 包含頭部、肩膀、臀部、腳踝、腿部等部位的 (x, y) 位置及可信度（visibility）。
  - 為避免單幀檢測不準確，系統使用滑動窗口平滑 (Sliding Window Average) 技術對關鍵點位置進行平滑處理。


## 跌倒分數計算

### 基本邏輯

根據提取到的平滑後的 landmarks，系統主要從三個面向計算跌倒分數：

1. **頭部與腳踝高度差 (score_head)**
2. **軀幹傾斜角 (score_torso)**
3. **腿部角度 (score_leg)**

每個部分經過線性轉換後，分別乘以權重，最後加權平均得到整體跌倒分數。

### 詳細計算步驟

#### 1. 頭部與腳踝高度差 (score_head)
- **資料來源：**
  - 使用 `landmarks[0].y` 表示頭部位置，使用 `landmarks[27].y` 與 `landmarks[28].y`（左右腳踝）計算其平均值。
- **計算方式：**
  - 計算高度差：
    `head_ankle_diff = ((landmarks[27].y + landmarks[28].y) / 2) - landmarks[0].y`
  - 若高度差小於一定值（經過扣除0.1），使用線性比例轉換，並由 `1.0 -` 此比例得到得分：
    `score_head = 1.0 - clamp((head_ankle_diff - 0.1) / 0.4, 0.0, 1.0)`
  - 當人物趴下或跌倒時，頭部與腳踝的高度差會顯著減少，使得該分數增高。

#### 2. 軀幹傾斜角 (score_torso)
- **資料來源：**
  - 使用左右肩膀（landmarks 11 與 12）計算肩部中心，
  - 使用左右臀部（landmarks 23 與 24）計算臀部中心。
- **計算方式：**
  - 計算肩部與臀部中心之間的水平 (dx) 與垂直 (dy) 位移，進而計算出與垂直方向夾角（用 `angle_from_vertical(dx, dy)` 函數返回角度值）。
  - 定義傾斜角：
    - 當角度 ≤ 30° 時，score_torso 為 0（代表較為直立）。
    - 當角度 ≥ 90° 時，score_torso 為 1（代表明顯倒下）。
    - 介於兩者則進行線性插值：
      `score_torso = (deg_torso - 30) / 60.0`

#### 3. 腿部角度 (score_leg)
- **資料來源：**
  - 分別計算左腿（landmarks[25] 與 landmarks[23]）與右腿（landmarks[26] 與 landmarks[24]）與垂直方向的角度。
- **計算方式：**
  - 使用 `angle_from_vertical(dx, dy)` 計算左右腿與垂直方向的角度，取較大值作為代表。
  - 當角度 ≤ 30° 時，score_leg 為 0；當角度 ≥ 90° 時，score_leg 為 1；介於之間則進行線性插值：
    `score_leg = (deg_leg - 30) / 60.0`

#### 4. 綜合跌倒分數 (fall_score)
- **加權平均公式：**
  - 使用權重分別為 0.4（頭部）、0.4（軀幹）與 0.2（腿部）。
  - 最終計算公式：
    `fall_score = 0.4 * score_head + 0.4 * score_torso + 0.2 * score_leg`
  - 當 fall_score 超過預設閾值（如 0.5），則系統將該情況視為跌倒事件。



---------------------------------------------------------------------------------------
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


## 📌 其他說明

- 此系統使用 JPEG 串流方式傳遞影像（非 RTSP/MJPEG），適用於局域網與 Tailscale 虛擬網路
- 若要延伸功能（如紀錄跌倒時間、連接資料庫等），可修改 `fall_warning` 為日誌或觸發 API
