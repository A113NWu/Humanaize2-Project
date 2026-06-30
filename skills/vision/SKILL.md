# Vision Skill - AI视觉交互技能

## 功能描述

该技能为AI提供视觉交互能力，包括屏幕捕获、摄像头调用、图像识别和场景分析。

## 主要功能

### 1. 视觉访问控制
- **屏幕捕获**：AI可自主捕获当前屏幕显示内容
- **实时访问**：确保AI能够随时获取屏幕信息

### 2. 摄像头调用机制
- **主动激活**：AI可按需启动/停止摄像头
- **场景触发**：
  - 用户指向实物提问时（如"这是什么"）
  - AI解决问题过程中需要视觉信息时

### 3. 图像识别能力
- **文本识别（OCR）**：识别图像中的文字内容
- **物体检测**：检测图像中的物体及其位置
- **综合分析**：结合文本识别和物体检测的综合分析

### 4. 多模块协作
- 视觉模块可与其他认知模块无缝协作
- 提供结构化的识别结果便于AI分析

### 5. 用户界面
- 摄像头激活后自动弹出独立显示窗口
- 在AI视觉聚焦区域生成高亮方框标记
- 显示识别结果及解读
- 提供相关问题的分步解决方案

## API 接口

### execute(input_data)

执行视觉技能操作。

#### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| input_data | str/dict | 操作命令或包含操作的字典 |

#### 支持的操作

| 操作 | 说明 | 示例 |
|------|------|------|
| `capture_screen` | 捕获当前屏幕 | `"capture_screen"` |
| `start_camera` | 启动摄像头 | `"start_camera"` |
| `stop_camera` | 停止摄像头 | `"stop_camera"` |
| `capture_frame` | 捕获摄像头帧 | `"capture_frame"` |
| `recognize_text` | 识别图像中文本 | `{"action": "recognize_text", "image": "base64..."}` |
| `detect_objects` | 检测图像中物体 | `{"action": "detect_objects", "image": "base64..."}` |
| `analyze` | 综合分析图像 | `{"action": "analyze", "image": "base64..."}` |
| `screen_analyze` | 捕获并分析屏幕 | `"screen_analyze"` |
| `camera_analyze` | 启动摄像头并分析 | `"camera_analyze"` |

#### 返回值

```json
{
    "success": true,
    "image": "base64_encoded_image",
    "source": "screen|camera",
    "text_recognition": {
        "text": "识别的文本内容",
        "bounding_boxes": [
            {
                "text": "文本片段",
                "confidence": 95,
                "bbox": {"x": 100, "y": 200, "width": 150, "height": 30}
            }
        ]
    },
    "object_detection": {
        "objects": [
            {
                "bbox": {"x": 50, "y": 50, "width": 200, "height": 150},
                "area": 30000
            }
        ],
        "count": 3
    },
    "highlight_boxes": [
        {
            "type": "text|object",
            "label": "标记内容",
            "bbox": {"x": 100, "y": 200, "width": 150, "height": 30},
            "confidence": 0.95
        }
    ]
}
```

## 依赖库

| 库 | 用途 | 安装命令 |
|----|------|----------|
| opencv-python | 图像处理和摄像头访问 | `pip install opencv-python` |
| numpy | 数值计算 | `pip install numpy` |
| pillow | 屏幕捕获 | `pip install pillow` |
| pytesseract | OCR文本识别 | `pip install pytesseract` |
| requests | API调用（可选） | `pip install requests` |

## 使用示例

### 示例1：捕获并分析屏幕
```python
from skills.vision import execute

result = execute("screen_analyze")
if result["success"]:
    print(f"识别到文本: {result['text_recognition']['text']}")
    print(f"检测到物体数量: {result['object_detection']['count']}")
```

### 示例2：启动摄像头并分析
```python
result = execute("camera_analyze")
if result["success"]:
    print(f"图像来源: {result['source']}")
    print(f"高亮标记: {result['highlight_boxes']}")
```

### 示例3：分析指定图像
```python
result = execute({
    "action": "analyze",
    "image": base64_encoded_image
})
```

## 调用方式

在Humanaize对话中，AI可以通过以下方式调用视觉技能：

```json
{"skill": "vision", "input": {"action": "screen_analyze"}}
{"skill": "vision", "input": {"action": "camera_analyze"}}
{"skill": "vision", "input": {"action": "recognize_text", "image": "base64..."}}
```

## 注意事项

1. 摄像头访问需要用户授权
2. 文本识别需要安装Tesseract引擎（中文支持需要额外安装语言包）
3. 屏幕捕获功能在Linux上需要额外配置
4. 建议在使用摄像头后及时调用`stop_camera`释放资源
