"""
Modern Binary Diff Tool GUI
现代化的二进制差分工具图形界面
"""

import sys
import os
import subprocess
import requests
import json
import shutil
import sqlite3
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QGroupBox,
    QFormLayout, QCheckBox, QMessageBox, QComboBox, QProgressBar,
    QTextEdit, QScrollArea, QFrame, QListWidget, QAbstractItemView, QListWidgetItem,
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import QThread, Signal, Qt, QUrl, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import (QIcon, QDesktopServices, QColor, QPalette, QFont,
                           QPainter, QLinearGradient, QPen, QBrush, QPainterPath)
import time

# ============================================================================
# 现代化样式表定义
# ============================================================================

MODERN_STYLE = """
/* 主窗口样式 */
QMainWindow {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #f5f7fa,
        stop:1 #e8ecf1
    );
}

/* 滚动区域样式 */
QScrollArea {
    border: none;
    background: transparent;
}

/* 分组框样式 - 现代卡片设计 */
QGroupBox {
    background: white;
    border: none;
    border-radius: 12px;
    margin-top: 20px;
    padding: 20px;
    font-size: 13px;
    font-weight: 500;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 8px 12px;
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #667eea,
        stop:1 #764ba2
    );
    color: white;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    margin-left: 10px;
}

/* 输入框样式 */
QLineEdit {
    background: #f8f9fa;
    border: 2px solid #e9ecef;
    border-radius: 8px;
    padding: 10px 15px;
    font-size: 13px;
    color: #495057;
    selection-background-color: #667eea;
}

QLineEdit:focus {
    border: 2px solid #667eea;
    background: white;
}

QLineEdit:hover {
    border: 2px solid #764ba2;
}

/* 按钮样式 - 主按钮 */
QPushButton {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #667eea,
        stop:1 #764ba2
    );
    color: white;
    border: none;
    border-radius: 8px;
    padding: 12px 24px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #5568d3,
        stop:1 #6a3f8f
    );
}

QPushButton:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #4a5bc4,
        stop:1 #5e3880
    );
}

QPushButton:disabled {
    background: #ced4da;
    color: #6c757d;
}

/* 次要按钮样式 */
QPushButton[class="secondary"] {
    background: white;
    color: #667eea;
    border: 2px solid #667eea;
}

QPushButton[class="secondary"]:hover {
    background: #f0f2ff;
}

/* 成功按钮样式 */
QPushButton[class="success"] {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #56ab2f,
        stop:1 #a8e063
    );
}

QPushButton[class="success"]:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #4a9628,
        stop:1 #95c956
    );
}

/* 文件浏览按钮样式 */
QPushButton[class="file"] {
    background: #6c757d;
    min-width: 100px;
}

QPushButton[class="file"]:hover {
    background: #5a6268;
}

/* 下拉框样式 */
QComboBox {
    background: white;
    border: 2px solid #e9ecef;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    min-width: 100px;
}

QComboBox:hover {
    border: 2px solid #667eea;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #667eea;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background: white;
    border: 2px solid #667eea;
    border-radius: 8px;
    padding: 5px;
    selection-background-color: #667eea;
    selection-color: white;
}

/* 复选框样式 */
QCheckBox {
    font-size: 13px;
    color: #495057;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border: 2px solid #ced4da;
    border-radius: 6px;
    background: white;
}

QCheckBox::indicator:hover {
    border: 2px solid #667eea;
}

QCheckBox::indicator:checked {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #667eea,
        stop:1 #764ba2
    );
    border: 2px solid #667eea;
}

QCheckBox::indicator:checked:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #5568d3,
        stop:1 #6a3f8f
    );
    border: 2px solid #4a5bc4;
}

/* 进度条样式 */
QProgressBar {
    background: #e9ecef;
    border: none;
    border-radius: 10px;
    height: 20px;
    text-align: center;
    font-size: 12px;
    font-weight: 600;
    color: white;
}

QProgressBar::chunk {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #667eea,
        stop:1 #764ba2
    );
    border-radius: 10px;
}

/* 文本编辑器样式 */
QTextEdit {
    background: #f8f9fa;
    border: 2px solid #e9ecef;
    border-radius: 8px;
    padding: 12px;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 12px;
    color: #495057;
}

/* 列表样式 */
QListWidget {
    background: white;
    border: 2px solid #e9ecef;
    border-radius: 8px;
    padding: 5px;
    font-size: 13px;
}

QListWidget::item {
    padding: 8px;
    border-radius: 6px;
    margin: 2px;
}

QListWidget::item:hover {
    background: #f0f2ff;
}

QListWidget::item:selected {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #667eea,
        stop:1 #764ba2
    );
    color: white;
}

/* 标签样式 */
QLabel {
    color: #495057;
    font-size: 13px;
}

QLabel[class="title"] {
    font-size: 24px;
    font-weight: 700;
    color: #2d3748;
}

QLabel[class="subtitle"] {
    font-size: 14px;
    color: #718096;
}

/* 滚动条样式 */
QScrollBar:vertical {
    background: #f8f9fa;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background: #ced4da;
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #adb5bd;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #f8f9fa;
    height: 12px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background: #ced4da;
    border-radius: 6px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: #adb5bd;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""

# ============================================================================
# 工具函数
# ============================================================================

# 嵌入的checkmark SVG内容
CHECKMARK_SVG = """<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M13.3333 4L6 11.3333L2.66667 8" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

def get_application_path():
    """获取应用程序的基础路径"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def create_checkmark_icon():
    """创建临时的checkmark图标文件，返回文件路径"""
    import tempfile

    # 创建临时文件
    temp_dir = tempfile.gettempdir()
    checkmark_path = os.path.join(temp_dir, "bsdiff_checkmark.svg")

    # 写入SVG内容
    with open(checkmark_path, 'w', encoding='utf-8') as f:
        f.write(CHECKMARK_SVG)

    return checkmark_path

def get_bsdiff_path():
    """获取bsdiff可执行文件的路径"""
    app_path = get_application_path()

    if getattr(sys, 'frozen', False):
        bsdiff_path = os.path.join(app_path, "bsdiff.exe")
    else:
        bsdiff_path = os.path.join(app_path, "bin", "bsdiff.exe")

    if os.path.exists(bsdiff_path):
        return bsdiff_path

    return "bsdiff"

# ============================================================================
# 服务器API客户端
# ============================================================================

class ServerApiClient:
    """Client for interacting with the server API"""
    def __init__(self, server_url, session_cookie=None, proxy=None):
        """Initialize API client"""
        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()
        if session_cookie:
            self.session.cookies.set('session', session_cookie)
        self.local_devices = [
            {'device_id': 'test_device_1', 'name': 'Test Device 1', 'current_version': '1.0.0'},
            {'device_id': 'test_device_2', 'name': 'Test Device 2', 'current_version': '1.0.0'}
        ]

    def get_app_database_devices(self):
        """Get devices from the app database"""
        devices = []
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        app_dir = os.path.join(parent_dir, 'app')
        if not os.path.exists(app_dir):
            app_dir = os.path.join(parent_dir, '..', 'app')
            if not os.path.exists(app_dir):
                return []

        app_db_path = os.path.join(app_dir, 'users.db')
        if os.path.exists(app_db_path):
            try:
                conn = sqlite3.connect(app_db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT device_id FROM devices")
                rows = cursor.fetchall()
                conn.close()

                if rows:
                    for row in rows:
                        device_id = row[0]
                        if not any(d.get('device_id') == device_id for d in devices):
                            devices.append({
                                'device_id': device_id,
                                'name': f'App Device {device_id}',
                                'current_version': '1.0.0'
                            })
                    return devices
            except Exception as e:
                print(f"读取应用数据库时出错: {str(e)}")

        return []

    def upload_patch(self, patch_file_path, old_version, new_version):
        """Upload a patch file to the server"""
        url = f"{self.server_url}/api/patches/upload"
        max_retries = 3
        timeout = 60

        for attempt in range(max_retries):
            try:
                with open(patch_file_path, 'rb') as f:
                    files = {'patch_file': (os.path.basename(patch_file_path), f)}
                    data = {
                        'old_version': old_version,
                        'new_version': new_version
                    }

                    headers = {'User-Agent': 'BSDiff-GUI/1.0'}
                    response = self.session.post(
                        url,
                        files=files,
                        data=data,
                        timeout=timeout,
                        headers=headers,
                        verify=False
                    )

                    if response.status_code == 200:
                        return response.json()
                    else:
                        if attempt < max_retries - 1:
                            time.sleep(2)
                        else:
                            error_message = "请求失败" if response.status_code != 200 else response.json().get('message', '未知错误')
                            raise Exception(f"上传失败 ({response.status_code}): {error_message}")
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    raise Exception(f"上传失败: {str(e)}")

        raise Exception("所有重试尝试均失败")

    def notify_all_devices(self, patch_id):
        """Send OTA notification to all devices"""
        devices = self.get_devices()
        if not devices:
            return {"success": False, "message": "未找到任何设备", "devices": []}

        valid_devices = []
        invalid_devices = []

        for device in devices:
            device_id = device.get('device_id', '')
            user_id = device.get('user_id')

            if not device_id:
                invalid_devices.append(f"设备缺少device_id: {device}")
                continue

            if not user_id or user_id == 'unknown':
                invalid_devices.append(f"设备缺少有效的user_id: {device}")
                continue

            valid_devices.append(device)

        if not valid_devices:
            return {
                "success": False,
                "message": "没有找到具有有效用户ID的设备",
                "invalid_devices": invalid_devices
            }

        device_info_list = []
        for device in valid_devices:
            device_id = device.get('device_id', '')
            user_id = device.get('user_id', 'unknown')
            device_info_list.append({
                'user_id': user_id,
                'device_id': device_id
            })

        url = f"{self.server_url}/api/patches/notify_all"
        data = {
            'patch_id': patch_id,
            'device_info_list': device_info_list
        }

        try:
            response = self.session.post(url, json=data)
            if response.status_code == 200:
                result = response.json()
                return result
            else:
                raise Exception(f"发送通知失败 ({response.status_code})")
        except Exception as e:
            return {
                "success": False,
                "message": f"发送通知时发生错误: {str(e)}",
                "error": str(e)
            }

    def send_ota_notification(self, device_id, patch_id, user_id=None):
        """Send OTA notification to a specific device"""
        url = f"{self.server_url}/api/patches/notify"

        if not user_id or user_id == 'unknown':
            raise Exception(f"无法发送OTA通知: 必须提供有效的用户ID")

        data = {
            'patch_id': patch_id,
            'device_info': {
                'device_id': device_id,
                'user_id': user_id
            }
        }

        response = self.session.post(url, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"发送通知失败 ({response.status_code})")

    def get_devices(self):
        """Get the list of available devices"""
        app_devices = self.get_app_database_devices()
        if app_devices:
            return app_devices

        url = f"{self.server_url}/api/devices"
        try:
            response = self.session.get(url, timeout=5)
            if response.status_code == 200:
                return response.json().get('devices', [])
            return []
        except:
            return []

# ============================================================================
# 现代化卡片组件
# ============================================================================

class ModernCard(QFrame):
    """现代化卡片容器"""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setObjectName("modernCard")
        self.setup_ui(title)
        self.add_shadow()

    def setup_ui(self, title):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        if title:
            title_label = QLabel(title)
            title_label.setProperty("class", "cardTitle")
            title_label.setStyleSheet("""
                font-size: 16px;
                font-weight: 600;
                color: #2d3748;
                padding-bottom: 10px;
                border-bottom: 2px solid #e2e8f0;
            """)
            layout.addWidget(title_label)

        self.content_layout = QVBoxLayout()
        layout.addLayout(self.content_layout)

    def add_shadow(self):
        """添加阴影效果"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

# ============================================================================
# Worker Thread
# ============================================================================

class WorkerThread(QThread):
    """后台工作线程"""
    finished = Signal(bool, str)
    progress = Signal(int)

    def __init__(self, old_file, new_file, patch_file, lzma_params=None, enable_aes=True):
        super().__init__()
        self.old_file = old_file
        self.new_file = new_file
        self.patch_file = patch_file
        self.lzma_params = lzma_params or {}
        self.enable_aes = enable_aes

    def run(self):
        try:
            bsdiff_path = get_bsdiff_path()

            if bsdiff_path == "bsdiff":
                try:
                    which_cmd = "where" if sys.platform == 'win32' else "which"
                    result = subprocess.run([which_cmd, "bsdiff"],
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE,
                                          text=True)

                    if result.returncode != 0:
                        self.finished.emit(False, "错误: 找不到 bsdiff 程序")
                        return
                except Exception as e:
                    self.finished.emit(False, f"错误: 检查 bsdiff 安装时出错: {str(e)}")
                    return

            command = [bsdiff_path, self.old_file, self.new_file, self.patch_file]

            for param_name, param_value in self.lzma_params.items():
                if param_value is not None:
                    command.append(f"-{param_name}")
                    command.append(str(param_value))

            if self.enable_aes:
                command.append("-aes")
                command.append("1")
            else:
                command.append("-aes")
                command.append("0")

            print("执行命令:", " ".join(command))
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                if os.path.exists(self.patch_file) and os.path.getsize(self.patch_file) > 0:
                    self.finished.emit(True, "✓ 补丁生成成功")
                else:
                    self.finished.emit(False, "补丁文件似乎为空或未创建")
            else:
                error_message = stderr.decode('utf-8', errors='ignore') if stderr else "未知错误"
                self.finished.emit(False, f"补丁生成失败: {error_message}")
        except Exception as e:
            self.finished.emit(False, f"操作失败: {str(e)}")

# ============================================================================
# 主窗口类
# ============================================================================

class ModernBinaryDiffGUI(QMainWindow):
    """现代化的二进制差分GUI"""

    def __init__(self):
        super().__init__()
        self.old_file_path = ""
        self.new_file_path = ""
        self.patch_file_path = ""
        self.worker_thread = None

        # 初始化API客户端
        self.api_client = ServerApiClient("http://localhost:5001")

        self.setup_window()
        self.init_ui()

    def setup_window(self):
        """设置窗口属性"""
        self.setWindowTitle("Binary Diff Tool - 现代化界面")
        self.setMinimumSize(900, 800)
        self.resize(1000, 850)

        # 创建checkmark图标文件（嵌入式，打包后也可用）
        checkmark_path = create_checkmark_icon()
        # Qt stylesheet需要使用正斜杠
        checkmark_path = checkmark_path.replace("\\", "/")

        # 应用样式表
        self.setStyleSheet(MODERN_STYLE + f"""
            QFrame#modernCard {{
                background: white;
                border-radius: 12px;
            }}

            QCheckBox::indicator:checked {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea,
                    stop:1 #764ba2
                );
                border: 2px solid #667eea;
                image: url({checkmark_path});
            }}

            QCheckBox::indicator:checked:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #5568d3,
                    stop:1 #6a3f8f
                );
                border: 2px solid #4a5bc4;
                image: url({checkmark_path});
            }}
        """)

    def init_ui(self):
        """初始化UI"""
        # 主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # 主布局
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # 添加标题区域
        self.add_header(main_layout)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 10, 0)
        scroll_layout.setSpacing(20)

        # 添加各个功能区域
        self.add_file_section(scroll_layout)
        self.add_version_section(scroll_layout)
        self.add_lzma_section(scroll_layout)
        self.add_aes_section(scroll_layout)
        self.add_operation_section(scroll_layout)
        self.add_cloud_section(scroll_layout)
        self.add_result_section(scroll_layout)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def add_header(self, layout):
        """添加标题区域"""
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea,
                    stop:1 #764ba2
                );
                border-radius: 12px;
                padding: 25px;
            }
        """)

        header_layout = QVBoxLayout(header_frame)

        title = QLabel("🚀 Binary Diff Tool")
        title.setStyleSheet("""
            font-size: 28px;
            font-weight: 700;
            color: white;
        """)

        subtitle = QLabel("现代化的二进制差分补丁生成工具")
        subtitle.setStyleSheet("""
            font-size: 14px;
            color: rgba(255, 255, 255, 0.9);
            margin-top: 5px;
        """)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        # 添加阴影
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 40))
        header_frame.setGraphicsEffect(shadow)

        layout.addWidget(header_frame)

    def add_file_section(self, layout):
        """添加文件选择区域"""
        card = ModernCard("📁 文件选择")

        # 旧版本文件
        old_file_layout = QHBoxLayout()
        self.old_file_edit = QLineEdit()
        self.old_file_edit.setPlaceholderText("选择旧版本文件...")
        old_file_btn = QPushButton("浏览")
        old_file_btn.setProperty("class", "file")
        old_file_btn.clicked.connect(self.browse_old_file)
        old_file_layout.addWidget(QLabel("旧版本:"))
        old_file_layout.addWidget(self.old_file_edit, 1)
        old_file_layout.addWidget(old_file_btn)

        # 新版本文件
        new_file_layout = QHBoxLayout()
        self.new_file_edit = QLineEdit()
        self.new_file_edit.setPlaceholderText("选择新版本文件...")
        new_file_btn = QPushButton("浏览")
        new_file_btn.setProperty("class", "file")
        new_file_btn.clicked.connect(self.browse_new_file)
        new_file_layout.addWidget(QLabel("新版本:"))
        new_file_layout.addWidget(self.new_file_edit, 1)
        new_file_layout.addWidget(new_file_btn)

        # 补丁文件
        patch_file_layout = QHBoxLayout()
        self.patch_file_edit = QLineEdit()
        self.patch_file_edit.setPlaceholderText("补丁文件保存路径...")
        patch_file_btn = QPushButton("浏览")
        patch_file_btn.setProperty("class", "file")
        patch_file_btn.clicked.connect(self.browse_patch_file)
        patch_file_layout.addWidget(QLabel("补丁文件:"))
        patch_file_layout.addWidget(self.patch_file_edit, 1)
        patch_file_layout.addWidget(patch_file_btn)

        card.content_layout.addLayout(old_file_layout)
        card.content_layout.addLayout(new_file_layout)
        card.content_layout.addLayout(patch_file_layout)

        layout.addWidget(card)

    def add_version_section(self, layout):
        """添加版本信息区域"""
        card = ModernCard("📌 版本信息")

        version_layout = QHBoxLayout()

        self.old_version_edit = QLineEdit()
        self.old_version_edit.setPlaceholderText("例如: 1.0.0")

        self.new_version_edit = QLineEdit()
        self.new_version_edit.setPlaceholderText("例如: 1.1.0")

        version_layout.addWidget(QLabel("旧版本号:"))
        version_layout.addWidget(self.old_version_edit)
        version_layout.addWidget(QLabel("新版本号:"))
        version_layout.addWidget(self.new_version_edit)

        card.content_layout.addLayout(version_layout)

        layout.addWidget(card)

    def add_lzma_section(self, layout):
        """添加LZMA压缩参数区域"""
        card = ModernCard("⚙️ LZMA 压缩参数")

        # 创建网格布局
        grid = QHBoxLayout()

        # 左列
        left_col = QVBoxLayout()

        # 字典大小
        dict_layout = QHBoxLayout()
        dict_layout.addWidget(QLabel("字典大小:"))
        self.dict_size_combo = QComboBox()
        for size_kb in [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]:
            self.dict_size_combo.addItem(f"{size_kb} KB", size_kb)
        self.dict_size_combo.setCurrentIndex(2)  # 默认4KB
        dict_layout.addWidget(self.dict_size_combo)
        left_col.addLayout(dict_layout)

        # lc
        lc_layout = QHBoxLayout()
        lc_layout.addWidget(QLabel("LC (上下文):"))
        self.lc_combo = QComboBox()
        for i in range(9):
            self.lc_combo.addItem(str(i), i)
        self.lc_combo.setCurrentIndex(2)  # 默认2
        lc_layout.addWidget(self.lc_combo)
        left_col.addLayout(lc_layout)

        # lp
        lp_layout = QHBoxLayout()
        lp_layout.addWidget(QLabel("LP (位置):"))
        self.lp_combo = QComboBox()
        for i in range(5):
            self.lp_combo.addItem(str(i), i)
        self.lp_combo.setCurrentIndex(0)  # 默认0
        lp_layout.addWidget(self.lp_combo)
        left_col.addLayout(lp_layout)

        grid.addLayout(left_col, 1)

        # 右列
        right_col = QVBoxLayout()

        # pb
        pb_layout = QHBoxLayout()
        pb_layout.addWidget(QLabel("PB (位数):"))
        self.pb_combo = QComboBox()
        for i in range(5):
            self.pb_combo.addItem(str(i), i)
        self.pb_combo.setCurrentIndex(0)  # 默认0
        pb_layout.addWidget(self.pb_combo)
        right_col.addLayout(pb_layout)

        # fb
        fb_layout = QHBoxLayout()
        fb_layout.addWidget(QLabel("FB (快速):"))
        self.fb_combo = QComboBox()
        for i in [5, 16, 32, 64, 128, 273]:
            self.fb_combo.addItem(str(i), i)
        self.fb_combo.setCurrentIndex(3)  # 默认64
        fb_layout.addWidget(self.fb_combo)
        right_col.addLayout(fb_layout)

        # algo
        algo_layout = QHBoxLayout()
        algo_layout.addWidget(QLabel("算法:"))
        self.algo_combo = QComboBox()
        self.algo_combo.addItem("快速 (0)", 0)
        self.algo_combo.addItem("正常 (1)", 1)
        self.algo_combo.setCurrentIndex(1)
        algo_layout.addWidget(self.algo_combo)
        right_col.addLayout(algo_layout)

        grid.addLayout(right_col, 1)

        card.content_layout.addLayout(grid)

        # EOS标记
        self.eos_checkbox = QCheckBox("写入结束标记 (推荐)")
        self.eos_checkbox.setChecked(True)
        card.content_layout.addWidget(self.eos_checkbox)

        # 重置按钮
        reset_btn = QPushButton("🔄 重置为默认值")
        reset_btn.setProperty("class", "secondary")
        reset_btn.clicked.connect(self.reset_lzma_params)
        card.content_layout.addWidget(reset_btn)

        layout.addWidget(card)

    def add_aes_section(self, layout):
        """添加AES加密选项区域"""
        card = ModernCard("🔐 AES128 加密选项")

        self.aes_encrypt_checkbox = QCheckBox("启用 AES-128-CTR 加密")
        self.aes_encrypt_checkbox.setChecked(True)
        self.aes_encrypt_checkbox.setStyleSheet("font-size: 14px; font-weight: 500;")

        info_label = QLabel("💡 启用后将使用AES-128-CTR对补丁文件进行加密，提高安全性")
        info_label.setStyleSheet("""
            color: #718096;
            font-size: 12px;
            padding: 10px;
            background: #f7fafc;
            border-radius: 6px;
            border-left: 3px solid #667eea;
        """)

        card.content_layout.addWidget(self.aes_encrypt_checkbox)
        card.content_layout.addWidget(info_label)

        layout.addWidget(card)

    def add_operation_section(self, layout):
        """添加操作按钮区域"""
        card = ModernCard()

        btn_layout = QHBoxLayout()

        # 生成按钮
        self.generate_button = QPushButton("🚀 生成补丁")
        self.generate_button.setProperty("class", "success")
        self.generate_button.setMinimumHeight(50)
        self.generate_button.clicked.connect(self.generate_patch)

        # 打开补丁按钮
        self.open_folder_button = QPushButton("📂 打开补丁")
        self.open_folder_button.setMinimumHeight(50)
        self.open_folder_button.setVisible(False)
        self.open_folder_button.clicked.connect(self.open_patch_folder)

        btn_layout.addWidget(self.generate_button, 2)
        btn_layout.addWidget(self.open_folder_button, 1)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("正在生成补丁...")

        card.content_layout.addLayout(btn_layout)
        card.content_layout.addWidget(self.progress_bar)

        layout.addWidget(card)

    def add_cloud_section(self, layout):
        """添加云服务功能区域"""
        card = ModernCard("☁️ 云服务功能 (可选)")

        # 上传到云服务器复选框
        self.upload_checkbox = QCheckBox("生成后上传到云服务器")
        self.upload_checkbox.setChecked(False)
        card.content_layout.addWidget(self.upload_checkbox)

        # 向特定设备发送OTA信息复选框
        self.notify_specific_checkbox = QCheckBox("向特定设备发送OTA信息")
        self.notify_specific_checkbox.setChecked(False)
        card.content_layout.addWidget(self.notify_specific_checkbox)

        # 设备列表提示
        device_hint_label = QLabel("可按住Ctrl或Shift键选择多个设备")
        device_hint_label.setStyleSheet("color: #666; font-size: 12px; margin-top: 5px;")
        card.content_layout.addWidget(device_hint_label)

        # 设备列表
        self.device_list = QListWidget()
        self.device_list.setMinimumHeight(180)
        self.device_list.setMaximumHeight(250)
        self.device_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.device_list.setEnabled(False)
        self.device_list.setAlternatingRowColors(True)
        self.device_list.itemSelectionChanged.connect(self.on_device_selection_changed)
        card.content_layout.addWidget(self.device_list)

        # 刷新设备按钮
        refresh_button_layout = QHBoxLayout()
        self.refresh_devices_button = QPushButton("🔄 刷新设备")
        self.refresh_devices_button.setProperty("class", "secondary")
        self.refresh_devices_button.clicked.connect(self.refresh_devices)
        refresh_button_layout.addStretch()
        refresh_button_layout.addWidget(self.refresh_devices_button)
        card.content_layout.addLayout(refresh_button_layout)

        # 向所有设备发送OTA信息复选框
        self.notify_all_checkbox = QCheckBox("向所有设备发送OTA信息")
        self.notify_all_checkbox.setChecked(False)
        card.content_layout.addWidget(self.notify_all_checkbox)

        # 连接复选框信号
        self.notify_specific_checkbox.stateChanged.connect(self.toggle_device_selector)
        self.notify_all_checkbox.stateChanged.connect(self.toggle_notify_all)

        layout.addWidget(card)

        # 服务器设置卡片
        server_card = ModernCard("🔧 服务器设置")

        # 服务器URL
        server_layout = QHBoxLayout()
        server_label = QLabel("服务器URL:")
        server_label.setMinimumWidth(100)
        self.server_url_combo = QComboBox()
        self.server_url_combo.setEditable(True)
        self.server_url_combo.addItem("http://localhost:5001")
        self.server_url_combo.addItem("http://193.112.247.49:5001")
        self.server_url_combo.addItem("http://ota.eitans.com")
        self.server_url_combo.setCurrentIndex(0)
        self.server_url_combo.currentTextChanged.connect(self.update_server_url)
        self.server_url_edit = self.server_url_combo  # 兼容性别名

        # 测试连接按钮
        self.test_connection_button = QPushButton("测试连接")
        self.test_connection_button.setProperty("class", "secondary")
        self.test_connection_button.setMinimumWidth(100)
        self.test_connection_button.clicked.connect(self.test_server_connection)

        server_layout.addWidget(server_label)
        server_layout.addWidget(self.server_url_combo, 1)
        server_layout.addWidget(self.test_connection_button)

        # Session Cookie
        session_layout = QHBoxLayout()
        session_label = QLabel("Session Cookie:")
        session_label.setMinimumWidth(100)
        self.session_cookie_edit = QLineEdit()
        self.session_cookie_edit.setPlaceholderText("可选，用于身份验证...")
        session_layout.addWidget(session_label)
        session_layout.addWidget(self.session_cookie_edit)

        server_card.content_layout.addLayout(server_layout)
        server_card.content_layout.addLayout(session_layout)

        layout.addWidget(server_card)

        # 加载服务器URL历史记录
        self.load_server_url_history()

    def add_result_section(self, layout):
        """添加结果显示区域"""
        card = ModernCard("📊 操作结果")

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(150)
        self.result_text.setPlaceholderText("操作结果将显示在这里...")
        self.result_text.setStyleSheet("""
            QTextEdit {
                background: #f7fafc;
                font-family: 'Consolas', 'Monaco', monospace;
            }
        """)

        card.content_layout.addWidget(self.result_text)

        layout.addWidget(card)

    # ========================================================================
    # 事件处理函数
    # ========================================================================

    def browse_old_file(self):
        """浏览旧版本文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择旧版本文件", "", "Binary Files (*.bin *.hex *.fw);;All Files (*.*)"
        )
        if file_path:
            self.old_file_path = file_path
            self.old_file_edit.setText(file_path)
            self.result_text.append(f"✓ 已选择旧版本文件: {os.path.basename(file_path)}")

    def browse_new_file(self):
        """浏览新版本文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择新版本文件", "", "Binary Files (*.bin *.hex *.fw);;All Files (*.*)"
        )
        if file_path:
            self.new_file_path = file_path
            self.new_file_edit.setText(file_path)
            self.result_text.append(f"✓ 已选择新版本文件: {os.path.basename(file_path)}")

            # 自动设置补丁文件名
            if not self.patch_file_path:
                patch_name = os.path.basename(file_path).replace('.', '_patch.')
                patch_path = os.path.join(os.path.dirname(file_path), patch_name)
                self.patch_file_path = patch_path
                self.patch_file_edit.setText(patch_path)

    def browse_patch_file(self):
        """浏览补丁文件保存路径"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存补丁文件", "", "Binary Files (*.bin);;All Files (*.*)"
        )
        if file_path:
            self.patch_file_path = file_path
            self.patch_file_edit.setText(file_path)
            self.result_text.append(f"✓ 补丁文件将保存为: {os.path.basename(file_path)}")

    def reset_lzma_params(self):
        """重置LZMA参数为默认值"""
        self.dict_size_combo.setCurrentIndex(2)  # 4KB
        self.lc_combo.setCurrentIndex(2)  # 2
        self.lp_combo.setCurrentIndex(0)  # 0
        self.pb_combo.setCurrentIndex(0)  # 0
        self.fb_combo.setCurrentIndex(3)  # 64
        self.algo_combo.setCurrentIndex(1)  # 1
        self.eos_checkbox.setChecked(True)
        self.result_text.append("✓ LZMA参数已重置为默认值")

    def generate_patch(self):
        """生成补丁"""
        if not self.old_file_path or not self.new_file_path:
            QMessageBox.warning(self, "警告", "请选择旧版本和新版本文件")
            return

        patch_file = self.patch_file_path
        if not patch_file:
            patch_file = self.patch_file_edit.text()
            if not os.path.isabs(patch_file):
                patch_file = os.path.join(os.path.dirname(self.new_file_path), patch_file)
            self.patch_file_path = patch_file

        if not self.old_version_edit.text() or not self.new_version_edit.text():
            QMessageBox.warning(self, "警告", "请输入版本信息")
            return

        dest_dir = os.path.dirname(patch_file)
        if dest_dir and not os.path.exists(dest_dir):
            try:
                os.makedirs(dest_dir)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法创建目标目录：{str(e)}")
                return

        # 收集LZMA参数
        lzma_params = {
            'lc': self.lc_combo.currentData(),
            'lp': self.lp_combo.currentData(),
            'pb': self.pb_combo.currentData(),
            'fb': self.fb_combo.currentData(),
            'dict': self.dict_size_combo.currentData(),
            'a': self.algo_combo.currentData(),
            'eos': 1 if self.eos_checkbox.isChecked() else 0
        }

        enable_aes = self.aes_encrypt_checkbox.isChecked()

        # 禁用UI
        self.generate_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.result_text.clear()
        self.result_text.append("🚀 开始生成补丁...")

        # 启动工作线程
        self.worker_thread = WorkerThread(
            self.old_file_path,
            self.new_file_path,
            patch_file,
            lzma_params,
            enable_aes
        )
        self.worker_thread.finished.connect(self.on_patch_generated)
        self.worker_thread.start()

    def on_patch_generated(self, success, message):
        """补丁生成完成处理"""
        self.generate_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success:
            self.open_folder_button.setVisible(True)
            self.result_text.append(f"\n{message}")

            # 显示文件信息
            if os.path.exists(self.patch_file_path):
                size = os.path.getsize(self.patch_file_path)
                self.result_text.append(f"📦 补丁文件大小: {size:,} 字节")

            # 检查加密文件
            encrypted_file = self.patch_file_path.replace('.bin', '_encrypt.bin')
            if os.path.exists(encrypted_file):
                enc_size = os.path.getsize(encrypted_file)
                self.result_text.append(f"🔐 加密补丁大小: {enc_size:,} 字节")

            QMessageBox.information(self, "成功", f"补丁生成成功！\n文件保存在：{self.patch_file_path}")

            patch_id = None

            # 云服务上传和通知功能
            if self.upload_checkbox.isChecked():
                try:
                    # 更新API客户端
                    if self.session_cookie_edit.text():
                        self.api_client = ServerApiClient(
                            self.server_url_combo.currentText(),
                            self.session_cookie_edit.text()
                        )

                    # 上传补丁
                    result = self.api_client.upload_patch(
                        self.patch_file_path,
                        self.old_version_edit.text(),
                        self.new_version_edit.text()
                    )

                    if result.get('success'):
                        self.download_url = result.get('download_url')
                        patch_id = result.get('patch_id')
                        self.result_text.append(
                            f"✓ 上传成功！下载地址：{self.download_url}"
                        )

                        # 向所有设备发送通知
                        if self.notify_all_checkbox.isChecked():
                            try:
                                notification_result = self.api_client.notify_all_devices(patch_id)

                                if notification_result.get('success'):
                                    success_devices = notification_result.get('success_devices', [])
                                    failed_devices = notification_result.get('failed_devices', [])

                                    if success_devices:
                                        self.result_text.append(
                                            f"✓ OTA通知已成功发送到 {len(success_devices)} 个设备"
                                        )

                                    if failed_devices:
                                        self.result_text.append(
                                            f"⚠ OTA通知发送失败到 {len(failed_devices)} 个设备"
                                        )
                                else:
                                    self.result_text.append(
                                        f"⚠ 向所有设备发送OTA通知失败：{notification_result.get('message', '未知错误')}"
                                    )
                            except Exception as e:
                                self.result_text.append(
                                    f"⚠ 向所有设备发送OTA通知失败：{str(e)}"
                                )

                        # 向特定设备发送通知
                        elif self.notify_specific_checkbox.isChecked():
                            selected_items = self.device_list.selectedItems()
                            if selected_items:
                                try:
                                    success_count = 0
                                    failed_count = 0

                                    for item in selected_items:
                                        try:
                                            device_info = item.data(Qt.UserRole)
                                            device_id = device_info.get('device_id', '')
                                            user_id = device_info.get('user_id')

                                            if user_id and str(user_id).lower() != 'unknown':
                                                notification_result = self.api_client.send_ota_notification(
                                                    device_id,
                                                    patch_id,
                                                    str(user_id)
                                                )

                                                if notification_result.get('success'):
                                                    success_count += 1
                                                else:
                                                    failed_count += 1
                                            else:
                                                failed_count += 1
                                        except Exception:
                                            failed_count += 1

                                    if success_count > 0:
                                        self.result_text.append(
                                            f"✓ OTA通知已成功发送到 {success_count} 个设备"
                                        )

                                    if failed_count > 0:
                                        self.result_text.append(
                                            f"⚠ OTA通知发送失败到 {failed_count} 个设备"
                                        )

                                except Exception as e:
                                    self.result_text.append(
                                        f"⚠ 发送OTA通知时出错：{str(e)}"
                                    )
                    else:
                        self.result_text.append(
                            f"⚠ 上传失败：{result.get('message', '未知错误')}"
                        )
                except Exception as e:
                    self.result_text.append(
                        f"⚠ 上传失败：{str(e)}"
                    )
        else:
            self.result_text.append(f"\n❌ {message}")
            QMessageBox.critical(self, "失败", message)

    def open_patch_folder(self):
        """打开补丁文件所在文件夹"""
        if self.patch_file_path:
            folder = os.path.dirname(self.patch_file_path)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    # ========================================================================
    # 云服务相关处理函数
    # ========================================================================

    def toggle_device_selector(self, state):
        """Enable/disable device selector based on notify specific checkbox"""
        is_checked = state == Qt.Checked
        self.device_list.setEnabled(is_checked)

        if is_checked:
            self.notify_all_checkbox.setChecked(False)
            if self.device_list.count() == 0:
                self.refresh_devices()
            else:
                if len(self.device_list.selectedItems()) == 0 and self.device_list.count() > 0:
                    self.device_list.item(0).setSelected(True)
            self.device_list.setFocus()
        else:
            self.device_list.clearSelection()

    def toggle_notify_all(self, state):
        """Handle notify all checkbox state changes"""
        is_checked = state == Qt.Checked

        if is_checked:
            self.notify_specific_checkbox.setChecked(False)
            self.device_list.setEnabled(False)
            self.device_list.clearSelection()

    def refresh_devices(self):
        """Refresh the list of available devices"""
        try:
            if self.session_cookie_edit.text():
                self.api_client = ServerApiClient(
                    self.server_url_combo.currentText(),
                    self.session_cookie_edit.text()
                )

            self.device_list.clear()
            self.device_list.addItem("正在获取设备列表...")
            QApplication.processEvents()

            devices = self.api_client.get_devices()
            self.device_list.clear()

            if not devices:
                self.device_list.addItem("未找到设备")
                return

            for device in devices:
                device_id = device.get('device_id', '')
                user_id = device.get('user_id', 'unknown')
                device_name = device.get('device_name', device_id)

                item_text = f"[{user_id}] {device_id} ({device_name})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, device)
                self.device_list.addItem(item)

            if self.notify_specific_checkbox.isChecked():
                self.device_list.setEnabled(True)
                if self.device_list.count() > 0:
                    self.device_list.item(0).setSelected(True)
                    self.device_list.setFocus()

            QMessageBox.information(self, "设备列表", f"成功获取 {len(devices)} 个设备")

        except Exception as e:
            self.device_list.clear()
            self.device_list.addItem("获取设备失败")
            QMessageBox.warning(self, "警告", f"获取设备列表失败：{str(e)}")

    def update_server_url(self, url):
        """Update the server URL for the API client"""
        if self.api_client:
            self.api_client = ServerApiClient(url, self.session_cookie_edit.text())
            self.save_server_url_history()

    def test_server_connection(self):
        """测试与服务器的连接"""
        url = self.server_url_combo.currentText()
        if not url:
            QMessageBox.warning(self, "警告", "请输入服务器URL")
            return

        previous_text = self.test_connection_button.text()
        self.test_connection_button.setText("测试中...")
        self.test_connection_button.setEnabled(False)
        QApplication.processEvents()

        self.result_text.setText(f"<p>正在测试与服务器 {url} 的连接...</p>")
        QApplication.processEvents()

        try:
            health_url = f"{url}/api/health"
            test_session = requests.Session()
            response = test_session.get(
                health_url,
                timeout=10,
                verify=False
            )

            if response.status_code == 200:
                health_data = response.json()
                server_info = health_data.get('server', '未知')
                mqtt_status = "已连接" if health_data.get('mqtt_connected', False) else "未连接"
                device_count = health_data.get('device_count', 0)

                self.result_text.setText(
                    f"<p style='color:green'>✓ 服务器连接成功!</p>"
                    f"<p>服务器: {server_info}</p>"
                    f"<p>MQTT状态: {mqtt_status}</p>"
                    f"<p>设备数量: {device_count}</p>"
                )
                QMessageBox.information(self, "成功", f"成功连接到服务器 {url}")
            else:
                self.result_text.setText(
                    f"<p style='color:red'>✗ 服务器连接失败</p>"
                    f"<p>状态码: {response.status_code}</p>"
                )
                QMessageBox.warning(self, "警告", f"服务器返回错误状态码: {response.status_code}")
        except Exception as e:
            self.result_text.setText(
                f"<p style='color:red'>✗ 连接失败</p>"
                f"<p>错误: {str(e)}</p>"
            )
            QMessageBox.warning(self, "警告", f"连接失败: {str(e)}")
        finally:
            self.test_connection_button.setText(previous_text)
            self.test_connection_button.setEnabled(True)

    def get_selected_devices(self):
        """Get the list of selected devices"""
        selected_items = self.device_list.selectedItems()
        devices = []
        for item in selected_items:
            device = item.data(Qt.UserRole)
            if device:
                devices.append(device)
        return devices

    def on_device_selection_changed(self):
        """Handle device selection changes"""
        pass

    def load_server_url_history(self):
        """Load server URL history from config file"""
        try:
            config_file = os.path.join(os.path.expanduser("~"), ".bsdiff_gui_config.json")
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    urls = config.get('server_urls', [])
                    for url in urls:
                        if self.server_url_combo.findText(url) == -1:
                            self.server_url_combo.addItem(url)
        except:
            pass

    def save_server_url_history(self):
        """Save server URL history to config file"""
        try:
            config_file = os.path.join(os.path.expanduser("~"), ".bsdiff_gui_config.json")
            urls = [self.server_url_combo.itemText(i) for i in range(self.server_url_combo.count())]
            config = {'server_urls': urls}
            with open(config_file, 'w') as f:
                json.dump(config, f)
        except:
            pass

# ============================================================================
# 主程序入口
# ============================================================================

def main():
    app = QApplication(sys.argv)

    # 设置应用程序属性
    app.setApplicationName("Binary Diff Tool")
    app.setOrganizationName("ModernDev")

    # 设置字体
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = ModernBinaryDiffGUI()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
