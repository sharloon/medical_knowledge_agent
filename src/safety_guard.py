# -*- coding: utf-8 -*-
"""
安全预警模块 - 伦理安全控制与高风险预警
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from src.term_mapper import DRUG_CONTRAINDICATIONS

logger = logging.getLogger(__name__)


class WarningSeverity(Enum):
    """预警严重程度"""
    INFO = "info"           # 提示
    WARNING = "warning"     # 警告
    CRITICAL = "critical"   # 严重
    EMERGENCY = "emergency" # 紧急


@dataclass
class SafetyWarning:
    """安全预警"""
    type: str               # 预警类型
    severity: WarningSeverity
    message: str            # 预警消息
    recommendation: str     # 建议措施
    evidence: str           # 证据来源
    requires_action: bool   # 是否需要立即处理


class SafetyGuard:
    """安全预警守卫"""
    
    def __init__(self):
        # 高风险药物类别
        self.high_risk_drugs = {
            "ACEI": ["依那普利", "贝那普利", "雷米普利", "培哚普利", "卡托普利"],
            "ARB": ["缬沙坦", "氯沙坦", "厄贝沙坦", "坎地沙坦", "替米沙坦"],
        }
        
        # 孕妇禁用药物
        self.pregnancy_contraindicated = ["ACEI", "ARB", "他汀类", "华法林"]
    
    def check(self, profile: Dict, recommendations: List[Dict] = None) -> List[SafetyWarning]:
        """
        全面安全检查
        
        Args:
            profile: 患者画像
            recommendations: 推荐的治疗方案
            
        Returns:
            预警列表
        """
        warnings = []
        
        # 1. 检查高血压急症
        emergency_warning = self.check_hypertension_emergency(profile)
        if emergency_warning:
            warnings.append(emergency_warning)
        
        # 2. 检查孕妇用药禁忌
        pregnancy_warnings = self.check_pregnancy_contraindications(profile, recommendations)
        warnings.extend(pregnancy_warnings)
        
        # 3. 检查药物冲突
        drug_warnings = self.check_drug_interactions(profile)
        warnings.extend(drug_warnings)
        
        # 4. 检查极端指标值
        extreme_warnings = self.check_extreme_values(profile)
        warnings.extend(extreme_warnings)
        
        # 按严重程度排序
        severity_order = {
            WarningSeverity.EMERGENCY: 0,
            WarningSeverity.CRITICAL: 1,
            WarningSeverity.WARNING: 2,
            WarningSeverity.INFO: 3
        }
        warnings.sort(key=lambda w: severity_order.get(w.severity, 4))
        
        logger.info(f"[安全检查] 发现 {len(warnings)} 个预警")
        return warnings
    
    def check_hypertension_emergency(self, profile: Dict) -> Optional[SafetyWarning]:
        """
        检查高血压急症
        
        高血压急症定义：SBP > 180 mmHg 和/或 DBP > 120 mmHg，伴有靶器官急性损害
        """
        ha = profile.get("hypertension_assessment")
        if not ha:
            return None
        
        sbp = float(ha.get("sbp", 0))
        dbp = float(ha.get("dbp", 0))
        
        # 高血压急症判断
        if sbp > 180 or dbp > 120:
            # 检查是否有急性症状
            symptoms = []
            clinical_conditions = ha.get("clinical_conditions", "")
            
            emergency_symptoms = ["头痛", "呕吐", "视物模糊", "胸痛", "呼吸困难", "意识障碍"]
            
            for symptom in emergency_symptoms:
                if symptom in clinical_conditions:
                    symptoms.append(symptom)
            
            if sbp >= 180 or dbp >= 120:
                severity = WarningSeverity.EMERGENCY if symptoms else WarningSeverity.CRITICAL
                
                message = f"⚠️ 高血压急症预警：血压 {sbp}/{dbp} mmHg"
                if symptoms:
                    message += f"，伴有症状：{', '.join(symptoms)}"
                
                return SafetyWarning(
                    type="高血压急症",
                    severity=severity,
                    message=message,
                    recommendation="""紧急处理建议：
1. 【立即转诊】建议紧急转诊至急诊科
2. 【静脉降压】启动静脉降压治疗
3. 【降压目标】1小时内降低不超过25%
4. 【监测】持续心电监护、血压监测
5. 【评估】排除继发性高血压、靶器官损害""",
                    evidence="中国高血压防治指南2023 (证据等级ⅠA)",
                    requires_action=True
                )
        
        return None
    
    def check_pregnancy_contraindications(self, profile: Dict, 
                                          recommendations: List[Dict] = None) -> List[SafetyWarning]:
        """
        检查孕妇用药禁忌
        
        妊娠期高血压禁用：ACEI、ARB类药物
        推荐：甲基多巴、拉贝洛尔、硝苯地平
        """
        warnings = []
        
        basic_info = profile.get("basic_info", {})
        
        # 判断是否为孕妇
        is_pregnant = False
        gender = basic_info.get("gender", "")
        age = basic_info.get("age", 0)
        
        # 检查诊断记录中是否有妊娠相关
        diagnoses = profile.get("diagnoses", [])
        for diag in diagnoses:
            diag_name = diag.get("diagnosis_name", "")
            if "妊娠" in diag_name or "孕" in diag_name:
                is_pregnant = True
                break
        
        # 检查病历中是否提及妊娠
        medical_records = profile.get("medical_records", [])
        for record in medical_records:
            for field in ["chief_complaint", "present_illness", "past_history"]:
                content = record.get(field, "") or ""
                if "妊娠" in content or "孕妇" in content or "怀孕" in content:
                    is_pregnant = True
                    break
        
        if not is_pregnant:
            return warnings
        
        logger.info("[安全检查] 检测到妊娠期患者")
        
        # 检查当前用药
        medications = profile.get("medications", [])
        contraindicated_meds = []
        
        for med in medications:
            drug_name = med.get("drug_name", "")
            drug_class = med.get("drug_class", "")
            
            # 检查 ACEI 类
            if drug_class == "ACEI" or any(d in drug_name for d in self.high_risk_drugs.get("ACEI", [])):
                contraindicated_meds.append({"name": drug_name, "class": "ACEI"})
            
            # 检查 ARB 类
            if drug_class == "ARB" or any(d in drug_name for d in self.high_risk_drugs.get("ARB", [])):
                contraindicated_meds.append({"name": drug_name, "class": "ARB"})
        
        if contraindicated_meds:
            med_names = [m["name"] for m in contraindicated_meds]
            warnings.append(SafetyWarning(
                type="妊娠期用药禁忌",
                severity=WarningSeverity.CRITICAL,
                message=f"⚠️ 严重警告：妊娠期患者正在使用禁忌药物：{', '.join(med_names)}",
                recommendation=f"""紧急处理建议：
1. 【立即停药】停用 ACEI/ARB 类药物
2. 【替代方案】推荐使用：
   - 甲基多巴（首选，证据等级ⅠB）
   - 拉贝洛尔（证据等级ⅠB）
   - 硝苯地平缓释片（证据等级ⅠC）
3. 【会诊】建议产科会诊，评估胎儿状况
4. 【监测】密切监测血压和胎儿情况""",
                evidence="中国高血压防治指南2023 - 妊娠期高血压章节 (证据等级ⅠA)",
                requires_action=True
            ))
        
        # 检查推荐方案中是否包含禁忌药物
        if recommendations:
            for rec in recommendations:
                drugs = rec.get("drugs", [])
                for drug in drugs:
                    if any(d in drug for d in ["ACEI", "ARB", "普利", "沙坦"]):
                        warnings.append(SafetyWarning(
                            type="推荐方案禁忌",
                            severity=WarningSeverity.CRITICAL,
                            message=f"⚠️ 警告：推荐方案中包含妊娠期禁忌药物：{drug}",
                            recommendation="妊娠期应避免使用 ACEI/ARB 类药物，建议使用甲基多巴或拉贝洛尔",
                            evidence="中国高血压防治指南2023",
                            requires_action=True
                        ))
        
        return warnings
    
    def check_drug_interactions(self, profile: Dict) -> List[SafetyWarning]:
        """检查药物相互作用"""
        warnings = []
        
        medications = profile.get("medications", [])
        if len(medications) < 2:
            return warnings
        
        drug_names = [med.get("drug_name", "") for med in medications]
        drug_classes = [med.get("drug_class", "") for med in medications]
        
        # 常见药物相互作用检查
        interactions = [
            {
                "drugs": ["ACEI", "ARB"],
                "risk": "双重RAS阻断增加高钾血症和肾功能损害风险",
                "severity": WarningSeverity.WARNING
            },
            {
                "drugs": ["ACEI", "保钾利尿剂"],
                "risk": "增加高钾血症风险",
                "severity": WarningSeverity.WARNING
            },
            {
                "drugs": ["β受体阻滞剂", "维拉帕米"],
                "risk": "可能导致严重心动过缓或传导阻滞",
                "severity": WarningSeverity.CRITICAL
            },
            {
                "drugs": ["二甲双胍", "造影剂"],
                "risk": "增加乳酸酸中毒风险，造影前后需停药",
                "severity": WarningSeverity.WARNING
            }
        ]
        
        for interaction in interactions:
            drugs_found = []
            for drug in interaction["drugs"]:
                if drug in drug_classes or any(drug in name for name in drug_names):
                    drugs_found.append(drug)
            
            if len(drugs_found) >= 2:
                warnings.append(SafetyWarning(
                    type="药物相互作用",
                    severity=interaction["severity"],
                    message=f"⚠️ 药物相互作用警告：{' + '.join(drugs_found)}",
                    recommendation=f"风险说明：{interaction['risk']}，建议评估是否需要调整用药方案",
                    evidence="药物相互作用数据库",
                    requires_action=interaction["severity"] == WarningSeverity.CRITICAL
                ))
        
        return warnings
    
    def check_extreme_values(self, profile: Dict) -> List[SafetyWarning]:
        """检查极端指标值"""
        warnings = []
        
        # 检查血糖
        da = profile.get("diabetes_assessment")
        if da:
            fg = da.get("fasting_glucose")
            if fg and float(fg) < 3.9:
                warnings.append(SafetyWarning(
                    type="低血糖",
                    severity=WarningSeverity.CRITICAL,
                    message=f"⚠️ 低血糖警告：空腹血糖 {fg} mmol/L",
                    recommendation="立即补充葡萄糖，评估降糖药物剂量是否过量",
                    evidence="中国2型糖尿病防治指南2020",
                    requires_action=True
                ))
            elif fg and float(fg) > 16.7:
                warnings.append(SafetyWarning(
                    type="严重高血糖",
                    severity=WarningSeverity.CRITICAL,
                    message=f"⚠️ 严重高血糖警告：空腹血糖 {fg} mmol/L",
                    recommendation="警惕糖尿病酮症酸中毒，建议急诊评估",
                    evidence="中国2型糖尿病防治指南2020",
                    requires_action=True
                ))
            
            hba1c = da.get("hba1c")
            if hba1c and float(hba1c) >= 10:
                warnings.append(SafetyWarning(
                    type="血糖控制极差",
                    severity=WarningSeverity.WARNING,
                    message=f"⚠️ HbA1c {hba1c}%，血糖控制极差",
                    recommendation="需要强化治疗，考虑起始或强化胰岛素治疗",
                    evidence="中国2型糖尿病防治指南2020",
                    requires_action=True
                ))
        
        return warnings
    
    def format_warnings(self, warnings: List[SafetyWarning]) -> str:
        """格式化预警信息为文本"""
        if not warnings:
            return "✅ 未发现安全风险预警"
        
        lines = ["=" * 50, "⚠️ 安全预警报告", "=" * 50]
        
        for i, warning in enumerate(warnings, 1):
            severity_icon = {
                WarningSeverity.EMERGENCY: "🚨",
                WarningSeverity.CRITICAL: "❗",
                WarningSeverity.WARNING: "⚠️",
                WarningSeverity.INFO: "ℹ️"
            }.get(warning.severity, "•")
            
            lines.append(f"\n{severity_icon} 预警 {i}: {warning.type}")
            lines.append(f"严重程度: {warning.severity.value}")
            lines.append(f"详情: {warning.message}")
            lines.append(f"\n建议措施:\n{warning.recommendation}")
            lines.append(f"\n证据来源: {warning.evidence}")
            if warning.requires_action:
                lines.append("⚡ 需要立即处理")
            lines.append("-" * 40)
        
        return "\n".join(lines)


# 全局安全预警实例
_safety_guard: Optional[SafetyGuard] = None


def get_safety_guard() -> SafetyGuard:
    """获取全局安全预警实例"""
    global _safety_guard
    if _safety_guard is None:
        _safety_guard = SafetyGuard()
    return _safety_guard

