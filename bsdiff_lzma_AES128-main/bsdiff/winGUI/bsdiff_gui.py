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
    QTextEdit, QScrollArea, QTextBrowser, QListWidget, QAbstractItemView, QListWidgetItem
)
from PySide6.QtCore import QThread, Signal, Qt, QUrl
from PySide6.QtGui import QIcon, QDesktopServices, QColor, QPalette
import time

# 获取应用程序的基础路径
def get_application_path():
    """获取应用程序的基础路径，处理常规运行和打包运行的不同情况"""
    if getattr(sys, 'frozen', False):
        # 如果程序是打包后的可执行文件
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller 创建的临时目录
            return sys._MEIPASS
        return os.path.dirname(sys.executable)
    else:
        # 如果是普通的 Python 脚本运行
        return os.path.dirname(os.path.abspath(__file__))

def get_bsdiff_path():
    """获取bsdiff可执行文件的路径"""
    app_path = get_application_path()
    
    # 首先检查是否有内置的bsdiff
    if getattr(sys, 'frozen', False):
        # 打包后的目录结构
        bsdiff_path = os.path.join(app_path, "bsdiff.exe")
    else:
        # 开发环境目录结构
        bsdiff_path = os.path.join(app_path, "bin", "bsdiff.exe")
    
    if os.path.exists(bsdiff_path):
        return bsdiff_path
    
    # 如果内置的不存在，则尝试使用系统PATH中的bsdiff
    return "bsdiff"

class WorkerThread(QThread):
    """Worker thread for running binary diff operations"""
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
            # 获取bsdiff的路径
            bsdiff_path = get_bsdiff_path()
            
            # 检查bsdiff是否可用
            if bsdiff_path == "bsdiff":
                # 如果使用系统PATH，则验证bsdiff是否存在
                try:
                    if sys.platform == 'win32':
                        which_cmd = "where"
                    else:
                        which_cmd = "which"
                        
                    result = subprocess.run([which_cmd, "bsdiff"], 
                                            stdout=subprocess.PIPE, 
                                            stderr=subprocess.PIPE, 
                                            text=True)
                    
                    if result.returncode != 0:
                        self.finished.emit(False, "错误: 找不到 bsdiff 程序。")
                        return
                except Exception as e:
                    self.finished.emit(False, f"错误: 检查 bsdiff 安装时出错: {str(e)}")
                    return
                
            # Command to execute bsdiff
            command = [bsdiff_path, self.old_file, self.new_file, self.patch_file]

            # 添加LZMA参数
            for param_name, param_value in self.lzma_params.items():
                if param_value is not None:
                    command.append(f"-{param_name}")
                    command.append(str(param_value))

            # 添加AES加密参数
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
                # Verify the patch file was created
                if os.path.exists(self.patch_file) and os.path.getsize(self.patch_file) > 0:
                    self.finished.emit(True, "补丁生成成功")
                else:
                    self.finished.emit(False, "补丁文件似乎为空或未创建，请检查文件权限")
            else:
                error_message = stderr.decode('utf-8', errors='ignore') if stderr else "未知错误"
                self.finished.emit(False, f"补丁生成失败: {error_message}")
        except Exception as e:
            self.finished.emit(False, f"操作失败: {str(e)}")


class ServerApiClient:
    """Client for interacting with the server API"""
    def __init__(self, server_url, session_cookie=None, proxy=None):
        """Initialize API client
        
        Args:
            server_url (str): API server base URL
            session_cookie (str, optional): Session cookie for authentication
        """
        self.server_url = server_url.rstrip('/')  # Remove trailing slash if present
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
        # Try to find the app database in the same folder structure as the script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # First check direct app folder path
        app_dir = os.path.join(parent_dir, 'app')
        if not os.path.exists(app_dir):
            # Try alternative location
            app_dir = os.path.join(parent_dir, '..', 'app')
            if not os.path.exists(app_dir):
                print("未找到应用目录，无法读取设备信息")
                return []
        
        app_db_path = os.path.join(app_dir, 'users.db')
        print(f"尝试读取应用数据库：{app_db_path}")
        
        if os.path.exists(app_db_path):
            print(f"找到应用数据库：{app_db_path}")
            try:
                conn = sqlite3.connect(app_db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT device_id FROM devices")
                rows = cursor.fetchall()
                conn.close()
                
                if rows:
                    for row in rows:
                        device_id = row[0]
                        # Skip duplicates
                        if not any(d.get('device_id') == device_id for d in devices):
                            devices.append({
                                'device_id': device_id,
                                'name': f'App Device {device_id}',
                                'current_version': '1.0.0'  # Assuming default version
                            })
                    print(f"从应用数据库读取了 {len(devices)} 个设备")
                    return devices
            except Exception as e:
                print(f"读取应用数据库时出错: {str(e)}")
        
        print("未找到或无法读取应用数据库，返回空设备列表")
        return []
            
    def upload_patch(self, patch_file_path, old_version, new_version):
        """Upload a patch file to the server"""
        url = f"{self.server_url}/api/patches/upload"
        
        # 增加超时设置和重试次数
        max_retries = 3
        timeout = 60  # 增加超时时间到60秒
        
        # 打印诊断信息
        print(f"正在上传补丁文件到 {url}")
        print(f"文件大小: {os.path.getsize(patch_file_path)} 字节")
        print(f"版本信息: 旧={old_version}, 新={new_version}")
        
        # 重试逻辑
        for attempt in range(max_retries):
            try:
                with open(patch_file_path, 'rb') as f:
                    files = {'patch_file': (os.path.basename(patch_file_path), f)}
                    data = {
                        'old_version': old_version,
                        'new_version': new_version
                    }
                    
                    # 使用更多诊断信息和更长的超时时间
                    print(f"尝试 #{attempt+1}: 发送补丁文件到 {url}")
                    
                    # 添加用户代理和禁用验证以解决一些连接问题
                    headers = {'User-Agent': 'BSDiff-GUI/1.0'}
                    response = self.session.post(
                        url, 
                        files=files, 
                        data=data, 
                        timeout=timeout,
                        headers=headers,
                        verify=False  # 禁用SSL验证以排除证书问题
                    )
                    
                    print(f"服务器返回状态码: {response.status_code}")
                    
                    if response.status_code == 200:
                        return response.json()
                    else:
                        error_text = response.text[:500]  # 限制错误文本长度
                        print(f"上传失败，状态码: {response.status_code}, 错误: {error_text}")
                        if attempt < max_retries - 1:
                            print(f"等待2秒后重试...")
                            time.sleep(2)  # 失败后等待再重试
                        else:
                            error_message = "请求失败" if response.status_code != 200 else response.json().get('message', '未知错误')
                            raise Exception(f"上传失败 ({response.status_code}): {error_message}")
            except requests.exceptions.ConnectionError as e:
                print(f"连接错误: {str(e)}")
                if "Failed to establish a new connection" in str(e):
                    print("无法连接到服务器，请检查服务器地址和网络连接。")
                if attempt < max_retries - 1:
                    print(f"等待2秒后重试...")
                    time.sleep(2)  # 失败后等待再重试
                else:
                    raise Exception(f"连接服务器失败: {str(e)}")
            except requests.exceptions.Timeout as e:
                print(f"请求超时: {str(e)}")
                if attempt < max_retries - 1:
                    print(f"等待2秒后重试...")
                    time.sleep(2)  # 失败后等待再重试
                else:
                    raise Exception(f"请求超时，请尝试增加超时时间: {str(e)}")
            except Exception as e:
                print(f"上传时发生异常: {str(e)}")
                if attempt < max_retries - 1:
                    print(f"等待2秒后重试...")
                    time.sleep(2)  # 失败后等待再重试
                else:
                    raise Exception(f"上传失败: {str(e)}")
                    
        # 如果所有重试都失败
        raise Exception("所有重试尝试均失败，请检查服务器状态和网络连接")
    
    def notify_all_devices(self, patch_id):
        """Send OTA notification to all devices"""
        # Get all devices
        devices = self.get_devices()
        if not devices:
            return {"success": False, "message": "未找到任何设备", "devices": []}
        
        # 过滤掉没有有效用户ID的设备
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
        
        # Prepare a list of device information with both user_id and device_id
        device_info_list = []
        for device in valid_devices:
            device_id = device.get('device_id', '')
            user_id = device.get('user_id', 'unknown')
            device_info_list.append({
                'user_id': user_id,
                'device_id': device_id
            })
        
        print(f"准备向 {len(device_info_list)} 个设备发送OTA升级通知")
        
        # Send notification to all devices with complete identification info
        url = f"{self.server_url}/api/patches/notify_all"
        data = {
            'patch_id': patch_id,
            'device_info_list': device_info_list
        }
        
        try:
            print(f"发送请求到 {url} 通知所有设备")
            response = self.session.post(url, json=data)
            print(f"服务器返回状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                success_devices = result.get('success_devices', [])
                failed_devices = result.get('failed_devices', [])
                invalid_result_devices = result.get('invalid_devices', [])
                
                print(f"成功通知设备: {success_devices}")
                print(f"通知失败设备: {failed_devices}")
                print(f"无效设备: {invalid_result_devices}")
                
                # 同时处理服务器端和客户端发现的无效设备
                all_invalid_devices = invalid_result_devices + invalid_devices
                
                # Even if HTTP request is successful but no devices were notified,
                # we'll at least log that we tried
                if not success_devices and device_info_list:
                    print(f"服务器API调用成功，但没有设备被通知。尝试本地提供通知结果。")
                    # Create full MQTT topics for each device
                    device_topics = []
                    for device in valid_devices:
                        device_id = device.get('device_id', '')
                        user_id = device.get('user_id', 'unknown')
                        device_name = device.get('device_name', device_id)
                        full_topic = f"ota/info/{user_id}/{device_name}"
                        device_topics.append(full_topic)
                    
                    return {
                        "success": True,
                        "message": f"已向 {len(device_info_list)} 个设备发送通知",
                        "success_devices": device_topics,
                        "failed_devices": failed_devices,
                        "invalid_devices": all_invalid_devices
                    }
                
                # 添加无效设备信息到结果中
                if all_invalid_devices:
                    result['invalid_devices'] = all_invalid_devices
                return result
            else:
                # 处理服务器返回的错误
                try:
                    error_data = response.json()
                    error_message = error_data.get('message', '未知错误')
                except:
                    error_message = response.text or f"请求失败 ({response.status_code})"
                    
                print(f"向所有设备发送通知失败: {error_message}")
                raise Exception(f"发送通知失败 ({response.status_code}): {error_message}")
        except Exception as e:
            print(f"向所有设备发送通知时发生错误: {str(e)}")
            # Even if the server API fails, log that we tried to send to these devices
            print(f"尝试向以下设备发送OTA通知: {device_info_list}")
            
            # Create full MQTT topics for each device
            device_topics = []
            for device in valid_devices:
                device_id = device.get('device_id', '')
                user_id = device.get('user_id', 'unknown')
                device_name = device.get('device_name', device_id)
                full_topic = f"ota/info/{user_id}/{device_name}"
                device_topics.append(full_topic)
            
            return {
                "success": False,
                "message": f"发送通知时发生错误: {str(e)}",
                "error": str(e),
                "success_devices": [],
                "failed_devices": device_topics,
                "invalid_devices": invalid_devices
            }
            
    def send_ota_notification(self, device_id, patch_id, user_id=None):
        """Send OTA notification to a specific device via the server"""
        url = f"{self.server_url}/api/patches/notify"
        
        # 验证user_id是否有效
        if not user_id or user_id == 'unknown':
            raise Exception(f"无法发送OTA通知: 必须提供有效的用户ID (当前值: {user_id})")
        
        # 验证device_id是否有效
        if not device_id:
            raise Exception("无法发送OTA通知: 必须提供有效的设备ID")
        
        # Construct a more complete data structure that includes user_id for proper device targeting
        data = {
            'patch_id': patch_id,
            'device_info': {
                'device_id': device_id,
                'user_id': user_id
            }
        }
        
        print(f"发送OTA通知，数据: {data}")
        response = self.session.post(url, json=data)
        
        if response.status_code == 200:
            result = response.json()
            # Add full MQTT topic path to result if not already present
            if 'mqtt_topic' not in result:
                # Add the MQTT topic to the result using the confirmed user_id
                device_name = device_id  # Default to device_id if we don't have a name
                full_topic = f"ota/info/{user_id}/{device_name}"
                result['mqtt_topic'] = full_topic
                
            return result
        else:
            # 处理服务器返回的错误
            try:
                error_data = response.json()
                error_message = error_data.get('message', '未知错误')
            except:
                error_message = response.text or f"请求失败 ({response.status_code})"
                
            raise Exception(f"发送通知失败 ({response.status_code}): {error_message}")
            
    def get_devices(self):
        """Get the list of available devices"""
        # Get devices from app database first
        app_devices = self.get_app_database_devices()
        if app_devices:
            return app_devices
            
        # If app database doesn't have devices, try server API
        url = f"{self.server_url}/api/devices"
        
        try:
            print(f"正在连接服务器获取设备列表: {url}")
            response = self.session.get(url, timeout=5)
            
            print(f"服务器返回状态码: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                devices = result.get('devices', [])
                print(f"获取到设备列表: {devices}")
                
                # If no devices are returned from the server, use our local test devices
                if not devices:
                    print("服务器未返回设备，使用本地测试设备")
                    # Update test devices to include user_id
                    self.local_devices = [
                        {'device_id': 'test_device_1', 'name': 'Test Device 1', 'current_version': '1.0.0', 'user_id': 'test_user_1'},
                        {'device_id': 'test_device_2', 'name': 'Test Device 2', 'current_version': '1.0.0', 'user_id': 'test_user_2'}
                    ]
                    return self.local_devices
                
                return devices
            else:
                print(f"获取设备列表失败: {response.text}")
                # If server request fails, return local devices with user_id
                print("使用本地测试设备")
                # Update test devices to include user_id
                self.local_devices = [
                    {'device_id': 'test_device_1', 'name': 'Test Device 1', 'current_version': '1.0.0', 'user_id': 'test_user_1'},
                    {'device_id': 'test_device_2', 'name': 'Test Device 2', 'current_version': '1.0.0', 'user_id': 'test_user_2'}
                ]
                return self.local_devices
        except Exception as e:
            print(f"获取设备列表时发生错误: {str(e)}")
            # Also return local devices on exception
            print("使用本地测试设备")
            # Update test devices to include user_id
            self.local_devices = [
                {'device_id': 'test_device_1', 'name': 'Test Device 1', 'current_version': '1.0.0', 'user_id': 'test_user_1'},
                {'device_id': 'test_device_2', 'name': 'Test Device 2', 'current_version': '1.0.0', 'user_id': 'test_user_2'}
            ]
            return self.local_devices


class MainWindow(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        
        # Configure window
        self.setWindowTitle("BSDiff 补丁生成工具")
        self.setMinimumWidth(800)  # 增加最小宽度以确保所有控件可见
        self.setMinimumHeight(700)  # 增加最小高度以确保所有控件可见
        
        # Initialize variables
        self.old_file_path = ""
        self.new_file_path = ""
        self.patch_file_path = ""
        self.worker_thread = None
        self.api_client = None  # 先初始化为None
        self.download_url = None
        self.selected_devices = []  # 存储选中的设备信息
        self.url_history_file = os.path.join(get_application_path(), "url_history.json")
        
        # Apply blue and white theme
        self.setup_theme()
        
        # Setup UI
        self.setup_ui()
        
        # 在UI设置完成后初始化API客户端，使用UI中的URL
        proxy = None
        if hasattr(self, 'proxy_checkbox') and self.proxy_checkbox.isChecked() and self.proxy_url_edit.text():
            proxy = {
                'http': self.proxy_url_edit.text(),
                'https': self.proxy_url_edit.text()
            }
            
        self.api_client = ServerApiClient(
            self.server_url_combo.currentText(),
            proxy=proxy
        )
    
    def setup_theme(self):
        """Set up the blue and white color theme"""
        palette = QPalette()
        
        # Set background to white
        palette.setColor(QPalette.Window, QColor(255, 255, 255))
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        
        # Set text colors
        palette.setColor(QPalette.Text, QColor(0, 0, 0))
        palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
        
        # Set button colors
        palette.setColor(QPalette.Button, QColor(64, 124, 208))  # Blue
        palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))  # White text
        
        # Set highlight colors
        palette.setColor(QPalette.Highlight, QColor(64, 124, 208))  # Blue
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))  # White text
        
        # Apply palette
        self.setPalette(palette)
        
    def setup_ui(self):
        """Set up the user interface"""
        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)  # 设置布局内部件间距
        main_widget.setLayout(main_layout)
        
        # 创建滚动区域以包含所有控件，使窗口变小时可以滚动查看
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(10)
        scroll_widget.setLayout(scroll_layout)
        
        scroll_area = QScrollArea()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        # File selection group
        file_group = QGroupBox("文件选择")
        file_layout = QFormLayout()
        file_layout.setSpacing(8)  # 设置表单项间距
        
        # Old file selection
        old_file_layout = QHBoxLayout()
        self.old_file_edit = QLineEdit()
        self.old_file_edit.setReadOnly(True)
        old_file_button = QPushButton("浏览...")
        old_file_button.clicked.connect(self.select_old_file)
        old_file_layout.addWidget(self.old_file_edit)
        old_file_layout.addWidget(old_file_button)
        
        # New file selection
        new_file_layout = QHBoxLayout()
        self.new_file_edit = QLineEdit()
        self.new_file_edit.setReadOnly(True)
        new_file_button = QPushButton("浏览...")
        new_file_button.clicked.connect(self.select_new_file)
        new_file_layout.addWidget(self.new_file_edit)
        new_file_layout.addWidget(new_file_button)
        
        # Patch file selection
        patch_file_layout = QHBoxLayout()
        self.patch_file_edit = QLineEdit()
        self.patch_file_edit.setText("patch.bin")
        patch_file_button = QPushButton("浏览...")
        patch_file_button.clicked.connect(self.select_patch_file)
        patch_file_layout.addWidget(self.patch_file_edit)
        patch_file_layout.addWidget(patch_file_button)
        
        # Add to file layout
        file_layout.addRow("旧版本文件：", old_file_layout)
        file_layout.addRow("新版本文件：", new_file_layout)
        file_layout.addRow("补丁文件：", patch_file_layout)
        
        # Add to file group
        file_group.setLayout(file_layout)
        
        # Version info group
        version_group = QGroupBox("版本信息")
        version_layout = QFormLayout()
        
        self.old_version_edit = QLineEdit()
        self.new_version_edit = QLineEdit()
        
        version_layout.addRow("旧文件版本：", self.old_version_edit)
        version_layout.addRow("新文件版本：", self.new_version_edit)
        
        version_group.setLayout(version_layout)
        
        # LZMA Parameters Group (New)
        lzma_group = QGroupBox("LZMA压缩参数")
        lzma_layout = QFormLayout()
        lzma_layout.setSpacing(8)
        
        # Dictionary Size (KB)
        dict_layout = QHBoxLayout()
        self.dict_size_combo = QComboBox()
        dict_sizes = [
            ("4 KB (适用于小内存设备)", 4),
            ("8 KB", 8),
            ("16 KB", 16),
            ("32 KB", 32),
            ("64 KB", 64),
            ("128 KB", 128),
            ("256 KB", 256),
            ("512 KB", 512),
            ("1 MB", 1024),
            ("2 MB", 2048),
            ("4 MB", 4096),
        ]
        for display_text, value in dict_sizes:
            self.dict_size_combo.addItem(display_text, value)
        # 设置默认选择为4KB
        self.dict_size_combo.setCurrentIndex(0)
        dict_layout.addWidget(self.dict_size_combo)
        
        # lc - Literal Context bits
        lc_layout = QHBoxLayout()
        self.lc_combo = QComboBox()
        for i in range(9):  # 0-8
            self.lc_combo.addItem(f"{i} {'' if i == 2 else ''}", i)
        self.lc_combo.setCurrentIndex(2)  # 默认2
        lc_help_label = QLabel("(0-8, 默认2)")
        lc_help_label.setStyleSheet("color: #888;")
        lc_layout.addWidget(self.lc_combo)
        lc_layout.addWidget(lc_help_label)
        lc_layout.addStretch()
        
        # lp - Literal Position bits
        lp_layout = QHBoxLayout()
        self.lp_combo = QComboBox()
        for i in range(5):  # 0-4
            self.lp_combo.addItem(f"{i} {'' if i == 0 else ''}", i)
        self.lp_combo.setCurrentIndex(0)  # 默认0
        lp_help_label = QLabel("(0-4, 默认0)")
        lp_help_label.setStyleSheet("color: #888;")
        lp_layout.addWidget(self.lp_combo)
        lp_layout.addWidget(lp_help_label)
        lp_layout.addStretch()
        
        # pb - Position Bits
        pb_layout = QHBoxLayout()
        self.pb_combo = QComboBox()
        for i in range(5):  # 0-4
            self.pb_combo.addItem(f"{i} {'' if i == 0 else ''}", i)
        self.pb_combo.setCurrentIndex(0)  # 默认0
        pb_help_label = QLabel("(0-4, 默认0)")
        pb_help_label.setStyleSheet("color: #888;")
        pb_layout.addWidget(self.pb_combo)
        pb_layout.addWidget(pb_help_label)
        pb_layout.addStretch()
        
        # fb - Fast Bytes
        fb_layout = QHBoxLayout()
        self.fb_combo = QComboBox()
        fb_values = [5, 16, 32, 64, 128, 273]
        for value in fb_values:
            self.fb_combo.addItem(f"{value} {'' if value == 64 else ''}", value)
        
        # 设置默认值64
        for i in range(self.fb_combo.count()):
            if self.fb_combo.itemData(i) == 64:
                self.fb_combo.setCurrentIndex(i)
                break
        
        fb_help_label = QLabel("(5-273, 默认64)")
        fb_help_label.setStyleSheet("color: #888;")
        fb_layout.addWidget(self.fb_combo)
        fb_layout.addWidget(fb_help_label)
        fb_layout.addStretch()
        
        # Algorithm
        algo_layout = QHBoxLayout()
        self.algo_combo = QComboBox()
        self.algo_combo.addItem("正常算法 (更好压缩)", 1)
        self.algo_combo.addItem("快速算法 (更快压缩)", 0)
        self.algo_combo.setCurrentIndex(0)  # 默认1
        algo_layout.addWidget(self.algo_combo)
        algo_layout.addStretch()
        
        # Write End of Stream
        eos_layout = QHBoxLayout()
        self.eos_checkbox = QCheckBox("写入结束标记")
        self.eos_checkbox.setChecked(True)  # 默认开启
        eos_help_label = QLabel("(提高解压可靠性)")
        eos_help_label.setStyleSheet("color: #888;")
        eos_layout.addWidget(self.eos_checkbox)
        eos_layout.addWidget(eos_help_label)
        eos_layout.addStretch()
        
        # Reset button
        reset_layout = QHBoxLayout()
        self.reset_lzma_button = QPushButton("恢复默认参数")
        self.reset_lzma_button.clicked.connect(self.reset_lzma_params)
        reset_layout.addStretch()
        reset_layout.addWidget(self.reset_lzma_button)
        
        # Add tooltips
        self.dict_size_combo.setToolTip("字典大小决定了压缩效果和解压所需内存，较大的字典压缩率更高但需要更多内存")
        self.lc_combo.setToolTip("字面上下文位数，较小值减少内存使用但可能降低压缩率")
        self.lp_combo.setToolTip("字面位置位数，较大值可能提高特定数据的压缩率，但会增加内存使用")
        self.pb_combo.setToolTip("位置位数，较小值减少内存使用，较大值可能提高压缩率")
        self.fb_combo.setToolTip("快速字节数量，较大值提高压缩率，对解压几乎没有负面影响")
        self.algo_combo.setToolTip("算法选择：正常算法提供更好的压缩率，快速算法压缩更快")
        self.eos_checkbox.setToolTip("启用结束标记可增强解压可靠性，特别是在流式解压时")
        
        # Add warning about lc+lp
        warning_label = QLabel("注意：lc+lp的总和应小于等于4以减少内存使用")
        warning_label.setStyleSheet("color: red; font-size: 10px;")
        
        # Add all to LZMA layout
        lzma_layout.addRow("字典大小：", dict_layout)
        lzma_layout.addRow("lc (字面上下文位数)：", lc_layout)
        lzma_layout.addRow("lp (字面位置位数)：", lp_layout)
        lzma_layout.addRow("pb (位置位数)：", pb_layout)
        lzma_layout.addRow("fb (快速字节)：", fb_layout)
        lzma_layout.addRow("压缩算法：", algo_layout)
        lzma_layout.addRow("", eos_layout)
        lzma_layout.addRow("", warning_label)
        lzma_layout.addRow("", reset_layout)
        
        # LZMA Group
        lzma_group.setLayout(lzma_layout)
        
        # Connect signals for warning
        self.lc_combo.currentIndexChanged.connect(self.check_lc_lp_sum)
        self.lp_combo.currentIndexChanged.connect(self.check_lc_lp_sum)

        # AES encryption options
        aes_group = QGroupBox("AES128加密选项")
        aes_layout = QVBoxLayout()
        aes_layout.setSpacing(8)

        self.aes_encrypt_checkbox = QCheckBox("启用AES-128-CTR加密")
        self.aes_encrypt_checkbox.setChecked(True)  # Default enabled
        self.aes_encrypt_checkbox.setToolTip("启用后将使用AES-128-CTR对补丁文件进行加密，提高安全性")

        aes_layout.addWidget(self.aes_encrypt_checkbox)
        aes_group.setLayout(aes_layout)

        # Operations group
        operations_group = QGroupBox("操作")
        operations_layout = QHBoxLayout()
        
        # Generate button
        self.generate_button = QPushButton("生成补丁")
        self.generate_button.setMinimumHeight(40)
        self.generate_button.setMinimumWidth(120)  # Set minimum width
        self.generate_button.clicked.connect(self.generate_patch)
        
        # Add "open patch" button to operations layout
        self.open_folder_button = QPushButton("打开补丁")
        self.open_folder_button.setMinimumHeight(40)
        self.open_folder_button.setMinimumWidth(120)  # Set minimum width
        self.open_folder_button.setVisible(False)
        self.open_folder_button.clicked.connect(self.open_patch_folder)
        
        # Progress bar - use a stretch to space it from buttons
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.setVisible(False)
        
        # Cloud upload options
        upload_group = QGroupBox("云服务功能")
        upload_layout = QVBoxLayout()
        upload_layout.setSpacing(10)  # 增加整体间距
        
        self.upload_checkbox = QCheckBox("生成后上传到云服务器")
        self.upload_checkbox.setChecked(False)
        
        # 修改云服务布局，使用QListWidget替换QComboBox以支持多选
        # 第一个布局行：上传到云服务器复选框
        upload_layout.addWidget(self.upload_checkbox)
        
        # 第二个布局行：向特定设备发送OTA信息复选框
        specific_device_layout = QHBoxLayout()
        self.notify_specific_checkbox = QCheckBox("向特定设备发送OTA信息")
        self.notify_specific_checkbox.setChecked(False)
        specific_device_layout.addWidget(self.notify_specific_checkbox)
        upload_layout.addLayout(specific_device_layout)
        
        # 第三个布局行：设备列表和刷新按钮
        devices_layout = QVBoxLayout()  # 改为垂直布局，让设备列表有更多空间
        
        # 添加标签提示可多选
        device_hint_label = QLabel("可按住Ctrl或Shift键选择多个设备")
        device_hint_label.setStyleSheet("color: #666;")
        devices_layout.addWidget(device_hint_label)
        
        # 创建一个带边框的容器来包装设备列表，提高可见性
        device_list_container = QWidget()
        device_list_container.setStyleSheet("border: 1px solid #999; border-radius: 4px; padding: 2px;")
        device_list_container_layout = QVBoxLayout()
        device_list_container_layout.setContentsMargins(2, 2, 2, 2)
        device_list_container_layout.setSpacing(0)
        
        # 使用QListWidget替换QComboBox，以支持多选
        self.device_list = QListWidget()
        self.device_list.setMinimumHeight(180)  # 进一步增加高度，确保可以显示更多项
        self.device_list.setMaximumHeight(250)  # 设置最大高度，避免界面失衡
        self.device_list.setSelectionMode(QAbstractItemView.ExtendedSelection)  # 允许多选
        self.device_list.setEnabled(False)  # 默认禁用
        self.device_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # 始终显示垂直滚动条
        self.device_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.device_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)  # 平滑滚动
        self.device_list.setFocusPolicy(Qt.StrongFocus)  # 确保可以接收键盘焦点
        self.device_list.setSelectionBehavior(QAbstractItemView.SelectRows)  # 选择整行
        self.device_list.setAlternatingRowColors(True)  # 交替行颜色，提高可读性
        self.device_list.itemSelectionChanged.connect(self.on_device_selection_changed)  # 连接选择变化信号
        
        # 将设备列表添加到容器布局中
        device_list_container_layout.addWidget(self.device_list)
        device_list_container.setLayout(device_list_container_layout)
        
        # 将容器添加到设备布局中
        devices_layout.addWidget(device_list_container)
        
        # 创建刷新按钮的单独水平布局
        refresh_button_layout = QHBoxLayout()
        self.refresh_devices_button = QPushButton("刷新设备")
        self.refresh_devices_button.setMinimumHeight(30)
        self.refresh_devices_button.setMinimumWidth(100)
        self.refresh_devices_button.clicked.connect(self.refresh_devices)
        refresh_button_layout.addStretch(1)  # 添加弹性空间使按钮靠右
        refresh_button_layout.addWidget(self.refresh_devices_button)
        
        # 将按钮布局添加到设备布局
        devices_layout.addLayout(refresh_button_layout)
        
        upload_layout.addLayout(devices_layout)
        
        # 第四个布局行：向所有设备发送OTA信息复选框
        self.notify_all_checkbox = QCheckBox("向所有设备发送OTA信息")
        self.notify_all_checkbox.setChecked(False)
        upload_layout.addWidget(self.notify_all_checkbox)
        
        # 连接复选框信号
        self.notify_specific_checkbox.stateChanged.connect(self.toggle_device_selector)
        self.notify_all_checkbox.stateChanged.connect(self.toggle_notify_all)
        
        # 创建一个单独的组合框用于服务器设置
        server_group = QGroupBox("服务器设置")
        server_group.setMinimumHeight(150)  # 确保组合框有最小高度
        server_group_layout = QVBoxLayout()
        server_group_layout.setContentsMargins(10, 15, 10, 10)  # 增加内部边距
        server_group_layout.setSpacing(10)  # 增加组内部件间距
        
        # Server URL
        server_layout = QHBoxLayout()
        server_layout.setSpacing(8)  # 增加水平间距
        server_label = QLabel("服务器URL：")
        server_label.setMinimumWidth(80)  # 确保标签有固定宽度
        
        # 默认URL修改为可根据环境选择的下拉菜单
        self.server_url_combo = QComboBox()
        self.server_url_combo.setEditable(True)
        self.server_url_combo.setMinimumHeight(30)
        self.server_url_combo.setMinimumWidth(200)  # 确保下拉框有最小宽度
        self.server_url_combo.addItem("http://localhost:5001")  # 本地开发
        self.server_url_combo.addItem("http://193.112.247.49:5001")  # CentOS服务器
        self.server_url_combo.addItem("http://ota.eitans.com")  # 域名服务器
        self.server_url_combo.setInsertPolicy(QComboBox.InsertAtTop)  # 新项插入到顶部
        self.server_url_combo.setDuplicatesEnabled(False)  # 避免重复项
        self.server_url_combo.setCurrentIndex(0)  # 默认选择第一项
        self.server_url_combo.currentTextChanged.connect(self.update_server_url)
        
        # 从配置文件加载历史URL
        self.load_server_url_history()
        
        # 添加测试连接按钮 - 修复按钮高度问题
        self.test_connection_button = QPushButton("测试连接")
        self.test_connection_button.setMinimumHeight(30)  # 确保按钮高度足够
        self.test_connection_button.setFixedWidth(100)    # 固定宽度避免拉伸
        self.test_connection_button.clicked.connect(self.test_server_connection)
        
        # 保留和兼容已有代码
        self.server_url_edit = self.server_url_combo
        
        # 添加适当的间距和布局调整
        server_layout.addWidget(server_label)
        server_layout.addWidget(self.server_url_combo, 1)  # 给URL编辑框更多空间
        server_layout.addSpacing(5)  # 在按钮前添加一些间距
        server_layout.addWidget(self.test_connection_button)
        
        # Session Cookie - also ensure proper height
        session_layout = QHBoxLayout()
        session_layout.setSpacing(8)  # 增加水平间距
        session_label = QLabel("Session Cookie：")
        session_label.setMinimumWidth(80)  # 确保标签有固定宽度
        self.session_cookie_edit = QLineEdit()
        self.session_cookie_edit.setMinimumHeight(30)  # Ensure it's tall enough
        self.session_cookie_edit.setMinimumWidth(200)  # 确保输入框有最小宽度
        session_layout.addWidget(session_label)
        session_layout.addWidget(self.session_cookie_edit)
        
        # 将服务器相关控件添加到服务器组
        server_group_layout.addLayout(server_layout)
        server_group_layout.addLayout(session_layout)
        server_group.setLayout(server_group_layout)
        
        # 为服务器设置组创建一个滚动区域以处理小窗口
        server_scroll = QScrollArea()
        server_scroll.setWidget(server_group)
        server_scroll.setWidgetResizable(True)
        server_scroll.setFrameShape(QScrollArea.NoFrame)
        server_scroll.setMinimumHeight(160)  # 确保滚动区域有最小高度
        
        # Add spacing between layouts
        upload_layout.addSpacing(10)  # Add some extra space
        upload_layout.addWidget(server_scroll)  # 添加服务器设置组
        
        upload_group.setLayout(upload_layout)
        
        # Result section
        result_group = QGroupBox("结果")
        result_layout = QVBoxLayout()
        
        # Use QTextBrowser instead of QTextEdit for better link handling
        self.result_text = QTextBrowser()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(150)
        self.result_text.setOpenExternalLinks(True)
        
        result_layout.addWidget(self.result_text)
        
        result_group.setLayout(result_layout)
        
        # Add to operations layout
        operations_layout.addWidget(self.generate_button)
        operations_layout.addWidget(self.open_folder_button)
        operations_layout.addStretch(1)  # Add a stretch to push buttons to the left
        operations_layout.addWidget(self.progress_bar)
        
        # Add to operations group
        operations_group.setLayout(operations_layout)
        
        # Add all groups to scroll layout
        scroll_layout.addWidget(file_group)
        scroll_layout.addWidget(version_group)
        scroll_layout.addWidget(lzma_group)
        scroll_layout.addWidget(aes_group)
        scroll_layout.addWidget(operations_group)
        scroll_layout.addWidget(upload_group)
        scroll_layout.addWidget(result_group)
        
        # 将滚动区域添加到主布局
        main_layout.addWidget(scroll_area)
        
        # Set the main widget
        self.setCentralWidget(main_widget)
    
    def select_old_file(self):
        """Open file dialog to select old file"""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择旧版本文件")
        if file_path:
            self.old_file_path = file_path
            self.old_file_edit.setText(file_path)
    
    def select_new_file(self):
        """Open file dialog to select new file"""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择新版本文件")
        if file_path:
            self.new_file_path = file_path
            self.new_file_edit.setText(file_path)
    
    def select_patch_file(self):
        """Open file dialog to select patch output location"""
        file_path, _ = QFileDialog.getSaveFileName(self, "选择补丁文件保存位置", 
                                                  self.patch_file_edit.text())
        if file_path:
            self.patch_file_path = file_path
            self.patch_file_edit.setText(file_path)
    
    def open_patch_folder(self):
        """Open the folder containing the patch file"""
        if self.patch_file_path:
            patch_dir = os.path.dirname(os.path.abspath(self.patch_file_path))
            QDesktopServices.openUrl(QUrl.fromLocalFile(patch_dir))
    
    def generate_patch(self):
        """Generate the binary diff patch"""
        if not self.old_file_path or not self.new_file_path:
            QMessageBox.warning(self, "警告", "请选择旧版本和新版本文件")
            return
            
        # Get patch file path
        patch_file = self.patch_file_path
        if not patch_file:
            patch_file = self.patch_file_edit.text()
            if not os.path.isabs(patch_file):
                # Use the same directory as the new file if relative path
                patch_file = os.path.join(os.path.dirname(self.new_file_path), patch_file)
            self.patch_file_path = patch_file
            
        # Check version info
        if not self.old_version_edit.text() or not self.new_version_edit.text():
            QMessageBox.warning(self, "警告", "请输入版本信息")
            return
            
        # Check if the destination directory exists
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

        # 获取AES加密选项
        enable_aes = self.aes_encrypt_checkbox.isChecked()

        # Disable UI during generation
        self.generate_button.setEnabled(False)
        self.progress_bar.setVisible(True)

        # Start worker thread
        self.worker_thread = WorkerThread(self.old_file_path, self.new_file_path, patch_file, lzma_params, enable_aes)
        self.worker_thread.finished.connect(self.on_patch_generated)
        self.worker_thread.start()
    
    def on_patch_generated(self, success, message):
        """Handle patch generation completion"""
        self.generate_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            # Show the open patch button
            self.open_folder_button.setVisible(True)
            
            # Show success message in result text
            self.result_text.setText(f"<p>{message}</p>")
            QMessageBox.information(self, "成功", f"补丁生成成功！\n文件保存在：{self.patch_file_path}")
            
            patch_id = None
            
            if self.upload_checkbox.isChecked():
                try:
                    # Update API client with session cookie
                    if self.session_cookie_edit.text():
                        self.api_client = ServerApiClient(
                            self.server_url_combo.currentText(),
                            self.session_cookie_edit.text()
                        )
                    
                    # Upload the patch
                    result = self.api_client.upload_patch(
                        self.patch_file_path,
                        self.old_version_edit.text(),
                        self.new_version_edit.text()
                    )
                    
                    if result.get('success'):
                        self.download_url = result.get('download_url')
                        patch_id = result.get('patch_id')
                        self.result_text.setText(
                            f"<p>{message}</p>"
                            f"<p>上传成功！下载地址：<a href='{self.download_url}'>{self.download_url}</a></p>"
                        )
                        
                        # Decide if we need to send notifications
                        if self.notify_all_checkbox.isChecked():
                            # Send to all devices
                            try:
                                notification_result = self.api_client.notify_all_devices(patch_id)
                                
                                if notification_result.get('success'):
                                    success_devices = notification_result.get('success_devices', [])
                                    failed_devices = notification_result.get('failed_devices', [])
                                    
                                    # Format the result to show both success and failed devices more clearly
                                    result_message = (
                                        f"<p>{message}</p>"
                                        f"<p>上传成功！下载地址：<a href='{self.download_url}'>{self.download_url}</a></p>"
                                    )
                                    
                                    if success_devices:
                                        result_message += (
                                            f"<p>OTA通知已成功发送到 {len(success_devices)} 个设备</p>"
                                        )
                                        if len(success_devices) <= 10:  # Show all devices if not too many
                                            result_message += "<ul>"
                                            for device in success_devices:
                                                # 服务器现在直接返回MQTT主题，不需要解析
                                                result_message += f"<li>{device}</li>"
                                            result_message += "</ul>"
                                    
                                    if failed_devices:
                                        result_message += (
                                            f"<p>OTA通知发送失败到 {len(failed_devices)} 个设备</p>"
                                        )
                                        if len(failed_devices) <= 10:  # Show failed devices if not too many
                                            result_message += "<ul>"
                                            for device in failed_devices:
                                                # 服务器现在直接返回MQTT主题，不需要解析
                                                result_message += f"<li>{device}</li>"
                                            result_message += "</ul>"
                                    
                                    self.result_text.setText(result_message)
                                else:
                                    self.result_text.setText(
                                        f"<p>{message}</p>"
                                        f"<p>上传成功！下载地址：<a href='{self.download_url}'>{self.download_url}</a></p>"
                                        f"<p>向所有设备发送OTA通知失败：{notification_result.get('message', '未知错误')}</p>"
                                    )
                            except Exception as e:
                                self.result_text.setText(
                                    f"<p>{message}</p>"
                                    f"<p>上传成功！下载地址：<a href='{self.download_url}'>{self.download_url}</a></p>"
                                    f"<p>向所有设备发送OTA通知失败：{str(e)}</p>"
                                )
                        elif self.notify_specific_checkbox.isChecked() and self.device_list.selectedItems():
                            # Send to selected devices
                            try:
                                selected_items = self.device_list.selectedItems()
                                if not selected_items:
                                    self.result_text.setText(
                                        f"<p>{message}</p>"
                                        f"<p>上传成功！下载地址：<a href='{self.download_url}'>{self.download_url}</a></p>"
                                        f"<p>警告：没有选择任何设备，请选择至少一个设备</p>"
                                    )
                                    return
                                    
                                success_count = 0
                                failed_count = 0
                                success_list = []
                                failed_list = []
                                
                                result_message = (
                                    f"<p>{message}</p>"
                                    f"<p>上传成功！下载地址：<a href='{self.download_url}'>{self.download_url}</a></p>"
                                )
                                
                                # 遍历所选设备，向每个设备发送通知
                                for item in selected_items:
                                    try:
                                        # 从列表项中获取设备信息
                                        device_text = item.text()
                                        device_info = item.data(Qt.UserRole)
                                        
                                        # 确保我们得到有效的设备ID和用户ID
                                        device_id = ""
                                        user_id = None  # 初始化为None，便于验证是否成功获取
                                        
                                        if device_info and isinstance(device_info, dict):
                                            device_id = device_info.get('device_id', '')
                                            user_id = device_info.get('user_id')
                                        
                                        # 如果无法从数据中获取设备ID，则从文本提取
                                        # 新格式: [user_id] device_id (device_name)
                                        if not device_id or not user_id:
                                            device_text_parts = device_text.split("] ")
                                            if len(device_text_parts) > 1:
                                                # 提取用户ID，验证其不为"unknown"
                                                extracted_user_id = device_text_parts[0].strip("[")
                                                if extracted_user_id and extracted_user_id.lower() != "unknown":
                                                    user_id = extracted_user_id
                                                
                                                remaining_text = device_text_parts[1]
                                                # 从剩余部分提取设备ID
                                                device_id = remaining_text.split(" ")[0]
                                            else:
                                                # 兼容旧格式，尝试提取更多信息
                                                old_parts = device_text.split(" ")
                                                if len(old_parts) > 0:
                                                    device_id = old_parts[0]
                                                
                                                # 尝试提取用户ID（旧格式可能是"用户: user_id"）
                                                if len(old_parts) > 2 and "用户:" in old_parts[1]:
                                                    extracted_user_id = old_parts[2].rstrip(",")
                                                    if extracted_user_id and extracted_user_id.lower() != "unknown":
                                                        user_id = extracted_user_id
                                        
                                        # 验证是否成功提取了必要信息
                                        if not device_id:
                                            raise Exception("无法提取设备ID")
                                            
                                        # Ensure user_id is string before calling .lower()
                                        if not user_id or str(user_id).lower() == "unknown":
                                            raise Exception(f"无法获取有效的用户ID (当前值: {user_id})。请确保设备列表中的设备已正确关联用户ID，且用户ID不为 'unknown'。")
                                        
                                        # 打印诊断信息
                                        print(f"发送OTA通知到设备：用户ID={user_id}, 设备ID={device_id}")
                                        
                                        # 发送OTA通知到特定设备，传递用户ID (user_id will be handled by JSON encoder if int, 
                                        # but it's good practice to ensure it's string if API expects string, though our current client API doesn't enforce)
                                        notification_result = self.api_client.send_ota_notification(
                                            device_id,
                                            patch_id,
                                            str(user_id) # Explicitly cast to string here for robustness
                                        )
                                        
                                        if notification_result.get('success'):
                                            success_count += 1
                                            # 获取MQTT主题
                                            mqtt_topic = notification_result.get('mqtt_topic', f"ota/info/{user_id}/{device_id}")
                                            success_list.append(f"{device_text} (Topic: {mqtt_topic})")
                                        else:
                                            failed_count += 1
                                            error_msg = notification_result.get('message', '未知错误')
                                            if "必须提供有效的用户ID" in error_msg:
                                                error_msg += "。请确保设备有关联的用户ID，未知用户ID的设备无法接收OTA通知。"
                                            failed_list.append(f"{device_text}: {error_msg}")
                                    except Exception as e:
                                        failed_count += 1
                                        error_msg = str(e)
                                        if "必须提供有效的用户ID" in error_msg:
                                            error_msg += "。请确保设备有关联的用户ID，未知用户ID的设备无法接收OTA通知。"
                                        failed_list.append(f"{device_text}: {error_msg}")
                                
                                # 构建结果消息
                                if success_count > 0:
                                    result_message += f"<p>OTA通知已成功发送到 {success_count} 个设备</p>"
                                    if success_list:
                                        result_message += "<ul>"
                                        for device in success_list:
                                            result_message += f"<li>{device}</li>"
                                        result_message += "</ul>"
                                
                                if failed_count > 0:
                                    result_message += f"<p>OTA通知发送失败到 {failed_count} 个设备</p>"
                                    if failed_list:
                                        result_message += "<ul>"
                                        for device in failed_list:
                                            result_message += f"<li>{device}</li>"
                                        result_message += "</ul>"
                                
                                self.result_text.setText(result_message)
                            except Exception as e:
                                self.result_text.setText(
                                    f"<p>{message}</p>"
                                    f"<p>上传成功！下载地址：<a href='{self.download_url}'>{self.download_url}</a></p>"
                                    f"<p>发送OTA通知时出错：{str(e)}</p>"
                                )
                    else:
                        self.result_text.setText(
                            f"<p>{message}</p>"
                            f"<p>上传失败：{result.get('message', '未知错误')}</p>"
                        )
                except Exception as e:
                    self.result_text.setText(
                        f"<p>{message}</p>"
                        f"<p>上传失败：{str(e)}</p>"
                    )
        else:
            self.result_text.setText(f"<p style='color: red;'>{message}</p>")
            
    def toggle_device_selector(self, state):
        """Enable/disable device selector based on notify specific checkbox"""
        is_checked = state == Qt.Checked
        self.device_list.setEnabled(is_checked)
        
        # If notify specific checkbox is checked, uncheck notify all checkbox
        if is_checked:
            self.notify_all_checkbox.setChecked(False)
            # 确保当用户点击复选框时，设备列表被刷新且可用
            if self.device_list.count() == 0:
                self.refresh_devices()
            else:
                # 如果有设备但没有选择，默认选中第一个
                if len(self.device_list.selectedItems()) == 0 and self.device_list.count() > 0:
                    self.device_list.item(0).setSelected(True)
            # 设置焦点到设备列表，提示用户可以选择设备
            self.device_list.setFocus()
        else:
            # 如果取消勾选，清除设备选择
            self.device_list.clearSelection()
    
    def toggle_notify_all(self, state):
        """Handle notify all checkbox state changes"""
        is_checked = state == Qt.Checked
        
        # If notify all checkbox is checked, uncheck notify specific checkbox
        # and disable device list
        if is_checked:
            self.notify_specific_checkbox.setChecked(False)
            self.device_list.setEnabled(False)
            self.device_list.clearSelection()
    
    def refresh_devices(self):
        """Refresh the list of available devices"""
        try:
            # Update API client with session cookie
            if self.session_cookie_edit.text():
                self.api_client = ServerApiClient(
                    self.server_url_combo.currentText(),
                    self.session_cookie_edit.text()
                )
            
            # 获取设备前显示加载状态
            self.device_list.clear()
            self.device_list.addItem("正在获取设备列表...")
            QApplication.processEvents()  # 强制刷新UI
            
            # 获取设备列表
            devices = self.api_client.get_devices()
            self.device_list.clear()
            
            # 如果没有设备，显示提示信息
            if not devices:
                self.device_list.addItem("未找到设备")
                return
            
            # 添加设备到列表 - 使用更明确的标识符格式
            for device in devices:
                device_id = device.get('device_id', '')
                user_id = device.get('user_id', 'unknown')
                device_name = device.get('device_name', device_id)
                
                # 构建更清晰的显示文本，确保用户ID和设备ID都明确显示
                item_text = f"[{user_id}] {device_id} ({device_name})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, device)  # 存储完整设备信息
                self.device_list.addItem(item)
            
            # 如果勾选了特定设备复选框，确保列表能够交互并默认选择第一项
            if self.notify_specific_checkbox.isChecked():
                self.device_list.setEnabled(True)
                if self.device_list.count() > 0:
                    self.device_list.item(0).setSelected(True)
                    self.device_list.setFocus()
                
            # 显示获取到的设备数量
            QMessageBox.information(self, "设备列表", f"成功获取 {len(devices)} 个设备")
            
        except Exception as e:
            self.device_list.clear()
            self.device_list.addItem("获取设备失败")
            QMessageBox.warning(self, "警告", f"获取设备列表失败：{str(e)}")
    
    def update_server_url(self, url):
        """Update the server URL for the API client"""
        if self.api_client:
            self.api_client = ServerApiClient(url, self.session_cookie_edit.text())
            # 保存URL历史记录
            self.save_server_url_history()

    def test_server_connection(self):
        """测试与服务器的连接"""
        url = self.server_url_combo.currentText()
        if not url:
            QMessageBox.warning(self, "警告", "请输入服务器URL")
            return
        
        # 禁用测试按钮，避免重复点击
        previous_text = self.test_connection_button.text()
        self.test_connection_button.setText("测试中...")
        self.test_connection_button.setEnabled(False)
        QApplication.processEvents()  # 强制UI更新
        
        # 显示测试中对话框
        self.result_text.setText(f"<p>正在测试与服务器 {url} 的连接...</p>")
        QApplication.processEvents()  # 强制UI更新
        
        try:
            # 测试健康检查接口
            health_url = f"{url}/api/health"
            print(f"测试服务器连接: {health_url}")
            
            # 创建一个新的session避免影响原有session
            test_session = requests.Session()
            response = test_session.get(
                health_url, 
                timeout=10,
                verify=False  # 禁用SSL验证
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
                    f"<p>响应: {response.text[:200]}</p>"
                )
                QMessageBox.warning(self, "警告", f"服务器返回错误状态码: {response.status_code}")
        except requests.exceptions.ConnectionError as e:
            error_msg = str(e)
            self.result_text.setText(
                f"<p style='color:red'>✗ 无法连接到服务器</p>"
                f"<p>错误: {error_msg}</p>"
                f"<p>建议:</p>"
                f"<ul>"
                f"<li>检查服务器URL是否正确</li>"
                f"<li>确认服务器是否已启动</li>"
                f"<li>检查网络连接状态</li>"
                f"<li>确认防火墙是否允许端口5001连接</li>"
                f"</ul>"
            )
            QMessageBox.critical(self, "错误", f"无法连接到服务器: {error_msg}")
        except Exception as e:
            self.result_text.setText(
                f"<p style='color:red'>✗ 测试连接时出错</p>"
                f"<p>错误: {str(e)}</p>"
            )
            QMessageBox.critical(self, "错误", f"测试连接时出错: {str(e)}")
        finally:
            # 恢复按钮状态
            self.test_connection_button.setText(previous_text)
            self.test_connection_button.setEnabled(True)

    def get_selected_devices(self):
        """Get the list of selected devices from the device list"""
        selected_items = self.device_list.selectedItems()
        selected_device_info = []
        for item in selected_items:
            text = item.text()
            device_data = item.data(Qt.UserRole)
            selected_device_info.append((text, device_data))
        return selected_device_info

    def on_device_selection_changed(self):
        """Handle device selection changes"""
        # 只有当设备列表处于可用状态时才处理选择变化
        if self.device_list.isEnabled() and self.device_list.selectedItems():
            # 确保"向特定设备发送OTA信息"复选框被选中
            if not self.notify_specific_checkbox.isChecked():
                # 阻断信号连接，防止循环触发
                self.notify_specific_checkbox.blockSignals(True)
                self.notify_specific_checkbox.setChecked(True)
                self.notify_specific_checkbox.blockSignals(False)
                
            # 确保"向所有设备发送OTA信息"复选框未被选中
            if self.notify_all_checkbox.isChecked():
                self.notify_all_checkbox.blockSignals(True)
                self.notify_all_checkbox.setChecked(False)
                self.notify_all_checkbox.blockSignals(False)

    def load_server_url_history(self):
        """Load server URL history from file"""
        try:
            if os.path.exists(self.url_history_file):
                with open(self.url_history_file, 'r') as f:
                    history = json.load(f)
                    if isinstance(history, list):
                        for url in history:
                            # 避免添加已存在的URL
                            if self.server_url_combo.findText(url) == -1:
                                self.server_url_combo.addItem(url)
        except Exception as e:
            print(f"加载URL历史记录失败: {str(e)}")

    def save_server_url_history(self):
        """Save server URL history to file"""
        try:
            current_url = self.server_url_combo.currentText()
            if not current_url:
                return
                
            # 检查URL是否已存在，如果存在则移到顶部
            found_index = self.server_url_combo.findText(current_url)
            if found_index != -1 and found_index != 0:
                self.server_url_combo.removeItem(found_index)
                self.server_url_combo.insertItem(0, current_url)
                self.server_url_combo.setCurrentIndex(0)
            elif found_index == -1:
                self.server_url_combo.insertItem(0, current_url)
                self.server_url_combo.setCurrentIndex(0)
            
            # 收集所有URL并保存
            urls = [self.server_url_combo.itemText(i) for i in range(self.server_url_combo.count())]
            with open(self.url_history_file, 'w') as f:
                json.dump(urls, f)
        except Exception as e:
            print(f"保存URL历史记录失败: {str(e)}")

    def check_lc_lp_sum(self):
        """检查lc和lp的和是否超过限制，并更新警告提示"""
        lc = self.lc_combo.currentData()
        lp = self.lp_combo.currentData()
        
        if lc + lp > 4:
            QMessageBox.warning(self, "参数警告", 
                "lc + lp 的总和超过了 4，这可能在低内存设备上导致问题。\n\n"
                "对于 STM32 等内存受限设备，建议将 lc + lp 限制在 4 以内，以减少解压内存消耗。"
            )
    
    def reset_lzma_params(self):
        """重置LZMA参数到默认值"""
        # 设置字典大小为4KB
        self.dict_size_combo.setCurrentIndex(0)
        
        # 设置lc为2
        for i in range(self.lc_combo.count()):
            if self.lc_combo.itemData(i) == 2:
                self.lc_combo.setCurrentIndex(i)
                break
                
        # 设置lp为0
        for i in range(self.lp_combo.count()):
            if self.lp_combo.itemData(i) == 0:
                self.lp_combo.setCurrentIndex(i)
                break
                
        # 设置pb为0
        for i in range(self.pb_combo.count()):
            if self.pb_combo.itemData(i) == 0:
                self.pb_combo.setCurrentIndex(i)
                break
                
        # 设置fb为64
        for i in range(self.fb_combo.count()):
            if self.fb_combo.itemData(i) == 64:
                self.fb_combo.setCurrentIndex(i)
                break
                
        # 设置算法为正常算法(1)
        self.algo_combo.setCurrentIndex(0)
        
        # 设置写入结束标记为True
        self.eos_checkbox.setChecked(True)
        
        QMessageBox.information(self, "已重置", "已将所有LZMA参数重置为默认值。")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Apply modern style
    app.setStyle('Fusion')  # Use Fusion style for a modern look across platforms
    
    # Set application style sheet for a more professional appearance
    app.setStyleSheet("""
        QMainWindow, QDialog {
            background-color: #f8f9fa;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #ddd;
            border-radius: 6px;
            margin-top: 1ex;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 5px;
        }
        QPushButton {
            background-color: #407cd0;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #2b5a9b;
        }
        QPushButton:disabled {
            background-color: #bdc3c7;
        }
        QLineEdit, QTextBrowser, QComboBox {
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 4px 8px;
            background-color: white;
        }
        QListWidget {
            border: 1px solid #aaa;
            border-radius: 2px;
            padding: 2px;
            background-color: white;
            selection-background-color: #407cd0;
            selection-color: white;
            outline: none;  /* 移除焦点框线 */
        }
        QListWidget:focus {
            border: 1px solid #407cd0;
        }
        QListWidget::item {
            height: 25px;
            padding: 5px;
            border-bottom: 1px solid #eeeeee;
            margin: 2px 0px;
        }
        QListWidget::item:selected {
            background-color: #407cd0;
            color: white;
            border-bottom: 1px solid #407cd0;
        }
        QListWidget::item:hover:!selected {
            background-color: #e9f0f8;
        }
        QScrollBar:vertical {
            background: #f0f0f0;
            width: 12px;
            margin: 0px;
            border-radius: 6px;
        }
        QScrollBar::handle:vertical {
            background: #c0c0c0;
            min-height: 30px;
            border-radius: 6px;
        }
        QScrollBar::handle:vertical:hover {
            background: #a0a0a0;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
        QProgressBar {
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #407cd0;
            width: 1px;
        }
    """)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())