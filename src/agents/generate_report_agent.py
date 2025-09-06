# src/agents/generate_report_agent.py
"""
最终报告生成代理
负责报告的最终处理、格式化、保存和元数据管理
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from src.core.state import GlobalState, AgentName, ValidationStatus
from src.utils.api_logger import log_workflow_event, log_performance_metric
from src.utils.observability import measure, user_friendly_progress_event
from src.utils.word_count import count_words

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@measure("agent.generate_report")
def generate_report_node(state: GlobalState) -> GlobalState:
    """
    最终报告生成代理节点
    
    功能:
    1. 验证报告完整性
    2. 生成报告元数据
    3. 多格式保存报告
    4. 计算质量指标
    5. 生成报告摘要
    
    Args:
        state: 当前工作流状态
        
    Returns:
        更新后的状态
    """
    logger.info("执行最终报告生成代理")
    
    try:
        user_friendly_progress_event("agent.generate_report", "start")
        
        # 验证输入
        if not state.get("final_report"):
            error_state = {
                **state,
                "current_agent": AgentName.WRITING,  # 使用WRITING作为报告生成agent
                "error_message": "无法生成最终报告：缺少报告内容",
                "validation_status": ValidationStatus.FAILED,
                "last_updated": datetime.now()
            }
            user_friendly_progress_event("agent.generate_report", "error", message="缺少报告内容")
            return GlobalState(**error_state)
        
        final_report = state["final_report"]
        
        # 1. 生成报告元数据
        user_friendly_progress_event("agent.generate_report", "metadata_generation")
        metadata = generate_report_metadata(state)
        
        # 2. 创建输出目录
        output_dir = Path("research_result/reports")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. 生成文件名（基于时间戳和查询摘要）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_summary = generate_query_summary(state["user_query"])
        base_filename = f"{timestamp}_{query_summary}"
        
        # 4. 多格式保存报告
        user_friendly_progress_event("agent.generate_report", "saving_files")
        saved_files = save_report_multiple_formats(
            final_report, metadata, output_dir, base_filename
        )
        
        # 5. 生成报告摘要和统计
        user_friendly_progress_event("agent.generate_report", "statistics")
        report_stats = calculate_report_statistics(final_report, state)
        
        # 6. 保存到传统位置（兼容性）
        legacy_save_report(final_report)
        
        # 7. 更新状态
        updated_state = {
            **state,
            "current_agent": AgentName.WRITING,  # 使用WRITING作为报告生成agent
            "last_updated": datetime.now(),
            "processing_time": state.get("processing_time", 0),
            "quality_metrics": {
                **state.get("quality_metrics", {}),
                **report_stats,
                "report_generation_completed": True,
                "saved_files": saved_files,
                "metadata": metadata
            },
            "warnings": state.get("warnings", [])
        }
        
        logger.info(f"最终报告生成完成，保存了{len(saved_files)}个文件")
        user_friendly_progress_event("agent.generate_report", "done", 
                      files_saved=len(saved_files),
                      word_count=report_stats.get("word_count", 0),
                      output_dir=str(output_dir))
        
        return GlobalState(**updated_state)
        
    except Exception as e:
        logger.error(f"最终报告生成失败: {str(e)}")
        error_state = {
            **state,
            "current_agent": AgentName.WRITING,  # 使用WRITING作为报告生成agent
            "error_message": f"最终报告生成失败: {str(e)}",
            "validation_status": ValidationStatus.FAILED,
            "last_updated": datetime.now()
        }
        user_friendly_progress_event("agent.generate_report", "error", message=str(e))
        return GlobalState(**error_state)


def generate_report_metadata(state: GlobalState) -> Dict[str, Any]:
    """生成报告元数据"""
    try:
        metadata = {
            "report_info": {
                "title": f"研究报告: {state['user_query'][:50]}...",
                "query": state["user_query"],
                "generated_at": datetime.now().isoformat(),
                "word_limit": state.get("word_limit", 0),
                "word_count": count_words(state["final_report"]),
                "revision_count": state.get("revision_count", 0)
            },
            "analysis_info": {
                "domain": getattr(state.get("requirements"), "domain", "未知") if state.get("requirements") else "未知",
                "analysis_intent": getattr(state.get("requirements"), "analysis_intent", "未知") if state.get("requirements") else "未知",
                "validation_status": state.get("validation_status", "unknown")
            },
            "processing_info": {
                "start_time": state.get("start_time", "").isoformat() if hasattr(state.get("start_time", ""), "isoformat") else str(state.get("start_time", "")),
                "processing_duration": f"{state.get('processing_time', 0):.2f}秒",
                "sections_processed": len(state.get("processed_sections", [])),
                "total_searches": state.get("total_search", 0)
            },
            "quality_metrics": state.get("quality_metrics", {}),
            "warnings": state.get("warnings", [])
        }
        return metadata
    except Exception as e:
        logger.warning(f"生成元数据时出错: {e}")
        return {
            "report_info": {
                "generated_at": datetime.now().isoformat(),
                "error": f"元数据生成失败: {str(e)}"
            }
        }


def generate_query_summary(query: str) -> str:
    """生成查询摘要用于文件命名"""
    try:
        # 清理查询文本，保留核心关键词
        import re
        # 移除标点符号
        clean_query = re.sub(r'[^\w\s]', '', query)
        # 分词并取前3个有意义的词
        words = clean_query.split()[:3]
        summary = "_".join(words) if words else "research"
        # 限制长度
        return summary[:30]
    except Exception:
        return "research_report"


def save_report_multiple_formats(
    report: str, 
    metadata: Dict[str, Any], 
    output_dir: Path, 
    base_filename: str
) -> List[str]:
    """保存多种格式的报告"""
    saved_files = []
    
    try:
        # 1. 保存纯文本格式
        txt_file = output_dir / f"{base_filename}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(report)
        saved_files.append(str(txt_file))
        
        # 2. 保存带元数据的JSON格式
        json_file = output_dir / f"{base_filename}_full.json"
        full_data = {
            "metadata": metadata,
            "content": report
        }
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, ensure_ascii=False, indent=2)
        saved_files.append(str(json_file))
        
        # 3. 保存元数据文件
        meta_file = output_dir / f"{base_filename}_metadata.json"
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        saved_files.append(str(meta_file))
        
        logger.info(f"成功保存{len(saved_files)}个文件到 {output_dir}")
        return saved_files
        
    except Exception as e:
        logger.error(f"保存多格式报告失败: {e}")
        # 至少尝试保存基本的文本文件
        try:
            basic_file = output_dir / f"{base_filename}_basic.txt"
            with open(basic_file, 'w', encoding='utf-8') as f:
                f.write(report)
            return [str(basic_file)]
        except Exception as e2:
            logger.error(f"保存基本文件也失败: {e2}")
            return []


def calculate_report_statistics(report: str, state: GlobalState) -> Dict[str, Any]:
    """计算报告统计信息"""
    try:
        word_count = count_words(report)
        char_count = len(report)
        target_words = state.get("word_limit", 0)
        
        # 计算完成率
        completion_rate = (word_count / target_words * 100) if target_words > 0 else 100
        
        # 分析报告结构
        lines = report.split('\n')
        paragraphs = [line.strip() for line in lines if line.strip()]
        
        # 统计标题数量（简单检测）
        headers = len([line for line in lines if line.strip().startswith('#') or 
                      any(keyword in line for keyword in ['摘要', '概述', '分析', '结论', '建议'])])
        
        stats = {
            "word_count": word_count,
            "character_count": char_count,
            "target_word_count": target_words,
            "completion_rate": round(completion_rate, 1),
            "paragraph_count": len(paragraphs),
            "estimated_headers": headers,
            "lines_count": len(lines),
            "average_paragraph_length": round(word_count / len(paragraphs)) if paragraphs else 0
        }
        
        return stats
        
    except Exception as e:
        logger.warning(f"计算报告统计信息失败: {e}")
        return {
            "word_count": len(report.split()) if report else 0,
            "error": f"统计计算失败: {str(e)}"
        }


def legacy_save_report(report: str) -> None:
    """保存到传统位置以保持兼容性"""
    try:
        # 保持原有的保存逻辑
        os.makedirs("research_result", exist_ok=True)
        with open('research_result/result.txt', 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info("已保存到传统位置: research_result/result.txt")
    except Exception as e:
        logger.warning(f"保存到传统位置失败: {e}")
