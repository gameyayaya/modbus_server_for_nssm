import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QCheckBox)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from pyModbusTCP.client import ModbusClient

# 掃描線程
class ScanThread(QThread):
    result_sig = Signal(list)
    error_sig = Signal(str)

    def __init__(self, ip, port, start_addr, count):
        super().__init__()
        self.ip = ip
        self.port = port
        self.start_addr = start_addr
        self.count = count

    def run(self):
        # 建立 Client，縮短 timeout 避免介面等待過久
        client = ModbusClient(host=self.ip, port=self.port, auto_open=True, timeout=0.8)
        
        try:
            regs = client.read_holding_registers(self.start_addr, self.count)
            if regs:
                data = []
                for i in range(len(regs)):
                    data.append((self.start_addr + i, regs[i]))
                self.result_sig.emit(data)
            else:
                self.error_sig.emit("讀取超時或地址錯誤")
        except Exception as e:
            self.error_sig.emit(f"連線異常: {str(e)}")
        finally:
            client.close()

class ModbusLiveScanner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modbus 即時監測 (修正版)")
        self.setMinimumSize(750, 600)
        
        # 核心元件
        self.scan_thread = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.start_scan)
        
        self.setup_ui()
        self.init_style()

    def init_style(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #0d1117; }
            QLabel { color: #8b949e; }
            QLineEdit { background-color: #161b22; color: #58a6ff; border: 1px solid #30363d; padding: 5px; }
            QPushButton { background-color: #238636; color: white; border-radius: 4px; font-weight: bold; }
            QTableWidget { background-color: #0d1117; color: #c9d1d9; gridline-color: #30363d; }
            QCheckBox { color: #58a6ff; }
        """)

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # 配置列
        cfg_layout = QHBoxLayout()
        self.txt_ip = QLineEdit("127.0.0.1")
        self.txt_port = QLineEdit("502")
        self.txt_start = QLineEdit("9900")
        self.txt_count = QLineEdit("10")
        
        for l, w in [("IP:", self.txt_ip), ("Port:", self.txt_port), ("起始:", self.txt_start), ("數量:", self.txt_count)]:
            cfg_layout.addWidget(QLabel(l))
            cfg_layout.addWidget(w)
        layout.addLayout(cfg_layout)

        # 控制列
        ctrl_layout = QHBoxLayout()
        self.btn_manual = QPushButton("手動單次掃描")
        self.btn_manual.clicked.connect(self.start_scan)
        ctrl_layout.addWidget(self.btn_manual)

        self.chk_auto = QCheckBox("每秒自動刷新")
        self.chk_auto.toggled.connect(self.toggle_timer)
        ctrl_layout.addWidget(self.chk_auto)
        layout.addLayout(ctrl_layout)

        self.lbl_status = QLabel("狀態: 待機")
        layout.addWidget(self.lbl_status)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["地址", "數值"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    def toggle_timer(self, checked):
        if checked:
            self.timer.start(1000)
            self.btn_manual.setEnabled(False)
            self.lbl_status.setText("狀態: 自動模式")
        else:
            self.timer.stop()
            self.btn_manual.setEnabled(True)
            self.lbl_status.setText("狀態: 已停止")

    def start_scan(self):
        # 檢查是否已有線程正在跑，防止堆疊
        if self.scan_thread and self.scan_thread.isRunning():
            return

        try:
            ip = self.txt_ip.text()
            port = int(self.txt_port.text())
            start = int(self.txt_start.text())
            count = int(self.txt_count.text())

            # 建立並啟動線程
            self.scan_thread = ScanThread(ip, port, start, count)
            self.scan_thread.result_sig.connect(self.update_ui)
            self.scan_thread.error_sig.connect(lambda e: self.lbl_status.setText(f"錯誤: {e}"))
            self.scan_thread.start()
        except Exception as e:
            self.lbl_status.setText(f"配置錯誤: {e}")

    def update_ui(self, data):
        # 更新表格內容
        if self.table.rowCount() != len(data):
            self.table.setRowCount(len(data))
            for i, (addr, val) in enumerate(data):
                self.table.setItem(i, 0, QTableWidgetItem(str(addr)))
                self.table.setItem(i, 1, QTableWidgetItem(str(val)))
        else:
            for i, (addr, val) in enumerate(data):
                item = self.table.item(i, 1)
                if item.text() != str(val):
                    item.setText(str(val))
                    item.setForeground(Qt.green) # 有變動變綠色
                else:
                    item.setForeground(Qt.white)
        self.lbl_status.setText(f"狀態: 更新於 {time.strftime('%H:%M:%S')}")

import time
if __name__ == "__main__":
    # 解決 Server 閃退關鍵：強制使用軟體渲染
    os.environ["QT_QUICK_BACKEND"] = "software"
    os.environ["QT_OPENGL"] = "software"

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ModbusLiveScanner()
    window.show()
    sys.exit(app.exec())