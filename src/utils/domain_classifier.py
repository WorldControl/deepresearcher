from typing import Tuple, List, Dict, Optional

from configs.domains import domain_keywords
from configs.intent import intent_keywords
from src.core.state import DomainCategory, AnalysisIntent


def calculate_keyword_scores(query: str, keywords: List[str]) -> Tuple[int, List[str]]:
    matched_keywords = []

    query_lower = query.lower()
    for keyword in keywords:
        if keyword in query_lower:
            matched_keywords.append(keyword)

    return len(matched_keywords), matched_keywords


def classify_domain_rule_based(
        query: str) -> Tuple[Optional[DomainCategory], float, List[str]]:
    """
    基于规则的领域分类函数
    使用关键词匹配和置信度评估来确定题目所属领域

    计算流程：
    1. 关键词匹配计分
    2. 基础置信度计算
    3. 主导领域增强
    4. 结果返回

    Args:
        query: 用户输入的报告题目

    Returns:
        (领域, 置信度, 匹配的关键词)
    """
    query_lower = query.lower()
    scores: Dict[str, int] = {}
    matched_keywords_all: Dict[str, List[str]] = {}
    for domain, keywords in domain_keywords.items():
        score, matched_keywords = calculate_keyword_scores(query_lower, keywords)
        scores[domain] = score
        matched_keywords_all[domain] = matched_keywords

    if not scores or max(scores.values()) == 0:
        return None, 0.0, []

    best_domain = max(scores, key=scores.get)
    max_score = scores[best_domain]

    # 步骤5: 计算基础置信度分数 (0.0-1.0)
    # 计算规则: 匹配关键词数量 ÷ 5，但不超过1.0
    # 为什么除以5？
    # - 经验值：匹配5个关键词通常表示很强的相关性
    # - 提供合理的置信度缩放：
    #   * 匹配1个关键词 → 置信度0.2（低）
    #   * 匹配3个关键词 → 置信度0.6（中等）
    #   * 匹配5个以上 → 置信度1.0（高）
    # - 避免少量关键词就给出高置信度
    confidence = min(max_score / 5, 1.0)

    other_scores = [s for d, s in scores.items() if d != best_domain]

    # 只有当存在其他领域且最佳领域得分明显占优时才增强
    if other_scores and max_score > max(other_scores) * 2:
        # 增强规则: 置信度 × 1.5，但不超过1.0
        # 为什么乘以1.5？
        # - 适度增强，避免过度自信
        # - 从0.8 → 1.0，从0.6 → 0.9等
        # - 保持一定的保守性
        #
        # 为什么需要主导领域检测？
        # - 避免平局情况：当两个领域得分接近时，不应给予高置信度
        # - 奖励明显优势：当某个领域明显更相关时，给予更高置信度
        #
        # 示例：
        # 情况1（平局）: [A:3, B:2, C:1] → 不增强（3 < 2×2）
        # 情况2（优势）: [A:4, B:1, C:1] → 增强（4 > 1×2）
        confidence = min(confidence * 1.5, 1.0)

    return DomainCategory(best_domain), confidence, matched_keywords_all[best_domain]


def classify_intent_rule_based(
        query: str) -> Tuple[
    Optional[AnalysisIntent], float, List[str]]:
    """
    基于规则的意图分类
    """
    query_lower = query.lower()
    scores = {}
    matched_keywords_all = {}

    for intent, keywords in intent_keywords.items():
        score, matched_keywords = calculate_keyword_scores(query_lower, keywords)
        scores[intent] = score
        matched_keywords_all[intent] = matched_keywords

    if not scores or max(scores.values()) == 0:
        return None, 0.0, []

    best_intent = max(scores, key=scores.get)
    max_score = scores[best_intent]

    # 计算置信度
    confidence = min(max_score / 3, 1.0)

    # 如果有明显主导的意图，提高置信度
    other_scores = [score for intent, score in scores.items() if
                    intent != best_intent]
    if other_scores and max_score > max(other_scores) * 2:
        confidence = min(confidence * 1.5, 1.0)

    return AnalysisIntent(best_intent), confidence, matched_keywords_all[
        best_intent]