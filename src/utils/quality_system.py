# src/utils/quality_system.py
"""
统一的质量评估系统
负责对报告进行全面的质量评估
"""

import ast
import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional

from src.llm_adapter import llm_client
from src.utils import rm_only_think
from src.utils.observability import user_friendly_progress_event
from src.utils.word_count import count_words

# 配置日志
logger = logging.getLogger(__name__)


class QualityMetrics:
    """质量评估结果"""
    def __init__(self, 
                 overall_score: float,
                 detailed_scores: Dict[str, float],
                 major_issues: List[str],
                 feedback: str,
                 word_count_accuracy: bool,
                 actual_word_count: int,
                 evaluation_method: str = "standard"):
        self.overall_score = overall_score
        self.detailed_scores = detailed_scores
        self.major_issues = major_issues
        self.feedback = feedback
        self.word_count_accuracy = word_count_accuracy
        self.actual_word_count = actual_word_count
        self.evaluation_method = evaluation_method
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "overall_score": self.overall_score,
            "detailed_scores": self.detailed_scores,
            "major_issues": self.major_issues,
            "feedback": self.feedback,
            "word_count_accuracy": self.word_count_accuracy,
            "actual_word_count": self.actual_word_count,
            "evaluation_method": self.evaluation_method,
            "timestamp": self.timestamp.isoformat()
        }
    
    def is_high_quality(self) -> bool:
        """判断是否为高质量报告（8.3分以上）"""
        return self.overall_score >= 8.3
    
    def is_acceptable_quality(self) -> bool:
        """判断是否为可接受质量（8.0分以上且无主要问题）"""
        return self.overall_score >= 8.0 and len(self.major_issues) == 0


class UnifiedQualityEvaluator:
    """统一的质量评估器"""
    
    def __init__(self):
        self.evaluation_prompt_template = """
请对以下报告进行全面的质量评估。

评估标准（每项2分，总分10分）：
1. 内容完整性（2分）：信息是否全面、深入，有无重要遗漏
2. 逻辑清晰度（2分）：结构是否清晰，论述是否有逻辑性
3. 语言表达（2分）：语言是否准确、流畅、专业
4. 专业深度（2分）：分析是否深入，是否体现专业水准
5. 结构合理性（2分）：章节安排是否合理，层次是否分明

评估要求：
- 给出0-10的整体评分（允许小数点后1位）
- 列出所有主要问题（影响报告质量的重要缺陷）
- 提供具体的改进建议
- 评估字数是否符合要求：目标字数 {word_limit}

报告内容：
{report}

请严格按照以下JSON格式输出评估结果：
{{
    "overall_score": 8.5,
    "detailed_scores": {{
        "content_completeness": 1.8,
        "logical_clarity": 1.7,
        "language_expression": 1.9,
        "professional_depth": 1.6,
        "structural_rationality": 1.5
    }},
    "major_issues": [
        "缺少具体的数据支撑",
        "结论部分论述不够充分"
    ],
    "feedback": "报告整体质量良好，但在数据支撑和结论论述方面有待改进。建议增加更多实证数据，加强结论的逻辑性。",
    "word_count_assessment": "字数基本符合要求"
}}
"""
    
    async def _get_llm_response(self, prompt: str) -> str:
        """获取LLM响应"""
        response_content = ""
        async for chunk in llm_client.generate(prompt):
            response_content += chunk
        return response_content
    
    def _parse_evaluation_response(self, response: str) -> Dict[str, Any]:
        """解析评估响应"""
        # 清理响应
        response = rm_only_think(response)
        
        # 尝试多种解析方法
        evaluation_result = None
        
        # 方法1: 直接JSON解析
        try:
            evaluation_result = json.loads(response)
        except Exception:
            pass
        
        # 方法2: 提取JSON片段
        if evaluation_result is None:
            try:
                start = response.find("{")
                end = response.rfind("}")
                if start != -1 and end != -1 and end > start:
                    evaluation_result = json.loads(response[start:end+1])
            except Exception:
                pass
        
        # 方法3: literal_eval
        if evaluation_result is None:
            try:
                evaluation_result = ast.literal_eval(response)
            except Exception:
                pass
        
        # 方法4: 正则表达式提取关键信息
        if evaluation_result is None:
            try:
                # 提取评分
                score_match = re.search(r'"overall_score":\s*(\d+\.?\d*)', response)
                overall_score = float(score_match.group(1)) if score_match else 5.0
                
                # 提取主要问题
                issues_match = re.search(r'"major_issues":\s*\[(.*?)\]', response, re.DOTALL)
                major_issues = []
                if issues_match:
                    issues_text = issues_match.group(1)
                    # 简单解析问题列表
                    for line in issues_text.split('\n'):
                        line = line.strip().strip(',').strip('"')
                        if line and not line.startswith('//'):
                            major_issues.append(line)
                
                # 提取反馈
                feedback_match = re.search(r'"feedback":\s*"(.*?)"', response, re.DOTALL)
                feedback = feedback_match.group(1) if feedback_match else "评估反馈解析失败"
                
                evaluation_result = {
                    "overall_score": overall_score,
                    "detailed_scores": {
                        "content_completeness": overall_score * 0.2,
                        "logical_clarity": overall_score * 0.2,
                        "language_expression": overall_score * 0.2,
                        "professional_depth": overall_score * 0.2,
                        "structural_rationality": overall_score * 0.2
                    },
                    "major_issues": major_issues,
                    "feedback": feedback,
                    "word_count_assessment": "需要人工检查"
                }
            except Exception:
                pass
        
        # 默认结果
        if evaluation_result is None:
            evaluation_result = {
                "overall_score": 5.0,
                "detailed_scores": {
                    "content_completeness": 1.0,
                    "logical_clarity": 1.0,
                    "language_expression": 1.0,
                    "professional_depth": 1.0,
                    "structural_rationality": 1.0
                },
                "major_issues": ["评估结果解析失败"],
                "feedback": "输出格式不标准，无法准确评估，建议重新评估。"
            }
        
        return evaluation_result
    
    async def evaluate_report_async(self, report: str, word_limit: Optional[int] = None, 
                                  evaluation_method: str = "standard") -> QualityMetrics:
        """异步评估报告质量"""
        try:
            user_friendly_progress_event("quality.evaluation", "start", method=evaluation_method)
            
            # 构建提示词
            prompt = self.evaluation_prompt_template.format(
                report=report,
                word_limit=word_limit or "无限制"
            )
            
            # 获取LLM评估
            user_friendly_progress_event("quality.evaluation", "llm_call")
            response = await self._get_llm_response(prompt)
            logger.info(f"质量评估原始结果：{response}")
            
            # 解析评估结果
            user_friendly_progress_event("quality.evaluation", "parse_result")
            evaluation_result = self._parse_evaluation_response(response)
            logger.info(f"质量评估解析结果：{evaluation_result}")
            
            # 检查字数准确性（严格±5%）
            actual_word_count = count_words(report)
            if word_limit is None:
                word_count_accuracy = True
            else:
                lower = int(word_limit * 0.95)
                upper = int(word_limit * 1.05)
                word_count_accuracy = lower <= actual_word_count <= upper
            
            # 创建质量指标对象
            quality_metrics = QualityMetrics(
                overall_score=float(evaluation_result.get("overall_score", 5.0)),
                detailed_scores=evaluation_result.get("detailed_scores", {}),
                major_issues=evaluation_result.get("major_issues", []),
                feedback=evaluation_result.get("feedback", ""),
                word_count_accuracy=word_count_accuracy,
                actual_word_count=actual_word_count,
                evaluation_method=evaluation_method
            )
            
            user_friendly_progress_event("quality.evaluation", "done", 
                          score=quality_metrics.overall_score,
                          major_issues_count=len(quality_metrics.major_issues),
                          word_count=actual_word_count)
            
            logger.info(f"质量评估完成：评分{quality_metrics.overall_score:.1f}，"
                       f"主要问题{len(quality_metrics.major_issues)}个")
            
            return quality_metrics
            
        except Exception as e:
            logger.error(f"质量评估失败: {str(e)}")
            user_friendly_progress_event("quality.evaluation", "error", message=str(e))
            
            # 返回默认的低分评估
            return QualityMetrics(
                overall_score=0.0,
                detailed_scores={},
                major_issues=[f"评估过程出错: {str(e)}"],
                feedback="评估系统出现错误，无法完成评估。",
                word_count_accuracy=False,
                actual_word_count=len(report),
                evaluation_method=evaluation_method
            )
    
    def evaluate_report(self, report: str, word_limit: Optional[int] = None,
                       evaluation_method: str = "standard") -> QualityMetrics:
        """同步评估报告质量"""
        return asyncio.run(self.evaluate_report_async(report, word_limit, evaluation_method))


# 全局评估器实例
quality_evaluator = UnifiedQualityEvaluator()


def evaluate_report_quality(report: str, word_limit: Optional[int] = None,
                           evaluation_method: str = "standard") -> QualityMetrics:
    """
    评估报告质量的便捷函数
    
    Args:
        report: 报告内容
        word_limit: 字数限制
        evaluation_method: 评估方法标识
    
    Returns:
        QualityMetrics: 质量评估结果
    """
    return quality_evaluator.evaluate_report(report, word_limit, evaluation_method)


def should_report_pass_quality_check(quality_metrics: QualityMetrics) -> bool:
    """
    判断报告是否通过质量检查
    
    Args:
        quality_metrics: 质量评估结果
    
    Returns:
        bool: 是否通过质量检查
    """
    # 高质量报告直接通过
    if quality_metrics.is_high_quality():
        logger.info(f"高质量报告（{quality_metrics.overall_score:.1f}分），直接通过")
        return True
    
    # 可接受质量报告通过
    if quality_metrics.is_acceptable_quality():
        logger.info(f"可接受质量报告（{quality_metrics.overall_score:.1f}分，无主要问题），通过")
        return True
    
    # 其他情况不通过
    logger.info(f"报告质量不足（{quality_metrics.overall_score:.1f}分，"
               f"{len(quality_metrics.major_issues)}个主要问题），需要修订")
    return False
