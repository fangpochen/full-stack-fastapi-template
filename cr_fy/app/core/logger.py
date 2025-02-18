"""
日志管理模块
提供统一的日志配置和管理功能
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

class Logger:
    """日志管理类"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, log_dir: str = "logs", log_level: int = logging.INFO):
        if hasattr(self, 'initialized'):
            return
            
        self.log_dir = Path(log_dir)
        self.log_level = log_level
        
        # 确保日志目录存在
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置根日志记录器
        self.setup_root_logger()
        self.initialized = True
        
    def setup_root_logger(self) -> None:
        """配置根日志记录器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # 清除现有的处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # 添加控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(self.get_formatter())
        root_logger.addHandler(console_handler)
        
        # 添加文件处理器
        file_handler = RotatingFileHandler(
            self.log_dir / "log.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(self.get_formatter())
        root_logger.addHandler(file_handler)
        
    def get_formatter(self) -> logging.Formatter:
        """获取日志格式化器"""
        return logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """获取指定名称的日志记录器"""
        return logging.getLogger(name)
        
def setup_logging(log_dir: str = "logs", log_level: int = logging.INFO) -> Logger:
    """设置日志系统"""
    return Logger(log_dir, log_level)

# 创建全局logger实例
logger = Logger().get_logger('app') 