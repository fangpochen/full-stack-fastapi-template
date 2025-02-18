from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

router = APIRouter(prefix="/ffmpeg", tags=["ffmpeg"])
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class FFmpegCommandRequest(BaseModel):
    """FFmpeg命令请求模型"""
    plan_id: int
    more_effects: bool = False
    canvas_y: float = 0.6  # 字幕区域的Y轴位置，默认0.6

class PlanResponse(BaseModel):
    """方案响应模型"""
    id: int
    name: str
    width: int
    height: int
    blur_bg: bool
    add_subtitle: bool = False
    description: str

def get_all_plans() -> List[Dict[str, Any]]:
    """获取所有可用的处理方案"""
    return [
        {
            "id": 1,
            "name": "方案1",
            "description": "竖屏标准尺寸",
            "width": 1200,
            "height": 2480,
            "blur_bg": False
        },
        {
            "id": 2,
            "name": "方案2",
            "description": "竖屏长尺寸",
            "width": 1200,
            "height": 3000,
            "blur_bg": False
        },
        {
            "id": 3,
            "name": "方案3",
            "description": "竖屏短尺寸带模糊",
            "width": 1200,
            "height": 1480,
            "blur_bg": True
        },
        {
            "id": 4,
            "name": "方案4 横屏",
            "description": "横屏标准尺寸",
            "width": 1200,
            "height": 1480,
            "blur_bg": False
        },
        {
            "id": 5,
            "name": "方案5 横屏",
            "description": "横屏大尺寸",
            "width": 1500,
            "height": 2800,
            "blur_bg": False
        },
        {
            "id": 6,
            "name": "方案6 自动字幕",
            "description": "竖屏带字幕",
            "width": 720,
            "height": 1080,
            "blur_bg": False,
            "add_subtitle": True
        }
    ]

def get_plan_params(plan_id: int) -> Dict[str, Any]:
    """获取方案参数"""
    plans = {plan["id"]: plan for plan in get_all_plans()}
    
    if plan_id not in plans:
        raise HTTPException(status_code=400, detail=f"不支持的方案ID: {plan_id}")
    
    return plans[plan_id]

@router.get("/plans", response_model=List[PlanResponse])
async def get_plans() -> List[Dict[str, Any]]:
    """获取所有可用的处理方案
    
    Returns:
        List[Dict[str, Any]]: 方案列表
    """
    try:
        plans = get_all_plans()
        if not plans:
            raise HTTPException(
                status_code=503,
                detail="获取方案列表失败。请联系作者喝杯咖啡吧~"
            )
        return plans
    except Exception as e:
        logger.error(f"获取方案列表失败: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="获取方案列表失败。请联系作者喝杯咖啡吧~"
        )

def generate_gpu_command(width: int, height: int, vf: str, plan_id: int = None, canvas_y: float = 0.6) -> str:
    """生成GPU版本的FFmpeg命令"""
    if plan_id == 6:  # 方案6 - 带字幕的竖屏视频
        # 计算字幕区域高度和位置
        box_height = 0.16  # 字幕框高度（占画面高度的16%）
        font_size = 25  # 使用固定字体大小
        
        # 使用列表组织滤镜
        vf_filters = [
            # 基础缩放和填充
            "scale=1080:1980:force_original_aspect_ratio=1",
            "pad=1080:1980:(ow-iw)/2:(oh-ih)/2:black",
            # 标题白色背景和文字
            "drawbox=x=0:y=0:w=iw:h=100:color=white:t=fill",
            "drawtext=text='%{filename}':fontfile='C\\:/Windows/Fonts/simhei.ttf':fontsize=40:fontcolor=black:x=(w-text_w)/2:y=(50-text_h)/2",
            # 字幕白色背景
            f"drawbox=x=0:y=ih*{canvas_y}:w=iw:h=ih*{box_height}:color=white:t=fill",
            # 添加字幕
            "subtitles='{subtitle_file}':force_style='FontName=SimHei,Fontsize=25,Alignment=2,"
            "Position=50%,"  # 水平居中
            f"Yabs=ih*{canvas_y}+(ih*{box_height}-th)/2,"  # 在白色背景中垂直居中
            "PrimaryColour=&H000000&,BorderStyle=1,Outline=1,"
            "OutlineColour=&HFFFFFF&,MarginL=10,MarginR=10'",
            # 图像优化
            "unsharp=5:5:1.8:5:5:0.5",
            "hqdn3d=1.2:1.2:4:4"
        ]
        
        # 组合滤镜链
        vf_string = ','.join(vf_filters)
        
        # 构建完整命令
        command = (
            'ffmpeg -y -i {input_file} '
            f'-vf "{vf_string}" '
            '-c:v h264_nvenc -preset p4 -tune ll -rc:v vbr -cq:v 23 '
            '-qmin 18 -qmax 28 -b:v 4M -maxrate 12M -bufsize 8M '
            '-spatial-aq 1 -temporal-aq 1 -aq-strength 8 '
            '-b_ref_mode 0 -multipass qres -profile:v high -level 5.1 '
            '-c:a aac -b:a 128k -threads 10 -movflags +faststart '
            '{output_file}'
        )
        return command
    else:  # 其他方案使用原有的命令生成逻辑
        command = 'ffmpeg -y -i {input_file} '
        command += f'-vf "{vf}" '
        command += (
            '-c:v h264_nvenc -preset p2 -tune hq -rc vbr -cq 23 '
            '-b:v 6M -maxrate 10M -bufsize 10M '
            '-spatial-aq 1 -temporal-aq 1 -profile:v high '
        )
        command += (
            '-c:a aac -b:a 128k -threads 10 -movflags +faststart '
            '{output_file}'
        )
        return command

def generate_cpu_command(width: int, height: int, vf: str, plan_id: int = None, canvas_y: float = 0.6) -> str:
    """生成CPU版本的FFmpeg命令"""
    if plan_id == 6:  # 方案6 - 带字幕的竖屏视频
        # 计算字幕区域高度和位置
        box_height = 0.16  # 字幕框高度（占画面高度的16%）
        font_size = 25  # 使用固定字体大小
        
        # 使用列表组织滤镜
        vf_filters = [
            # 基础缩放和填充
            "scale=1080:1980:force_original_aspect_ratio=1",
            "pad=1080:1980:(ow-iw)/2:(oh-ih)/2:black",
            # 标题白色背景和文字
            "drawbox=x=0:y=0:w=iw:h=100:color=white:t=fill",
            "drawtext=text='%{filename}':fontfile='C\\:/Windows/Fonts/simhei.ttf':fontsize=40:fontcolor=black:x=(w-text_w)/2:y=(50-text_h)/2",
            # 字幕白色背景
            f"drawbox=x=0:y=ih*{canvas_y}:w=iw:h=ih*{box_height}:color=white:t=fill",
            # 添加字幕
            "subtitles='{subtitle_file}':force_style='FontName=SimHei,Fontsize=25,Alignment=2,"
            "Position=50%,"  # 水平居中
            f"Yabs=ih*{canvas_y}+(ih*{box_height}-th)/2,"  # 在白色背景中垂直居中
            "PrimaryColour=&H000000&,BorderStyle=1,Outline=1,"
            "OutlineColour=&HFFFFFF&,MarginL=10,MarginR=10'",
            # 图像优化
            "unsharp=5:5:1.8:5:5:0.5",
            "hqdn3d=1.2:1.2:4:4"
        ]
        
        # 组合滤镜链
        vf_string = ','.join(vf_filters)
        
        # 构建完整命令
        command = (
            'ffmpeg -y -i {input_file} '
            f'-vf "{vf_string}" '
            '-c:v libx264 -preset medium -crf 23 -tune film '
            '-x264opts keyint=24:min-keyint=24:no-scenecut '
            '-c:a aac -b:a 128k -threads 10 -movflags +faststart '
            '{output_file}'
        )
        return command
    else:  # 其他方案使用原有的命令生成逻辑
        command = 'ffmpeg -y -i {input_file} '
        command += f'-vf "{vf}" '
        # CPU编码参数
        command += (
            '-c:v libx264 -preset medium -crf 23 '
            '-b:v 6M -maxrate 10M -bufsize 10M '
            '-profile:v high '
        )
        # 音频和其他参数
        command += (
            '-c:a aac -b:a 128k -threads 10 -movflags +faststart '
            '{output_file}'
        )
        return command

def generate_ffmpeg_command(plan_params: Dict[str, Any], more_effects: bool, canvas_y: float = 0.6) -> Dict[str, str]:
    """生成FFmpeg命令
    
    Args:
        plan_params: 方案参数
        more_effects: 是否启用更多效果
        canvas_y: 字幕区域的Y轴位置，默认0.6
        
    Returns:
        Dict[str, str]: 包含GPU和CPU命令的响应
    """
    # 基础参数
    width = plan_params["width"]
    height = plan_params["height"]
    plan_id = plan_params["id"]
    
    # 定义不同效果的滤镜链
    filter_chains = {
        "blur_bg": (
            f'split [main][bg];'
            f'[main]scale={width}:{height}:force_original_aspect_ratio=1[fg];'
            f'[bg]scale={width}:{height}:force_original_aspect_ratio=increase,'
            f'crop={width}:{height},boxblur=20:5[blurred];'
            f'[blurred][fg]overlay=(W-w)/2:(H-h)/2'
            f',unsharp=5:5:1.8:5:5:0.5,hqdn3d=1.2:1.2:4:4'
        ),
        "more_effects": (
            f'split[original][blur];'
            f'[blur]boxblur=1:1[blurred];'
            f'[original][blurred]overlay=0:0:0.05,'
            f'drawgrid=width=10:height=100:thickness=2:color=black@0.01,'
            f'pad=w=iw+20:h=ih+20:x=10:y=10:color=gray@0.05,'
            f'scale={width}:{height}:force_original_aspect_ratio=1,'
            f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,'
            f'unsharp=5:5:1.8:5:5:0.5,hqdn3d=1.2:1.2:4:4'
        ),
        "basic": (
            f'scale={width}:{height}:force_original_aspect_ratio=1,'
            f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black'
        )
    }
    
    # 选择滤镜链
    if plan_params.get("blur_bg", False):
        vf = filter_chains["blur_bg"]
    elif more_effects:
        vf = filter_chains["more_effects"]
    else:
        vf = filter_chains["basic"]
    
    # 生成两种版本的命令
    return {
        "gpu_command": generate_gpu_command(width, height, vf, plan_id, canvas_y),
        "cpu_command": generate_cpu_command(width, height, vf, plan_id, canvas_y)
    }

@router.post("/command", response_model=Dict[str, str])
async def get_ffmpeg_command(request: FFmpegCommandRequest) -> Dict[str, str]:
    """获取FFmpeg命令
    
    Args:
        request: 包含plan_id、more_effects和canvas_y的请求
        
    Returns:
        Dict[str, str]: 包含GPU和CPU命令的响应
    """
    try:
        # 获取方案参数
        plan_params = get_plan_params(request.plan_id)
        
        # 生成命令
        commands = generate_ffmpeg_command(
            plan_params, 
            request.more_effects,
            request.canvas_y
        )
        
        return commands
        
    except Exception as e:
        logger.error(f"生成命令失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成命令失败: {str(e)}") 