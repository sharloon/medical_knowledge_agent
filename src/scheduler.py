# -*- coding: utf-8 -*-
"""
定时任务调度器 - 自动更新索引
"""
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.config import INDEX_UPDATE_INTERVAL_MINUTES

logger = logging.getLogger(__name__)

# 全局调度器
_scheduler = None


def index_update_job():
    """索引更新任务"""
    from src.vector_store import rebuild_index
    
    logger.info(f"[定时任务] 开始自动更新索引 - {datetime.now().isoformat()}")
    
    try:
        result = rebuild_index()
        if result["success"]:
            logger.info(f"[定时任务] 索引更新成功 - {result['timestamp']}")
        else:
            logger.error(f"[定时任务] 索引更新失败 - {result['message']}")
    except Exception as e:
        logger.error(f"[定时任务] 索引更新错误 - {str(e)}")


def start_scheduler():
    """启动定时调度器"""
    global _scheduler
    
    if _scheduler is not None:
        logger.warning("[调度器] 调度器已在运行")
        return
    
    _scheduler = BackgroundScheduler()
    
    # 添加索引更新任务
    _scheduler.add_job(
        index_update_job,
        trigger=IntervalTrigger(minutes=INDEX_UPDATE_INTERVAL_MINUTES),
        id='index_update',
        name='自动更新RAG索引',
        replace_existing=True
    )
    
    _scheduler.start()
    logger.info(f"[调度器] 已启动，索引更新间隔: {INDEX_UPDATE_INTERVAL_MINUTES} 分钟")


def stop_scheduler():
    """停止定时调度器"""
    global _scheduler
    
    if _scheduler is not None:
        _scheduler.shutdown()
        _scheduler = None
        logger.info("[调度器] 已停止")


def get_scheduler_status():
    """获取调度器状态"""
    global _scheduler
    
    if _scheduler is None:
        return {"running": False}
    
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None
        })
    
    return {
        "running": _scheduler.running,
        "jobs": jobs
    }

