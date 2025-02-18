"""
视频处理线程模块
处理视频剪辑和处理的核心功能
"""
import os
import time
import logging
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal
from app.core.audio_processor import OptimizedProcessor
from app.core.api_client import APIClient
from app.core.config import Config
from concurrent.futures import ThreadPoolExecutor, as_completed

# 设置日志记录器级别为INFO
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class VideoProcessThread(QThread):
    """视频处理线程类"""
    log_message = pyqtSignal(str)  # 日志信息信号
    finished = pyqtSignal(int, float)  # 处理完成信号(处理数量, 总时间)
    error = pyqtSignal(str)  # 错误信号
    
    # 类级别的命令模板缓存
    _command_templates = {}
    _command_lock = threading.Lock()
    
    def __init__(self, input_dir, output_dir, use_gpu=True, add_glow=False, 
                 add_border=False, add_grid=False, threads=10, blur_bg=False, 
                 delete_after=False, loop_process=False, add_subtitle=False,
                 canvas_y=0.6, selected_plan_id=1):  # 移除margin_v参数
        """初始化处理线程"""
        super().__init__()
        # 线程ID
        self.thread_id = threading.get_ident()
        
        # 初始化API客户端
        config = Config()
        self.api_client = APIClient(config)
        
        # 获取选择的方案
        plans = self.api_client.get_plans()
        selected_plan = next((plan for plan in plans if plan["id"] == selected_plan_id), None)
        
        # 基本参数
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.use_gpu = use_gpu
        self.add_glow = add_glow
        self.add_border = add_border
        self.add_grid = add_grid
        self.threads = threads
        self.blur_bg = blur_bg
        
        # 设置GPU并发数
        # 对于大多数显卡，同时处理4-6个视频是比较合适的
        # 如果总线程数大于8，则使用6个GPU并发
        # 如果总线程数在5-8之间，则使用4个GPU并发
        # 如果总线程数小于等于4，则GPU并发等于线程数
        if threads > 8:
            gpu_concurrent = 6
        elif threads > 4:
            gpu_concurrent = 4
        else:
            gpu_concurrent = threads
            
        self.log(f"设置GPU并发数为: {gpu_concurrent}")
        self.gpu_semaphore = threading.Semaphore(gpu_concurrent)
        
        # 处理控制
        self._stop_flag = False
        self.current_process = None
        self.is_running = True
        
        # 目录和方案
        self.input_dirs = [input_dir]
        self.dir_limits = {}
        
        if selected_plan:
            self.log(f"使用选中的方案: {selected_plan}")
            self.selected_plans = [selected_plan]
        else:
            self.log(f"未找到方案 {selected_plan_id}，使用默认方案")
            self.selected_plans = [{"id": 1, "width": 1200, "height": 2480, "blur_bg": blur_bg}]
        
        # 特效和选项
        self.more_effects = add_glow
        self.delete_after = delete_after
        self.loop_process = loop_process
        self.add_subtitle = add_subtitle
        self.canvas_y = canvas_y
        
        # 音频处理器
        self.audio_processor = OptimizedProcessor()

    def log(self, message: str, thread_id: int = None, level: str = 'INFO') -> None:
        """
        带线程ID的日志输出
        
        Args:
            message: 日志消息
            thread_id: 线程ID，如果为None则自动获取
            level: 日志级别，可选值：DEBUG, INFO, WARNING, ERROR
        """
        if thread_id is None:
            thread_id = threading.get_ident()
            
        # 转换日志级别为logging模块的级别
        log_level = getattr(logging, level.upper(), logging.INFO)
        
        # 只有当日志级别大于等于INFO时才输出
        if log_level >= logging.INFO:
            formatted_message = f"[Thread-{thread_id}] {message}"
            # 发送到UI
            self.log_message.emit(formatted_message)
            # 写入日志文件
            log_func = getattr(logger, level.lower(), logger.info)
            log_func(formatted_message)

    def get_ffmpeg_command(self, input_file: str, output_file: str, plan_id: int, use_gpu: bool, thread_id: int, subtitle_file: str = None) -> str:
        """
        获取FFmpeg处理命令
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径
            plan_id: 处理方案ID
            use_gpu: 是否使用GPU
            thread_id: 线程ID
            subtitle_file: 字幕文件路径（可选）
            
        Returns:
            str: FFmpeg命令
        """
        try:
            # 获取命令模板
            commands = self.api_client.get_ffmpeg_command(
                plan_id=plan_id,
                more_effects=self.more_effects,
                canvas_y=self.canvas_y
            )
            
            if not commands:
                self.log(f"获取命令模板失败", thread_id, 'ERROR')
                return None
                
            # 根据GPU选项选择命令
            command_template = commands.get('gpu_command' if use_gpu else 'cpu_command')
            if not command_template:
                self.log(f"未找到{'GPU' if use_gpu else 'CPU'}命令模板", thread_id, 'ERROR')
                return None
                
            # 替换文件路径
            command = command_template.replace('{input_file}', input_file)
            command = command.replace('{output_file}', output_file)
            
            # 如果是方案6且有字幕文件，替换字幕文件路径和文件名
            if plan_id == 6 and subtitle_file:
                # 获取输入文件名（不包含扩展名）
                filename = Path(input_file).stem
                command = command.replace('{subtitle_file}', subtitle_file)
                command = command.replace('%{filename}', filename)
            
            # 打印完整的FFmpeg命令
            self.log(f"完整的FFmpeg命令: {command}", thread_id, 'INFO')
            return command
            
        except Exception as e:
            self.log(f"生成命令失败: {str(e)}", thread_id, 'ERROR')
            return None

    def run(self):
        """运行处理线程"""
        try:
            self.log("\n=== 线程开始 ===")
            self.log(f"线程参数:")
            self.log(f"添加字幕: {self.add_subtitle}")
            self.log(f"选中的方案: {self.selected_plans}")
            self.log(f"更多效果: {self.more_effects}")
            self.log(f"并发线程数: {self.threads}")
            self.log(f"循环剪辑: {self.loop_process}")
            
            total_processed = 0
            total_start_time = time.time()
            
            while self.is_running:  # 外层循环，用于循环剪辑
                # 创建线程池
                with ThreadPoolExecutor(max_workers=self.threads) as executor:
                    # 存储所有任务
                    futures = []
                    
                    for input_dir in self.input_dirs:
                        if not self.is_running:
                            break
                        
                        # 获取当前目录的限制数量
                        limit = self.dir_limits.get(input_dir, 0)
                        
                        # 获取目录中的视频文件
                        video_files = [f for f in Path(input_dir).rglob("*") 
                                     if f.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv']]
                        
                        if not video_files:
                            self.log(f"目录 {input_dir} 中没有视频文件", None, 'WARNING')
                            continue
                            
                        # 应用限制
                        if limit > 0:
                            video_files = video_files[:limit]
                            self.log(f"目录 {input_dir} 限制处理 {limit} 个文件", None, 'INFO')
                        
                        for video_file in video_files:
                            if not self.is_running:
                                break
                                
                            for plan in self.selected_plans:
                                if not self.is_running:
                                    break
                                    
                                plan_id = plan["id"]
                                self.log(f"处理方案ID: {plan_id}")
                                
                                # 构建输出文件路径
                                input_dir_name = Path(input_dir).name
                                output_file = Path(self.output_dir) / input_dir_name / f"{video_file.stem}{video_file.suffix}"
                                output_file.parent.mkdir(parents=True, exist_ok=True)
                                
                                # 提交任务到线程池
                                future = executor.submit(
                                    self.process_video,
                                    video_file,
                                    output_file,
                                    plan_id,
                                    self.more_effects
                                )
                                futures.append(future)
                    
                    # 等待所有任务完成并收集结果
                    for future in as_completed(futures):
                        try:
                            if future.result():
                                total_processed += 1
                        except Exception as e:
                            self.log(f"处理任务失败: {str(e)}")
                
                # 检查是否继续循环
                if not self.loop_process or not self.is_running:
                    break
                    
                # 检查是否还有文件需要处理
                has_files = False
                for input_dir in self.input_dirs:
                    if list(Path(input_dir).rglob("*.mp4")) or \
                       list(Path(input_dir).rglob("*.avi")) or \
                       list(Path(input_dir).rglob("*.mov")) or \
                       list(Path(input_dir).rglob("*.mkv")):
                        has_files = True
                        break
                
                if not has_files:
                    self.log("所有目录中的视频文件都已处理完成", None, 'INFO')
                    break
                    
                self.log("开始新一轮循环处理", None, 'INFO')
            
            total_time = time.time() - total_start_time
            self.finished.emit(total_processed, total_time)
            
        except Exception as e:
            self.error.emit(str(e))
            
    def process_video(self, video_file: Path, output_file: Path, plan_id: int, more_effects: bool) -> bool:
        """在线程池中处理单个视频"""
        thread_id = threading.get_ident()
        audio_file = None
        subtitle_file = None
        
        try:
            use_gpu = self.use_gpu and self.gpu_semaphore.acquire(blocking=False)
            
            try:
                if use_gpu:
                    self.log(f"获取到GPU信号量，使用GPU处理", thread_id, 'INFO')
                else:
                    self.log(f"使用CPU处理 (GPU信号量未获取到或未启用GPU)", thread_id, 'INFO')

                # 如果是方案6，先进行字幕识别
                if plan_id == 6:
                    self.log(f"开始识别字幕: {video_file.name}", thread_id, 'INFO')
                    try:
                        # 生成字幕并获取音频文件路径
                        subtitle_file, audio_file = self.audio_processor.generate_srt(str(video_file))
                        if not subtitle_file:
                            self.log(f"字幕识别失败，跳过文件: {video_file.name}", thread_id, 'ERROR')
                            return False
                        self.log(f"字幕识别成功: {subtitle_file}", thread_id, 'INFO')
                    except Exception as e:
                        self.log(f"字幕识别出错: {str(e)}", thread_id, 'ERROR')
                        return False

                # 获取FFmpeg命令
                ffmpeg_cmd = self.get_ffmpeg_command(
                    str(video_file),
                    str(output_file),
                    plan_id,
                    use_gpu,
                    thread_id,
                    subtitle_file  # 传递字幕文件路径
                )
                
                if not ffmpeg_cmd:
                    self.log(f"获取处理命令失败，跳过文件: {video_file.name}", thread_id, 'ERROR')
                    return False
                    
                self.log(f"\n开始处理文件: {video_file.name}", thread_id, 'INFO')
                self.log(f"使用方案 {plan_id} ({'GPU' if use_gpu else 'CPU'})", thread_id, 'INFO')
                self.log(f"更多效果: {more_effects}", thread_id, 'DEBUG')
                
                # 使用UTF-8编码处理命令
                process = subprocess.Popen(
                    ffmpeg_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    encoding='utf-8',
                    errors='ignore'
                )
                
                with self._command_lock:
                    self.current_process = process
                
                error_output = []
                progress_pattern = r"time=(\d{2}:\d{2}:\d{2}.\d{2})"
                
                while True:
                    if not self.is_running:
                        process.terminate()
                        self.log("处理被用户中断", thread_id, 'WARNING')
                        return False
                        
                    line = process.stderr.readline()
                    if not line and process.poll() is not None:
                        break
                        
                    if "Error" in line or "错误" in line:
                        error_output.append(line.strip())
                        self.log(f"FFmpeg错误: {line.strip()}", thread_id, 'ERROR')
                    
                    if "time=" in line:
                        import re
                        match = re.search(progress_pattern, line)
                        if match:
                            self.log(f"处理进度: {match.group(1)}", thread_id, 'DEBUG')  # 改为DEBUG级别
                            
                if process.returncode == 0:
                    if output_file.exists() and output_file.stat().st_size > 0:
                        self.log(f"成功处理: {video_file.name}", thread_id, 'INFO')
                        # 清理临时字幕文件
                        if subtitle_file and os.path.exists(subtitle_file):
                            try:
                                os.remove(subtitle_file)
                                self.log(f"已删除临时字幕文件: {subtitle_file}", thread_id, 'DEBUG')
                            except Exception as e:
                                self.log(f"删除临时字幕文件失败: {str(e)}", thread_id, 'WARNING')
                                
                        if self.delete_after:
                            try:
                                video_file.unlink()
                                self.log(f"已删除原文件: {video_file.name}", thread_id, 'INFO')
                            except Exception as e:
                                self.log(f"删除原文件失败: {str(e)}", thread_id, 'ERROR')
                        return True
                    else:
                        self.log(f"处理失败: 输出文件不存在或大小为0", thread_id, 'ERROR')
                        return False
                else:
                    self.log(f"处理失败: {video_file.name}", thread_id, 'ERROR')
                    if error_output:
                        self.log("错误详情:", thread_id, 'ERROR')
                        for error in error_output:
                            self.log(error, thread_id, 'ERROR')
                    return False
                
            finally:
                if use_gpu:
                    self.gpu_semaphore.release()
                    self.log("释放GPU信号量", thread_id, 'DEBUG')
                
                # 清理临时文件
                try:
                    # 清理临时音频文件
                    if audio_file and os.path.exists(audio_file):
                        os.remove(audio_file)
                        self.log(f"已删除临时音频文件: {audio_file}", thread_id, 'DEBUG')
                    # 清理临时字幕文件
                    if subtitle_file and os.path.exists(subtitle_file):
                        os.remove(subtitle_file)
                        self.log(f"已删除临时字幕文件: {subtitle_file}", thread_id, 'DEBUG')
                except Exception as e:
                    self.log(f"清理临时文件失败: {str(e)}", thread_id, 'WARNING')
                
            return True
            
        except Exception as e:
            self.log(f"处理出错: {str(e)}", thread_id, 'ERROR')
            return False 