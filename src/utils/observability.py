import asyncio
import json
import logging
import os
import time
from datetime import datetime
from functools import wraps
from typing import Any, Callable


_METRICS_DIR = os.path.join(os.getcwd(), "research_result")
_METRICS_FILE = os.path.join(_METRICS_DIR, "metrics.jsonl")
os.makedirs(_METRICS_DIR, exist_ok=True)


def _append_metrics(payload: dict) -> None:
    try:
        with open(_METRICS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def log_event(event: str, **fields: Any) -> None:
    payload = {"ts": datetime.now().isoformat(), "event": event, **fields}
    logging.getLogger(__name__).info(json.dumps(payload, ensure_ascii=False))
    _append_metrics(payload)


def measure(operation: str) -> Callable:
    """同时输出结构化日志与基础指标的计时装饰器。

    支持同步/异步函数。
    字段：operation、duration_ms、success、exception(optional)。
    """

    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    duration = (time.perf_counter() - start) * 1000.0
                    log_event(
                        "measure",
                        operation=operation,
                        duration_ms=round(duration, 2),
                        success=True,
                    )
                    return result
                except Exception as e:  # noqa: BLE001
                    duration = (time.perf_counter() - start) * 1000.0
                    log_event(
                        "measure",
                        operation=operation,
                        duration_ms=round(duration, 2),
                        success=False,
                        exception=str(e),
                    )
                    raise

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = (time.perf_counter() - start) * 1000.0
                log_event(
                    "measure",
                    operation=operation,
                    duration_ms=round(duration, 2),
                    success=True,
                )
                return result
            except Exception as e:  # noqa: BLE001
                duration = (time.perf_counter() - start) * 1000.0
                log_event(
                    "measure",
                    operation=operation,
                    duration_ms=round(duration, 2),
                    success=False,
                    exception=str(e),
                )
                raise

        return sync_wrapper

    return decorator


def progress_event(operation: str, phase: str, **fields: Any) -> None:
    """记录阶段性进度事件（写入 metrics.jsonl 并打印 JSON）。"""
    log_event("phase", operation=operation, phase=phase, **fields)


def user_friendly_progress_event(operation: str, phase: str, **fields: Any) -> None:
    """记录用户友好的进度事件，提供可读性强的进度信息。"""
    # 定义用户友好的操作名称映射
    operation_names = {
        "agent.problem_understanding": "问题理解",
        "agent.structure_planning": "结构规划",
        "agent.knowledge_retrieval": "知识检索",
        "agent.writing_polishing": "报告撰写",
        "agent.validation": "质量校验",
        "agent.revision": "内容修订",
        "external.deep_search.run": "外部搜索",
        "quality.evaluation": "质量评估",
        "agent.report_writing": "报告撰写",
        "agent.generate_report": "生成报告"
    }

    # 定义用户友好的阶段名称映射
    phase_names = {
        "start": "开始",
        "skip": "跳过",
        "llm_call": "AI分析中",
        "parse_result": "解析结果",
        "done": "完成",
        "error": "出错",
        "external_search_start": "开始搜索",
        "external_search_done": "搜索完成",
        "section_done": "章节完成",
        "quality_evaluation": "质量评估",
        "llm_call_smart_revision": "智能修订",
        "llm_call_traditional_revision": "传统修订",
        "score_comparison": "评分对比"
    }

    # 构建用户友好的消息
    operation_name = operation_names.get(operation, operation)
    phase_name = phase_names.get(phase, phase)

    # 根据不同的操作和阶段构建具体消息
    message = ""
    if operation == "agent.problem_understanding":
        if phase == "start":
            message = "正在分析您的问题..."
        elif phase == "llm_call":
            message = "正在理解问题的核心要点..."
        elif phase == "parse_result":
            domain = fields.get("domain", "未知领域")
            intent = fields.get("intent", "未知类型")
            message = f"识别到：{domain}领域的{intent}分析"
        elif phase == "done":
            message = "问题理解完成"

    elif operation == "agent.structure_planning":
        if phase == "start":
            message = "正在规划报告结构..."
        elif phase == "llm_call":
            message = "正在设计章节大纲..."
        elif phase == "parse_result":
            count = fields.get("sections_count", 0)
            message = f"规划了{count}个章节"
        elif phase == "done":
            message = "报告结构规划完成"

    elif operation == "agent.knowledge_retrieval":
        if phase == "external_search_start":
            message = "正在搜索相关资料..."
        elif phase == "external_search_done":
            docs = fields.get("docs", 0)
            message = f"找到了{docs}个相关文档"
        elif phase == "section_done":
            title = fields.get("title", "")
            message = f"完成了章节：{title}"
        elif phase == "start":
            message = "正在生成报告内容..."
        elif phase == "done":
            message = "内容生成完成"

    elif operation == "agent.writing_polishing":
        if phase == "start":
            message = "正在润色报告..."
        elif phase == "llm_call":
            message = "正在优化语言表达..."
        elif phase == "done":
            word_count = fields.get("word_count", 0)
            target = fields.get("target_word_limit", 0)
            message = f"报告撰写完成（{word_count}字，目标{target}字）"

    elif operation == "agent.validation":
        if phase == "start":
            message = "正在检查报告质量..."
        elif phase == "llm_call":
            message = "正在评估内容质量..."
        elif phase == "parse_result":
            score = fields.get("score", 0)
            message = f"质量评分：{score}/10"
        elif phase == "done":
            status = fields.get("status", "")
            if status == "validated":
                message = "质量检查通过"
            else:
                message = "需要进一步优化"

    elif operation == "agent.revision":
        if phase == "start":
            message = "正在修订报告..."
        elif phase == "llm_call":
            message = "正在优化内容..."
        elif phase == "llm_call_smart_revision":
            strategy = fields.get("strategy", "智能")
            message = f"正在执行{strategy}修订..."
        elif phase == "score_comparison":
            original_score = fields.get("original_score", 0)
            revised_score = fields.get("revised_score", 0)
            decision = fields.get("decision", "")
            if decision == "keep_revised":
                message = f"修订提升效果显著（{original_score:.1f}→{revised_score:.1f}）"
            else:
                message = f"保留原版本（修订后：{revised_score:.1f}，原版：{original_score:.1f}）"
        elif phase == "done":
            count = fields.get("revision_count", 0)
            message = f"完成第{count}轮修订"

    elif operation == "quality.evaluation":
        if phase == "start":
            method = fields.get("method", "标准")
            message = f"开始{method}质量评估..."
        elif phase == "llm_call":
            message = "正在分析报告质量..."
        elif phase == "parse_result":
            message = "正在解析评估结果..."
        elif phase == "done":
            score = fields.get("score", 0)
            message = f"评估完成（评分：{score:.1f}/10）"
    
    elif operation == "agent.report_writing":
        if phase == "start":
            message = "开始报告撰写..."
        elif phase == "llm_call":
            message = "正在生成报告内容..."
        elif phase == "done":
            message = "报告撰写完成"
    
    elif operation == "agent.generate_report":
        if phase == "start":
            message = "开始生成最终报告..."
        elif phase == "done":
            message = "最终报告生成完成"

    # 如果没有特定消息，使用通用格式
    if not message:
        message = f"{operation_name}：{phase_name}"

    # 记录用户友好的进度事件
    # 从fields中移除message字段，避免重复
    clean_fields = {k: v for k, v in fields.items() if k != "message"}
    log_event("user_progress", operation=operation_name, phase=phase_name, message=message, **clean_fields)


