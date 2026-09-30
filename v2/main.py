"""
main.py — CLI 入口點（v2.0）

執行方式：
  python v2/main.py <command>     ← 直接執行
  python -m v2.main <command>     ← package 模式（從專案根目錄執行）
"""

import sys
import os

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from cli import app  # noqa: E402

if __name__ == "__main__":
    app()
