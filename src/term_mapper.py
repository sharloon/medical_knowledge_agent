# -*- coding: utf-8 -*-
"""
术语映射模块 - 医学术语标准化与同义词映射
"""
import logging
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# 医学术语映射表
TERM_MAPPINGS = {
    # 心血管疾病
    "心梗": "心肌梗死",
    "心肌梗塞": "心肌梗死",
    "MI": "心肌梗死",
    "AMI": "急性心肌梗死",
    "冠心病": "冠状动脉粥样硬化性心脏病",
    "冠状动脉硬化": "冠状动脉粥样硬化性心脏病",
    "CHD": "冠状动脉粥样硬化性心脏病",
    "中风": "脑卒中",
    "脑中风": "脑卒中",
    "脑梗": "脑梗死",
    "脑梗塞": "脑梗死",
    "脑溢血": "脑出血",
    "高血压": "高血压病",
    "血压高": "高血压病",
    "HTN": "高血压病",
    "房颤": "心房颤动",
    "心律不齐": "心律失常",
    
    # 糖尿病相关
    "糖尿病": "糖尿病",
    "DM": "糖尿病",
    "血糖高": "高血糖",
    "低血糖": "低血糖症",
    "1型糖尿病": "1型糖尿病",
    "T1DM": "1型糖尿病",
    "2型糖尿病": "2型糖尿病",
    "T2DM": "2型糖尿病",
    "糖化血红蛋白": "糖化血红蛋白",
    "HbA1c": "糖化血红蛋白",
    "糖化": "糖化血红蛋白",
    
    # 药物类别
    "ACEI": "血管紧张素转换酶抑制剂",
    "普利类": "血管紧张素转换酶抑制剂",
    "ARB": "血管紧张素II受体拮抗剂",
    "沙坦类": "血管紧张素II受体拮抗剂",
    "CCB": "钙通道阻滞剂",
    "地平类": "钙通道阻滞剂",
    "β受体阻滞剂": "β受体阻滞剂",
    "洛尔类": "β受体阻滞剂",
    "利尿剂": "利尿剂",
    "噻嗪类": "噻嗪类利尿剂",
    
    # 具体药物
    "氨氯地平": "苯磺酸氨氯地平",
    "络活喜": "苯磺酸氨氯地平",
    "缬沙坦": "缬沙坦",
    "代文": "缬沙坦",
    "氯沙坦": "氯沙坦钾",
    "科素亚": "氯沙坦钾",
    "二甲双胍": "盐酸二甲双胍",
    "格华止": "盐酸二甲双胍",
    "甲基多巴": "甲基多巴",
    "拉贝洛尔": "盐酸拉贝洛尔",
    
    # 检查检验
    "血压": "血压测量",
    "BP": "血压测量",
    "收缩压": "收缩压",
    "SBP": "收缩压",
    "舒张压": "舒张压",
    "DBP": "舒张压",
    "空腹血糖": "空腹血糖",
    "FPG": "空腹血糖",
    "FBG": "空腹血糖",
    "餐后血糖": "餐后2小时血糖",
    "餐后2h血糖": "餐后2小时血糖",
    "2hPG": "餐后2小时血糖",
    
    # 症状
    "头晕": "眩晕",
    "头痛": "头痛",
    "胸闷": "胸闷",
    "胸痛": "胸痛",
    "心慌": "心悸",
    "气短": "呼吸困难",
    "水肿": "水肿",
    "浮肿": "水肿",
    
    # 并发症
    "肾病": "肾脏病变",
    "肾功能不全": "慢性肾脏病",
    "CKD": "慢性肾脏病",
    "视网膜病变": "糖尿病视网膜病变",
    "DR": "糖尿病视网膜病变",
    "神经病变": "糖尿病周围神经病变",
    "DPN": "糖尿病周围神经病变",
    "糖足": "糖尿病足",
    
    # 特殊人群
    "孕妇": "妊娠期",
    "妊娠": "妊娠期",
    "老年人": "老年患者",
    "老人": "老年患者",
}

# 反向映射（标准术语到别名列表）
REVERSE_MAPPINGS: Dict[str, List[str]] = {}
for alias, standard in TERM_MAPPINGS.items():
    if standard not in REVERSE_MAPPINGS:
        REVERSE_MAPPINGS[standard] = []
    if alias != standard:
        REVERSE_MAPPINGS[standard].append(alias)


class TermMapper:
    """医学术语映射器"""
    
    def __init__(self, custom_mappings: Dict[str, str] = None):
        """
        初始化术语映射器
        
        Args:
            custom_mappings: 自定义映射表
        """
        self.mappings = TERM_MAPPINGS.copy()
        if custom_mappings:
            self.mappings.update(custom_mappings)
        
        # 构建反向映射
        self.reverse_mappings = {}
        for alias, standard in self.mappings.items():
            if standard not in self.reverse_mappings:
                self.reverse_mappings[standard] = []
            if alias != standard:
                self.reverse_mappings[standard].append(alias)
    
    def normalize(self, term: str) -> Tuple[str, bool]:
        """
        标准化术语
        
        Args:
            term: 输入术语
            
        Returns:
            (标准术语, 是否发生映射)
        """
        term = term.strip()
        
        # 直接匹配
        if term in self.mappings:
            standard = self.mappings[term]
            if term != standard:
                logger.info(f"[术语映射] '{term}' -> '{standard}'")
                return standard, True
            return term, False
        
        # 大小写不敏感匹配
        term_lower = term.lower()
        for alias, standard in self.mappings.items():
            if alias.lower() == term_lower:
                logger.info(f"[术语映射] '{term}' -> '{standard}'")
                return standard, True
        
        return term, False
    
    def suggest(self, term: str, threshold: float = 0.6) -> List[Dict]:
        """
        建议相似术语
        
        Args:
            term: 输入术语
            threshold: 相似度阈值
            
        Returns:
            [{"term": str, "standard": str, "similarity": float}]
        """
        suggestions = []
        term_lower = term.lower()
        
        for alias, standard in self.mappings.items():
            # 计算相似度
            similarity = SequenceMatcher(None, term_lower, alias.lower()).ratio()
            
            if similarity >= threshold:
                suggestions.append({
                    "term": alias,
                    "standard": standard,
                    "similarity": round(similarity, 2)
                })
        
        # 按相似度降序排序
        suggestions.sort(key=lambda x: x["similarity"], reverse=True)
        
        return suggestions[:5]  # 返回前5个建议
    
    def get_aliases(self, standard_term: str) -> List[str]:
        """
        获取标准术语的所有别名
        
        Args:
            standard_term: 标准术语
            
        Returns:
            别名列表
        """
        return self.reverse_mappings.get(standard_term, [])
    
    def get_mapping_table(self) -> Dict[str, Dict]:
        """
        获取完整映射表
        
        Returns:
            {标准术语: {"aliases": [别名列表]}}
        """
        table = {}
        for standard, aliases in self.reverse_mappings.items():
            table[standard] = {
                "aliases": aliases,
                "count": len(aliases)
            }
        return table
    
    def add_mapping(self, alias: str, standard: str) -> bool:
        """
        添加新的映射关系
        
        Args:
            alias: 别名
            standard: 标准术语
            
        Returns:
            是否成功
        """
        try:
            self.mappings[alias] = standard
            if standard not in self.reverse_mappings:
                self.reverse_mappings[standard] = []
            if alias not in self.reverse_mappings[standard]:
                self.reverse_mappings[standard].append(alias)
            
            logger.info(f"[术语映射] 添加映射: '{alias}' -> '{standard}'")
            return True
        except Exception as e:
            logger.error(f"[术语映射] 添加失败: {str(e)}")
            return False
    
    def expand_query(self, query: str) -> str:
        """
        扩展查询，将术语替换为标准术语
        
        Args:
            query: 原始查询
            
        Returns:
            扩展后的查询
        """
        expanded = query
        
        # 按术语长度降序排序，避免短术语替换长术语中的内容
        sorted_terms = sorted(self.mappings.keys(), key=len, reverse=True)
        
        for term in sorted_terms:
            if term in expanded:
                standard = self.mappings[term]
                if term != standard:
                    expanded = expanded.replace(term, standard)
        
        if expanded != query:
            logger.info(f"[查询扩展] '{query}' -> '{expanded}'")
        
        return expanded


# 药物禁忌映射
DRUG_CONTRAINDICATIONS = {
    "血管紧张素转换酶抑制剂": {
        "禁忌人群": ["妊娠期", "哺乳期", "双侧肾动脉狭窄", "高钾血症"],
        "相对禁忌": ["单侧肾动脉狭窄", "严重肾功能不全"],
        "注意事项": ["干咳", "血管性水肿风险"]
    },
    "血管紧张素II受体拮抗剂": {
        "禁忌人群": ["妊娠期", "哺乳期", "双侧肾动脉狭窄"],
        "相对禁忌": ["严重肾功能不全"],
        "注意事项": ["高钾血症风险"]
    },
    "钙通道阻滞剂": {
        "禁忌人群": ["严重主动脉瓣狭窄", "心源性休克"],
        "相对禁忌": ["严重心动过缓", "心力衰竭"],
        "注意事项": ["下肢水肿", "头痛", "面部潮红"]
    },
    "β受体阻滞剂": {
        "禁忌人群": ["严重心动过缓", "二度以上房室传导阻滞", "支气管哮喘"],
        "相对禁忌": ["COPD", "周围血管病"],
        "注意事项": ["糖尿病患者可能掩盖低血糖症状"]
    },
    "噻嗪类利尿剂": {
        "禁忌人群": ["痛风", "低钾血症", "低钠血症"],
        "相对禁忌": ["糖尿病", "高尿酸血症"],
        "注意事项": ["电解质紊乱", "血糖升高"]
    }
}


# 全局术语映射器实例
_term_mapper: Optional[TermMapper] = None


def get_term_mapper() -> TermMapper:
    """获取全局术语映射器实例"""
    global _term_mapper
    if _term_mapper is None:
        _term_mapper = TermMapper()
    return _term_mapper

