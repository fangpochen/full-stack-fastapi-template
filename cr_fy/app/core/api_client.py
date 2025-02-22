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
        self.base_url = config.get('api.base_url', 'http://139.224.70.41:8000')
        
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
            # 获取 API key
            api_key = self.config.get_cached_key()
            if not api_key:
                api_key = self.config.get('api.api_key')
                
            if not api_key:
                self.logger.error("未配置API密钥")
                return []
            
            url = f"{self.base_url}/api/v1/ffmpeg/plans"
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": api_key,
                "User-Agent": f"CR-Client/{getattr(sys, 'frozen', False)}"
            }
            
            self.logger.debug(f"发送请求到 {url}")
            self.logger.debug(f"请求头: {headers}")
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"获取方案列表失败: {str(e)}")
            return []
            
    def get_ffmpeg_command(self, plan_id: int, more_effects: bool = False, canvas_y: float = 0.6, font_size: int = 20, margin_v: int = 85) -> dict:
        """获取FFmpeg命令模板"""
        try:
            # 获取 API key
            api_key = self.config.get_cached_key()
            if not api_key:
                api_key = self.config.get('api.api_key')
                
            if not api_key:
                self.logger.error("未配置API密钥")
                return {}

            # 构建请求参数
            params = {
                'plan_id': plan_id,
                'more_effects': more_effects,
                'canvas_y': canvas_y,
                'font_size': font_size,
                'margin_v': margin_v
            }
            
            # 发送请求
            url = f"{self.base_url}/api/v1/ffmpeg/command"
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": api_key
            }
            
            self.logger.debug(f"发送请求到 {url}")
            self.logger.debug(f"请求参数: {params}")
            self.logger.debug(f"请求头: {headers}")
            
            response = requests.post(url, json=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
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
            url = f"{self.base_url}/api/v1/ffmpeg/plans"
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": self.config.get('api.api_key')
            }
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    self.logger.error(f"获取处理方案失败: {response.status}")
                    return []
        except Exception as e:
            self.logger.error(f"获取处理方案时出错: {str(e)}")
            return []
        
    def verify_api_key(self, api_key: str, is_background: bool = False, item: str = "clip") -> bool:
        """
        验证API密钥（同步方法）
        
        Args:
            api_key: API密钥
            is_background: 是否为后台验证
            item: 项目标识，默认为"clip"
            
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
            url = f"{self.base_url}/api/v1/api-keys/verify"
            payload = {
                "key": api_key,
                "machine_info": {
                    "hostname": hostname,
                    "os": os_info,
                    "cpu": cpu_info,
                    "mac": mac,
                    "item": item
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
                    error_msg = result.get("message", "验证失败")
                    self.logger.error(f"密钥验证失败: {error_msg}")
                    if not is_background:
                        sys.exit(1)
                    return False
                    
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