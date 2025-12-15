# -*- coding: utf-8 -*-
"""
工具函数模块
"""
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.config import LOG_CONFIG, LOG_DIR

# 配置日志
def setup_logging():
    """配置日志系统"""
    LOG_DIR.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, LOG_CONFIG["level"]),
        format=LOG_CONFIG["format"],
        handlers=[
            logging.FileHandler(LOG_CONFIG["file"], encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


logger = setup_logging()


def log_operation(operation_type: str, details: str, patient_id: str = None, 
                  execution_time_ms: int = None, status: str = "成功"):
    """
    记录操作日志
    
    Args:
        operation_type: 操作类型 (查询/插入/更新/删除/分析)
        details: 操作详情
        patient_id: 患者ID
        execution_time_ms: 执行时间(毫秒)
        status: 状态 (成功/失败/警告)
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "operation_type": operation_type,
        "details": details,
        "patient_id": patient_id,
        "execution_time_ms": execution_time_ms,
        "status": status
    }
    
    if status == "成功":
        logger.info(f"[{operation_type}] {details}")
    elif status == "失败":
        logger.error(f"[{operation_type}] {details}")
    else:
        logger.warning(f"[{operation_type}] {details}")
    
    return log_entry


def format_source_reference(source_type: str, reference: str, 
                            page: int = None, row: int = None, table: str = None) -> Dict:
    """
    格式化数据来源引用
    
    Args:
        source_type: 来源类型 (pdf/excel/mysql)
        reference: 引用说明
        page: PDF页码
        row: Excel行号
        table: MySQL表名
        
    Returns:
        格式化的来源引用字典
    """
    ref = {
        "type": source_type,
        "reference": reference
    }
    
    if page is not None:
        ref["page"] = page
    if row is not None:
        ref["row"] = row
    if table is not None:
        ref["table"] = table
    
    return ref


def format_evidence_level(level: str) -> str:
    """
    格式化证据等级显示
    
    Args:
        level: 证据等级 (ⅠA/ⅠB/ⅡA/ⅡB/Ⅲ)
        
    Returns:
        格式化的证据等级字符串
    """
    level_descriptions = {
        "ⅠA": "ⅠA级 (强推荐，高质量证据)",
        "ⅠB": "ⅠB级 (强推荐，中等质量证据)",
        "ⅡA": "ⅡA级 (中等推荐，高质量证据)",
        "ⅡB": "ⅡB级 (中等推荐，中等质量证据)",
        "Ⅲ": "Ⅲ级 (弱推荐)"
    }
    return level_descriptions.get(level, level)


def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    """计算BMI"""
    if height_cm <= 0 or weight_kg <= 0:
        return 0
    height_m = height_cm / 100
    return round(weight_kg / (height_m ** 2), 1)


def classify_bp(sbp: float, dbp: float) -> Dict:
    """
    高血压分级
    
    Args:
        sbp: 收缩压
        dbp: 舒张压
        
    Returns:
        {"level": int, "name": str, "description": str}
    """
    if sbp < 120 and dbp < 80:
        return {"level": 0, "name": "正常血压", "description": "理想血压水平"}
    elif sbp < 140 and dbp < 90:
        return {"level": 0.5, "name": "正常高值", "description": "血压偏高，需注意"}
    elif sbp < 160 and dbp < 100:
        return {"level": 1, "name": "1级高血压", "description": "轻度高血压"}
    elif sbp < 180 and dbp < 110:
        return {"level": 2, "name": "2级高血压", "description": "中度高血压"}
    else:
        return {"level": 3, "name": "3级高血压", "description": "重度高血压"}


def classify_hba1c(hba1c: float) -> Dict:
    """
    糖化血红蛋白分级
    
    Args:
        hba1c: 糖化血红蛋白值
        
    Returns:
        {"level": str, "description": str}
    """
    if hba1c < 5.7:
        return {"level": "正常", "description": "血糖控制正常"}
    elif hba1c < 6.5:
        return {"level": "糖尿病前期", "description": "需要加强生活方式干预"}
    elif hba1c < 7.0:
        return {"level": "控制良好", "description": "糖尿病控制良好"}
    elif hba1c < 8.0:
        return {"level": "控制一般", "description": "需要加强治疗"}
    else:
        return {"level": "控制不佳", "description": "需要强化治疗，考虑调整方案"}


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """安全的 JSON 解析"""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default

