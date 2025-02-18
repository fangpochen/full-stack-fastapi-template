"""
配置管理模块
负责管理应用程序的所有配置项，包括API配置、FFmpeg配置等
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any

class Config:
    """配置管理类"""
    
    def __init__(self):
        # 基础配置
        self.config_dir = Path("app/resources/config")
        self.config_file = self.config_dir / "config.json"
        self.default_config = {
            "api": {
                "base_url": "http://localhost:8000",
                "api_key": "",
                "timeout": 30
            },
            "ffmpeg": {
                "ffmpeg_path": "ffmpeg.exe",
                "ffprobe_path": "ffprobe.exe",
                "temp_dir": "temp"
            },
            "processing": {
                "max_concurrent_tasks": 3,
                "default_output_dir": "output"
            }
        }
        
        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载配置
        self.config = self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # 如果配置文件不存在，创建默认配置
                self.save_config(self.default_config)
                return self.default_config
        except Exception as e:
            logging.error(f"加载配置文件失败: {str(e)}")
            return self.default_config
            
    def save_config(self, config: Dict[str, Any]) -> None:
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            self.config = config
        except Exception as e:
            logging.error(f"保存配置文件失败: {str(e)}")
            
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
        
    def set(self, key: str, value: Any) -> None:
        """设置配置项"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config(self.config)
        
    def update_api_key(self, api_key: str) -> None:
        """更新API密钥"""
        self.set('api.api_key', api_key)
        
    def update_api_url(self, base_url: str) -> None:
        """更新API基础URL"""
        self.set('api.base_url', base_url) 