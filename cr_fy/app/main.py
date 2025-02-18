"""
应用程序主入口
"""
import sys
import multiprocessing
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMessageBox
from app.ui.main_window import MainWindow
from app.core.logger import setup_logging

def main():
    """程序入口"""
    # 多进程支持
    multiprocessing.freeze_support()
    
    # 检查日期
    expiry_date = datetime(2025, 3, 31)
    current_date = datetime.now()
    
    if current_date > expiry_date:
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "错误", "服务已过期")
        return 1
    
    # 设置日志
    setup_logging()
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用
    return app.exec_()

if __name__ == '__main__':
    sys.exit(main()) 