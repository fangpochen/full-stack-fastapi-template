import os

from app.core.audio_processor import OptimizedProcessor
from app.core.process_thread import VideoProcessThread  # 导入核心实现
os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.*=false'
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QFileDialog, QTextEdit, QMessageBox, QSpinBox, QInputDialog, QLineEdit, QDialog, QListWidget, QListWidgetItem, QMenu, QDoubleSpinBox, QComboBox
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QMetaType
from PyQt5.QtGui import QPixmap, QPalette, QBrush, QTextCursor, QIcon
import sys
import os
from pathlib import Path
from app.core.logger import Logger
import subprocess
import time
from app.utils.key_verification import verify_key
import json
import multiprocessing
import logging
from app.core.api_client import APIClient
from app.core.config import Config


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 获取日志记录器
        self.logger = Logger().get_logger('ui')
        # 初始化基本属性
        self.dir_limits = {}  # 添加这行
        self.input_dirs = []
        self.output_dir = ""
        self.config_file = 'config.json'
        
        # 验证相关
        self.verified = False
        self._verify_key()
        if not self.verified:
            sys.exit(1)
        
        # UI初始化
        self._init_ui()
        
        # 加载配置
        self.load_config()
        
        # 更新界面
        self.update_dir_list()
        self.update_video_count()
        
        self.current_process = None
        self.is_processing = False
        self.process_thread = None
        
        # 连接按钮信号
        self.select_input_dir_btn.clicked.connect(self.select_input_directory)
        self.select_output_dir_btn.clicked.connect(self.select_output_directory)
        self.cut_btn.clicked.connect(self.on_cut_clicked)
        self.stop_btn.clicked.connect(self.on_stop_clicked)

        # 设置定时器进行密钥校验
        self.verify_timer = QTimer()
        self.verify_timer.timeout.connect(self._periodic_verify)
        self.verify_timer.start(5 * 60 * 1000)  # 5分钟 = 5 * 60 * 1000 毫秒

        self._setup_log_display()

        # 添加一个类变量来存储上次验证时间
        self._last_verify_time = time.time()
        # 设置验证间隔时间（例如每30分钟验证一次）
        self._verify_interval = 30 * 60  # 30分钟，单位：秒


    def _verify_key(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("密钥验证")
        layout = QVBoxLayout()

        # 创建输入框和复选框
        key_input = QLineEdit()
        remember_cb = QCheckBox("记住密钥")
        
        # 从本地文件读取保存的密钥
        if os.path.exists('key.txt'):
            try:
                with open('key.txt', 'r') as f:
                    saved_key = f.read().strip()
                    key_input.setText(saved_key)
                    remember_cb.setChecked(True)
            except:
                pass

        # 添加到布局
        layout.addWidget(QLabel("请输入密钥:"))
        layout.addWidget(key_input)
        layout.addWidget(remember_cb)

        # 创建按钮
        buttons = QHBoxLayout()
        ok_button = QPushButton("确定")
        cancel_button = QPushButton("取消")
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

        dialog.setLayout(layout)

        # 连接按钮信号
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            key = key_input.text()
            if key and verify_key(key):
                self.verified = True
                # 如果选中"记住密钥"，保存密钥到本地
                if remember_cb.isChecked():
                    try:
                        with open('key.txt', 'w') as f:
                            f.write(key)
                    except:
                        pass
                QMessageBox.information(None, "验证成功", "密钥验证通过！")
            else:
                QMessageBox.critical(None, "验证失败", "无效的密钥！")
        else:
            QMessageBox.critical(None, "验证失败", "请输入密钥！")

    def _init_ui(self):
        # 基础设置
        self.setWindowTitle("视频剪辑工具")
        self.setGeometry(100, 100, 800, 800)
        
        # 设置窗口图标
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(os.path.dirname(__file__))
        icon_path = os.path.join(base_path, 'icon.ico')
        self.setWindowIcon(QIcon(icon_path))
        
        self._set_background()
        
        # 创建主布局
        central_widget = QWidget()
        central_widget.setAutoFillBackground(False)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)

        # 创建目录列表控件
        self.dir_list = QListWidget()
        self.dir_list.setStyleSheet(self._get_style("list"))
        self.dir_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.dir_list.customContextMenuRequested.connect(self._show_dir_context_menu)

        # 先创建日志区域
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet(self._get_style("log"))
        self.log_area.setMinimumHeight(200)

        # 然后再添加其他组件
        main_layout.addLayout(self._create_checkboxes())
        main_layout.addLayout(self._create_buttons())
        main_layout.addWidget(self._create_video_count_label())
        main_layout.addWidget(self._create_status_label())
        main_layout.addWidget(self.log_area)
        main_layout.addLayout(self._create_thread_layout())
        main_layout.addWidget(self.dir_list)

        # 初始化复选框状态
        self.use_gpu_cb.setChecked(True)
        self.delete_after_cb.setChecked(False)
        
        # 确保复选框的信号连接在初始化之后
        self._setup_checkbox_connections()

    def _set_background(self):
        try:
            # 获取打包后的资源路径
            if getattr(sys, 'frozen', False):
                # 如果是打包后的可执行文件
                base_path = sys._MEIPASS
            else:
                # 如果是开发环境
                base_path = os.path.abspath(os.path.dirname(__file__))
            
            background_path = os.path.join(base_path, '壁纸.jpg')
            
            # 检查文件是否存在
            if os.path.exists(background_path):
                background = QPixmap(background_path)
                if not background.isNull():
                    background = background.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                    palette = self.palette()
                    palette.setBrush(QPalette.Window, QBrush(background))
                    self.setPalette(palette)
                else:
                    self._set_default_background()
            else:
                self._set_default_background()
                self.logger.warning(f"背景图片不存在: {background_path}")
        except Exception as e:
            self.logger.error(f"设置背景图片失败: {str(e)}")
            self._set_default_background()
            
    def _set_default_background(self):
        """设置默认背景色"""
        palette = self.palette()
        # 设置浅灰色背景
        palette.setColor(QPalette.Window, Qt.lightGray)
        self.setPalette(palette)

    def _create_checkboxes(self):
        self.use_gpu_cb = QCheckBox("使用GPU")
        self.more_effects_cb = QCheckBox("更多效果")
        self.delete_after_cb = QCheckBox("剪辑后删除原视频")
        self.loop_process_cb = QCheckBox("循环剪辑")
        
        # 创建布局并设置间距
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # 添加基本选项
        layout.addWidget(self.use_gpu_cb)
        layout.addWidget(self.more_effects_cb)
        layout.addWidget(self.delete_after_cb)
        layout.addWidget(self.loop_process_cb)
        layout.addSpacing(20)
        
        # 创建方案选择下拉框
        plan_layout = QHBoxLayout()
        plan_label = QLabel("选择方案:")
        plan_label.setStyleSheet(self._get_style("label"))
        self.plan_combo = QComboBox()
        self.plan_combo.setStyleSheet(self._get_style("combobox"))
        self.plan_combo.setMinimumWidth(300)
        
        # 添加一个刷新按钮
        refresh_btn = QPushButton("刷新方案")
        refresh_btn.setStyleSheet(self._get_style("button"))
        refresh_btn.clicked.connect(self._load_plans)
        
        plan_layout.addWidget(plan_label)
        plan_layout.addWidget(self.plan_combo)
        plan_layout.addWidget(refresh_btn)
        plan_layout.addStretch()
        
        layout.addLayout(plan_layout)
        
        # 初始化方案数据存储
        self.plans_data = []  # 改为列表存储
        
        # 加载方案列表
        self._load_plans()
        
        return layout

    def _setup_checkbox_connections(self):
        """设置复选框信号连接"""
        # 先断开所有信号连接，防止重复
        self.delete_after_cb.stateChanged.disconnect() if self.delete_after_cb.receivers(self.delete_after_cb.stateChanged) > 0 else None
        
        # 重新连接信号
        self.delete_after_cb.stateChanged.connect(self._on_delete_checkbox_changed)

    def _on_delete_checkbox_changed(self, state):
        """删除模式复选框状态改变处理"""
        if state == Qt.Checked:
            self.append_to_log("删除模式已启用")
            QMessageBox.warning(
                self,
                "删除模式提示",
                "删除模式下请谨慎操作，处理完成后原视频将被删除",
                QMessageBox.Ok
            )

    def _create_buttons(self):
        self.select_input_dir_btn = QPushButton("选择输入目录")
        self.select_output_dir_btn = QPushButton("选择输出目录")
        self.cut_btn = QPushButton("剪切视频")
        self.stop_btn = QPushButton("停止剪辑")
        self.stop_btn.setEnabled(False)
        
        style = self._get_style("button")
        # 设置停止按钮的特殊样式
        stop_style = style + """
            QPushButton:enabled { 
                background-color: rgba(255, 100, 100, 150);
            }
            QPushButton:hover:enabled { 
                background-color: rgba(255, 100, 100, 200);
            }
        """
        self.stop_btn.setStyleSheet(stop_style)
        
        for btn in [self.select_input_dir_btn, self.select_output_dir_btn, self.cut_btn]:
            btn.setStyleSheet(style)
        
        layout = QHBoxLayout()
        layout.setSpacing(20)
        for btn in [self.select_input_dir_btn, self.select_output_dir_btn, 
                   self.cut_btn, self.stop_btn]:
            layout.addWidget(btn)
        
        # 添加删除目录按钮
        self.delete_dir_btn = QPushButton("删除选中目录")
        self.delete_dir_btn.setStyleSheet(style)
        self.delete_dir_btn.clicked.connect(self._delete_selected_dir)
        layout.addWidget(self.delete_dir_btn)
        
        return layout

    def _delete_selected_dir(self):
        current_item = self.dir_list.currentItem()
        if current_item:
            row = self.dir_list.row(current_item)
            self.dir_list.takeItem(row)
            del self.input_dirs[row]
            self.update_video_count()
            self.save_config()  # 保存配置

    def _create_video_count_label(self):
        self.video_count_label = QLabel("未选择目录")
        self.video_count_label.setAlignment(Qt.AlignCenter)
        self.video_count_label.setStyleSheet(self._get_style("label"))
        return self.video_count_label

    def _create_status_label(self):
        self.status_label = QLabel("就绪")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(self._get_style("label"))
        return self.status_label

    def _create_thread_layout(self):
        thread_layout = QHBoxLayout()
        
        # CPU线程数设置
        thread_label = QLabel("CPU线程数:")
        thread_label.setStyleSheet(self._get_style("label"))
        self.thread_spinbox = QSpinBox()
        self.thread_spinbox.setMinimum(0)
        self.thread_spinbox.setMaximum(32)
        self.thread_spinbox.setValue(10)
        self.thread_spinbox.setStyleSheet(self._get_style("spinbox"))
        
        # 视频数量限制设置
        limit_label = QLabel("每个目录限制数量:")
        limit_label.setStyleSheet(self._get_style("label"))
        self.limit_spinbox = QSpinBox()
        self.limit_spinbox.setMinimum(0)
        self.limit_spinbox.setMaximum(999999)
        self.limit_spinbox.setValue(50)
        self.limit_spinbox.setStyleSheet(self._get_style("spinbox"))
        self.limit_spinbox.setToolTip("0表示不限制数量，默认限制50个")
        
        # 添加画布位置设置
        canvas_y_label = QLabel("画布位置(0-1):")
        canvas_y_label.setStyleSheet(self._get_style("label"))
        self.canvas_y_spinbox = QDoubleSpinBox()  # 使用QDoubleSpinBox支持小数
        self.canvas_y_spinbox.setMinimum(0.0)
        self.canvas_y_spinbox.setMaximum(1.0)
        self.canvas_y_spinbox.setValue(0.6)  # 默认值0.6
        self.canvas_y_spinbox.setSingleStep(0.1)  # 步长0.1
        self.canvas_y_spinbox.setStyleSheet(self._get_style("spinbox"))
        self.canvas_y_spinbox.setToolTip("画布在视频中的相对位置(0表示顶部,1表示底部)")
        
        thread_layout.addWidget(thread_label)
        thread_layout.addWidget(self.thread_spinbox)
        thread_layout.addSpacing(20)
        thread_layout.addWidget(limit_label)
        thread_layout.addWidget(self.limit_spinbox)
        thread_layout.addSpacing(20)
        thread_layout.addWidget(canvas_y_label)
        thread_layout.addWidget(self.canvas_y_spinbox)
        
        return thread_layout

    def _get_style(self, widget_type):
        base_font = """
            font-family: "Microsoft YaHei", "SimHei", "黑体";
            font-weight: bold;
        """
        match widget_type:
            case "combobox":
                return f"""
                    QComboBox {{ 
                        {base_font}
                        font-size: 14pt; 
                        padding: 5px;
                        background-color: rgba(255, 255, 255, 150);
                        border: 1px solid black;
                        border-radius: 5px;
                        min-height: 30px;
                    }}
                    QComboBox::drop-down {{
                        border: none;
                        padding-right: 10px;
                    }}
                    QComboBox::down-arrow {{
                        width: 12px;
                        height: 12px;
                    }}
                    QComboBox QAbstractItemView {{
                        {base_font}
                        background-color: white;
                        selection-background-color: lightgray;
                        selection-color: black;
                    }}
                """
            case "button":
                return f"""
                    QPushButton {{ 
                        {base_font}
                        font-size: 16pt; 
                        padding: 10px; 
                        min-width: 150px;
                        color: black;
                        background-color: rgba(255, 255, 255, 150);
                        border: 2px solid black;
                        border-radius: 10px;
                    }}
                    QPushButton:hover {{
                        background-color: rgba(255, 255, 255, 200);
                    }}
                """
            case "label":
                return f"""
                    QLabel {{ 
                        {base_font}
                        font-size: 14pt; 
                        padding: 10px;
                        color: black;
                        background-color: rgba(255, 255, 255, 150);
                        border-radius: 5px;
                    }}
                """
            case "log":
                return f"""
                    QTextEdit {{ 
                        {base_font}
                        font-size: 12pt; 
                        padding: 10px;
                        color: black;
                        background-color: rgba(255, 255, 255, 150);
                        border-radius: 5px;
                        border: 1px solid black;
                    }}
                """
            case "spinbox":
                return f"""
                    QSpinBox, QDoubleSpinBox {{
                        {base_font}
                        font-size: 14pt;
                        padding: 5px;
                        background-color: rgba(255, 255, 255, 150);
                        border-radius: 5px;
                        border: 1px solid black;
                    }}
                """
            case "list":
                return f"""
                    QListWidget {{ 
                        {base_font}
                        font-size: 12pt; 
                        padding: 10px;
                        color: black;
                        background-color: rgba(255, 255, 255, 150);
                        border-radius: 5px;
                        border: 1px solid black;
                    }}
                """
            case _:
                return ""

    def _init_signals(self):
        self.select_input_dir_btn.clicked.connect(self.select_input_directory)
        self.select_output_dir_btn.clicked.connect(self.select_output_directory)
        self.cut_btn.clicked.connect(self.on_cut_clicked)
        self.stop_btn.clicked.connect(self.on_stop_clicked)

    def select_input_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择输入目录")
        if dir_path:
            # 获取所有子目录
            subdirs = [str(p) for p in Path(dir_path).rglob('*') if p.is_dir()]
            
            # 过滤掉已存在的目录
            new_dirs = [d for d in subdirs if d not in self.input_dirs]
            
            if new_dirs:
                # 询问用户是否添加所有子目录
                msg = QMessageBox()
                msg.setWindowTitle("添加子目录")
                msg.setText(f"找到 {len(new_dirs)} 个子目录，是否添加？")
                msg.setInformativeText("选择'否'将只添加主目录")
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
                msg.setDefaultButton(QMessageBox.Yes)
                
                ret = msg.exec_()
                
                if ret == QMessageBox.Yes:
                    # 只添加子目录
                    self.input_dirs.extend(new_dirs)
                    self.append_to_log(f"已添加 {len(new_dirs)} 个子目录")
                elif ret == QMessageBox.No:
                    # 只添加主目录
                    if dir_path not in self.input_dirs:
                        self.input_dirs.append(dir_path)
                        self.append_to_log(f"已添加主目录: {dir_path}")
                
                self.update_dir_list()
                self.update_video_count()
                self.save_config()

    def update_dir_list(self):
        self.dir_list.clear()
        for i, dir_path in enumerate(self.input_dirs, 1):
            limit = self.dir_limits.get(dir_path, 0)
            limit_text = f" (限制: {limit}个)" if limit > 0 else ""
            item = QListWidgetItem(f"{i}. {Path(dir_path).name}{limit_text}")
            item.setData(Qt.UserRole, dir_path)
            self.dir_list.addItem(item)

    def update_video_count(self):
        total_videos = 0
        for dir_path in self.input_dirs:
            video_files = [f for f in Path(dir_path).rglob("*") 
                          if f.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv']]
            count = len(video_files)
            if count == 0:
                self.logger.warning(f"目录 {dir_path} 中未找到视频文件")
            else:
                self.logger.info(f"目录 {dir_path} 中找到 {count} 个视频文件")
                for video in video_files:
                    self.logger.debug(f"  - {video}")
            total_videos += count
        
        self.video_count_label.setText(f"共找到 {total_videos} 个视频文件")
        if total_videos == 0:
            self.logger.warning("所有目录中都未找到视频文件！")
        else:
            self.logger.info(f"目录数: {len(self.input_dirs)}, 总视频数: {total_videos}")

    def select_output_directory(self):
        self.output_dir = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if self.output_dir:
            self.status_label.setText(f"输出目录: {self.output_dir}")
            self.append_to_log(f"已选择输出目录: {self.output_dir}")
            self.save_config()  # 保存配置
    
    def on_cut_clicked(self):
        # 检查目录是否存在
        if not self.input_dirs or not self.output_dir:
            QMessageBox.warning(
                self,
                "错误",
                "请先选择输入和输出目录",
                QMessageBox.Ok
            )
            return
            
        # 获取选中的方案
        current_text = self.plan_combo.currentText()
        selected_plan = None
        
        # 从显示文本中提取方案名称
        plan_name = current_text.split(" - ")[0] if " - " in current_text else current_text
        
        # 在plans_data列表中查找匹配的方案
        for plan in self.plans_data:
            if plan["name"] == plan_name:
                selected_plan = plan
                break
                
        if not selected_plan:
            QMessageBox.warning(
                self,
                "错误",
                "请先选择处理方案",
                QMessageBox.Ok
            )
            return
            
        # 创建处理线程时传递限制信息
        self.process_thread = VideoProcessThread(
            input_dir=self.input_dirs[0],
            output_dir=self.output_dir,
            use_gpu=self.use_gpu_cb.isChecked(),
            add_glow=self.more_effects_cb.isChecked(),
            add_border=self.more_effects_cb.isChecked(),
            add_grid=self.more_effects_cb.isChecked(),
            threads=self.thread_spinbox.value(),
            blur_bg=selected_plan.get("blur_bg", False),
            delete_after=self.delete_after_cb.isChecked(),
            loop_process=self.loop_process_cb.isChecked(),
            add_subtitle=selected_plan.get("add_subtitle", False),
            canvas_y=self.canvas_y_spinbox.value(),
            selected_plan_id=selected_plan.get("id", 1)
        )
        self.process_thread.dir_limits = self.dir_limits
        self.process_thread.input_dirs = self.input_dirs
        self.process_thread.selected_plans = [selected_plan]
        
        self.append_to_log("\n=== 线程参数 ===")
        self.append_to_log(f"线程输入目录: {self.process_thread.input_dirs}")
        self.append_to_log(f"线程选中方案: {self.process_thread.selected_plans}")
        self.append_to_log(f"线程删除选项: {self.process_thread.delete_after}")
        self.append_to_log(f"线程字幕选项: {self.process_thread.add_subtitle}")
        
        self.is_processing = True
        self.status_label.setText("正在剪切视频...")
        
        # 连接信号
        self.process_thread.log_message.connect(self.append_to_log)
        self.process_thread.finished.connect(self.on_process_finished)
        self.process_thread.error.connect(self.on_process_error)
        self.process_thread.start()
        
        # 更新按钮状态
        self.cut_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.select_input_dir_btn.setEnabled(False)
        self.select_output_dir_btn.setEnabled(False)

    def on_process_finished(self, processed_count, total_time):
        """处理完成的回调函数"""
        self.process_thread = None
        self.cut_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        # 格式化时间字符串
        hours = int(total_time // 3600)
        minutes = int((total_time % 3600) // 60)
        seconds = total_time % 60
        
        if hours > 0:
            time_str = f"{hours}小时{minutes}分{seconds:.1f}秒"
        elif minutes > 0:
            time_str = f"{minutes}分{seconds:.1f}秒"
        else:
            time_str = f"{seconds:.1f}秒"
            
        self.status_label.setText("处理完成")
        QMessageBox.information(
            self,
            "处理完成",
            f"所有视频已处理完成！\n\n"
            f"共处理 {processed_count} 个视频\n"
            f"总用时：{time_str}",
            QMessageBox.Ok
        )

    def on_process_error(self, error_msg):
        self.is_processing = False
        self.current_process = None
        error_msg = f"处理失败: {error_msg}"
        self.status_label.setText(error_msg)
        self.append_to_log(error_msg)
        
        # 恢复按钮状态
        self.cut_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.select_input_dir_btn.setEnabled(True)
        self.select_output_dir_btn.setEnabled(True)
        
        # 显示错误提示框
        QMessageBox.critical(
            self,
            "处理失败",
            f"视频处理失败：\n{error_msg}",
            QMessageBox.Ok
        )

    def on_stop_clicked(self):
        """停止处理"""
        if self.process_thread and self.process_thread.isRunning():
            self.append_to_log("正在停止处理...")
            self.append_to_log("注意：已经开始处理的视频将继续完成，新的视频将不再开始处理")
            self.status_label.setText("正在停止...")
            
            # 停止处理线程
            self.process_thread.stop()
            self.stop_btn.setEnabled(False)
            
            # 恢复其他按钮状态
            self.cut_btn.setEnabled(True)
            self.select_input_dir_btn.setEnabled(True)
            self.select_output_dir_btn.setEnabled(True)

    def set_current_process(self, process):
        self.current_process = process

    def update_log_display(self):
        """从日志文件更新显示"""
        try:
            with open('log.log', 'r', encoding='utf-8') as f:
                f.seek(self.last_log_position)
                new_logs = f.read()
                if new_logs:
                    self.log_area.append(new_logs)
                    self.last_log_position = f.tell()
        except FileNotFoundError:
            pass

    def _show_dir_context_menu(self, position):
        """显示目录列表的右键菜单"""
        menu = QMenu()
        delete_action = menu.addAction("删除")
        clear_action = menu.addAction("清空列表")
        set_limit_action = menu.addAction("设置剪辑数量")  # 新增菜单项
        
        action = menu.exec_(self.dir_list.mapToGlobal(position))
        
        if action == delete_action:
            # 获取当前选中的项
            current_item = self.dir_list.currentItem()
            if current_item:
                # 获取项的索引
                row = self.dir_list.row(current_item)
                # 从列表和数据中删除
                self.dir_list.takeItem(row)
                del self.input_dirs[row]
                self.update_video_count()
                self.save_config()  # 保存配置
        elif action == clear_action:
            # 清空列表
            self.dir_list.clear()
            self.input_dirs.clear()
            self.update_video_count()
        elif action == set_limit_action:
            current_item = self.dir_list.currentItem()
            if current_item:
                dir_path = current_item.data(Qt.UserRole)
                self._show_limit_dialog(dir_path)

    def _show_limit_dialog(self, dir_path):
        """显示设置剪辑数量的对话框"""
        current_limit = self.dir_limits.get(dir_path, 0)
        number, ok = QInputDialog.getInt(
            self,
            "设置剪辑数量",
            f"请输入要处理的视频数量\n(0表示处理所有视频)：\n{Path(dir_path).name}",
            current_limit,
            0, 999999, 1
        )
        
        if ok:
            if number == 0:
                # 如果设置为0，则删除限制
                self.dir_limits.pop(dir_path, None)
            else:
                self.dir_limits[dir_path] = number
            
            # 更新显示
            self._update_dir_list_display()
            self.save_config()

    def _update_dir_list_display(self):
        """更新目录列表显示，包含剪辑数量限制信息"""
        self.dir_list.clear()
        for i, dir_path in enumerate(self.input_dirs, 1):
            limit = self.dir_limits.get(dir_path, 0)
            limit_text = f" (限制: {limit}个)" if limit > 0 else ""
            item = QListWidgetItem(f"{i}. {Path(dir_path).name}{limit_text}")
            item.setData(Qt.UserRole, dir_path)
            self.dir_list.addItem(item)

    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 检查目录是否存在
                    input_dirs = config.get('input_dirs', [])
                    output_dir = config.get('output_dir', '')
                    
                    # 只加载存在的目录
                    self.input_dirs = [d for d in input_dirs if os.path.exists(d)]
                    self.output_dir = output_dir if os.path.exists(output_dir) else ""
                    
                    # 如果有目录被过滤，保存更新后的配置
                    if len(self.input_dirs) != len(input_dirs) or (output_dir and not self.output_dir):
                        self.save_config()
                    
                    self.dir_limits = config.get('dir_limits', {})  # 新增：加载目录限制
                    
                    # 加载全局限制
                    if 'global_limit' in config:
                        self.limit_spinbox.setValue(config['global_limit'])
        except Exception as e:
            self.append_to_log(f"加载配置失败: {str(e)}")

    def save_config(self):
        """保存配置到文件"""
        try:
            config = {
                'input_dirs': self.input_dirs,
                'output_dir': self.output_dir,
                'dir_limits': self.dir_limits,
                'global_limit': self.limit_spinbox.value()  # 保存全局限制
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.append_to_log(f"保存配置失败: {str(e)}")

    def closeEvent(self, event):
        """窗口关闭时保存配置"""
        self.save_config()
        event.accept()

    def _periodic_verify(self):
        """定时校验密钥"""
        # 检查是否到达验证间隔时间
        current_time = time.time()
        if current_time - self._last_verify_time < self._verify_interval:
            return
            
        try:
            if os.path.exists('key.txt'):
                with open('key.txt', 'r') as f:
                    key = f.read().strip()
                    # 使用后台模式进行验证
                    if not verify_key(key, is_background=True):
                        QMessageBox.critical(self, "验证失败", "密钥已失效，请重新验证！")
                        self.close()
            else:
                QMessageBox.critical(self, "验证失败", "未找到密钥文件，请重新验证！")
                self.close()
                
            # 更新上次验证时间
            self._last_verify_time = current_time
            
        except Exception as e:
            self.logger.error(f"定时验证失败: {e}")
            QMessageBox.critical(self, "验证失败", f"密钥验证出错：{str(e)}")
            self.close()

    def append_to_log(self, message):
        """更新日志显示并写入日志文件"""
        # 更新UI显示
        self.log_area.append(message)
        # 写入日志（添加UI标记，避免与处理日志混淆）
        self.logger.info(f"[UI] {message}")

    def _setup_log_display(self):
        """设置日志显示"""
        # 创建日志目录
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        self.log_file = log_dir / 'log.log'
        
        def write_to_log(message):
            # 写入日志文件
            with open(self.log_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f'{timestamp} - {message}\n')
            # 更新UI显示
            self.log_area.append(message)

        # 替换原来的 append_to_log 方法
        self.append_to_log = write_to_log

    def _load_plans(self):
        """从服务器加载方案列表"""
        self.plan_combo.clear()
        self.plans_data = []  # 改为列表存储
        
        try:
            # 获取方案列表
            config = Config()
            api_client = APIClient(config)
            plans = api_client.get_plans()
            
            if plans:
                for plan in plans:
                    # 使用方案名称和描述作为显示文本
                    display_text = f"{plan['name']} - {plan['description']}"
                    self.plan_combo.addItem(display_text)
                    # 存储方案数据
                    self.plans_data.append(plan)  # 直接存储整个plan对象
                self.append_to_log("成功加载方案列表")
            else:
                # 显示错误对话框
                QMessageBox.warning(
                    self,
                    "加载失败",
                    "获取方案列表失败。请联系作者喝杯咖啡吧~",
                    QMessageBox.Ok
                )
                self.append_to_log("获取方案列表失败，请联系作者")
        except Exception as e:
            self.append_to_log(f"加载方案列表出错: {str(e)}")
            QMessageBox.warning(
                self,
                "加载失败",
                "获取方案列表失败。请联系作者喝杯咖啡吧~\n",
                QMessageBox.Ok
            )

if __name__ == '__main__':
    # 检查日期
    multiprocessing.freeze_support()
    expiry_date = datetime(2025, 3, 31)  # 设置为明天的日期
    current_date = datetime.now()
    
    if current_date > expiry_date:
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "错误", "服务已过期")
        sys.exit(1)
    
    # 正常运行程序
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
