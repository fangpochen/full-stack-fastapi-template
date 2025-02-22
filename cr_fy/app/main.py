"""
主程序入口模块
负责初始化应用程序、配置和UI界面
"""
import sys
import os
import multiprocessing
import logging
from datetime import datetime
from pathlib import Path
import torch
import whisper
from PyQt5.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.core.logger import setup_logging
from app.core.config import Config
from app.utils.key_verification import verify_key
from app.core.audio_processor import OptimizedProcessor

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath('.')
    return os.path.join(base_path, relative_path)

def load_whisper_model():
    """
    预加载Whisper模型
    在应用启动时加载,避免多线程同时加载
    """
    logger = logging.getLogger(__name__)
    try:
        # 获取模型路径
        MODELS_DIR = os.path.join(os.path.dirname(get_resource_path('.')), 'models')
        model_path = os.path.join(MODELS_DIR, 'small.pt')
        logger.info(f"检查模型文件: {model_path}")
            
        if os.path.exists(model_path):
            logger.info(f"找到模型文件: {model_path}")
            # 直接加载整个模型
            model = torch.load(model_path, map_location='cpu')
            # 设置为评估模式
            model.eval()
            # 移动到适当的设备
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model = model.to(device)
            logger.info(f"成功加载Whisper模型到 {device} 设备")
            # 将模型保存到 OptimizedProcessor 的静态变量中
            OptimizedProcessor._model = model
            return True
        else:
            logger.error(f"模型文件不存在: {model_path}")
            return False
            
    except Exception as e:
        logger.error(f"加载Whisper模型失败: {str(e)}")
        return False

def main():
    """程序入口函数"""
    # 多进程支持
    multiprocessing.freeze_support()
    
    try:
        # 设置日志系统
        setup_logging()
        logger = logging.getLogger(__name__)
        
        # 初始化配置
        config = Config()
        
        # 预加载Whisper模型
        logger.info("开始预加载Whisper模型...")
        if not load_whisper_model():
            logger.error("预加载Whisper模型失败,应用程序将退出")
            return 1
        
        # 创建应用
        app = QApplication(sys.argv)
        
        # 创建主窗口
        window = MainWindow()
        
        # 显示窗口
        window.show()
        
        # 运行应用
        return app.exec_()
        
    except Exception as e:
        print(f"程序启动失败: {str(e)}")
        return 1

if __name__ == '__main__':
    sys.exit(main()) 