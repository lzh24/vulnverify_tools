"""
Example Tool Service - 示例工具服务

本工具演示如何使用外部工具框架创建一个新的工具服务。
使用 @tool_action 装饰器定义多个功能（action）。
"""

from typing import Dict, Any

from core.base_tool_service import BaseToolService, tool_action


class ExampleToolService(BaseToolService):
    """
    示例工具服务类
    
    展示了如何：
    1. 继承 BaseToolService
    2. 使用 @tool_action 装饰器注册功能
    3. 实现参数验证和业务逻辑
    """
    
    def __init__(self):
        super().__init__("example-tool", "1.0.0")
        self.logger.info("Example tool service initialized")

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Legacy parameter validation - kept for backward compatibility"""
        return True

    async def _execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy execution method - not used with new action pattern"""
        raise NotImplementedError("Use action-based methods instead")

    @tool_action("uppercase", "Convert text to uppercase")
    async def convert_uppercase(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        将文本转换为大写
        
        参数:
            text (str): 要转换的文本（必需）
        
        返回:
            processed_text (str): 转换后的大写文本
            length (int): 文本长度
            message (str): 处理信息
        """
        text = params.get("text")
        if not text:
            raise ValueError("text parameter is required")
        
        if not isinstance(text, str):
            raise ValueError("text must be a string")
        
        result = text.upper()
        
        self.logger.info(f"Converted {len(text)} characters to uppercase")
        
        return {
            "processed_text": result,
            "length": len(text),
            "message": f"Successfully converted {len(text)} characters to uppercase"
        }

    @tool_action("lowercase", "Convert text to lowercase")
    async def convert_lowercase(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        将文本转换为小写
        
        参数:
            text (str): 要转换的文本（必需）
        
        返回:
            processed_text (str): 转换后的小写文本
            length (int): 文本长度
            message (str): 处理信息
        """
        text = params.get("text")
        if not text:
            raise ValueError("text parameter is required")
        
        if not isinstance(text, str):
            raise ValueError("text must be a string")
        
        result = text.lower()
        
        self.logger.info(f"Converted {len(text)} characters to lowercase")
        
        return {
            "processed_text": result,
            "length": len(text),
            "message": f"Successfully converted {len(text)} characters to lowercase"
        }

    @tool_action("reverse", "Reverse the text")
    async def reverse_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        反转文本
        
        参数:
            text (str): 要反转的文本（必需）
        
        返回:
            processed_text (str): 反转后的文本
            length (int): 文本长度
            message (str): 处理信息
        """
        text = params.get("text")
        if not text:
            raise ValueError("text parameter is required")
        
        if not isinstance(text, str):
            raise ValueError("text must be a string")
        
        result = text[::-1]
        
        self.logger.info(f"Reversed {len(text)} characters")
        
        return {
            "processed_text": result,
            "length": len(text),
            "message": f"Successfully reversed {len(text)} characters"
        }
