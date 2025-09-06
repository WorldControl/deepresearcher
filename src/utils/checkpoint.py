import json
from datetime import datetime
from typing import Any, Dict

from src.core.state import (
    GlobalState,
    AnalysisQuery,
    ReportStructure,
    ValidationStatus,
    AgentName,
    AnalysisIntent,
)


def _serialize_datetime(value: datetime) -> str:
    return value.isoformat()


def _deserialize_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def serialize_state(state: GlobalState) -> Dict[str, Any]:
    """将 GlobalState 转换为可 JSON 序列化的字典。"""
    def to_serializable(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, datetime):
            return _serialize_datetime(value)
        if isinstance(value, ValidationStatus):
            return value.value
        if isinstance(value, AgentName):
            return value.value
        if isinstance(value, AnalysisQuery):
            return value.model_dump()
        if isinstance(value, ReportStructure):
            return value.model_dump()
        if isinstance(value, list):
            return [to_serializable(v) for v in value]
        if isinstance(value, dict):
            return {k: to_serializable(v) for k, v in value.items()}
        return value

    return {k: to_serializable(v) for k, v in state.items() if v is not None}


def deserialize_state(data: Dict[str, Any]) -> GlobalState:
    """从 JSON 字典恢复为 GlobalState。"""
    def coerce_analysis_intent(value: Any) -> AnalysisIntent:
        if isinstance(value, AnalysisIntent):
            return value
        if isinstance(value, str):
            # 允许多种写法：枚举值、名称、中文别名
            normalized = value.strip().lower()
            alias_map = {
                "概览": "overview",
                "总体概览": "overview",
                "overview": "overview",
                "对比": "comparison",
                "比较": "comparison",
                "comparison": "comparison",
                "因果分析": "causal_analysis",
                "因果": "causal_analysis",
                "causal_analysis": "causal_analysis",
                "趋势预测": "trend_prediction",
                "预测": "trend_prediction",
                "trend_prediction": "trend_prediction",
                "利弊评估": "pros_cons",
                "优缺点": "pros_cons",
                "pros_cons": "pros_cons",
                "解决方案": "solution_proposal",
                "方案建议": "solution_proposal",
                "solution_proposal": "solution_proposal",
            }
            target = alias_map.get(normalized, normalized)
            try:
                return AnalysisIntent(target)
            except Exception:
                # 回退：尝试用名称匹配
                for item in AnalysisIntent:
                    if item.name.lower() == normalized:
                        return item
        # 无法识别时默认用概览，避免恢复失败
        return AnalysisIntent.OVERVIEW
    def from_serializable(key: str, value: Any) -> Any:
        if value is None:
            return None
        if key in {"start_time", "last_updated"} and isinstance(value, str):
            return _deserialize_datetime(value)
        if key == "validation_status" and isinstance(value, str):
            return ValidationStatus(value)
        if key == "current_agent" and isinstance(value, str):
            return AgentName(value)
        if key == "requirements" and isinstance(value, dict):
            patched = dict(value)
            if "analysis_intent" in patched:
                patched["analysis_intent"] = coerce_analysis_intent(patched["analysis_intent"]).value
            return AnalysisQuery(**patched)
        if key == "structure" and isinstance(value, dict):
            return ReportStructure(**value)
        return value

    restored: Dict[str, Any] = {}
    for k, v in data.items():
        restored[k] = from_serializable(k, v)
    # 类型提示为 GlobalState（TypedDict）
    return restored  # type: ignore[return-value]


def save_checkpoint(state: GlobalState, path: str) -> None:
    try:
        payload = {
            "state": serialize_state(state),
            "meta": {
                "saved_at": datetime.now().isoformat(),
                "version": 1,
            },
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        # 如果序列化失败，记录错误但不中断流程
        import logging
        logging.error(f"保存 checkpoint 失败: {e}")


def load_checkpoint(path: str) -> GlobalState:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    data = payload.get("state", payload)
    return deserialize_state(data)


