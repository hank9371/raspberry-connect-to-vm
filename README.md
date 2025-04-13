# 樹莓派跌倒偵測專案

本專案利用樹莓派進行攝影機影像捕捉，並透過經 Tailscale VPN 建立的連線，將影像資料傳輸至虛擬機，
進而透過 Flask 網頁伺服器進行即時影像串流顯示。主要目的是提供一個穩定、即時的影像監控與跌倒偵測平台。

## 架構說明

1. **樹莓派端 (sender.py)**  
   - **影像捕捉與處理：** 利用 OpenCV 捕捉攝影機即時影像，並依需求調整尺寸後以 JPEG 格式編碼。  
   - **網路傳輸：** 透過 TCP Socket 傳送前先封裝影像的長度，再送出 JPEG 影像資料；整體設計具備重試連線與錯誤處理機制。

2. **虛擬機端 (backend_server.py)**  
   - **影像接收：** 以獨立線程啟動 Socket 伺服器接收樹莓派傳送的資料，使用獨立的 `recvall()` 函數保證資料完整性。  
   - **網頁串流服務：** 結合 Flask 與多執行緒技術，提供基於 MJPEG 格式的即時影像串流服務，同時顯示系統時間等輔助資訊。



## 所用技術

### Python 與 OpenCV
- **Python 3:**  
  作為主要的開發語言，提供簡潔且高效的程式撰寫環境。  
- **OpenCV:**  
  負責影像擷取、尺寸調整及 JPEG 編碼；透過 `cv2.VideoCapture` 及 `cv2.imencode` 完成影像處理流程，並在樹莓派端有效降低頻寬使用量。

### Socket 程式設計
- **TCP Socket 傳輸:**  
  利用 Python 的 `socket` 模組建立點對點連線。樹莓派端在傳輸影像前，先以固定長度（4 bytes）的方式傳送資料大小，再傳送實際的 JPEG 影像資料。  
- **錯誤處理與重試機制:**  
  當連線或資料傳輸中斷，程式能立即釋放相關資源並重試連線，確保整個系統具有容錯性與連續性。

### Flask 與多執行緒
- **Flask Web 伺服器:**  
  虛擬機端建立簡單的 HTTP 伺服器，用於即時影像串流與網頁前端顯示。  
- **多執行緒處理:**  
  結合 Python `threading` 模組，讓 Socket 伺服器與 Flask 服務能夠並行運作；使用 threading Lock 保護全域影像資料，防止資料競爭與不一致性問題。

### 設定覆蓋網路 (Tailscale)
- Tailscale 提供了一種簡單且安全的方式在多個裝置之間建立覆蓋網路，讓跨網段通訊更為便捷。

## 優化重點

- **模組化設計：**  
  將影像尺寸調整及資料接收封裝成獨立函數 (`resize_frame` 與 `recvall`)，提升程式碼可讀性及維護性。

- **錯誤處理與重連機制：**  
  增加例外處理機制與重連邏輯，確保在連線失敗或攝影機錯誤時能自動回收資源並重試。

- **線程安全處理：**  
  使用 threading Lock 保護全域最新影像資料，確保多線程環境下資料不會競爭衝突。

- **簡化資料接收流程：**  
  利用 `recvall()` 函數確保接收固定長度資料，減少原有多重循環邏輯，穩定性更高。

## 使用方法

1. **環境建置：**  
   - 確認已安裝 Python 3 與 opencv,flask。  
   - 安裝所需套件：  
     ```
     pip install opencv-python flask
     ```

2. **設定 Tailscale IP：**  
   - 在 `sender.py` 與 `backend_server.py` 中，確認 `SERVER_IP` (或 `vm_tailscale_ip`) 已正確設定為虛擬機的 Tailscale IP。
     
3. **安裝 Tailscale 客戶端:**
  - 開啟終端機，執行以下命令來添加 Tailscale 的 GPG 金鑰和 APT 倉庫源。

 ```
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/$(lsb_release -cs).noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/tailscale-archive-keyring.gpg] https://pkgs.tailscale.com/stable/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/tailscale.list
 ```
  - 啟動並認證 Tailscal
  - 獲取虛擬機的 Tailscale IP:

 ```
sudo apt-get install tailscale -y
sudo tailscale up
tailscale ip -4
  ```
 
**啟動程式：**  

   - 透過瀏覽器訪問 `http://[虛擬機Tailscale IP]:5000` 以觀看即時影像。

## 結語

本專案透過模組化設計、錯誤處理以及多線程配合，提供了一個穩定、高效、易於維護的影像傳輸與串流平臺。未來可進一步結合跌倒偵測演算法，將智慧型影像監控應用於安全監控與健康管理領域。
