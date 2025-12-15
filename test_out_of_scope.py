# -*- coding: utf-8 -*-
"""
测试超出范围查询的处理
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.rag_service import get_rag_service

def test_out_of_scope_queries():
    """测试超出范围查询"""
    rag = get_rag_service()
    
    test_cases = [
        "骨折怎么治疗",
        "眼科疾病如何诊断",
        "癌症的治疗方案",
        "高血压怎么治疗",  # 应该正常回答
        "糖尿病用药方案",  # 应该正常回答
    ]
    
    print("=" * 60)
    print("测试超出范围查询处理")
    print("=" * 60)
    
    for query in test_cases:
        print(f"\n查询: {query}")
        print("-" * 60)
        
        result = rag.rag_answer(query)
        
        print(f"是否有知识库: {result.get('has_knowledge')}")
        print(f"是否超出范围: {result.get('is_out_of_scope')}")
        print(f"回答预览: {result.get('answer', '')[:200]}...")
        
        # 检查是否符合预期
        if "骨折" in query or "眼科" in query or "癌症" in query:
            if result.get("is_out_of_scope") or not result.get("has_knowledge"):
                print("✅ 正确识别为超出范围")
            else:
                print("❌ 未正确识别为超出范围")
        else:
            if result.get("has_knowledge"):
                print("✅ 正确识别为有知识库")
            else:
                print("⚠️ 可能误判为无知识库")

if __name__ == "__main__":
    # 需要设置环境变量
    if not os.getenv("DASHSCOPE_API_KEY"):
        print("警告: 未设置 DASHSCOPE_API_KEY 环境变量")
        print("部分功能可能无法正常工作")
    
    test_out_of_scope_queries()

