"""Cython 编译入口：把 vulnverify_tools 核心模块编译为 .so，提升逆向门槛。

仅编译第一阶段目标模块（无 pydantic 模型、无动态加载的核心业务逻辑）。
core/config.py 是 pydantic-settings BaseSettings，保持 .pyc 不编译。
本文件只在 Docker builder 阶段使用，不修改业务代码。
"""

from Cython.Build import cythonize
from setuptools import setup

# 第一阶段目标模块（保密价值高、无 pydantic 模型、纯业务逻辑）
TARGETS = [
    "core/auth.py",
    "core/base_tool_service.py",
    "core/image_hosting.py",
    "core/logger.py",
    "core/mcp_server.py",
    "core/tool_manager.py",
]

setup(
    name="vulnverify-tools-cython",
    packages=[],
    py_modules=[],
    ext_modules=cythonize(
        TARGETS,
        compiler_directives={
            "language_level": 3,
            "c_string_type": "str",
            "c_string_encoding": "utf8",
        },
    ),
)
