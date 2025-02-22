"""
打包脚本 - 简化版本
"""
import os
import sys
import shutil
import torch
import whisper
import PyInstaller.__main__

# 清理旧的构建文件
print("清理旧的构建文件...")
if os.path.exists('build'):
    shutil.rmtree('build')
if os.path.exists('dist'):
    shutil.rmtree('dist')
if os.path.exists('视频处理工具.spec'):
    os.remove('视频处理工具.spec')

# 创建必要的目录
print("创建必要的目录...")
os.makedirs('models', exist_ok=True)
os.makedirs('app/resources/config', exist_ok=True)
os.makedirs('app/resources/images', exist_ok=True)

# 检查 FFmpeg 文件
print("检查 FFmpeg 文件...")
required_files = ['ffmpeg.exe', 'ffprobe.exe']
for file in required_files:
    if not os.path.exists(file):
        print(f"错误: 找不到 {file}，请确保它在项目根目录中")
        sys.exit(1)
    else:
        print(f"找到 {file}")

# 下载并保存whisper模型
print("下载并保存whisper模型...")
model = whisper.load_model("small")
model_path = os.path.join('models', 'small.pt')
torch.save(model, model_path)
print(f"模型已保存到: {model_path}")

# 复制配置文件
print("创建配置文件...")
config_content = '''{
    "api": {
        "base_url": "http://139.224.70.41:8000",
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
}'''

with open('app/resources/config/config.json', 'w', encoding='utf-8') as f:
    f.write(config_content)

# 创建运行时钩子
print("创建运行时钩子...")
hook_content = '''
import os
import sys
import torch

# 禁用tqdm进度条
os.environ["TQDM_DISABLE"] = "1"

# 创建日志目录
os.makedirs('logs', exist_ok=True)
'''

with open('hook.py', 'w', encoding='utf-8') as f:
    f.write(hook_content)

# 打包参数
print("开始打包...")
opts = [
    'app/main.py',                                    # 主程序入口
    '--name=视频处理工具',                            # 程序名称
    '--onefile',                                      # 打包成单个文件
    '--clean',                                        # 清理临时文件
    '--noconfirm',                                    # 不确认覆盖
    '--add-data=app/resources;app/resources',         # 添加资源文件
    '--add-data=models;models',                       # 添加模型文件
    '--add-data=ffmpeg.exe;.',                       # 添加 FFmpeg
    '--add-data=ffprobe.exe;.',                      # 添加 FFprobe
    '--runtime-hook=hook.py',                         # 添加运行时钩子
    '--hidden-import=torch',                          # PyTorch
    '--hidden-import=whisper',                        # Whisper
    '--hidden-import=PyQt5',                          # PyQt5
    '--collect-data=whisper',                         # Whisper数据文件
    '--collect-data=torch',                           # PyTorch数据文件
    '--icon=app/resources/images/icon.ico',           # 图标
]

# 执行打包
PyInstaller.__main__.run(opts)

# 清理临时文件
print("清理临时文件...")
if os.path.exists('hook.py'):
    os.remove('hook.py')

print("打包完成!") 