import whisper
import subprocess
import os
from datetime import timedelta
import uuid
from pathlib import Path
import torch
import threading
import sys
import logging
import tempfile

# 完全禁用tqdm
os.environ["TQDM_DISABLE"] = "1"

# 创建一个假的tqdm类
class FakeTqdm:
    def __init__(self, *args, **kwargs):
        self.iterable = args[0] if args else None
        
    def __iter__(self):
        return iter(self.iterable) if self.iterable is not None else iter([])
        
    def __enter__(self):
        return self
        
    def __exit__(self, *args, **kwargs):
        pass
        
    def update(self, *args, **kwargs):
        pass
        
    def close(self, *args, **kwargs):
        pass
        
    def set_description(self, *args, **kwargs):
        pass
        
    def write(self, *args, **kwargs):
        pass

# 替换tqdm模块
sys.modules['tqdm'] = type('FakeTqdmModule', (), {
    'tqdm': FakeTqdm,
    'trange': lambda *args, **kwargs: FakeTqdm(range(*args)),
    '__version__': '0.0.0'
})

sys.modules['tqdm.auto'] = sys.modules['tqdm']
sys.modules['tqdm.std'] = sys.modules['tqdm']

# 设置模型下载目录
MODELS_DIR = Path("models")
os.environ["WHISPER_MODEL_DIR"] = str(MODELS_DIR)

logger = logging.getLogger(__name__)

class OptimizedProcessor:
    _instance = None
    _lock = threading.Lock()
    _model = None  # 添加静态模型变量
    
    @classmethod
    def get_instance(cls):
        """单例模式，确保只有一个处理器实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    # 在这里初始化 process_lock
                    cls._instance.process_lock = threading.Lock()
        return cls._instance
    
    def __init__(self):
        """
        初始化音频处理器
        - 加载whisper小型模型以平衡速度和精度
        - 初始化纠错词典用于字幕优化
        """
        # 初始化日志记录器
        self.logger = logging.getLogger(__name__)
        
        # 创建模型目录
        MODELS_DIR.mkdir(exist_ok=True)
        
        # 创建临时目录
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)
        
        # 添加处理锁
        self.process_lock = threading.Lock()
        
        # 只在模型未加载时加载
        if OptimizedProcessor._model is None:
            with OptimizedProcessor._lock:
                if OptimizedProcessor._model is None:
                    print("正在加载模型...")
                    try:
                        # 首先检查开发环境的模型目录
                        dev_models_dir = Path("/models")
                        dev_model_path = dev_models_dir / "small.pt"
                        print(f"检查开发环境模型: {dev_model_path}")
                        
                        if dev_model_path.exists():
                            print(f"使用开发环境的模型文件: {dev_model_path}")
                            # 确保本地模型目录存在
                            MODELS_DIR.mkdir(exist_ok=True)
                            # 复制模型文件到本地目录（如果需要）
                            target_model = MODELS_DIR / "small.pt"
                            if not target_model.exists():
                                print(f"复制模型到本地: {target_model}")
                                import shutil
                                shutil.copy2(str(dev_model_path), str(target_model))
                            print("开始加载模型到内存...")
                            OptimizedProcessor._model = whisper.load_model(
                                "small", 
                                download_root=str(MODELS_DIR),
                                device="cuda" if torch.cuda.is_available() else "cpu"
                            )
                            print("模型加载成功")
                            self.model = OptimizedProcessor._model
                        else:
                            # 然后检查打包的模型文件
                            print("检查打包环境模型...")
                            if getattr(sys, '_MEIPASS', None):
                                bundled_model = Path(sys._MEIPASS) / "models" / "small.pt"
                                print(f"检查打包模型: {bundled_model}")
                                if bundled_model.exists():
                                    print(f"使用打包的模型文件: {bundled_model}")
                                    # 确保模型目录存在
                                    MODELS_DIR.mkdir(exist_ok=True)
                                    # 复制模型文件到模型目录（如果需要）
                                    target_model = MODELS_DIR / "small.pt"
                                    if not target_model.exists():
                                        print(f"复制打包模型到本地: {target_model}")
                                        import shutil
                                        shutil.copy2(str(bundled_model), str(target_model))
                                    print("开始加载打包模型到内存...")
                                    OptimizedProcessor._model = whisper.load_model(
                                        "small", 
                                        download_root=str(MODELS_DIR),
                                        device="cuda" if torch.cuda.is_available() else "cpu"
                                    )
                                    print("打包模型加载成功")
                                    self.model = OptimizedProcessor._model
                            else:
                                # 最后检查本地模型文件
                                print("检查本地模型文件...")
                                local_model = MODELS_DIR / "small.pt"
                                if local_model.exists():
                                    print(f"使用本地模型文件: {local_model}")
                                    print("开始加载本地模型到内存...")
                                    # 设置设备
                                    device = "cuda" if torch.cuda.is_available() else "cpu"
                                    # 如果使用CUDA，先清理缓存
                                    if torch.cuda.is_available():
                                        torch.cuda.empty_cache()
                                        
                                    OptimizedProcessor._model = whisper.load_model(
                                        "small", 
                                        download_root=str(MODELS_DIR),
                                        device=device,
                                        in_memory=True
                                    )
                                    
                                    # 设置模型为评估模式
                                    OptimizedProcessor._model.eval()
                                    
                                    # 确保模型在正确的设备上
                                    if device == "cuda":
                                        OptimizedProcessor._model = OptimizedProcessor._model.cuda()
                                    else:
                                        OptimizedProcessor._model = OptimizedProcessor._model.cpu()
                                        
                                    print(f"本地模型加载成功 (使用 {device})")
                                    self.model = OptimizedProcessor._model
                                else:
                                    # 如果都没有找到，尝试下载
                                    print("未找到任何模型文件，尝试下载...")
                                    print(f"下载目录: {MODELS_DIR}")
                                    OptimizedProcessor._model = whisper.load_model(
                                        "small", 
                                        download_root=str(MODELS_DIR),
                                        device="cuda" if torch.cuda.is_available() else "cpu"
                                    )
                                    print("模型下载并加载成功")
                                    self.model = OptimizedProcessor._model
                                    
                    except Exception as e:
                        error_msg = (
                            f"加载模型失败，详细错误:\n"
                            f"错误类型: {type(e).__name__}\n"
                            f"错误信息: {str(e)}\n"
                            f"当前目录: {os.getcwd()}\n"
                            f"MODELS_DIR: {MODELS_DIR}\n"
                            f"CUDA可用: {torch.cuda.is_available()}\n"
                            f"Python版本: {sys.version}\n"
                            f"Torch版本: {torch.__version__}"
                        )
                        print(error_msg)
                        raise RuntimeError(error_msg)
        
        # 使用已加载的模型
        self.model = OptimizedProcessor._model
        
        # 纠错词典
        self.replacements = {
            '蓝皱': '兰州', 
            '夜码': '野马', 
            '多笑见': '董小姐',
            '不生的': '陌生的', 
            '做爱': '所谓', 
            '久动': '兰州'
        }

    def fast_extract_audio(self, video_path: str) -> str:
        """
        从视频中快速提取音频
        
        Args:
            video_path (str): 输入视频的路径
            
        Returns:
            str: 提取的音频文件路径
        """
        # 生成临时文件名
        random_filename = f"temp_{uuid.uuid4().hex[:8]}_audio.wav"
        output_path = str(self.temp_dir / random_filename).replace('\\', '/')
        
        try:
            # 设置 ffmpeg 启动信息
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            # 首先检查音频流
            probe_cmd = [
                'ffmpeg', '-i', video_path,
                '-hide_banner'
            ]
            
            probe_result = subprocess.run(
                probe_cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                startupinfo=startupinfo
            )
            
            # 检查音频流
            if 'Audio:' not in probe_result.stderr:
                raise RuntimeError("视频文件没有音频流")
            
            # 提取音频命令 - 使用更优化的参数
            extract_cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vn',                          # 不处理视频
                '-ac', '1',                     # 转换为单声道
                '-ar', '16000',                 # 采样率16kHz
                '-af', 'volume=2,dynaudnorm=f=150:g=15',  # 简单的音量标准化
                '-acodec', 'pcm_s16le',         # 使用无损编码
                '-loglevel', 'error',           # 只显示错误信息
                output_path
            ]
            
            # 执行提取
            result = subprocess.run(
                extract_cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                startupinfo=startupinfo
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"音频提取失败: {result.stderr}")
            
            return output_path
            
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise e
            raise RuntimeError(f"音频提取失败: {str(e)}")

    def _load_model(self):
        """加载Whisper模型"""
        if self.model is None:
            try:
                self.logger.info("正在加载Whisper模型...")
                self.model = whisper.load_model("base")
                self.logger.info("Whisper模型加载完成")
            except Exception as e:
                self.logger.error(f"加载Whisper模型失败: {str(e)}")
                raise
                
    def _format_time(self, seconds: float) -> str:
        """
        将秒数转换为SRT格式的时间字符串
        
        Args:
            seconds: 秒数
            
        Returns:
            str: SRT格式的时间字符串 (HH:MM:SS,mmm)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int((seconds % 1) * 1000)
        seconds = int(seconds)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
        
    def _write_srt(self, segments, output_file: str):
        """
        将识别结果写入SRT文件
        
        Args:
            segments: Whisper识别结果
            output_file: 输出文件路径
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, 1):
                # 写入字幕序号
                f.write(f"{i}\n")
                
                # 写入时间戳
                start_time = self._format_time(segment['start'])
                end_time = self._format_time(segment['end'])
                f.write(f"{start_time} --> {end_time}\n")
                
                # 写入字幕文本
                f.write(f"{segment['text'].strip()}\n\n")
                
    def generate_srt(self, video_file: str) -> tuple[str | None, str | None]:
        """
        从视频文件生成SRT字幕文件
        
        Args:
            video_file: 视频文件路径
            
        Returns:
            tuple[str | None, str | None]: 返回 (字幕文件路径, 音频文件路径)，如果失败则返回 (None, None)
        """
        audio_file = None
        srt_file = None
        error_occurred = False
        
        try:
            # 使用锁确保同一时间只有一个线程在处理
            with self.process_lock:
                # 清理GPU缓存
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                # 先提取音频
                self.logger.info(f"开始提取音频: {video_file}")
                audio_file = self.fast_extract_audio(video_file)
                self.logger.info(f"音频提取成功: {audio_file}")
                
                # 加载音频数据
                try:
                    # 使用whisper的内置加载器
                    audio = whisper.load_audio(audio_file)
                    # 生成log-mel频谱图
                    mel = whisper.log_mel_spectrogram(audio)
                    
                    if mel.shape[1] == 0:
                        raise RuntimeError("音频数据为空")
                        
                except Exception as e:
                    raise RuntimeError(f"音频加载失败: {str(e)}")
                
                # 识别音频
                self.logger.info(f"开始识别音频: {audio_file}")
                
                # 使用更稳定的参数配置进行转写
                result = self.model.transcribe(
                    audio_file,
                    language="zh",                # 设置语言为中文
                    task="transcribe",            # 转录任务
                    verbose=False,                # 不显示进度
                    fp16=False,                   # 禁用半精度，提高稳定性
                    beam_size=1,                  # 使用较小的beam size避免内存问题
                    temperature=0.0,              # 使用确定性输出
                    condition_on_previous_text=True,  # 启用上下文条件
                    initial_prompt="以下是标准普通话内容转写：",  # 添加提示词
                    no_speech_threshold=0.3       # 降低无语音检测阈值
                )
                
                # 验证结果
                if not isinstance(result, dict) or 'segments' not in result:
                    raise RuntimeError("转写结果无效")
                    
                if not result['segments']:
                    raise RuntimeError("未检测到有效语音内容")
                
                # 生成字幕文件名并保存到temp目录
                video_name = Path(video_file).stem
                srt_file = str(self.temp_dir / f"{video_name}.srt").replace('\\', '/')
                
                # 写入SRT文件
                self._write_srt(result["segments"], srt_file)
                self.logger.info(f"字幕文件已生成: {srt_file}")
                
                return srt_file, audio_file
                
        except Exception as e:
            error_occurred = True
            self.logger.error(f"生成字幕文件失败: {str(e)}")
            return None, None
            
        finally:
            # 如果生成失败，清理未完成的字幕文件
            if error_occurred and srt_file and os.path.exists(srt_file):
                try:
                    os.remove(srt_file)
                except Exception as e:
                    self.logger.warning(f"删除临时字幕文件失败: {str(e)}")
                    
            # 再次清理GPU缓存
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def _format_with_corrections(self, segments):
        """
        将whisper识别结果格式化为SRT格式，并应用纠错
        
        Args:
            segments: whisper识别的文本片段
            
        Returns:
            str: 格式化后的SRT字幕内容
        """
        srt = []
        for i, seg in enumerate(segments, 1):
            # 获取文本并应用纠错
            text = seg['text'].strip()
            for wrong, right in self.replacements.items():
                text = text.replace(wrong, right)
            
            # 格式化时间戳
            start_time = self._format_time(seg['start'])
            end_time = self._format_time(seg['end'])
            
            # 格式化为SRT条目
            srt.append(
                f"{i}\n"
                f"{start_time} --> {end_time}\n"
                f"{text}\n"
            )
        
        return '\n'.join(srt)

def test_single_video():
    """
    测试单个视频的字幕生成
    """
    try:
        # 初始化处理器
        processor = OptimizedProcessor.get_instance()
        
        # 测试视频路径
        video_path = input("请输入视频文件路径: ").strip('"')  # 去除可能的引号
        
        print(f"\n开始处理视频: {video_path}")
        print("1. 初始化完成，开始提取音频和生成字幕...")
        
        # 生成字幕
        srt_path, audio_path = processor.generate_srt(video_path)
        if not srt_path:
            raise RuntimeError("字幕生成失败")
            
        print(f"2. 音频提取成功: {audio_path}")
        print(f"3. 字幕生成成功: {srt_path}")
        
        print("\n字幕内容预览:")
        print("="*50)
        with open(srt_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()
            print(srt_content[:500] + "..." if len(srt_content) > 500 else srt_content)
        print("="*50)
        
        # 清理临时文件
        try:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
                print(f"已删除临时音频文件: {audio_path}")
            if srt_path and os.path.exists(srt_path):
                os.remove(srt_path)
                print(f"已删除临时字幕文件: {srt_path}")
        except Exception as e:
            print(f"清理临时文件失败: {str(e)}")
        
    except Exception as e:
        print(f"\n错误: {str(e)}")
        if "音频提取失败" in str(e):
            print("\n可能的原因:")
            print("1. 视频文件不存在或路径错误")
            print("2. 视频文件没有音频流")
            print("3. 视频文件可能已损坏")
        elif "字幕生成失败" in str(e):
            print("\n可能的原因:")
            print("1. 音频质量太差")
            print("2. 没有检测到语音内容")
            print("3. 系统内存不足")
        print("\n建议:")
        print("1. 检查视频文件是否正确")
        print("2. 确保视频包含有效的音频")
        print("3. 尝试使用其他视频测试")

if __name__ == "__main__":
    test_single_video() 