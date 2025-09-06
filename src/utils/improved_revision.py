# src/utils/improved_revision.py

import logging
from typing import List, Dict, Any
from src.utils.quality_system import QualityMetrics

logger = logging.getLogger(__name__)


def generate_conservative_revision_prompt(
    original_report: str,
    quality_metrics: QualityMetrics,
    target_length: int,
    revision_strategy: str = "conservative"
) -> str:
    """
    生成保守的修订prompt，保护报告的优点
    
    Args:
        original_report: 原始报告
        quality_metrics: 质量评估结果
        target_length: 目标字数
        revision_strategy: 修订策略 (conservative, targeted, aggressive)
    
    Returns:
        改进的修订prompt
    """
    
    # 分析报告的优点和问题
    strengths = _identify_report_strengths(quality_metrics)
    critical_issues = _prioritize_issues(quality_metrics.major_issues)
    
    if revision_strategy == "conservative":
        prompt = _generate_conservative_prompt(
            original_report, strengths, critical_issues, target_length
        )
    elif revision_strategy == "targeted":
        prompt = _generate_targeted_prompt(
            original_report, quality_metrics, target_length
        )
    else:  # aggressive
        prompt = _generate_aggressive_prompt(
            original_report, quality_metrics, target_length
        )
    
    return prompt


def _identify_report_strengths(quality_metrics: QualityMetrics) -> List[str]:
    """识别报告的优点"""
    strengths = []
    
    # 基于详细评分识别优点
    detailed_scores = quality_metrics.detailed_scores
    
    if detailed_scores.get("content_completeness", 0) >= 1.6:
        strengths.append("内容完整性较好")
    
    if detailed_scores.get("logical_clarity", 0) >= 1.6:
        strengths.append("逻辑结构清晰")
    
    if detailed_scores.get("language_expression", 0) >= 1.6:
        strengths.append("语言表达流畅")
    
    if detailed_scores.get("professional_depth", 0) >= 1.6:
        strengths.append("专业深度适当")
    
    if detailed_scores.get("structural_rationality", 0) >= 1.6:
        strengths.append("结构安排合理")
    
    if quality_metrics.word_count_accuracy:
        strengths.append("字数控制准确")
    
    # 如果总分较高，说明整体质量不错
    if quality_metrics.overall_score >= 7.5:
        strengths.append("整体质量良好")
    
    return strengths


def _prioritize_issues(major_issues: List[str]) -> List[str]:
    """优先级排序问题，关键问题优先"""
    # 定义问题重要性权重
    priority_keywords = {
        "事实错误": 10,
        "逻辑错误": 9, 
        "数据错误": 9,
        "内容缺失": 8,
        "结构问题": 7,
        "语言表达": 6,
        "格式问题": 5,
        "字数": 4
    }
    
    # 对问题按重要性排序
    scored_issues = []
    for issue in major_issues:
        score = 0
        for keyword, weight in priority_keywords.items():
            if keyword in issue:
                score = weight
                break
        scored_issues.append((score, issue))
    
    # 按分数降序排列，返回问题列表
    scored_issues.sort(key=lambda x: x[0], reverse=True)
    return [issue for score, issue in scored_issues]


def _generate_conservative_prompt(
    original_report: str,
    strengths: List[str],
    critical_issues: List[str],
    target_length: int
) -> str:
    """生成保守的修订prompt"""
    
    strengths_text = "、".join(strengths) if strengths else "基础质量尚可"
    issues_text = "\n".join([f"- {issue}" for issue in critical_issues[:3]])  # 只关注前3个关键问题
    
    return f"""你是一位专业的报告优化专家，擅长对高质量报告进行精细化改进。

**重要原则：这是一份{strengths_text}的报告，请谨慎修改，保持原有优点**

**原始报告**：
{original_report}

**需要改进的关键问题**（仅针对以下问题进行修改）：
{issues_text}

**修改指导原则**：
1. **保护性修改**：保留报告中的所有优质内容、准确数据和有价值的分析
2. **精准改进**：只针对上述列出的关键问题进行修改，不要大范围重写
3. **增量优化**：在原有基础上改进，而不是推倒重来
4. **质量保证**：修改后的版本必须优于原版本
5. **内容保真**：不要删除或大幅修改高质量的段落和分析

**技术要求**：
- 保持字数在{target_length}字左右（允许±5%的误差）
- 保持原有的专业术语和准确表述
- 保持原有的逻辑结构，除非结构本身有问题
- 不要添加编造的内容或数据

**输出要求**：
- 直接输出改进后的完整报告
- 不要包含修改说明或其他额外信息
- 确保输出是一个完整的、可直接使用的报告

请基于以上原则，对报告进行谨慎的改进。"""


def _generate_targeted_prompt(
    original_report: str,
    quality_metrics: QualityMetrics,
    target_length: int
) -> str:
    """生成针对性修订prompt"""
    
    # 分析具体的改进领域
    improvement_areas = []
    detailed_scores = quality_metrics.detailed_scores
    
    if detailed_scores.get("content_completeness", 0) < 1.5:
        improvement_areas.append("补充内容完整性")
    if detailed_scores.get("logical_clarity", 0) < 1.5:
        improvement_areas.append("改进逻辑清晰度")
    if detailed_scores.get("language_expression", 0) < 1.5:
        improvement_areas.append("优化语言表达")
    if detailed_scores.get("professional_depth", 0) < 1.5:
        improvement_areas.append("增强专业深度")
    if detailed_scores.get("structural_rationality", 0) < 1.5:
        improvement_areas.append("调整结构安排")
    
    areas_text = "、".join(improvement_areas) if improvement_areas else "整体优化"
    issues_text = "\n".join([f"- {issue}" for issue in quality_metrics.major_issues])
    
    return f"""你是一位专业的报告优化专家，请针对性地改进报告质量。

**原始报告**：
{original_report}

**当前质量状况**：
- 总体评分：{quality_metrics.overall_score:.1f}/10
- 主要改进领域：{areas_text}

**具体问题**：
{issues_text}

**针对性改进要求**：
1. **重点改进**：集中精力改进{areas_text}
2. **保留优点**：保持报告中的高质量部分不变
3. **系统优化**：对问题区域进行系统性改进
4. **平衡发展**：确保各个评估维度都达到良好水平

**质量标准**：
- 目标评分：8.5分以上
- 字数要求：{target_length}字左右
- 主要问题：完全解决
- 整体质量：明显优于原版本

请输出改进后的完整报告。"""


def _generate_aggressive_prompt(
    original_report: str,
    quality_metrics: QualityMetrics,
    target_length: int
) -> str:
    """生成激进的修订prompt（适用于质量较差的报告）"""
    
    issues_text = "\n".join([f"- {issue}" for issue in quality_metrics.major_issues])
    
    return f"""你是一位专业的报告重构专家，这份报告需要大幅改进。

**原始报告**（质量评分：{quality_metrics.overall_score:.1f}/10）：
{original_report}

**存在的主要问题**：
{issues_text}

**重构要求**：
1. **大幅改进**：对报告进行系统性重构和优化
2. **全面提升**：在内容、逻辑、表达、专业性等各方面全面提升
3. **保留核心**：保留报告的核心观点和有价值的信息
4. **重新组织**：重新组织结构，确保逻辑清晰
5. **语言优化**：全面改进语言表达的准确性和流畅性

**质量目标**：
- 目标评分：8.0分以上
- 字数要求：{target_length}字左右
- 问题解决：解决所有主要问题
- 质量飞跃：实现质量的显著提升

请输出重构后的高质量报告。"""


def should_use_conservative_revision(quality_metrics: QualityMetrics) -> bool:
    """判断是否应该使用保守的修订策略"""
    # 如果原报告质量较高，使用保守修订
    if quality_metrics.overall_score >= 7.5:
        return True
    
    # 如果只有少数问题，使用保守修订
    if len(quality_metrics.major_issues) <= 2:
        return True
    
    # 如果某些维度评分很高，使用保守修订
    high_score_count = 0
    for score in quality_metrics.detailed_scores.values():
        if score >= 1.7:  # 8.5分对应的分项分数
            high_score_count += 1
    
    if high_score_count >= 3:  # 超过一半维度高分
        return True
    
    return False


def get_revision_strategy(quality_metrics: QualityMetrics) -> str:
    """根据质量评估结果确定修订策略"""
    if should_use_conservative_revision(quality_metrics):
        return "conservative"
    elif quality_metrics.overall_score >= 6.0:
        return "targeted"
    else:
        return "aggressive"
