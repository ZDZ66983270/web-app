#!/usr/bin/env python3
"""
初始化期权数据表
"""

from sqlmodel import SQLModel
from backend.database import engine
from backend.option_models import OptionData

def init_option_tables():
    """创建期权数据表"""
    print("正在创建期权数据表...")
    SQLModel.metadata.create_all(engine)
    print("✅ 期权数据表创建成功！")

if __name__ == "__main__":
    init_option_tables()
