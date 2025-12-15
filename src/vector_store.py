# -*- coding: utf-8 -*-
"""
向量存储模块 - 使用 LlamaIndex + DashScope Embedding
"""
import logging
import os
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

from llama_index.core import (
    SimpleDirectoryReader, 
    VectorStoreIndex, 
    StorageContext,
    load_index_from_storage,
    Document,
    Settings
)
from llama_index.embeddings.dashscope import DashScopeEmbedding, DashScopeTextEmbeddingModels
from llama_index.llms.openai_like import OpenAILike

from src.config import (
    KNOWLEDGE_BASE_DIR, DATA_DIR, DASHSCOPE_API_KEY, 
    DASHSCOPE_BASE_URL, LLM_MODEL, RAG_CONFIG
)

logger = logging.getLogger(__name__)

# 设置日志级别避免干扰
logging.getLogger("llama_index").setLevel(logging.WARNING)


class VectorStore:
    """向量存储管理器"""
    
    def __init__(self, persist_path: Path = None):
        self.persist_path = persist_path or KNOWLEDGE_BASE_DIR / "medical_index"
        self.index: Optional[VectorStoreIndex] = None
        self.query_engine = None
        self.last_update_time: Optional[datetime] = None
        
        # 初始化 embedding 模型
        self.embed_model = DashScopeEmbedding(
            model_name=DashScopeTextEmbeddingModels.TEXT_EMBEDDING_V2,
            api_key=DASHSCOPE_API_KEY
        )
        
        # 初始化 LLM
        self.llm = OpenAILike(
            model=LLM_MODEL,
            api_base=DASHSCOPE_BASE_URL,
            api_key=DASHSCOPE_API_KEY,
            is_chat_model=True
        )
        
        # 配置全局设置
        Settings.embed_model = self.embed_model
        Settings.llm = self.llm
        Settings.chunk_size = RAG_CONFIG["chunk_size"]
        Settings.chunk_overlap = RAG_CONFIG["chunk_overlap"]
    
    def build_index_from_directory(self, directory: Path = None) -> bool:
        """
        从目录构建索引
        
        Args:
            directory: 文档目录路径
            
        Returns:
            是否成功
        """
        directory = directory or DATA_DIR
        
        try:
            logger.info(f"[索引构建] 开始从目录加载文档: {directory}")
            
            # 加载文档
            documents = SimpleDirectoryReader(
                input_dir=str(directory),
                recursive=True,
                filename_as_id=True
            ).load_data()
            
            logger.info(f"[索引构建] 加载了 {len(documents)} 个文档")
            
            # 构建索引
            self.index = VectorStoreIndex.from_documents(
                documents,
                embed_model=self.embed_model,
                show_progress=True
            )
            
            # 持久化
            self.persist_path.mkdir(parents=True, exist_ok=True)
            self.index.storage_context.persist(persist_dir=str(self.persist_path))
            
            self.last_update_time = datetime.now()
            logger.info(f"[索引构建] 完成并持久化到: {self.persist_path}")
            logger.info(f"[索引更新时间] {self.last_update_time.isoformat()}")
            
            return True
            
        except Exception as e:
            logger.error(f"[索引构建] 失败: {str(e)}")
            return False
    
    def build_index_from_chunks(self, chunks: List[Dict]) -> bool:
        """
        从文本块构建索引
        
        Args:
            chunks: [{"text": str, "source": str, "page": int, ...}]
            
        Returns:
            是否成功
        """
        try:
            logger.info(f"[索引构建] 开始处理 {len(chunks)} 个文本块")
            
            # 转换为 Document 对象
            documents = []
            for chunk in chunks:
                metadata = {
                    "source": chunk.get("source", "unknown"),
                    "source_type": chunk.get("source_type", "unknown"),
                    "page": chunk.get("page", 0),
                    "row_start": chunk.get("row_start", 0),
                    "row_end": chunk.get("row_end", 0)
                }
                doc = Document(
                    text=chunk.get("text", ""),
                    metadata=metadata
                )
                documents.append(doc)
            
            # 构建索引
            self.index = VectorStoreIndex.from_documents(
                documents,
                embed_model=self.embed_model,
                show_progress=True
            )
            
            # 持久化
            self.persist_path.mkdir(parents=True, exist_ok=True)
            self.index.storage_context.persist(persist_dir=str(self.persist_path))
            
            self.last_update_time = datetime.now()
            logger.info(f"[索引构建] 完成，时间戳: {self.last_update_time.isoformat()}")
            
            return True
            
        except Exception as e:
            logger.error(f"[索引构建] 失败: {str(e)}")
            return False
    
    def load_index(self) -> bool:
        """
        加载已持久化的索引
        
        Returns:
            是否成功
        """
        try:
            if not self.persist_path.exists():
                logger.warning(f"[索引加载] 索引路径不存在: {self.persist_path}")
                return False
            
            logger.info(f"[索引加载] 从 {self.persist_path} 加载索引")
            
            storage_context = StorageContext.from_defaults(
                persist_dir=str(self.persist_path)
            )
            self.index = load_index_from_storage(
                storage_context,
                embed_model=self.embed_model
            )
            
            logger.info("[索引加载] 成功")
            return True
            
        except Exception as e:
            logger.error(f"[索引加载] 失败: {str(e)}")
            return False
    
    def get_query_engine(self, similarity_top_k: int = None):
        """
        获取查询引擎
        
        Args:
            similarity_top_k: 返回的最相似结果数量
        """
        if self.index is None:
            if not self.load_index():
                raise ValueError("索引未加载，请先构建或加载索引")
        
        top_k = similarity_top_k or RAG_CONFIG["top_k"]
        
        self.query_engine = self.index.as_query_engine(
            streaming=True,
            similarity_top_k=top_k,
            llm=self.llm
        )
        
        return self.query_engine
    
    def search(self, query: str, top_k: int = None) -> List[Dict]:
        """
        向量检索
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            [{"content": str, "score": float, "source": dict}]
        """
        if self.index is None:
            if not self.load_index():
                return []
        
        top_k = top_k or RAG_CONFIG["top_k"]
        
        try:
            logger.info(f"[向量检索] 查询: {query[:50]}...")
            
            retriever = self.index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(query)
            
            results = []
            for node in nodes:
                results.append({
                    "content": node.node.text,
                    "score": float(node.score) if node.score else 0.0,
                    "source": {
                        "type": node.node.metadata.get("source_type", "unknown"),
                        "file": node.node.metadata.get("source", "unknown"),
                        "page": node.node.metadata.get("page", 0),
                        "row_start": node.node.metadata.get("row_start", 0),
                        "row_end": node.node.metadata.get("row_end", 0)
                    }
                })
            
            logger.info(f"[向量检索] 返回 {len(results)} 个结果")
            return results
            
        except Exception as e:
            logger.error(f"[向量检索] 失败: {str(e)}")
            return []
    
    def query_with_sources(self, question: str) -> Dict:
        """
        带来源的问答查询
        
        Args:
            question: 问题
            
        Returns:
            {"answer": str, "sources": list}
        """
        if self.query_engine is None:
            self.get_query_engine()
        
        try:
            logger.info(f"[RAG问答] 问题: {question[:50]}...")
            
            response = self.query_engine.query(question)
            
            # 提取来源信息
            sources = []
            if hasattr(response, 'source_nodes'):
                for node in response.source_nodes:
                    sources.append({
                        "content": node.node.text[:200] + "..." if len(node.node.text) > 200 else node.node.text,
                        "source": node.node.metadata.get("source", "unknown"),
                        "page": node.node.metadata.get("page", 0),
                        "score": float(node.score) if node.score else 0.0
                    })
            
            answer = str(response)
            logger.info(f"[RAG问答] 回答长度: {len(answer)}, 来源数: {len(sources)}")
            
            return {
                "answer": answer,
                "sources": sources
            }
            
        except Exception as e:
            logger.error(f"[RAG问答] 失败: {str(e)}")
            return {
                "answer": f"查询失败: {str(e)}",
                "sources": []
            }


# 全局向量存储实例
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """获取全局向量存储实例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def rebuild_index() -> Dict:
    """
    重建索引
    
    Returns:
        {"success": bool, "timestamp": str, "message": str}
    """
    from src.data_ingest import load_all_pdf_documents, ExcelProcessor
    from src.config import EXCEL_FILE
    
    try:
        logger.info("[索引重建] 开始...")
        
        # 加载 PDF 文档
        pdf_chunks = load_all_pdf_documents()
        
        # 加载 Excel 数据
        excel_processor = ExcelProcessor(EXCEL_FILE)
        excel_chunks = excel_processor.to_chunks()
        
        # 合并所有文档块
        all_chunks = pdf_chunks + excel_chunks
        
        # 构建索引
        store = get_vector_store()
        success = store.build_index_from_chunks(all_chunks)
        
        timestamp = datetime.now().isoformat()
        
        if success:
            logger.info(f"[索引重建] 完成，时间戳: {timestamp}")
            return {
                "success": True,
                "timestamp": timestamp,
                "message": f"索引重建成功，共处理 {len(all_chunks)} 个文档块"
            }
        else:
            return {
                "success": False,
                "timestamp": timestamp,
                "message": "索引重建失败"
            }
            
    except Exception as e:
        logger.error(f"[索引重建] 错误: {str(e)}")
        return {
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "message": f"索引重建错误: {str(e)}"
        }

