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

# 创建一个更完整的假的tqdm类
class FakeTqdm:
    def __init__(self, *args, **kwargs):
        self.iterable = args[0] if args else None
        self.total = len(self.iterable) if self.iterable is not None else kwargs.get('total', 0)
        self.desc = kwargs.get('desc', '')
        self.ncols = kwargs.get('ncols', 80)
        self.position = kwargs.get('position', 0)
        self.write = self._write  # 添加write方法的引用
        
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
        
    def set_description(self, desc=None, refresh=True):
        self.desc = desc or ''
        
    def _write(self, s, file=None, end="\n", nolock=False):
        """实现write方法"""
        pass
        
    def clear(self, *args, **kwargs):
        pass
        
    def reset(self, *args, **kwargs):
        pass
        
    def display(self, *args, **kwargs):
        pass
        
    @property
    def format_dict(self):
        return {'n': 0, 'total': self.total, 'rate': 0, 'desc': self.desc}

# 替换tqdm模块
sys.modules['tqdm'] = type('FakeTqdmModule', (), {
    'tqdm': FakeTqdm,
    'trange': lambda *args, **kwargs: FakeTqdm(range(*args)),
    '__version__': '0.0.0'
})

sys.modules['tqdm.auto'] = sys.modules['tqdm']
sys.modules['tqdm.std'] = sys.modules['tqdm']

def get_resource_path(relative_path):
    """获取资源文件的路径，适用于开发环境和打包环境"""
    try:
        # 判断是否是打包环境
        if getattr(sys, 'frozen', False):
            # 如果是打包环境，使用 sys._MEIPASS
            base_path = sys._MEIPASS
        else:
            # 如果是开发环境，使用当前目录的上级目录
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            
        # 获取完整路径
        full_path = os.path.join(base_path, relative_path)
        return full_path
    except Exception as e:
        logging.error(f"获取资源路径失败: {str(e)}")
        return None

# 设置模型下载目录
MODELS_DIR = os.path.join(os.path.dirname(get_resource_path('.')), 'models')
os.environ["WHISPER_MODEL_DIR"] = str(MODELS_DIR)

logger = logging.getLogger(__name__)

def get_ffmpeg_path():
    """获取 FFmpeg 可执行文件的路径"""
    try:
        # 如果是打包环境，优先在临时目录中查找
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
            ffmpeg_paths = [
                os.path.join(base_path, 'ffmpeg.exe'),  # 打包后的临时目录
            ]
            # 添加日志
            logging.info(f"打包环境基础路径: {base_path}")
        else:
            # 开发环境，在当前目录和上级目录查找
            current_dir = os.getcwd()
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ffmpeg_paths = [
                os.path.join(current_dir, 'ffmpeg.exe'),  # 当前目录
                os.path.join(base_path, 'ffmpeg.exe'),    # 项目根目录
            ]
            # 添加日志
            logging.info(f"开发环境当前目录: {current_dir}")
            logging.info(f"开发环境基础路径: {base_path}")
        
        # 检查所有可能的路径
        for path in ffmpeg_paths:
            logging.info(f"检查 FFmpeg 路径: {path}")
            if os.path.exists(path):
                logging.info(f"找到 FFmpeg: {path}")
                return os.path.abspath(path)
        
        # 如果都找不到，返回打包环境或当前目录的路径
        default_path = os.path.join(base_path, 'ffmpeg.exe')
        logging.info(f"未找到 FFmpeg，使用默认路径: {default_path}")
        return default_path
        
    except Exception as e:
        logging.error(f"获取 FFmpeg 路径失败: {str(e)}")
        return 'ffmpeg.exe'

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
        
        # 获取 FFmpeg 路径
        self.ffmpeg_path = get_ffmpeg_path()
        self.logger.info(f"FFmpeg 路径: {self.ffmpeg_path}")
        
        # 检查是否在打包环境
        if getattr(sys, 'frozen', False):
            self.logger.info(f"运行在打包环境中，临时目录: {sys._MEIPASS}")
        else:
            self.logger.info("运行在开发环境中")
        
        # 检查 FFmpeg 是否存在
        if not os.path.exists(self.ffmpeg_path):
            self.logger.error(f"找不到 FFmpeg: {self.ffmpeg_path}")
            # 在打包环境中，尝试在临时目录中查找
            if getattr(sys, 'frozen', False):
                temp_ffmpeg = os.path.join(sys._MEIPASS, 'ffmpeg.exe')
                if os.path.exists(temp_ffmpeg):
                    self.ffmpeg_path = temp_ffmpeg
                    self.logger.info(f"在临时目录找到 FFmpeg: {self.ffmpeg_path}")
                else:
                    self.logger.error(f"在临时目录中也找不到 FFmpeg: {temp_ffmpeg}")
        
        # 创建临时目录
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)
        
        # 添加处理锁
        self.process_lock = threading.Lock()
        
        # 只在模型未加载时加载
        if OptimizedProcessor._model is None:
            with OptimizedProcessor._lock:
                if OptimizedProcessor._model is None:
                    self.logger.info("开始加载模型...")
                    try:
                        # 获取模型路径
                        model_path = os.path.join(MODELS_DIR, 'small.pt')
                        self.logger.info(f"检查模型文件: {model_path}")
                            
                        if os.path.exists(model_path):
                            self.logger.info(f"找到模型文件: {model_path}")
                            # 直接从模型文件加载
                            OptimizedProcessor._model = torch.load(model_path, map_location='cpu')
                            # 设置为评估模式
                            if hasattr(OptimizedProcessor._model, 'eval'):
                                OptimizedProcessor._model.eval()
                            # 移动到适当的设备
                            device = "cuda" if torch.cuda.is_available() else "cpu"
                            if hasattr(OptimizedProcessor._model, 'to'):
                                OptimizedProcessor._model = OptimizedProcessor._model.to(device)
                            self.logger.info(f"成功加载模型到 {device} 设备")
                        else:
                            self.logger.error(f"模型文件不存在: {model_path}")
                            OptimizedProcessor._model = None
                            
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
                        self.logger.error(error_msg)
                        OptimizedProcessor._model = None
        
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
            # 添加详细的路径日志
            self.logger.info(f"当前工作目录: {os.getcwd()}")
            self.logger.info(f"FFmpeg 路径: {self.ffmpeg_path}")
            self.logger.info(f"FFmpeg 是否存在: {os.path.exists(self.ffmpeg_path)}")
            self.logger.info(f"视频文件路径: {video_path}")
            self.logger.info(f"输出文件路径: {output_path}")
            
            # 如果找不到 FFmpeg，先尝试重新获取路径
            if not os.path.exists(self.ffmpeg_path):
                self.ffmpeg_path = get_ffmpeg_path()
                self.logger.info(f"重新获取 FFmpeg 路径: {self.ffmpeg_path}")
                
            if not os.path.exists(self.ffmpeg_path):
                raise RuntimeError(f"找不到 FFmpeg，请确保 ffmpeg.exe 在正确的位置")
            
            # 设置 ffmpeg 启动信息
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            # 首先检查音频流
            probe_cmd = [
                self.ffmpeg_path, '-i', video_path,
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
                self.ffmpeg_path, '-y',
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
        """
        加载 Whisper 模型
        - 使用预加载的模型实例
        - 如果预加载失败,尝试重新加载
        """
        try:
            # 如果已经有预加载的模型,直接返回
            if OptimizedProcessor._model is not None:
                self.logger.info("使用预加载的Whisper模型")
                return OptimizedProcessor._model
                
            # 如果没有预加载的模型,尝试加载
            self.logger.warning("预加载模型不存在,尝试重新加载...")
            
            # 获取模型路径
            model_path = os.path.join(MODELS_DIR, 'small.pt')
            self.logger.info(f"检查模型文件: {model_path}")
            
            if os.path.exists(model_path):
                self.logger.info(f"找到模型文件: {model_path}")
                # 直接加载整个模型
                model = torch.load(model_path, map_location='cpu')
                # 设置为评估模式
                model.eval()
                # 移动到适当的设备
                device = "cuda" if torch.cuda.is_available() else "cpu"
                model = model.to(device)
                self.logger.info(f"成功加载Whisper模型到 {device} 设备")
                # 保存到静态变量
                OptimizedProcessor._model = model
                return model
            else:
                self.logger.error(f"模型文件不存在: {model_path}")
                return None
                
        except Exception as e:
            self.logger.error(f"加载Whisper模型失败: {str(e)}")
            return None
        
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
                    self.logger.info("开始加载音频数据...")
                    audio = whisper.load_audio(audio_file)
                    self.logger.info("音频数据加载成功")
                    
                    # 生成log-mel频谱图
                    self.logger.info("开始生成频谱图...")
                    mel = whisper.log_mel_spectrogram(audio)
                    self.logger.info(f"频谱图生成成功, shape: {mel.shape}")
                    
                    if mel.shape[1] == 0:
                        raise RuntimeError("音频数据为空")
                        
                except Exception as e:
                    raise RuntimeError(f"音频加载失败: {str(e)}")
                
                # 检查模型是否正确加载
                self.logger.info("检查模型状态...")
                if self.model is None:
                    self.model = self._load_model()
                    if self.model is None:
                        raise RuntimeError("模型加载失败")
                self.logger.info(f"模型状态: {type(self.model)}")
                
                # 识别音频
                self.logger.info(f"开始识别音频: {audio_file}")
                
                # 使用更稳定的参数配置进行转写
                try:
                    self.logger.info("开始转写...")
                    # 禁用进度条
                    os.environ["TOKENIZERS_PARALLELISM"] = "false"
                    
                    # 生成临时文件名
                    video_name = Path(video_file).stem
                    srt_file = str(self.temp_dir / f"{video_name}.srt").replace('\\', '/')
                    
                    # 转写过程
                    with torch.inference_mode():
                        result = self.model.transcribe(
                            audio_file,
                            language="zh",                # 设置语言为中文
                            task="transcribe",            # 转录任务
                            verbose=None,                 # 完全禁用进度显示
                            fp16=False,                   # 禁用半精度，提高稳定性
                            beam_size=1,                  # 使用较小的beam size避免内存问题
                            temperature=0.0,              # 使用确定性输出
                            condition_on_previous_text=True,  # 启用上下文条件
                            initial_prompt="以下是标准普通话内容转写：",  # 添加提示词
                            no_speech_threshold=0.3       # 降低无语音检测阈值
                        )
                    self.logger.info("转写完成")
                    
                    # 详细验证结果
                    if not isinstance(result, dict):
                        raise RuntimeError(f"转写结果类型错误: {type(result)}")
                    if 'segments' not in result:
                        raise RuntimeError(f"转写结果缺少 segments 字段: {result.keys()}")
                    if not result['segments']:
                        raise RuntimeError("转写结果为空列表")
                        
                    # 记录一些转写结果的信息
                    self.logger.info(f"转写结果: {len(result['segments'])} 个片段")
                    for i, seg in enumerate(result['segments']):
                        self.logger.info(f"片段 {i+1}: {seg.get('text', '').strip()}")
                    
                    # 写入SRT文件
                    self._write_srt(result["segments"], srt_file)
                    self.logger.info(f"字幕文件已生成: {srt_file}")
                    
                    return srt_file, audio_file
                    
                except Exception as e:
                    self.logger.error(f"转写过程出错: {str(e)}")
                    raise RuntimeError(f"转写失败: {str(e)}")
                
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