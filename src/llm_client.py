# -*- coding: utf-8 -*-
"""
LLM 客户端模块 - 封装百炼 API 调用
"""
import logging
from typing import List, Dict, Optional, Generator
from openai import OpenAI

from src.config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, LLM_MODEL

logger = logging.getLogger(__name__)


class LLMClient:
    """百炼大模型客户端"""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or DASHSCOPE_API_KEY
        self.base_url = base_url or DASHSCOPE_BASE_URL
        self.model = model or LLM_MODEL
        
        if not self.api_key:
            logger.warning("DASHSCOPE_API_KEY 未设置，请配置环境变量")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def generate(self, prompt: str, history: List[Dict] = None, 
                 system_prompt: str = None, temperature: float = 0.7) -> Dict:
        """
        生成回复
        
        Args:
            prompt: 用户输入
            history: 对话历史 [{"role": "user/assistant", "content": "..."}]
            system_prompt: 系统提示词
            temperature: 温度参数
            
        Returns:
            {"success": bool, "content": str, "error": str}
        """
        try:
            messages = []
            
            # 添加系统提示
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            # 添加历史对话
            if history:
                messages.extend(history)
            
            # 添加当前用户输入
            messages.append({"role": "user", "content": prompt})
            
            logger.info(f"[LLM调用] 模型: {self.model}, 消息数: {len(messages)}")
            
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature
            )
            
            content = completion.choices[0].message.content
            logger.info(f"[LLM响应] 长度: {len(content)} 字符")
            
            return {
                "success": True,
                "content": content,
                "error": None
            }
            
        except Exception as e:
            error_msg = f"LLM 调用失败: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "content": None,
                "error": error_msg
            }
    
    def generate_stream(self, prompt: str, history: List[Dict] = None,
                        system_prompt: str = None, temperature: float = 0.7) -> Generator[str, None, None]:
        """
        流式生成回复
        
        Yields:
            生成的文本片段
        """
        try:
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            if history:
                messages.extend(history)
            
            messages.append({"role": "user", "content": prompt})
            
            logger.info(f"[LLM流式调用] 模型: {self.model}")
            
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                stream=True
            )
            
            for chunk in completion:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            error_msg = f"LLM 流式调用失败: {str(e)}"
            logger.error(error_msg)
            yield f"\n[错误] {error_msg}"


# 医疗助手系统提示词
MEDICAL_SYSTEM_PROMPT = """你是一个专业的医疗知识助手，专注于高血压和糖尿病的诊疗决策支持。

你的职责包括：
1. 根据患者信息生成患者画像
2. 进行高血压和糖尿病的风险分层评估
3. 检测药物冲突和禁忌
4. 生成个性化的诊疗方案
5. 进行结构化问诊（SOAP格式）

重要原则：
- 所有建议必须基于医学指南和证据
- 标注证据等级（如ⅠA、ⅠB、ⅡA等）
- 对高风险情况（如孕妇、急症）必须给出预警
- 如无相关知识，明确说明而非猜测

回复格式要求：
- 使用结构化格式
- 标注数据来源（PDF页码、数据库表名等）
- 对重要信息加粗或突出显示
"""


# 全局 LLM 客户端实例
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取全局 LLM 客户端实例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client

