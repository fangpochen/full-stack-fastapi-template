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
from pathlib import Path

# 创建日志目录
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)

# 配置日志
logger = logging.getLogger('key_verification')

# 服务器配置
SERVER_IP = '139.224.70.41'
# SERVER_IP = 'localhost'

def verify_key(api_key: str, is_background: bool = False) -> bool:
    """
    验证密钥
    
    Args:
        api_key: 密钥字符串
        is_background: 是否为后台验证
        
    Returns:
        bool: 验证是否成功
    """
    # 获取机器信息
    hostname = socket.gethostname()
    os_info = f"{platform.system()} {platform.release()}"
    cpu_info = cpuinfo.get_cpu_info()['brand_raw']
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                    for elements in range(0,2*6,2)][::-1])

    # 准备请求数据
    url = f"http://{SERVER_IP}:8000/api/v1/api-keys/verify"
    headers = {"Content-Type": "application/json"}
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

    try:
        # 后台验证时使用更短的超时时间
        timeout = 5 if is_background else 30
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        
        # 根据验证模式记录不同级别的日志
        if is_background:
            logger.debug(f"后台密钥验证结果: {result}")
        else:
            logger.info(f"密钥验证结果: {result}")
            
        return result.get("valid", False)
        
    except requests.exceptions.RequestException as e:
        if is_background:
            logger.debug(f"后台密钥验证失败: {e}")
        else:
            logger.error(f"密钥验证失败: {e}")
        return False