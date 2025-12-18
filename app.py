# -*- coding: utf-8 -*-
"""
医疗知识助手智能体 - Flask 应用入口
"""
import logging
import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建 Flask 应用
app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# 延迟导入，避免循环依赖
def get_agent():
    from src.medical_agent import get_medical_agent
    return get_medical_agent()

def get_vector_store():
    from src.vector_store import get_vector_store as _get_vs
    return _get_vs()

def get_rag_service():
    from src.rag_service import get_rag_service as _get_rag
    return _get_rag()

def get_db_client():
    from src.db_client import get_db_client as _get_db
    return _get_db()

def get_db_simulation_functions():
    from src.db_client import (
        set_db_failure_simulation,
        is_db_failure_simulation_enabled,
        check_db_connection
    )
    return set_db_failure_simulation, is_db_failure_simulation_enabled, check_db_connection


# ==================== 页面路由 ====================

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


# ==================== API 路由 ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "医疗知识助手智能体"
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """智能对话接口"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        patient_id = data.get('patient_id')
        
        if not message:
            return jsonify({"error": "消息不能为空"}), 400
        
        logger.info(f"[API] 对话请求: {message[:50]}...")
        
        agent = get_agent()
        result = agent.chat(message, patient_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"[API] 对话错误: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/patient/<patient_id>', methods=['GET'])
def get_patient(patient_id):
    """获取患者画像"""
    try:
        logger.info(f"[API] 查询患者: {patient_id}")
        
        agent = get_agent()
        result = agent.chat(f"查询患者ID={patient_id}的完整信息", patient_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"[API] 患者查询错误: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/patient/<patient_id>/risk-assessment', methods=['GET'])
def get_risk_assessment(patient_id):
    """获取患者风险评估"""
    try:
        from src.risk_engine import get_risk_engine
        
        logger.info(f"[API] 风险评估: {patient_id}")
        
        risk_engine = get_risk_engine()
        result = risk_engine.comprehensive_assessment(patient_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"[API] 风险评估错误: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/search', methods=['POST'])
def search():
    """跨源检索接口"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        filters = data.get('filters', {})
        
        if not query:
            return jsonify({"error": "查询内容不能为空"}), 400
        
        logger.info(f"[API] 检索请求: {query}")
        
        rag = get_rag_service()
        result = rag.search(query, filters)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"[API] 检索错误: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/guidelines', methods=['GET'])
def get_guidelines():
    """获取指南推荐"""
    try:
        disease_type = request.args.get('disease_type')
        update_date_after = request.args.get('update_date_after')
        
        logger.info(f"[API] 指南查询: disease_type={disease_type}, after={update_date_after}")
        
        db = get_db_client()
        guidelines = db.get_guideline_recommendations(disease_type, update_date_after)
        
        return jsonify({
            "success": True,
            "data": guidelines
        })
        
    except Exception as e:
        logger.error(f"[API] 指南查询错误: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/term-mapping', methods=['GET'])
def get_term_mapping():
    """获取术语映射表"""
    try:
        agent = get_agent()
        mapping_table = agent.get_term_mapping_table()
        
        return jsonify({
            "success": True,
            "data": mapping_table
        })
        
    except Exception as e:
        logger.error(f"[API] 术语映射错误: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/term-normalize', methods=['POST'])
def normalize_term():
    """术语标准化"""
    try:
        from src.term_mapper import get_term_mapper
        
        data = request.get_json()
        term = data.get('term', '')
        
        if not term:
            return jsonify({"error": "术语不能为空"}), 400
        
        mapper = get_term_mapper()
        normalized, is_mapped = mapper.normalize(term)
        suggestions = mapper.suggest(term) if not is_mapped else []
        
        return jsonify({
            "success": True,
            "data": {
                "original": term,
                "normalized": normalized,
                "is_mapped": is_mapped,
                "suggestions": suggestions
            }
        })
        
    except Exception as e:
        logger.error(f"[API] 术语标准化错误: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/insulin-analysis', methods=['GET'])
def get_insulin_analysis():
    """获取胰岛素使用率分析"""
    try:
        agent = get_agent()
        analysis = agent.get_insulin_usage_analysis()
        
        return jsonify({
            "success": True,
            "data": analysis
        })
        
    except Exception as e:
        logger.error(f"[API] 胰岛素分析错误: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/pdf-structure', methods=['GET'])
def get_pdf_structure():
    """获取PDF目录结构"""
    try:
        agent = get_agent()
        structure = agent.get_pdf_structure()
        
        return jsonify({
            "success": True,
            "data": structure
        })
        
    except Exception as e:
        logger.error(f"[API] PDF结构获取错误: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/index/rebuild', methods=['POST'])
def rebuild_index():
    """重建索引"""
    try:
        from src.vector_store import rebuild_index as _rebuild
        
        logger.info("[API] 开始重建索引...")
        result = _rebuild()
        
        return jsonify({
            "success": result["success"],
            "data": result
        })
        
    except Exception as e:
        logger.error(f"[API] 索引重建错误: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/index/status', methods=['GET'])
def get_index_status():
    """获取索引状态"""
    try:
        vs = get_vector_store()
        
        status = {
            "has_index": vs.index is not None,
            "last_update": vs.last_update_time.isoformat() if vs.last_update_time else None,
            "persist_path": str(vs.persist_path)
        }
        
        return jsonify({
            "success": True,
            "data": status
        })
        
    except Exception as e:
        logger.error(f"[API] 索引状态查询错误: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/clear-history', methods=['POST'])
def clear_history():
    """清空对话历史"""
    try:
        agent = get_agent()
        agent.clear_history()
        
        return jsonify({
            "success": True,
            "message": "对话历史已清空"
        })
        
    except Exception as e:
        logger.error(f"[API] 清空历史错误: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==================== 数据库模拟故障控制 ====================

@app.route('/api/db/status', methods=['GET'])
def get_db_status():
    """获取数据库连接状态"""
    try:
        _, is_simulation_enabled, check_connection = get_db_simulation_functions()
        
        status = check_connection()
        status["simulation_enabled"] = is_simulation_enabled()
        
        return jsonify({
            "success": True,
            "data": status
        })
        
    except Exception as e:
        logger.error(f"[API] 数据库状态查询错误: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/db/simulate-failure', methods=['POST'])
def toggle_db_failure_simulation():
    """切换数据库故障模拟开关"""
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)
        
        set_simulation, is_simulation_enabled, check_connection = get_db_simulation_functions()
        
        set_simulation(enabled)
        status = "启用" if enabled else "禁用"
        logger.info(f"[API] 数据库故障模拟已{status}")
        
        # 返回当前状态
        db_status = check_connection()
        
        return jsonify({
            "success": True,
            "message": f"数据库故障模拟已{status}",
            "data": {
                "simulation_enabled": is_simulation_enabled(),
                "db_status": db_status
            }
        })
        
    except Exception as e:
        logger.error(f"[API] 数据库故障模拟设置错误: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/db/test-connection', methods=['GET'])
def test_db_connection():
    """测试数据库连接"""
    try:
        _, is_simulation_enabled, check_connection = get_db_simulation_functions()
        
        status = check_connection()
        
        return jsonify({
            "success": True,
            "data": {
                "connected": status["connected"],
                "message": status["message"],
                "simulated_failure": status.get("simulated_failure", False),
                "simulation_enabled": is_simulation_enabled()
            }
        })
        
    except Exception as e:
        logger.error(f"[API] 数据库连接测试错误: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "接口不存在"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "服务器内部错误"}), 500


# ==================== 启动 ====================

if __name__ == '__main__':
    # 检查环境变量
    if not os.getenv("DASHSCOPE_API_KEY"):
        logger.warning("警告: DASHSCOPE_API_KEY 环境变量未设置")
    
    # 启动定时任务
    # from src.scheduler import start_scheduler
    # start_scheduler()
    
    # 启动服务
    logger.info("医疗知识助手智能体启动中...")
    app.run(host='0.0.0.0', port=5001, debug=True)

