"""
简单的工具加载测试脚本
验证截图工具是否能正确初始化和注册
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.tool_manager import ToolManager

def test_screenshot_tool():
    """测试截图工具加载"""
    print("=" * 60)
    print("测试截图工具加载")
    print("=" * 60)
    
    # 初始化工具管理器
    manager = ToolManager()
    
    # 列出所有工具
    tools = manager.list_tools()
    print(f"\n已加载的工具: {tools}")
    
    # 检查截图工具是否加载
    if "screenshot" in tools:
        print(f"✓ 截图工具已加载 (版本: {tools['screenshot']})")
        
        # 获取工具实例
        tool = manager.get_tool("screenshot")
        
        # 检查工具属性
        print(f"  - 工具名称: {tool.tool_name}")
        print(f"  - 工具版本: {tool.tool_version}")
        
        # 检查注册的actions
        if hasattr(tool, 'actions'):
            print(f"  - 注册的Actions:")
            for action_name, action_info in tool.actions.items():
                print(f"    • {action_name}: {action_info}")
        else:
            print("  - 警告: 未找到actions属性")
        
        # 获取健康状态
        health = manager.get_tool_health("screenshot")
        print(f"\n工具健康状态:")
        print(f"  - 状态: {health.get('status')}")
        print(f"  - 运行时间: {health.get('uptime_seconds')} 秒")
        
        print("\n✓ 所有测试通过!")
        return True
    else:
        print("✗ 截图工具未加载")
        print(f"可用的工具: {list(tools.keys())}")
        return False

if __name__ == "__main__":
    success = test_screenshot_tool()
    sys.exit(0 if success else 1)