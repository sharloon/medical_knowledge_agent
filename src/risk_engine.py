# -*- coding: utf-8 -*-
"""
风险评估引擎 - 高血压/糖尿病风险分层与随访计划
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from src.utils import classify_bp, classify_hba1c, format_evidence_level
from src.db_client import get_db_client

logger = logging.getLogger(__name__)


class RiskEngine:
    """风险评估引擎"""
    
    def __init__(self):
        self.db_client = get_db_client()
    
    def assess_hypertension_risk(self, profile: Dict) -> Dict:
        """
        高血压风险分层评估
        
        基于《中国高血压防治指南2023》的风险分层标准
        
        Args:
            profile: 患者画像
            
        Returns:
            风险评估结果
        """
        result = {
            "risk_level": "未评估",
            "risk_factors": [],
            "target_organ_damage": [],
            "clinical_conditions": [],
            "bp_classification": None,
            "follow_up_plan": None,
            "recommendations": [],
            "evidence_level": "ⅠA",
            "source": "中国高血压防治指南2023"
        }
        
        # 获取血压数据
        ha = profile.get("hypertension_assessment")
        basic_info = profile.get("basic_info", {})
        
        if not ha:
            logger.warning("[风险评估] 缺少高血压评估数据")
            result["risk_level"] = "无法评估（缺少血压数据）"
            return result
        
        sbp = float(ha.get("sbp", 0))
        dbp = float(ha.get("dbp", 0))
        
        # 血压分级
        bp_class = classify_bp(sbp, dbp)
        result["bp_classification"] = bp_class
        
        # 收集危险因素
        risk_factors = []
        age = basic_info.get("age", 0)
        gender = basic_info.get("gender", "")
        
        # 年龄因素
        if (gender == "男" and age >= 55) or (gender == "女" and age >= 65):
            risk_factors.append("年龄（男≥55岁/女≥65岁）")
        
        # BMI
        bmi = basic_info.get("bmi")
        if bmi and float(bmi) >= 28:
            risk_factors.append(f"肥胖（BMI {bmi}）")
        elif bmi and float(bmi) >= 24:
            risk_factors.append(f"超重（BMI {bmi}）")
        
        # 从评估记录中获取其他危险因素
        if ha.get("risk_factors"):
            factors = ha["risk_factors"].split(",")
            risk_factors.extend([f.strip() for f in factors if f.strip()])
        
        result["risk_factors"] = risk_factors
        
        # 靶器官损害
        if ha.get("target_organs_damage"):
            damages = ha["target_organs_damage"].split(",")
            result["target_organ_damage"] = [d.strip() for d in damages if d.strip()]
        
        # 临床疾患
        if ha.get("clinical_conditions"):
            conditions = ha["clinical_conditions"].split(",")
            result["clinical_conditions"] = [c.strip() for c in conditions if c.strip()]
        
        # 检查是否合并糖尿病
        da = profile.get("diabetes_assessment")
        if da:
            risk_factors.append("糖尿病")
        
        # 风险分层
        risk_level = self._calculate_risk_level(
            bp_class["level"],
            len(risk_factors),
            len(result["target_organ_damage"]),
            len(result["clinical_conditions"]),
            da is not None
        )
        result["risk_level"] = risk_level
        
        # 生成随访计划
        result["follow_up_plan"] = self._generate_follow_up_plan(risk_level, bp_class["level"])
        
        # 生成治疗建议
        result["recommendations"] = self._generate_bp_recommendations(
            bp_class["level"], risk_level, risk_factors
        )
        
        logger.info(f"[风险评估] 高血压风险分层: {risk_level}")
        return result
    
    def _calculate_risk_level(self, bp_level: float, rf_count: int, 
                              tod_count: int, cc_count: int, has_dm: bool) -> str:
        """
        计算风险等级
        
        基于血压分级、危险因素数量、靶器官损害、临床疾患进行分层
        """
        # 有临床疾患直接为很高危
        if cc_count > 0:
            return "很高危"
        
        # 有靶器官损害或糖尿病
        if tod_count > 0 or has_dm:
            if bp_level >= 2:
                return "很高危"
            else:
                return "高危"
        
        # 根据危险因素数量和血压分级
        if bp_level >= 3:
            return "很高危"
        elif bp_level == 2:
            if rf_count >= 3:
                return "很高危"
            elif rf_count >= 1:
                return "高危"
            else:
                return "中危"
        elif bp_level == 1:
            if rf_count >= 3:
                return "高危"
            elif rf_count >= 1:
                return "中危"
            else:
                return "低危"
        else:
            if rf_count >= 3:
                return "中危"
            else:
                return "低危"
    
    def _generate_follow_up_plan(self, risk_level: str, bp_level: float) -> Dict:
        """生成随访计划"""
        plans = {
            "低危": {
                "frequency": "3个月",
                "next_visit": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
                "monitoring": ["血压监测（每周1-2次）", "生活方式评估"],
                "targets": ["血压<140/90 mmHg"]
            },
            "中危": {
                "frequency": "1个月",
                "next_visit": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
                "monitoring": ["血压监测（每周2-3次）", "心血管危险因素评估", "靶器官检查"],
                "targets": ["血压<140/90 mmHg", "评估是否需要药物治疗"]
            },
            "高危": {
                "frequency": "2周",
                "next_visit": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"),
                "monitoring": ["血压监测（每日）", "心血管风险评估", "肾功能检查", "心电图"],
                "targets": ["血压<130/80 mmHg", "立即开始药物治疗"]
            },
            "很高危": {
                "frequency": "1周",
                "next_visit": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
                "monitoring": ["血压监测（每日2次）", "心血管全面评估", "肾功能", "眼底检查"],
                "targets": ["尽快将血压控制在安全范围", "强化治疗", "考虑转诊"]
            }
        }
        return plans.get(risk_level, plans["中危"])
    
    def _generate_bp_recommendations(self, bp_level: float, risk_level: str, 
                                     risk_factors: List[str]) -> List[Dict]:
        """生成降压治疗建议"""
        recommendations = []
        
        # 生活方式建议（所有患者）
        recommendations.append({
            "type": "生活方式干预",
            "content": "限盐（<6g/d）、减重、规律运动、戒烟限酒、DASH饮食",
            "evidence_level": "ⅠA",
            "source": "中国高血压防治指南2023"
        })
        
        # 药物治疗
        if risk_level in ["高危", "很高危"]:
            recommendations.append({
                "type": "药物治疗",
                "content": "立即开始降压药物治疗，推荐起始联合治疗",
                "drugs": ["CCB（如氨氯地平）", "ACEI/ARB（如缬沙坦）"],
                "evidence_level": "ⅠA",
                "source": "中国高血压防治指南2023"
            })
        elif risk_level == "中危":
            recommendations.append({
                "type": "药物治疗",
                "content": "生活方式干预4周后若血压未达标，开始药物治疗",
                "drugs": ["CCB", "ACEI/ARB", "利尿剂（任选一种）"],
                "evidence_level": "ⅠA",
                "source": "中国高血压防治指南2023"
            })
        else:
            recommendations.append({
                "type": "观察随访",
                "content": "首先强化生活方式干预，密切监测血压",
                "evidence_level": "ⅠB",
                "source": "中国高血压防治指南2023"
            })
        
        # 合并糖尿病的特殊建议
        if "糖尿病" in risk_factors:
            recommendations.append({
                "type": "合并糖尿病",
                "content": "优先选择ACEI/ARB类药物，有肾脏保护作用",
                "drugs": ["ACEI（如依那普利）", "ARB（如缬沙坦）"],
                "evidence_level": "ⅠA",
                "source": "中国高血压防治指南2023"
            })
        
        return recommendations
    
    def assess_diabetes_control(self, profile: Dict) -> Dict:
        """
        糖尿病控制评估
        
        基于《中国2型糖尿病防治指南》
        
        Args:
            profile: 患者画像
            
        Returns:
            评估结果
        """
        result = {
            "control_status": "未评估",
            "hba1c_classification": None,
            "recommendations": [],
            "follow_up_plan": None,
            "evidence_level": "ⅠA",
            "source": "中国2型糖尿病防治指南2020"
        }
        
        da = profile.get("diabetes_assessment")
        if not da:
            logger.warning("[风险评估] 缺少糖尿病评估数据")
            result["control_status"] = "无法评估（缺少数据）"
            return result
        
        # HbA1c 分级
        hba1c = da.get("hba1c")
        if hba1c:
            hba1c = float(hba1c)
            result["hba1c_classification"] = classify_hba1c(hba1c)
            
            # 控制状态
            if hba1c < 7.0:
                result["control_status"] = "良好"
            elif hba1c < 8.0:
                result["control_status"] = "一般"
            else:
                result["control_status"] = "不佳"
        
        # 血糖值
        fg = da.get("fasting_glucose")
        pg = da.get("postprandial_glucose")
        
        result["glucose_values"] = {
            "fasting": float(fg) if fg else None,
            "postprandial": float(pg) if pg else None
        }
        
        # 生成治疗建议
        result["recommendations"] = self._generate_dm_recommendations(
            hba1c, fg, pg, da.get("insulin_usage")
        )
        
        # 生成随访计划
        result["follow_up_plan"] = self._generate_dm_follow_up(result["control_status"])
        
        logger.info(f"[风险评估] 糖尿病控制状态: {result['control_status']}")
        return result
    
    def _generate_dm_recommendations(self, hba1c: float, fg: float, 
                                     pg: float, insulin_usage: bool) -> List[Dict]:
        """生成糖尿病治疗建议"""
        recommendations = []
        
        # 生活方式干预
        recommendations.append({
            "type": "生活方式干预",
            "content": "医学营养治疗、运动疗法、戒烟、糖尿病自我管理教育",
            "evidence_level": "ⅠA",
            "source": "中国2型糖尿病防治指南2020"
        })
        
        if hba1c:
            if hba1c >= 9.0:
                recommendations.append({
                    "type": "强化治疗",
                    "content": "HbA1c≥9.0%，建议起始胰岛素治疗或联合治疗",
                    "drugs": ["基础胰岛素", "二甲双胍联合胰岛素"],
                    "evidence_level": "ⅠA",
                    "source": "中国2型糖尿病防治指南2020"
                })
            elif hba1c >= 7.5:
                recommendations.append({
                    "type": "联合治疗",
                    "content": "HbA1c≥7.5%，建议二甲双胍联合其他降糖药",
                    "drugs": ["二甲双胍+DPP-4抑制剂", "二甲双胍+SGLT-2抑制剂", "二甲双胍+GLP-1受体激动剂"],
                    "evidence_level": "ⅠA",
                    "source": "中国2型糖尿病防治指南2020"
                })
            elif hba1c >= 7.0:
                recommendations.append({
                    "type": "调整治疗",
                    "content": "HbA1c 7.0-7.5%，强化生活方式干预，必要时增加药物",
                    "drugs": ["二甲双胍（一线）"],
                    "evidence_level": "ⅠA",
                    "source": "中国2型糖尿病防治指南2020"
                })
            else:
                recommendations.append({
                    "type": "维持治疗",
                    "content": "HbA1c<7.0%，控制良好，维持当前治疗方案",
                    "evidence_level": "ⅠA",
                    "source": "中国2型糖尿病防治指南2020"
                })
        
        return recommendations
    
    def _generate_dm_follow_up(self, control_status: str) -> Dict:
        """生成糖尿病随访计划"""
        plans = {
            "良好": {
                "frequency": "3个月",
                "next_visit": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
                "monitoring": ["HbA1c（每3个月）", "空腹血糖", "餐后血糖"],
                "annual_check": ["眼底检查", "肾功能", "足部检查"]
            },
            "一般": {
                "frequency": "1-2个月",
                "next_visit": (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d"),
                "monitoring": ["HbA1c（每3个月）", "血糖谱监测", "用药依从性评估"],
                "annual_check": ["眼底检查", "肾功能", "神经病变筛查", "足部检查"]
            },
            "不佳": {
                "frequency": "2-4周",
                "next_visit": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"),
                "monitoring": ["强化血糖监测", "HbA1c（每3个月）", "并发症筛查"],
                "annual_check": ["眼底检查", "肾功能", "心血管风险评估", "神经病变", "足部检查"]
            }
        }
        return plans.get(control_status, plans["一般"])
    
    def comprehensive_assessment(self, patient_id: str) -> Dict:
        """
        综合风险评估
        
        Args:
            patient_id: 患者ID
            
        Returns:
            综合评估结果
        """
        # 获取完整患者画像
        profile = self.db_client.get_full_patient_profile(patient_id)
        
        if not profile.get("basic_info"):
            return {
                "success": False,
                "error": f"未找到患者: {patient_id}",
                "patient_id": patient_id
            }
        
        result = {
            "success": True,
            "patient_id": patient_id,
            "profile": profile,
            "assessments": {}
        }
        
        # 高血压风险评估
        result["assessments"]["hypertension"] = self.assess_hypertension_risk(profile)
        
        # 糖尿病控制评估
        result["assessments"]["diabetes"] = self.assess_diabetes_control(profile)
        
        # 综合风险等级
        result["overall_risk"] = self._calculate_overall_risk(
            result["assessments"]["hypertension"],
            result["assessments"]["diabetes"]
        )
        
        logger.info(f"[综合评估] 患者 {patient_id} 综合风险: {result['overall_risk']}")
        return result
    
    def _calculate_overall_risk(self, hp_assessment: Dict, dm_assessment: Dict) -> str:
        """计算综合风险等级"""
        hp_risk = hp_assessment.get("risk_level", "")
        dm_control = dm_assessment.get("control_status", "")
        
        # 高血压很高危或糖尿病控制不佳
        if hp_risk == "很高危" or dm_control == "不佳":
            return "很高危"
        
        # 高血压高危或糖尿病控制一般
        if hp_risk == "高危" or dm_control == "一般":
            return "高危"
        
        # 高血压中危
        if hp_risk == "中危":
            return "中危"
        
        return "低危"


# 全局风险评估引擎实例
_risk_engine: Optional[RiskEngine] = None


def get_risk_engine() -> RiskEngine:
    """获取全局风险评估引擎实例"""
    global _risk_engine
    if _risk_engine is None:
        _risk_engine = RiskEngine()
    return _risk_engine

