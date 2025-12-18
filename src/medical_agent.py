# -*- coding: utf-8 -*-
"""
医疗智能体核心模块 - 整合所有功能的决策支持服务
"""
import logging
import json
from typing import Dict, List, Optional, Generator
from datetime import datetime

from src.llm_client import get_llm_client, MEDICAL_SYSTEM_PROMPT
from src.db_client import (
    get_db_client, 
    check_db_connection, 
    DatabaseConnectionError,
    set_db_failure_simulation,
    is_db_failure_simulation_enabled
)
from src.rag_service import get_rag_service
from src.risk_engine import get_risk_engine
from src.safety_guard import get_safety_guard, SafetyWarning
from src.term_mapper import get_term_mapper
from src.data_ingest import ExcelProcessor, get_pdf_toc_and_tables
from src.config import EXCEL_FILE

logger = logging.getLogger(__name__)


class MedicalAgent:
    """医疗智能体 - 集成所有决策支持功能"""
    
    def __init__(self):
        self.llm = get_llm_client()
        self.db = get_db_client()
        self.rag = get_rag_service()
        self.risk_engine = get_risk_engine()
        self.safety_guard = get_safety_guard()
        self.term_mapper = get_term_mapper()
        self.conversation_history: List[Dict] = []
    
    def chat(self, message: str, patient_id: str = None) -> Dict:
        """
        智能对话入口
        
        Args:
            message: 用户消息
            patient_id: 患者ID（可选）
            
        Returns:
            {"answer": str, "sources": list, "warnings": list, ...}
        """
        logger.info(f"[智能体] 收到消息: {message[:50]}...")
        
        # 术语标准化
        normalized_message = self.term_mapper.expand_query(message)
        
        # 获取患者上下文 - 带数据库异常处理
        patient_context = None
        db_available = True
        if patient_id:
            try:
                db_status = check_db_connection()
                if db_status["connected"]:
                    patient_context = self.db.get_full_patient_profile(patient_id)
                    if patient_context.get("db_unavailable"):
                        db_available = False
                        patient_context = None
                else:
                    db_available = False
                    logger.warning(f"[智能体] 数据库不可用，跳过患者上下文获取")
            except DatabaseConnectionError as e:
                db_available = False
                logger.warning(f"[智能体] 获取患者上下文失败: {str(e)}")
        
        # 意图识别与路由
        intent = self._classify_intent(message)
        logger.info(f"[智能体] 识别意图: {intent}")
        
        # 根据意图路由到不同处理器
        if intent == "patient_query":
            return self._handle_patient_query(message, patient_id)
        elif intent == "diagnosis":
            return self._handle_diagnosis_query(message, patient_context)
        elif intent == "treatment":
            return self._handle_treatment_query(message, patient_context)
        elif intent == "emergency":
            return self._handle_emergency_query(message, patient_context)
        elif intent == "guideline":
            return self._handle_guideline_query(message)
        elif intent == "soap_inquiry":
            return self._handle_soap_inquiry(message, patient_context)
        else:
            # 默认 RAG 问答
            return self._handle_general_query(message, patient_context)
    
    def _classify_intent(self, message: str) -> str:
        """简单的意图分类"""
        message_lower = message.lower()
        
        # 首先检查是否超出范围（优先判断）
        out_of_scope_keywords = [
            "骨折", "骨科", "眼科", "皮肤", "癌症", "肿瘤", "手术", "外科",
            "妇科", "产科", "儿科", "耳鼻喉", "口腔", "精神", "心理"
        ]
        # 如果包含超出范围关键词，且不包含支持的关键词，直接返回 general 让 RAG 处理
        has_out_of_scope = any(kw in message_lower for kw in out_of_scope_keywords)
        supported_keywords = ["高血压", "糖尿病", "血压", "血糖"]
        has_supported = any(kw in message_lower for kw in supported_keywords)
        
        if has_out_of_scope and not has_supported:
            # 超出范围的问题，返回 general 让 RAG 的 _is_out_of_scope 处理
            return "general"
        
        # 紧急情况
        emergency_keywords = ["急症", "急诊", "紧急", "180", "190", "200", "昏迷", "休克"]
        if any(kw in message for kw in emergency_keywords):
            return "emergency"
        
        # 患者查询
        if "患者" in message and ("画像" in message or "信息" in message or "ID" in message.upper()):
            return "patient_query"
        
        # 诊断相关
        diagnosis_keywords = ["诊断", "鉴别", "是什么病", "什么症状", "症状"]
        if any(kw in message for kw in diagnosis_keywords):
            return "diagnosis"
        
        # 治疗相关
        treatment_keywords = ["治疗", "方案", "用药", "药物", "处方", "怎么治"]
        if any(kw in message for kw in treatment_keywords):
            return "treatment"
        
        # 指南查询
        guideline_keywords = ["指南", "推荐", "证据", "等级"]
        if any(kw in message for kw in guideline_keywords):
            return "guideline"
        
        # SOAP 问诊
        soap_keywords = ["头晕", "头痛", "不舒服", "难受"]
        if any(kw in message for kw in soap_keywords) and len(message) < 50:
            return "soap_inquiry"
        
        return "general"
    
    def _handle_patient_query(self, message: str, patient_id: str = None) -> Dict:
        """处理患者信息查询"""
        if not patient_id:
            # 尝试从消息中提取患者ID
            import re
            id_match = re.search(r'(?:患者|ID|id)[=:：]?\s*(\S+)', message)
            if id_match:
                patient_id = id_match.group(1)
        
        if not patient_id:
            return {
                "answer": "请提供患者ID以查询患者信息。例如：查询患者ID=1002_0_20210504的信息",
                "sources": [],
                "success": True
            }
        
        # 检查数据库连接状态
        db_status = check_db_connection()
        if not db_status["connected"]:
            return self._handle_db_unavailable(patient_id, db_status)
        
        # 获取完整患者画像
        try:
            profile = self.db.get_full_patient_profile(patient_id)
        except DatabaseConnectionError as e:
            return self._handle_db_unavailable(patient_id, {
                "connected": False,
                "message": str(e),
                "simulated_failure": True
            })
        
        # 检查是否数据库不可用
        if profile.get("db_unavailable"):
            return self._handle_db_unavailable(patient_id, {
                "connected": False,
                "message": profile.get("error", "数据库连接失败"),
                "simulated_failure": True
            })
        
        if not profile.get("basic_info"):
            return {
                "answer": f"未找到患者ID为 {patient_id} 的信息，请确认患者ID是否正确。",
                "sources": [],
                "success": True
            }
        
        # 进行风险评估
        assessment = self.risk_engine.comprehensive_assessment(patient_id)
        
        # 安全检查
        warnings = self.safety_guard.check(profile)
        
        # 生成患者画像报告
        report = self._generate_patient_report(profile, assessment, warnings)
        
        return {
            "answer": report,
            "profile": profile,
            "assessment": assessment,
            "warnings": [self._warning_to_dict(w) for w in warnings],
            "sources": [{"type": "mysql", "tables": profile["source"]["tables"]}],
            "success": True
        }
    
    def _handle_db_unavailable(self, patient_id: str, db_status: Dict) -> Dict:
        """
        处理数据库不可用的情况 - 优雅降级
        
        Args:
            patient_id: 患者ID
            db_status: 数据库状态信息
            
        Returns:
            包含友好提示的响应字典
        """
        logger.warning(f"[优雅降级] 数据库不可用，无法查询患者 {patient_id} 的信息")
        
        # 构建友好的降级提示
        degraded_response = f"""## ⚠️ 数据库服务暂时不可用

**错误信息**: {db_status.get('message', '未知错误')}

### 📋 系统状态
- **患者ID**: {patient_id}
- **数据库状态**: 🔴 不可用
- **降级模式**: 已启用

### 💡 当前可用功能

虽然无法访问患者数据库，但您仍可以使用以下功能：

1. **📚 医学知识查询**
   - 查询高血压/糖尿病诊疗指南
   - 获取药物使用建议
   - 了解疾病症状和诊断标准

2. **📊 Excel数据分析**
   - 查询糖尿病患者统计数据
   - 分析胰岛素使用率

3. **🤖 智能问答**
   - 进行 SOAP 格式问诊
   - 获取一般医学建议

### 🔧 建议操作

- 请稍后重试查询患者信息
- 如问题持续，请联系系统管理员
- 可以先使用知识库查询功能

---
*提示：输入 "高血压治疗指南" 或 "糖尿病用药建议" 等问题，我可以为您提供相关医学知识。*
"""
        
        return {
            "answer": degraded_response,
            "sources": [],
            "success": True,
            "db_unavailable": True,
            "degraded_mode": True,
            "error": db_status.get('message')
        }
    
    def _generate_patient_report(self, profile: Dict, assessment: Dict, 
                                 warnings: List[SafetyWarning]) -> str:
        """生成患者画像报告"""
        basic = profile.get("basic_info", {})
        ha = profile.get("hypertension_assessment")
        da = profile.get("diabetes_assessment")
        meds = profile.get("medications", [])
        
        report_parts = []
        
        # 基本信息
        report_parts.append("## 📋 患者画像报告\n")
        report_parts.append(f"**患者ID**: {profile['patient_id']}")
        report_parts.append(f"**姓名**: {basic.get('name', '未知')}")
        report_parts.append(f"**性别**: {basic.get('gender', '未知')}")
        report_parts.append(f"**年龄**: {basic.get('age', '未知')}岁")
        
        if basic.get('bmi'):
            report_parts.append(f"**BMI**: {basic.get('bmi')}")
        
        # 血压评估
        if ha:
            report_parts.append("\n### 🩺 高血压评估")
            report_parts.append(f"**血压**: {ha.get('sbp', '-')}/{ha.get('dbp', '-')} mmHg")
            hp_assess = assessment.get("assessments", {}).get("hypertension", {})
            if hp_assess.get("bp_classification"):
                report_parts.append(f"**血压分级**: {hp_assess['bp_classification'].get('name', '-')}")
            report_parts.append(f"**风险等级**: {hp_assess.get('risk_level', '未评估')}")
            
            if hp_assess.get("risk_factors"):
                report_parts.append(f"**危险因素**: {', '.join(hp_assess['risk_factors'])}")
        
        # 糖尿病评估
        if da:
            report_parts.append("\n### 🍬 糖尿病评估")
            report_parts.append(f"**HbA1c**: {da.get('hba1c', '-')}%")
            report_parts.append(f"**空腹血糖**: {da.get('fasting_glucose', '-')} mmol/L")
            dm_assess = assessment.get("assessments", {}).get("diabetes", {})
            report_parts.append(f"**控制状态**: {dm_assess.get('control_status', '未评估')}")
        
        # 当前用药
        if meds:
            report_parts.append("\n### 💊 当前用药")
            for med in meds[:5]:
                report_parts.append(f"- {med.get('drug_name', '')} {med.get('dosage', '')} {med.get('frequency', '')}")
        
        # 安全预警
        if warnings:
            report_parts.append("\n### ⚠️ 安全预警")
            for warning in warnings:
                report_parts.append(f"- **{warning.type}**: {warning.message}")
        
        # 随访计划
        hp_assess = assessment.get("assessments", {}).get("hypertension", {})
        if hp_assess.get("follow_up_plan"):
            plan = hp_assess["follow_up_plan"]
            report_parts.append("\n### 📅 随访计划")
            report_parts.append(f"**随访频率**: {plan.get('frequency', '-')}")
            report_parts.append(f"**下次随访**: {plan.get('next_visit', '-')}")
            report_parts.append(f"**监测项目**: {', '.join(plan.get('monitoring', []))}")
        
        # 治疗建议
        if hp_assess.get("recommendations"):
            report_parts.append("\n### 💡 治疗建议")
            for rec in hp_assess["recommendations"]:
                report_parts.append(f"\n**{rec.get('type', '')}** ({rec.get('evidence_level', '')})")
                report_parts.append(f"{rec.get('content', '')}")
                if rec.get("drugs"):
                    report_parts.append(f"推荐药物: {', '.join(rec['drugs'])}")
                report_parts.append(f"*来源: {rec.get('source', '')}*")
        
        # 数据来源
        report_parts.append("\n---")
        report_parts.append("*数据来源: MySQL数据库 (patient_info, hypertension_risk_assessment, diabetes_control_assessment, medication_records)*")
        
        return "\n".join(report_parts)
    
    def _handle_diagnosis_query(self, message: str, patient_context: Dict = None) -> Dict:
        """处理诊断相关查询"""
        # 使用 RAG 检索相关信息
        rag_result = self.rag.rag_answer(message, patient_context)
        
        if not rag_result.get("has_knowledge"):
            return rag_result
        
        # 构建诊断推理提示
        prompt = f"""基于患者信息和医学知识，进行鉴别诊断分析。

要求：
1. 列出至少3个可能的诊断，按概率排序
2. 说明诊断依据和推理过程
3. 标注证据等级
4. 提出需要进一步检查的项目

患者信息/症状描述：{message}

参考资料已在上下文中提供。

请给出结构化的鉴别诊断分析："""
        
        result = self.llm.generate(
            prompt=prompt,
            history=self.conversation_history[-4:],
            system_prompt=MEDICAL_SYSTEM_PROMPT
        )
        
        if result["success"]:
            self.conversation_history.append({"role": "user", "content": message})
            self.conversation_history.append({"role": "assistant", "content": result["content"]})
        
        return {
            "answer": result["content"] if result["success"] else result["error"],
            "sources": rag_result.get("sources", []),
            "success": result["success"]
        }
    
    def _handle_treatment_query(self, message: str, patient_context: Dict = None) -> Dict:
        """处理治疗方案查询"""
        # 使用 RAG 获取指南推荐
        rag_result = self.rag.rag_answer(message, patient_context)
        
        # 如果有患者上下文，进行安全检查
        warnings = []
        if patient_context:
            warnings = self.safety_guard.check(patient_context)
        
        # 构建治疗方案生成提示
        prompt = f"""基于医学指南和患者情况，生成个性化治疗方案。

要求：
1. 给出具体的药物选择和剂量
2. 说明选择依据
3. 标注证据等级（如ⅠA、ⅠB、ⅡA等）
4. 列出需要注意的禁忌和不良反应
5. 给出随访监测建议

查询：{message}

请生成结构化的治疗方案："""
        
        result = self.llm.generate(
            prompt=prompt,
            history=self.conversation_history[-4:],
            system_prompt=MEDICAL_SYSTEM_PROMPT
        )
        
        response = result["content"] if result["success"] else result["error"]
        
        # 添加安全预警
        if warnings:
            warning_text = self.safety_guard.format_warnings(warnings)
            response = warning_text + "\n\n" + response
        
        return {
            "answer": response,
            "sources": rag_result.get("sources", []),
            "warnings": [self._warning_to_dict(w) for w in warnings],
            "success": result["success"]
        }
    
    def _handle_emergency_query(self, message: str, patient_context: Dict = None) -> Dict:
        """处理紧急情况查询"""
        # 首先检查是否是高血压急症
        emergency_response = """## 🚨 高血压急症处理指南

### 识别标准
- 收缩压 > 180 mmHg 和/或 舒张压 > 120 mmHg
- 伴有靶器官急性损害表现

### 紧急处理步骤

1. **立即评估**
   - 确认血压读数
   - 评估靶器官损害（头痛、视力改变、胸痛、呼吸困难）
   - 完善必要检查（心电图、肾功能、CT/MRI）

2. **降压治疗** (证据等级 ⅠA)
   - 启动静脉降压治疗
   - 首选药物：乌拉地尔、硝普钠、尼卡地平
   - 目标：1小时内降低不超过25%

3. **转诊建议**
   - 建议紧急转诊至急诊科/ICU
   - 持续心电监护
   - 专科会诊

### 特殊情况处理

- **高血压脑病**：降压同时预防脑水肿
- **主动脉夹层**：快速降压，目标SBP 100-120 mmHg
- **急性冠脉综合征**：联合抗缺血治疗

---
*来源: 中国高血压防治指南2023 (证据等级ⅠA)*
"""
        
        # 使用 RAG 补充信息
        rag_result = self.rag.rag_answer(message, patient_context)
        
        if rag_result.get("has_knowledge") and rag_result.get("answer"):
            emergency_response += f"\n\n### 📚 相关指南信息\n{rag_result['answer']}"
        
        return {
            "answer": emergency_response,
            "sources": rag_result.get("sources", []) + [{"type": "指南", "name": "中国高血压防治指南2023"}],
            "is_emergency": True,
            "success": True
        }
    
    def _handle_guideline_query(self, message: str) -> Dict:
        """处理指南查询"""
        # 检查是否有日期过滤
        import re
        date_match = re.search(r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})', message)
        
        filters = {}
        if date_match:
            date_str = date_match.group(1)
            # 标准化日期格式
            date_str = date_str.replace('年', '-').replace('月', '-').replace('/', '-')
            filters["update_date_after"] = date_str
        
        # 使用 RAG 检索
        search_results = self.rag.search(message, filters)
        
        if not search_results["hits"]:
            return {
                "answer": "未找到符合条件的指南推荐。",
                "sources": [],
                "success": True
            }
        
        # 格式化结果
        response_parts = ["## 📖 指南推荐查询结果\n"]
        
        for i, hit in enumerate(search_results["hits"][:5], 1):
            response_parts.append(f"### {i}. 结果")
            response_parts.append(hit["content"])
            source = hit.get("source", {})
            response_parts.append(f"\n*来源: {source.get('type', 'unknown')} - {source.get('table', source.get('file', ''))}*")
            response_parts.append("")
        
        return {
            "answer": "\n".join(response_parts),
            "sources": [hit["source"] for hit in search_results["hits"][:5]],
            "total_hits": search_results["total_hits"],
            "success": True
        }
    
    def _handle_soap_inquiry(self, message: str, patient_context: Dict = None) -> Dict:
        """处理 SOAP 格式问诊"""
        soap_prompt = f"""你是一位经验丰富的内科医生，正在对患者进行问诊。患者主诉："{message}"

请按照 SOAP 格式进行结构化问诊：

**S (Subjective 主观资料)**
请询问患者以下信息（列出需要追问的问题）：
- 症状的具体表现
- 起病时间和持续时间
- 诱发和缓解因素
- 伴随症状
- 既往病史

**O (Objective 客观资料)**
建议检查的项目：
- 体格检查
- 实验室检查
- 影像学检查

**A (Assessment 评估)**
根据现有信息的初步判断和鉴别诊断思路

**P (Plan 计划)**
下一步诊疗计划

请以问诊对话的形式，首先向患者追问关键信息："""
        
        result = self.llm.generate(
            prompt=soap_prompt,
            system_prompt="你是一位专业的内科医生，擅长高血压和糖尿病的诊疗。请使用专业但易懂的语言与患者交流。"
        )
        
        if result["success"]:
            self.conversation_history.append({"role": "user", "content": message})
            self.conversation_history.append({"role": "assistant", "content": result["content"]})
        
        return {
            "answer": result["content"] if result["success"] else result["error"],
            "sources": [],
            "inquiry_type": "SOAP",
            "success": result["success"]
        }
    
    def _handle_general_query(self, message: str, patient_context: Dict = None) -> Dict:
        """处理一般查询"""
        result = self.rag.rag_answer(message, patient_context, self.conversation_history[-4:])
        
        # 如果是超出范围或无知识库，直接返回，不调用 LLM
        if not result.get("has_knowledge") or result.get("is_out_of_scope"):
            return result
        
        # 如果有知识库，更新对话历史
        if result.get("success") and result.get("has_knowledge"):
            self.conversation_history.append({"role": "user", "content": message})
            self.conversation_history.append({"role": "assistant", "content": result.get("answer", "")})
        
        return result
    
    def _warning_to_dict(self, warning: SafetyWarning) -> Dict:
        """将 SafetyWarning 转换为字典"""
        return {
            "type": warning.type,
            "severity": warning.severity.value,
            "message": warning.message,
            "recommendation": warning.recommendation,
            "evidence": warning.evidence,
            "requires_action": warning.requires_action
        }
    
    def get_insulin_usage_analysis(self) -> Dict:
        """获取胰岛素使用率分析"""
        processor = ExcelProcessor(EXCEL_FILE)
        return processor.analyze_insulin_usage()
    
    def get_pdf_structure(self) -> Dict:
        """获取 PDF 目录结构和表格"""
        return get_pdf_toc_and_tables()
    
    def get_term_mapping_table(self) -> Dict:
        """获取术语映射表"""
        return self.term_mapper.get_mapping_table()
    
    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []
        logger.info("[智能体] 对话历史已清空")
    
    def check_database_status(self) -> Dict:
        """
        检查数据库连接状态
        
        Returns:
            {"connected": bool, "message": str, "simulated_failure": bool}
        """
        return check_db_connection()
    
    def set_database_failure_simulation(self, enabled: bool) -> Dict:
        """
        设置数据库故障模拟开关
        
        Args:
            enabled: True 启用模拟故障，False 禁用模拟故障
            
        Returns:
            {"success": bool, "message": str, "simulation_enabled": bool}
        """
        try:
            set_db_failure_simulation(enabled)
            status = "启用" if enabled else "禁用"
            return {
                "success": True,
                "message": f"数据库故障模拟已{status}",
                "simulation_enabled": enabled
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"设置失败: {str(e)}",
                "simulation_enabled": is_db_failure_simulation_enabled()
            }
    
    def is_database_simulation_enabled(self) -> bool:
        """检查数据库故障模拟是否启用"""
        return is_db_failure_simulation_enabled()


# 全局医疗智能体实例
_medical_agent: Optional[MedicalAgent] = None


def get_medical_agent() -> MedicalAgent:
    """获取全局医疗智能体实例"""
    global _medical_agent
    if _medical_agent is None:
        _medical_agent = MedicalAgent()
    return _medical_agent

