"""
API客户端模块
负责与服务器进行通信，获取处理命令和方案
"""
import sys
import aiohttp
import logging
import platform
import socket
import uuid
import cpuinfo
import requests
from typing import Dict, Any, List, Optional
from .config import Config

class APIClient:
    """API客户端类，处理与服务器的所有通信"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_url = config.get('api.base_url', 'http://localhost:8000')
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
            self.session = None
            
    def get_plans(self) -> List[Dict[str, Any]]:
        """
        获取所有可用的处理方案
        
        Returns:
            List[Dict[str, Any]]: 方案列表
        """
        try:
            url = f"{self.base_url}/api/v1/ffmpeg/plans"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"获取方案列表失败: {str(e)}")
            return []
            
    def get_ffmpeg_command(self, plan_id: int, more_effects: bool = False, canvas_y: float = 0.6) -> Dict[str, str]:
        """
        获取FFmpeg处理命令
        
        Args:
            plan_id: 处理方案ID
            more_effects: 是否启用更多效果
            canvas_y: 字幕区域的Y轴位置，默认0.6
                
        Returns:
            Dict[str, str]: 包含GPU和CPU处理命令的响应
        """
        try:
            self.logger.debug(f"获取FFmpeg命令: {plan_id}, {more_effects}, {canvas_y}")
            url = f"{self.base_url}/api/v1/ffmpeg/command"
            payload = {
                "plan_id": plan_id,
                "more_effects": more_effects,
                "canvas_y": canvas_y
            }
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            self.logger.debug(f"获取FFmpeg命令结果: {result}")
            if "gpu_command" in result and "cpu_command" in result:
                return result
            else:
                self.logger.error("获取FFmpeg命令失败：返回数据格式错误")
                return {}
                
        except Exception as e:
            self.logger.error(f"获取FFmpeg命令失败: {str(e)}")
            return {}
            
    async def get_processing_plans(self) -> List[Dict[str, Any]]:
        """
        获取可用的处理方案列表
        
        Returns:
            List[Dict[str, Any]]: 处理方案列表
        """
        try:
            async with self.session.get(f"{self.base_url}/api/plans") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    self.logger.error(f"获取处理方案失败: {response.status}")
                    return []
        except Exception as e:
            self.logger.error(f"获取处理方案时出错: {str(e)}")
            return []
        
    def verify_api_key(self, api_key: str, is_background: bool = False) -> bool:
        """
        验证API密钥（同步方法）
        
        Args:
            api_key: API密钥
            is_background: 是否为后台验证
            
        Returns:
            bool: 验证是否成功
        """
        try:
            # 获取机器信息
            hostname = socket.gethostname()
            os_info = f"{platform.system()} {platform.release()}"
            cpu_info = cpuinfo.get_cpu_info()['brand_raw']
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                           for elements in range(0,2*6,2)][::-1])
            
            # 准备请求数据
            url = f"http://{self.base_url}/api/v1/api-keys/verify"
            payload = {
                "key": api_key,
                "machine_info": {
                    "hostname": hostname,
                    "os": os_info,
                    "cpu": cpu_info,
                    "mac": mac,
                    "item": "clip"
                }
            }
            
            # 设置超时时间
            timeout = 5 if is_background else 30
            
            # 使用同步请求
            response = requests.post(url, json=payload, timeout=timeout)
            
            if response.status_code == 200:
                result = response.json()
                # 根据验证模式记录不同级别的日志
                if is_background:
                    self.logger.debug(f"后台密钥验证结果: {result}")
                else:
                    self.logger.info(f"密钥验证结果: {result}")
                    
                if not result.get("valid", False):
                    self.logger.error("密钥验证失败")
                    sys.exit(1)
                    
                return True
            else:
                self.logger.error(f"验证请求失败: {response.status_code} - {response.text}")
                if not is_background:
                    sys.exit(1)
                return False
                    
        except Exception as e:
            if is_background:
                self.logger.debug(f"后台密钥验证失败: {e}")
            else:
                self.logger.error(f"密钥验证失败: {e}")
                sys.exit(1)
            return False 