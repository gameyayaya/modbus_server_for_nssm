"""
================================================================================
Modbus TCP Server - Windows Server 無人值守專業版
================================================================================
版本: 1.5 (IT 運維強化版)
適用環境: Windows Server 2016 / 2019 / 2022 / Win10 / Win11
日誌路徑: C:\\modbus_server_log\\service_log.txt

------------------------------- Holding Register 点表 (4x) -----------------------
位址 (Address) | 說明 (Description)              | 單位/範圍      | IT 運維用途
--------------------------------------------------------------------------------
9900-9905      | 系統 年/月/日/時/分/秒           | 數值          | 時間同步檢查
9906           | 心跳信號 (Heartbeat)             | 0 / 1 切換    | 服務存活監測
9907-9908      | 服務運行時間 (Uptime)            | 秒 (32-bit)   | 判斷是否重啟過
9909           | C 槽剩餘空間 (Disk Free)         | GB            | 磁碟滿溢預警
9910           | 目前 TCP 連線數 (Clients)        | 個            | 通訊負載監測
9911           | CPU 使用率 (CPU Usage)          | %             | 效能監控
9912           | RAM 使用率 (RAM Usage)          | %             | 記憶體壓力
9913           | 可用實體記憶體 (Free RAM)        | MB            | IT 資產監控
9914           | 系統句柄數 (Handle Count)        | 個            | 判斷資源洩漏(Leak)
9915           | 主網卡 IP 末碼 (IP Last Byte)    | 0-255         | 快速識別主機
--------------------------------------------------------------------------------
9920           | 遠端控制指令 (Remote Command)    | 999:清日誌     | 遠端維護
================================================================================
"""

import time
import sys
import logging
import os
import psutil
import socket
import ctypes
from datetime import datetime
from threading import Thread
from pyModbusTCP.server import ModbusServer

# --- 環境配置 ---
LOG_DIR = r"C:\modbus_server_log"
LOG_FILE = os.path.join(LOG_DIR, "service_log_port502.txt")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE, 
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s', 
    encoding='utf-8'
)

def get_ip_last_byte():
    """獲取主網卡 IP 的最後一個位元組"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return int(ip.split('.')[-1])
    except:
        return 0

class ServerMonitorService:
    def __init__(self):
        self.server = ModbusServer(host="0.0.0.0", port=502, no_block=True)
        self.start_time = time.time()
        self.process = psutil.Process(os.getpid())

    def update_loop(self):
        hb = 0
        logging.info("IT 監控線程啟動，開始監測系統資源...")
        
        while True:
            try:
                now = datetime.now()
                uptime = int(time.time() - self.start_time)
                
                # IT 運維核心數據
                cpu = int(psutil.cpu_percent(interval=None))
                mem = psutil.virtual_memory()
                disk = psutil.disk_usage('C:')
                
                # 獲取進程 Handle 數 (IT 常用來判斷程式穩不穩定)
                handles = self.process.num_handles()
                
                # 取得 IP 末碼
                ip_byte = get_ip_last_byte()
                
                # 取得連線數
                conns = len(self.server.list_clients()) if hasattr(self.server, 'list_clients') else 0

                # 準備點表數據 (9900 - 9915)
                map_data = [
                    now.year, now.month, now.day, now.hour, now.minute, now.second,
                    0,               # 9906 Heartbeat
                    uptime & 0xFFFF, # 9907
                    (uptime >> 16),  # 9908
                    int(disk.free / (1024**3)), # 9909 GB
                    conns,           # 9910
                    cpu,             # 9911 %
                    int(mem.percent),# 9912 %
                    int(mem.available / (1024**2)), # 9913 MB
                    handles,         # 9914
                    ip_byte          # 9915
                ]
                
                hb = 1 if hb == 0 else 0
                map_data[6] = hb
                
                # 寫入寄存器
                self.server.data_bank.set_holding_registers(9900, map_data)

                # 指令處理
                cmd = self.server.data_bank.get_holding_registers(9920, 1)
                if cmd and cmd[0] == 999:
                    open(LOG_FILE, 'w').close()
                    self.server.data_bank.set_holding_registers(9920, [0])

                time.sleep(1)
            except Exception as e:
                logging.error(f"監控循環異常: {e}")
                time.sleep(2)

    def start(self):
        Thread(target=self.update_loop, daemon=True).start()
        try:
            logging.info("Server 啟動完成。監聽 Port 502。")
            self.server.start()
            while True:
                time.sleep(1)
        except Exception as e:
            logging.error(f"服務崩潰: {e}")
        finally:
            self.server.stop()

if __name__ == "__main__":
    ServerMonitorService().start()