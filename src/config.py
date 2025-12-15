# -*- coding: utf-8 -*-
"""
配置文件 - 医疗知识助手智能体
"""
import os
from pathlib import Path

# ===================== 项目路径配置 =====================
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
LOG_DIR = BASE_DIR / "logs"

# 确保目录存在
KNOWLEDGE_BASE_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# ===================== 百炼/LLM 配置 =====================
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL = "qwen-plus-latest"
EMBEDDING_MODEL = "text-embedding-v2"

# ===================== MySQL 数据库配置 =====================
MYSQL_CONFIG = {
    "host": "rm-bp1y35g510t57uexqlo.mysql.rds.aliyuncs.com",
    "port": 3306,
    "user": "logcloud",
    "password": "Logcloud4321",
    "database": "medical_knowledge_base",
    "charset": "utf8mb4"
}

# ===================== RAG 配置 =====================
RAG_CONFIG = {
    "chunk_size": 500,
    "chunk_overlap": 50,
    "top_k": 5,
    "similarity_threshold": 0.3
}

# ===================== 索引更新配置 =====================
INDEX_UPDATE_INTERVAL_MINUTES = 2  # 索引更新间隔(分钟)

# ===================== 日志配置 =====================
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": LOG_DIR / "medical_agent.log"
}

# ===================== PDF 文档配置 =====================
PDF_FILES = [
    DATA_DIR / "高血压诊疗指南.pdf",
    DATA_DIR / "中国高血压防治指南.pdf"
]

# Excel 文件配置
EXCEL_FILE = DATA_DIR / "糖尿病病例统计.xlsx"

