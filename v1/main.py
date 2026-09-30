"""
main.py — CLI 入口點

執行方式：
  python v1/main.py <command>     ← 教授 / CI 直接執行
  python -m v1.main <command>     ← package 模式（從 HW2/ 執行）
"""

import sys
import os

# 將 v1/ 目錄加入 sys.path，讓 absolute import 在任何執行方式下都能運作
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from cli import app  # noqa: E402

if __name__ == "__main__":
    app()
