# -*- coding: utf-8 -*-
"""
RAG 服务模块 - 跨源检索与答案生成
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime

from src.vector_store import get_vector_store
from src.db_client import get_db_client
from src.term_mapper import get_term_mapper
from src.llm_client import get_llm_client, MEDICAL_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class RAGService:
    """RAG 检索服务"""
    
    def __init__(self):
        self.vector_store = get_vector_store()
        self.db_client = get_db_client()
        self.term_mapper = get_term_mapper()
        self.llm_client = get_llm_client()
    
    def search(self, query: str, filters: Dict = None) -> Dict:
        """
        跨源统一检索
        
        Args:
            query: 查询语句
            filters: 过滤条件 {"source_types": [], "update_date_after": str}
            
        Returns:
            {"hits": list, "sources": list, "normalized_query": str}
        """
        filters = filters or {}
        
        # 术语标准化
        normalized_query = self.term_mapper.expand_query(query)
        logger.info(f"[RAG检索] 原始查询: {query}, 标准化后: {normalized_query}")
        
        all_hits = []
        sources_used = []
        
        # 1. 向量检索 (PDF/Excel)
        try:
            vector_results = self.vector_store.search(normalized_query, top_k=5)
            for result in vector_results:
                result["retrieval_type"] = "vector"
            all_hits.extend(vector_results)
            sources_used.append("pdf_excel_index")
            logger.info(f"[RAG检索] 向量检索返回 {len(vector_results)} 条结果")
        except Exception as e:
            logger.error(f"[RAG检索] 向量检索失败: {str(e)}")
        
        # 2. 数据库检索 (MySQL)
        try:
            db_results = self.db_client.search_by_keyword(normalized_query)
            for result in db_results:
                all_hits.append({
                    "content": self._format_db_result(result),
                    "score": 0.8,  # 数据库匹配默认得分
                    "source": {
                        "type": "mysql",
                        "table": result.get("source_table", "unknown")
                    },
                    "retrieval_type": "database",
                    "raw_data": result
                })
            sources_used.append("mysql")
            logger.info(f"[RAG检索] 数据库检索返回 {len(db_results)} 条结果")
        except Exception as e:
            logger.error(f"[RAG检索] 数据库检索失败: {str(e)}")
        
        # 3. 指南推荐过滤
        if filters.get("update_date_after"):
            try:
                guidelines = self.db_client.get_guideline_recommendations(
                    update_date_after=filters["update_date_after"]
                )
                for g in guidelines:
                    all_hits.append({
                        "content": self._format_guideline(g),
                        "score": 0.9,
                        "source": {
                            "type": "mysql",
                            "table": "guideline_recommendations",
                            "update_date": str(g.get("update_date", ""))
                        },
                        "retrieval_type": "database",
                        "raw_data": g
                    })
                logger.info(f"[RAG检索] 指南过滤返回 {len(guidelines)} 条结果")
            except Exception as e:
                logger.error(f"[RAG检索] 指南过滤失败: {str(e)}")
        
        # 按得分排序
        all_hits.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return {
            "hits": all_hits[:10],  # 返回前10条
            "sources": sources_used,
            "normalized_query": normalized_query,
            "original_query": query,
            "total_hits": len(all_hits)
        }
    
    def _format_db_result(self, result: Dict) -> str:
        """格式化数据库查询结果为文本"""
        lines = []
        for key, value in result.items():
            if value is not None and key != "source_table":
                lines.append(f"{key}: {value}")
        return "\n".join(lines)
    
    def _format_guideline(self, guideline: Dict) -> str:
        """格式化指南推荐为文本"""
        return f"""
指南名称: {guideline.get('guideline_name', '')}
疾病类型: {guideline.get('disease_type', '')}
适用条件: {guideline.get('patient_condition', '')}
推荐等级: {guideline.get('recommendation_level', '')}
推荐内容: {guideline.get('recommendation_content', '')}
证据来源: {guideline.get('evidence_source', '')}
更新日期: {guideline.get('update_date', '')}
        """.strip()
    
    def rag_answer(self, query: str, patient_context: Dict = None, 
                   history: List[Dict] = None) -> Dict:
        """
        RAG 问答
        
        Args:
            query: 用户问题
            patient_context: 患者上下文信息
            history: 对话历史
            
        Returns:
            {"answer": str, "sources": list, "success": bool}
        """
        # 1. 首先检查是否超出知识库范围
        if self._is_out_of_scope(query):
            logger.info(f"[RAG问答] 检测到超出范围的问题: {query}")
            return {
                "answer": self._get_no_knowledge_response(query),
                "sources": [],
                "success": True,
                "has_knowledge": False,
                "is_out_of_scope": True
            }
        
        # 2. 检索相关内容
        search_results = self.search(query)
        
        # 3. 检查是否有相关知识（包括相关性得分判断）
        if not search_results["hits"]:
            logger.warning(f"[RAG问答] 未找到相关知识: {query}")
            return {
                "answer": self._get_no_knowledge_response(query),
                "sources": [],
                "success": True,
                "has_knowledge": False
            }
        
        # 4. 检查检索结果的相关性得分
        # 如果最高得分低于阈值，判定为无相关知识
        from src.config import RAG_CONFIG
        max_score = max([hit.get("score", 0) for hit in search_results["hits"]])
        similarity_threshold = RAG_CONFIG.get("similarity_threshold", 0.3)
        
        if max_score < similarity_threshold:
            logger.warning(f"[RAG问答] 检索结果相关性过低 (最高得分: {max_score:.3f} < {similarity_threshold}): {query}")
            return {
                "answer": self._get_no_knowledge_response(query),
                "sources": [],
                "success": True,
                "has_knowledge": False,
                "max_score": max_score
            }
        
        # 5. 过滤低相关性结果
        filtered_hits = [
            hit for hit in search_results["hits"] 
            if hit.get("score", 0) >= similarity_threshold
        ]
        
        if not filtered_hits:
            logger.warning(f"[RAG问答] 过滤后无有效结果: {query}")
            return {
                "answer": self._get_no_knowledge_response(query),
                "sources": [],
                "success": True,
                "has_knowledge": False
            }
        
        # 6. 构建上下文（只使用过滤后的高相关性结果）
        context_parts = []
        sources = []
        
        for hit in filtered_hits[:5]:
            context_parts.append(f"【来源: {hit['source'].get('type', 'unknown')}】\n{hit['content']}")
            sources.append({
                "type": hit["source"].get("type"),
                "file": hit["source"].get("file"),
                "page": hit["source"].get("page"),
                "table": hit["source"].get("table"),
                "score": hit.get("score", 0)
            })
        
        context = "\n\n---\n\n".join(context_parts)
        
        # 添加患者上下文
        patient_info = ""
        if patient_context:
            patient_info = f"\n\n【患者信息】\n{self._format_patient_context(patient_context)}"
        
        # 构建提示词
        prompt = f"""基于以下参考资料回答问题。请务必：
1. 仅基于提供的参考资料回答，不要编造信息
2. 如果资料不足以完整回答，请说明
3. 标注证据等级和来源
4. 对高风险情况给出预警

【参考资料】
{context}
{patient_info}

【问题】
{query}

【回答】"""
        
        # 调用 LLM
        result = self.llm_client.generate(
            prompt=prompt,
            history=history,
            system_prompt=MEDICAL_SYSTEM_PROMPT
        )
        
        if result["success"]:
            return {
                "answer": result["content"],
                "sources": sources,
                "success": True,
                "has_knowledge": True,
                "normalized_query": search_results["normalized_query"]
            }
        else:
            return {
                "answer": f"生成回答时出错: {result['error']}",
                "sources": [],
                "success": False,
                "has_knowledge": True
            }
    
    def _format_patient_context(self, context: Dict) -> str:
        """格式化患者上下文"""
        parts = []
        
        if context.get("basic_info"):
            info = context["basic_info"]
            parts.append(f"基本信息: {info.get('name', '未知')}, {info.get('gender', '')}, {info.get('age', '')}岁")
            if info.get("bmi"):
                parts.append(f"BMI: {info['bmi']}")
        
        if context.get("hypertension_assessment"):
            ha = context["hypertension_assessment"]
            parts.append(f"血压: {ha.get('sbp', '')}/{ha.get('dbp', '')} mmHg")
            parts.append(f"高血压风险等级: {ha.get('risk_level', '未评估')}")
        
        if context.get("diabetes_assessment"):
            da = context["diabetes_assessment"]
            if da.get("hba1c"):
                parts.append(f"HbA1c: {da['hba1c']}%")
            parts.append(f"糖尿病控制状态: {da.get('control_status', '未评估')}")
        
        if context.get("medications"):
            med_names = [m.get("drug_name", "") for m in context["medications"][:5]]
            parts.append(f"当前用药: {', '.join(med_names)}")
        
        return "\n".join(parts)
    
    def _is_out_of_scope(self, query: str) -> bool:
        """
        判断查询是否超出知识库范围
        
        Args:
            query: 用户查询
            
        Returns:
            是否超出范围
        """
        # 系统支持的关键词
        supported_keywords = [
            "高血压", "糖尿病", "血压", "血糖", "HbA1c", "糖化血红蛋白",
            "降压", "降糖", "ACEI", "ARB", "CCB", "利尿剂",
            "心肌梗死", "冠心病", "脑卒中", "肾病", "视网膜病变",
            "胰岛素", "二甲双胍", "氨氯地平", "缬沙坦"
        ]
        
        # 超出范围的关键词
        out_of_scope_keywords = [
            "骨折", "骨科", "眼科", "皮肤", "癌症", "肿瘤", "手术", "外科",
            "妇科", "产科", "儿科", "耳鼻喉", "口腔", "精神", "心理", "感冒",
            "肝病", "肺病", "胃病", "肠病", "甲状腺", "风湿", "免疫", "中医"
        ]
        
        query_lower = query.lower()
        
        # 如果包含超出范围的关键词，且不包含支持的关键词，判定为超出范围
        has_out_of_scope = any(keyword in query_lower for keyword in out_of_scope_keywords)
        has_supported = any(keyword in query_lower for keyword in supported_keywords)
        
        if has_out_of_scope and not has_supported:
            return True
        
        return False
    
    def _get_no_knowledge_response(self, query: str) -> str:
        """生成无知识库匹配时的专业回复"""
        # 检查是否是超出范围的问题
        out_of_scope_keywords = [
            "骨折", "骨科", "眼科", "皮肤", "癌症", "肿瘤", "手术", "外科",
            "妇科", "产科", "儿科", "耳鼻喉", "口腔", "精神", "心理"
        ]
        
        for keyword in out_of_scope_keywords:
            if keyword in query:
                return f"""抱歉，本系统是高血压和糖尿病诊疗决策支持助手，暂不支持"{keyword}"相关问题的查询。

本系统支持的功能包括：
1. 高血压诊疗相关问题
2. 糖尿病诊疗相关问题  
3. 患者画像与风险评估
4. 用药方案与禁忌查询
5. 指南推荐与循证医学支持

如需其他疾病的诊疗信息，请咨询相关专科医生。"""
        
        return f"""抱歉，在当前知识库中未找到与"{query}"相关的信息。

可能的原因：
1. 查询的内容不在本系统覆盖范围内
2. 请尝试使用更具体或标准的医学术语

本系统主要支持高血压和糖尿病相关的诊疗决策支持。如有其他问题，请咨询专业医生。"""


# 全局 RAG 服务实例
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """获取全局 RAG 服务实例"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service

