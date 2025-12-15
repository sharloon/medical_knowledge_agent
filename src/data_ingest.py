# -*- coding: utf-8 -*-
"""
数据摄取模块 - PDF/Excel/MySQL 数据加载与解析
"""
import logging
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime

import pandas as pd
import pdfplumber

from src.config import PDF_FILES, EXCEL_FILE, DATA_DIR

logger = logging.getLogger(__name__)


class PDFProcessor:
    """PDF 文档处理器"""
    
    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self.filename = pdf_path.name
    
    def extract_text_with_pages(self) -> List[Dict]:
        """
        提取 PDF 文本及页码信息
        
        Returns:
            [{"page": int, "text": str, "source": str}]
        """
        chunks = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                logger.info(f"[PDF解析] 开始处理: {self.filename}, 共 {len(pdf.pages)} 页")
                
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text and text.strip():
                        chunks.append({
                            "page": i + 1,
                            "text": text.strip(),
                            "source": self.filename,
                            "source_type": "pdf"
                        })
                
                logger.info(f"[PDF解析] 完成: {self.filename}, 提取 {len(chunks)} 个文本块")
        except Exception as e:
            logger.error(f"[PDF解析] 失败: {self.filename}, 错误: {str(e)}")
        
        return chunks
    
    def extract_tables(self) -> List[Dict]:
        """
        提取 PDF 中的表格
        
        Returns:
            [{"page": int, "table_index": int, "data": list, "source": str}]
        """
        tables = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_tables = page.extract_tables()
                    for j, table in enumerate(page_tables):
                        if table and len(table) > 1:
                            tables.append({
                                "page": i + 1,
                                "table_index": j,
                                "data": table,
                                "source": self.filename,
                                "source_type": "pdf_table"
                            })
                
                logger.info(f"[PDF表格] {self.filename}: 提取 {len(tables)} 个表格")
        except Exception as e:
            logger.error(f"[PDF表格] 提取失败: {str(e)}")
        
        return tables
    
    def extract_toc(self) -> List[Dict]:
        """
        提取 PDF 目录结构（基于文本格式推断）
        
        Returns:
            [{"level": int, "title": str, "page": int}]
        """
        toc = []
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for i, page in enumerate(pdf.pages[:10]):  # 通常目录在前10页
                    text = page.extract_text()
                    if text:
                        # 匹配常见目录格式
                        lines = text.split('\n')
                        for line in lines:
                            # 匹配 "第X章 标题" 或 "X.X 标题" 格式
                            chapter_match = re.match(r'^第?([一二三四五六七八九十\d]+)[章节]?\s*[\.、]?\s*(.+?)(?:\s*\.{2,}\s*(\d+))?$', line.strip())
                            section_match = re.match(r'^(\d+\.?\d*)\s+(.+?)(?:\s*\.{2,}\s*(\d+))?$', line.strip())
                            
                            if chapter_match:
                                toc.append({
                                    "level": 1,
                                    "title": chapter_match.group(2).strip(),
                                    "page": i + 1,
                                    "source": self.filename
                                })
                            elif section_match:
                                level = len(section_match.group(1).split('.'))
                                toc.append({
                                    "level": level,
                                    "title": section_match.group(2).strip(),
                                    "page": i + 1,
                                    "source": self.filename
                                })
                
                logger.info(f"[PDF目录] {self.filename}: 提取 {len(toc)} 个目录项")
        except Exception as e:
            logger.error(f"[PDF目录] 提取失败: {str(e)}")
        
        return toc


class ExcelProcessor:
    """Excel 数据处理器"""
    
    def __init__(self, excel_path: Path):
        self.excel_path = excel_path
        self.filename = excel_path.name
        self.df: Optional[pd.DataFrame] = None
    
    def load_data(self) -> pd.DataFrame:
        """加载 Excel 数据"""
        try:
            self.df = pd.read_excel(self.excel_path)
            logger.info(f"[Excel加载] {self.filename}: {len(self.df)} 行, {len(self.df.columns)} 列")
            logger.info(f"[Excel列名] {list(self.df.columns)}")
            return self.df
        except Exception as e:
            logger.error(f"[Excel加载] 失败: {str(e)}")
            return pd.DataFrame()
    
    def analyze_insulin_usage(self) -> Dict:
        """
        分析胰岛素使用率数据分布
        
        根据PRD说明：
        - 空腹胰岛素和餐后2小时胰岛素都没有值或为空，说明没有用胰岛素
        - 表格中共有125人，都是糖尿病人
        
        Returns:
            分析结果字典
        """
        if self.df is None:
            self.load_data()
        
        if self.df is None or self.df.empty:
            return {"error": "无法加载Excel数据"}
        
        result = {
            "total_patients": len(self.df),
            "source": self.filename,
            "source_type": "excel"
        }
        
        # 尝试找到胰岛素相关列
        insulin_cols = [col for col in self.df.columns if '胰岛素' in str(col)]
        fasting_insulin_col = None
        postprandial_insulin_col = None
        
        for col in insulin_cols:
            if '空腹' in str(col):
                fasting_insulin_col = col
            elif '餐后' in str(col) or '2小时' in str(col):
                postprandial_insulin_col = col
        
        # 计算胰岛素使用情况
        if fasting_insulin_col or postprandial_insulin_col:
            # 判断是否使用胰岛素：两列都为空则未使用
            def is_using_insulin(row):
                fasting = row.get(fasting_insulin_col) if fasting_insulin_col else None
                postprandial = row.get(postprandial_insulin_col) if postprandial_insulin_col else None
                
                fasting_empty = pd.isna(fasting) or fasting == '' or fasting == 0
                postprandial_empty = pd.isna(postprandial) or postprandial == '' or postprandial == 0
                
                return not (fasting_empty and postprandial_empty)
            
            self.df['使用胰岛素'] = self.df.apply(is_using_insulin, axis=1)
            
            insulin_users = self.df['使用胰岛素'].sum()
            non_users = len(self.df) - insulin_users
            
            result["insulin_usage"] = {
                "using_insulin": int(insulin_users),
                "not_using_insulin": int(non_users),
                "usage_rate": round(insulin_users / len(self.df) * 100, 2)
            }
        
        # 按性别分布
        gender_col = None
        for col in self.df.columns:
            if '性别' in str(col):
                gender_col = col
                break
        
        if gender_col:
            gender_dist = self.df[gender_col].value_counts().to_dict()
            result["gender_distribution"] = {str(k): int(v) for k, v in gender_dist.items()}
            
            # 按性别的胰岛素使用率
            if '使用胰岛素' in self.df.columns:
                gender_insulin = self.df.groupby(gender_col)['使用胰岛素'].agg(['sum', 'count'])
                result["insulin_by_gender"] = {
                    str(gender): {
                        "using": int(row['sum']),
                        "total": int(row['count']),
                        "rate": round(row['sum'] / row['count'] * 100, 2)
                    }
                    for gender, row in gender_insulin.iterrows()
                }
        
        # 年龄分布
        age_col = None
        for col in self.df.columns:
            if '年龄' in str(col):
                age_col = col
                break
        
        if age_col:
            result["age_statistics"] = {
                "mean": round(float(self.df[age_col].mean()), 1),
                "min": int(self.df[age_col].min()),
                "max": int(self.df[age_col].max()),
                "std": round(float(self.df[age_col].std()), 1)
            }
            
            # 年龄段分布
            bins = [0, 40, 50, 60, 70, 100]
            labels = ['<40岁', '40-50岁', '50-60岁', '60-70岁', '>70岁']
            self.df['年龄段'] = pd.cut(self.df[age_col], bins=bins, labels=labels, right=False)
            age_dist = self.df['年龄段'].value_counts().sort_index().to_dict()
            result["age_distribution"] = {str(k): int(v) for k, v in age_dist.items()}
        
        logger.info(f"[Excel分析] 胰岛素使用率分析完成")
        return result
    
    def get_summary_stats(self) -> Dict:
        """获取数据摘要统计"""
        if self.df is None:
            self.load_data()
        
        if self.df is None or self.df.empty:
            return {"error": "无法加载Excel数据"}
        
        return {
            "total_rows": len(self.df),
            "total_columns": len(self.df.columns),
            "columns": list(self.df.columns),
            "dtypes": {col: str(dtype) for col, dtype in self.df.dtypes.items()},
            "source": self.filename
        }
    
    def to_chunks(self, chunk_size: int = 10) -> List[Dict]:
        """
        将 Excel 数据转换为文本块用于 RAG
        
        Args:
            chunk_size: 每个块包含的行数
            
        Returns:
            文本块列表
        """
        if self.df is None:
            self.load_data()
        
        chunks = []
        if self.df is None or self.df.empty:
            return chunks
        
        for i in range(0, len(self.df), chunk_size):
            chunk_df = self.df.iloc[i:i+chunk_size]
            text = f"糖尿病病例统计数据 (行 {i+1}-{min(i+chunk_size, len(self.df))}):\n"
            text += chunk_df.to_string()
            
            chunks.append({
                "text": text,
                "source": self.filename,
                "source_type": "excel",
                "row_start": i + 1,
                "row_end": min(i + chunk_size, len(self.df))
            })
        
        return chunks


def load_all_pdf_documents() -> List[Dict]:
    """加载所有 PDF 文档"""
    all_chunks = []
    
    for pdf_path in PDF_FILES:
        if pdf_path.exists():
            processor = PDFProcessor(pdf_path)
            chunks = processor.extract_text_with_pages()
            all_chunks.extend(chunks)
        else:
            logger.warning(f"[PDF] 文件不存在: {pdf_path}")
    
    logger.info(f"[PDF汇总] 共加载 {len(all_chunks)} 个文本块")
    return all_chunks


def load_excel_data() -> Tuple[pd.DataFrame, Dict]:
    """加载 Excel 数据及分析结果"""
    processor = ExcelProcessor(EXCEL_FILE)
    df = processor.load_data()
    analysis = processor.analyze_insulin_usage()
    return df, analysis


def get_pdf_toc_and_tables() -> Dict:
    """获取所有 PDF 的目录和表格"""
    result = {
        "toc": [],
        "tables": []
    }
    
    for pdf_path in PDF_FILES:
        if pdf_path.exists():
            processor = PDFProcessor(pdf_path)
            result["toc"].extend(processor.extract_toc())
            result["tables"].extend(processor.extract_tables())
    
    return result

