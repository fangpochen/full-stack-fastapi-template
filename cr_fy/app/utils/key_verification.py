"""
密钥验证模块
处理软件的密钥验证功能
"""
import os
import platform
import socket
import uuid
import logging
import requests
import cpuinfo
import sys
from pathlib import Path
from app.core.config import Config

# 创建日志目录
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)

# 配置日志
logger = logging.getLogger('key_verification')
logger.setLevel(logging.DEBUG)  # 设置为DEBUG级别以获取更多信息

def verify_key(api_key: str, is_background: bool = False, item: str = "clip") -> bool:
    """
    验证密钥
    
    Args:
        api_key: 密钥字符串
        is_background: 是否为后台验证
        item: 项目标识，默认为"clip"
        
    Returns:
        bool: 验证是否成功
    """
    try:
        # 获取配置实例
        config = Config()
        
        # 记录运行环境信息
        logger.info(f"运行模式: {'打包环境' if getattr(sys, 'frozen', False) else '开发环境'}")
        logger.info(f"当前工作目录: {os.getcwd()}")
        
        # 如果是后台验证且有缓存的密钥，直接返回True
        if is_background and config.get_cached_key() == api_key:
            return True
        
        # 获取机器信息
        hostname = socket.gethostname()
        os_info = f"{platform.system()} {platform.release()}"
        cpu_info = cpuinfo.get_cpu_info()['brand_raw']
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                        for elements in range(0,2*6,2)][::-1])

        # 从配置中获取服务器地址
        base_url = config.get('api.base_url')
        if not base_url:
            logger.error("未找到服务器地址配置")
            return False
            
        logger.info(f"使用服务器地址: {base_url}")

        # 准备请求数据
        url = f"{base_url}/api/v1/api-keys/verify"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"CR-Client/{getattr(sys, 'frozen', False)}"  # 添加客户端标识
        }
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
        
        logger.info(f"验证请求URL: {url}")
        logger.info(f"请求头: {headers}")
        logger.info(f"请求数据: {payload}")

        try:
            # 后台验证时使用更短的超时时间
            timeout = 5 if is_background else 30
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            logger.info(f"服务器响应状态码: {response.status_code}")
            logger.info(f"服务器响应内容: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            
            # 根据验证模式记录不同级别的日志
            if is_background:
                logger.debug(f"后台密钥验证结果: {result}")
            else:
                logger.info(f"密钥验证结果: {result}")
                
            if not result.get("valid", False):
                error_msg = result.get("message", "验证失败")
                logger.error(f"密钥验证失败: {error_msg}")
                config.clear_key_cache()  # 清除缓存
                return False
                
            # 验证成功，缓存密钥
            config.cache_verified_key(api_key)
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"请求异常: {str(e)}")
            if is_background:
                logger.debug(f"后台密钥验证失败: {e}")
            else:
                logger.error(f"密钥验证失败: {e}")
            config.clear_key_cache()  # 清除缓存
            return False
            
    except Exception as e:
        logger.error(f"验证过程发生未预期的错误: {str(e)}", exc_info=True)
        return False