# -*- coding: utf-8 -*-
"""
数据库客户端模块 - MySQL 连接与查询
"""
import logging
import time
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from src.config import MYSQL_CONFIG

logger = logging.getLogger(__name__)


class DBClient:
    """MySQL 数据库客户端"""
    
    def __init__(self, config: Dict = None):
        self.config = config or MYSQL_CONFIG
        self._connection = None
    
    def _get_connection(self):
        """获取数据库连接"""
        if self._connection is None or not self._connection.open:
            try:
                self._connection = pymysql.connect(
                    host=self.config["host"],
                    port=self.config["port"],
                    user=self.config["user"],
                    password=self.config["password"],
                    database=self.config["database"],
                    charset=self.config["charset"],
                    cursorclass=DictCursor,
                    connect_timeout=10
                )
                logger.info(f"[数据库] 连接成功: {self.config['host']}")
            except Exception as e:
                logger.error(f"[数据库] 连接失败: {str(e)}")
                raise
        return self._connection
    
    @contextmanager
    def cursor(self):
        """获取游标的上下文管理器"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            cursor.close()
    
    def execute_query(self, sql: str, params: tuple = None) -> Dict:
        """
        执行查询
        
        Args:
            sql: SQL语句
            params: 参数
            
        Returns:
            {"success": bool, "data": list, "error": str, "execution_time_ms": int}
        """
        start_time = time.time()
        try:
            with self.cursor() as cursor:
                logger.info(f"[SQL查询] {sql[:200]}...")
                cursor.execute(sql, params)
                data = cursor.fetchall()
                execution_time = int((time.time() - start_time) * 1000)
                logger.info(f"[SQL结果] 返回 {len(data)} 条记录, 耗时 {execution_time}ms")
                
                return {
                    "success": True,
                    "data": data,
                    "error": None,
                    "execution_time_ms": execution_time
                }
        except Exception as e:
            error_msg = f"SQL执行失败: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "data": [],
                "error": error_msg,
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }
    
    def get_patient_info(self, patient_id: str) -> Optional[Dict]:
        """获取患者基本信息"""
        sql = "SELECT * FROM patient_info WHERE patient_id = %s"
        result = self.execute_query(sql, (patient_id,))
        if result["success"] and result["data"]:
            return result["data"][0]
        return None
    
    def get_patient_medical_records(self, patient_id: str) -> List[Dict]:
        """获取患者病历记录"""
        sql = """
            SELECT * FROM medical_records 
            WHERE patient_id = %s 
            ORDER BY visit_date DESC
        """
        result = self.execute_query(sql, (patient_id,))
        return result["data"] if result["success"] else []
    
    def get_patient_lab_results(self, patient_id: str) -> List[Dict]:
        """获取患者检查检验结果"""
        sql = """
            SELECT * FROM lab_results 
            WHERE patient_id = %s 
            ORDER BY test_date DESC
        """
        result = self.execute_query(sql, (patient_id,))
        return result["data"] if result["success"] else []
    
    def get_patient_medications(self, patient_id: str) -> List[Dict]:
        """获取患者用药记录"""
        sql = """
            SELECT * FROM medication_records 
            WHERE patient_id = %s 
            ORDER BY medication_date DESC
        """
        result = self.execute_query(sql, (patient_id,))
        return result["data"] if result["success"] else []
    
    def get_patient_diagnoses(self, patient_id: str) -> List[Dict]:
        """获取患者诊断记录"""
        sql = """
            SELECT * FROM diagnosis_records 
            WHERE patient_id = %s 
            ORDER BY diagnosis_date DESC
        """
        result = self.execute_query(sql, (patient_id,))
        return result["data"] if result["success"] else []
    
    def get_hypertension_assessment(self, patient_id: str) -> Optional[Dict]:
        """获取患者高血压风险评估"""
        sql = """
            SELECT * FROM hypertension_risk_assessment 
            WHERE patient_id = %s 
            ORDER BY assessment_date DESC 
            LIMIT 1
        """
        result = self.execute_query(sql, (patient_id,))
        if result["success"] and result["data"]:
            return result["data"][0]
        return None
    
    def get_diabetes_assessment(self, patient_id: str) -> Optional[Dict]:
        """获取患者糖尿病控制评估"""
        sql = """
            SELECT * FROM diabetes_control_assessment 
            WHERE patient_id = %s 
            ORDER BY assessment_date DESC 
            LIMIT 1
        """
        result = self.execute_query(sql, (patient_id,))
        if result["success"] and result["data"]:
            return result["data"][0]
        return None
    
    def get_guideline_recommendations(self, disease_type: str = None, 
                                      update_date_after: str = None) -> List[Dict]:
        """
        获取指南推荐规则
        
        Args:
            disease_type: 疾病类型过滤
            update_date_after: 更新日期之后的记录
        """
        sql = "SELECT * FROM guideline_recommendations WHERE is_active = TRUE"
        params = []
        
        if disease_type:
            sql += " AND disease_type = %s"
            params.append(disease_type)
        
        if update_date_after:
            sql += " AND update_date >= %s"
            params.append(update_date_after)
        
        sql += " ORDER BY update_date DESC"
        
        result = self.execute_query(sql, tuple(params) if params else None)
        return result["data"] if result["success"] else []
    
    def get_full_patient_profile(self, patient_id: str) -> Dict:
        """
        获取完整患者画像
        
        Returns:
            包含患者所有信息的完整画像字典
        """
        profile = {
            "patient_id": patient_id,
            "basic_info": self.get_patient_info(patient_id),
            "medical_records": self.get_patient_medical_records(patient_id),
            "lab_results": self.get_patient_lab_results(patient_id),
            "medications": self.get_patient_medications(patient_id),
            "diagnoses": self.get_patient_diagnoses(patient_id),
            "hypertension_assessment": self.get_hypertension_assessment(patient_id),
            "diabetes_assessment": self.get_diabetes_assessment(patient_id),
            "source": {
                "type": "mysql",
                "tables": ["patient_info", "medical_records", "lab_results", 
                          "medication_records", "diagnosis_records",
                          "hypertension_risk_assessment", "diabetes_control_assessment"]
            }
        }
        return profile
    
    def log_system_operation(self, operation_type: str, operation_user: str,
                             operation_details: str, patient_id: str = None,
                             execution_time_ms: int = None, status: str = "成功"):
        """记录系统操作日志到数据库"""
        sql = """
            INSERT INTO system_logs 
            (operation_type, operation_user, operation_details, patient_id, execution_time_ms, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        try:
            with self.cursor() as cursor:
                cursor.execute(sql, (operation_type, operation_user, operation_details,
                                    patient_id, execution_time_ms, status))
        except Exception as e:
            logger.error(f"记录系统日志失败: {str(e)}")
    
    def search_by_keyword(self, keyword: str, tables: List[str] = None) -> List[Dict]:
        """
        在数据库中搜索关键词
        
        Args:
            keyword: 搜索关键词
            tables: 要搜索的表列表
        """
        results = []
        
        # 搜索指南推荐
        sql = """
            SELECT 'guideline_recommendations' as source_table, 
                   guideline_name, disease_type, patient_condition,
                   recommendation_level, recommendation_content, 
                   evidence_source, update_date
            FROM guideline_recommendations 
            WHERE is_active = TRUE 
              AND (recommendation_content LIKE %s 
                   OR patient_condition LIKE %s
                   OR guideline_name LIKE %s)
        """
        search_pattern = f"%{keyword}%"
        result = self.execute_query(sql, (search_pattern, search_pattern, search_pattern))
        if result["success"]:
            results.extend(result["data"])
        
        return results
    
    def close(self):
        """关闭数据库连接"""
        if self._connection and self._connection.open:
            self._connection.close()
            logger.info("[数据库] 连接已关闭")


# 全局数据库客户端实例
_db_client: Optional[DBClient] = None


def get_db_client() -> DBClient:
    """获取全局数据库客户端实例"""
    global _db_client
    if _db_client is None:
        _db_client = DBClient()
    return _db_client

