"""
核心状态模型定义，定义了整个工作流中各个智能体间传递的数据结构
"""
from datetime import datetime
from typing import List, Optional, Literal, TypedDict, Dict
from pydantic import BaseModel, Field
from enum import Enum

import uuid
from typing import Literal, Any
from dataclasses import dataclass, field


@dataclass
class Doc:
    """文档数据类"""
    doc_type: Literal["web_page"]
    content: str
    title: str
    link: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    unique_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    is_chunk: bool = False
    chunk_id: int = -1  # chunk标记

    def __str__(self):
        doc_type_map = {
            "web_page": "网页",
        }

        return (
            f"Doc(\n"
            f"  文档类型={doc_type_map.get(self.doc_type, self.doc_type)},\n"
            f"  文档标题={self.title},\n"
            f"  文档链接={self.link},\n"
            f"  文档内容={self.content},\n"
            f")"
        )

    def to_html(self):
        return (
            f"<div>\n"
            f"  <p>文档类型:{self.doc_type}</p>\n"
            f"  <p>文档标题:{self.title}</p>\n"
            f"  <p>文档链接:{self.link}</p>\n"
            f"  <p>文档内容:{self.content}</p>\n"
            f"</div>"
        )

    def to_dict(self, truncate_len: int = 0):
        content = self.content[0:truncate_len] if truncate_len > 0 else self.content
        return {
            "doc_type": self.doc_type,
            "content": content,
            "title": self.title,
            "link": self.link,
            "data": self.data,
        }


class AnalysisIntent(str, Enum):
    OVERVIEW = "overview"
    COMPARISON = "comparison"
    CAUSAL_ANALYSIS = "causal_analysis"
    TREND_PREDICTION = "trend_prediction"
    PROS_CONS = "pros_cons"
    SOLUTION_PROPOSAL = "solution_proposal"


class DomainCategory(str, Enum):
    AI = "前沿科技与人工智能"  # Cutting-Edge Tech & AI
    BUSINESS_MODEL = "商业模式与市场动态"  # Business Models & Market Dynamics
    SUSTAINABILITY = "可持续发展与环境治理"  # Sustainability & Environmental Governance
    SOCIAL_CHANGE = "社会变迁与文化趋势"  # Social Change & Cultural Trends
    LIFE_SCIENCES = "生命科学与公共健康"  # Life Sciences & Public Health
    GLOBAL_AFFAIRS = "全球事务与未来治理"  # Global Affairs & Future Governance
    GENERAL = "通用"  # 除以上六大类比之外的领域


class ValidationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VALIDATED = "validated"
    NEEDS_REVISION = "needs_revision"
    FAILED = "failed"


class AgentName(str, Enum):
    COORDINATOR = "chief_coordinator_agent" # 主控agent
    UNDERSTANDING = "problem_understanding_agent"
    STRUCTURING = "report_structure_planning_agent"
    KNOWLEDGE = "knowledge_retrieval_agent"
    WRITING = "report_writing_agent"
    VALIDATION = "validation_agent"
    REVISION = "revision_agent"


class AnalysisQuery(BaseModel):
    """
    用户提问解析结果的结构化表示
    由问题解析和意图理解Agent生成
    """
    domain: DomainCategory  # 所属领域类别
    analysis_intent: AnalysisIntent
    # keywords: List[str] = Field(
    #     description="题目中的核心关键词"
    # )
    # entities: List[str] = Field(
    #     description="题目中出现的重要实体（公司，技术，事件等）"
    # )


class ReportSection(BaseModel):
    """报告单个章节的内容结构"""
    title: str  # 章节标题
    key_questions: List[str]  # 本章节需要回答的关键问题
    content: str  # 章节内容
    sources: List[str] = []  # 引用来源列表
    status: Literal[
        "outlined", "researching", "drafted", "polished"] = "outlined"  # 章节状态：已规划/研究中/已起草/已润色


class ReportStructure(BaseModel):
    """报告结构大纲的结构化表示"""
    template_type: str  # 使用的报告模板类型
    sections: List[ReportSection]  # 所有章节的列表
    executive_summary_required: bool = True  # 是否需要执行摘要
    recommendations_required: bool = True  # 是否需要建议部分
    target_length: int  # 目标长度，如"2000字"、"5页"
    length_tolerance: int = 0


class GlobalState(TypedDict):
    """智能体的状态定义规则：
状态是系统在特定时间点的完整快照，包含了所有必要信息来：
描述当前情况
决定下一步行动
记录历史过程
支持错误恢复

2. 状态设计的关键考量
完整性	状态应包含所有必要信息	  包含原始查询、解析结果、中间成果和最终输出
一致性	状态结构应在整个系统中保持一致	使用统一的数据模型和命名规范
可序列化	状态应能轻松转换为JSON等格式	使用基本数据类型和可序列化对象
可追溯性	状态变化应有清晰的历史记录	包含时间戳和修订计数
容错性	状态应支持错误处理和恢复	包含错误信息和验证状态
    """
    # 原始查询
    user_query: str  # 用户输入的原始查询题目

    # 解析成果
    requirements: Optional[AnalysisQuery]  # 题目解析后的需求说明

    # 输出相关
    structure: Optional[ReportStructure]  # 报告结构规划
    draft_report: Optional[str]  # 报告草稿
    final_report: Optional[str]  # 最终报告

    # 处理过程相关
    validation_status: ValidationStatus  # 整体验证状态
    revision_count: int = 0  # 修订次数计数
    current_agent: AgentName  # 当前正在执行的智能体
    active_section: Optional[str]  # 当前正在处理的章节标题
    processed_sections: List[str]  # 已处理完成的章节标题列表

    # 元数据相关
    start_time: datetime  # 任务开始时间
    last_updated: datetime  # 最后更新时间
    error_message: Optional[str]  # 错误信息（如有）
    warnings: List[str]  # 警告信息列表

    total_search_per_section: Dict[str, int]  # 记录每个section已经搜索的次数
    total_search: int  # 所有问题搜索的总次数

    # 性能与质量追踪
    quality_metrics: Dict[
        str, float]  # 质量指标字典，如{"coherence_score": 0.85, "fact_accuracy": 0.92}
    processing_time: Optional[float]  # 总处理时间（秒）

    word_limit: int
