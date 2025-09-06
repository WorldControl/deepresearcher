import json
import os
import queue
import threading
import time
import traceback
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import create_init_state
from src.core.graph import create_graph
from src.core.state import GlobalState
from src.utils.api_logger import (
    log_api_request, log_api_response, log_workflow_event, 
    log_checkpoint_operation, log_error, log_performance_metric
)
from src.utils.checkpoint import load_checkpoint, save_checkpoint
from src.utils.word_count import count_words


class RunRequest(BaseModel):
    query: Optional[str] = Field(default=None, description="用户查询内容；当 resume=true 时可为空")
    checkpoint: str = Field(default=os.path.join(os.getcwd(), "research_result", "checkpoint.json"))
    resume: bool = Field(default=False)
    word_limit: Optional[int] = Field(default=None)
    stream: bool = Field(default=False, description="是否以流式返回处理进度（SSE/json lines）")


class RunResponse(BaseModel):
    success: bool
    message: str
    final_report: Optional[str] = None
    state: Optional[Dict[str, Any]] = None


app = FastAPI(title="Deep Researcher API", version="0.1.0")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/checkpoint/exists")
def checkpoint_exists(path: str) -> Dict[str, Any]:
    """检查指定路径的检查点文件是否存在。"""
    try:
        return {"exists": os.path.exists(path), "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run", response_model=RunResponse)
async def run_workflow(req: RunRequest, request: Request):
    start_time = time.time()
    
    try:
        # 记录API请求
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        log_api_request("POST", "/run", req.dict(), user_agent, client_ip)
        
        os.makedirs(os.path.dirname(req.checkpoint), exist_ok=True)

        app_graph = create_graph()

        if req.resume and os.path.exists(req.checkpoint):
            state: GlobalState = load_checkpoint(req.checkpoint)
            log_checkpoint_operation("load", req.checkpoint, True)
        else:
            if not req.query:
                error_msg = "query 不能为空，或者设置 resume=true 并提供有效 checkpoint"
                log_error("VALIDATION_ERROR", error_msg)
                raise HTTPException(status_code=400, detail=error_msg)
            state = create_init_state(req.query)
            if req.word_limit:
                state["word_limit"] = req.word_limit

        # 流式返回处理进度
        if req.stream:
            def event_stream():
                steps_done = 0
                last_state_local: Optional[GlobalState] = None

                q: "queue.Queue[str]" = queue.Queue()
                stop_event = threading.Event()
                metrics_path = os.path.join(os.getcwd(), "research_result", "metrics.jsonl")
                
                log_workflow_event("stream_start", "workflow", "开始流式处理")

                def tail_metrics():
                    try:
                        # 确保文件存在
                        os.makedirs(os.path.dirname(metrics_path), exist_ok=True)
                        open(metrics_path, "a").close()
                        with open(metrics_path, "r", encoding="utf-8") as f:
                            f.seek(0, os.SEEK_END)
                            while not stop_event.is_set():
                                pos = f.tell()
                                line = f.readline()
                                if not line:
                                    time.sleep(0.2)
                                    f.seek(pos)
                                    continue
                                # 仅透传 phase 事件
                                try:
                                    payload = json.loads(line)
                                    if payload.get("event") == "phase":
                                        q.put(json.dumps({
                                            "event": "phase",
                                            **{k: v for k, v in payload.items() if k != "event"}
                                        }, ensure_ascii=False))
                                    elif payload.get("event") == "user_progress":
                                        # 推送用户友好的进度信息
                                        q.put(json.dumps({
                                            "event": "progress",
                                            "message": payload.get("message", ""),
                                            "operation": payload.get("operation", ""),
                                            "phase": payload.get("phase", ""),
                                            "timestamp": payload.get("ts", "")
                                        }, ensure_ascii=False))
                                except Exception:
                                    continue
                    except Exception:
                        # 忽略尾随错误
                        pass

                def run_workflow_thread():
                    nonlocal last_state_local, steps_done
                    try:
                        for output in app_graph.stream(state):
                            for node, value in output.items():
                                steps_done += 1
                                last_state_local = value
                                
                                # 记录工作流节点执行（不再输出“节点完成 X/Y”样式给前端）
                                node_start_time = time.time()
                                log_workflow_event("node_execution", node, "执行中")
                                
                                # 保存检查点
                                try:
                                    save_checkpoint(value, req.checkpoint)
                                    log_checkpoint_operation("save", req.checkpoint, True)
                                except Exception as e:
                                    log_checkpoint_operation("save", req.checkpoint, False, error=str(e))
                                
                                # 记录节点完成
                                node_duration = time.time() - node_start_time
                                log_workflow_event("node_completion", node, "完成", node_duration)
                        # 检查是否完成所有修订
                        is_final = False
                        if last_state_local:
                            validation_status = last_state_local.get("validation_status")
                            revision_count = last_state_local.get("revision_count", 0)
                            
                            # 记录修订状态
                            log_workflow_event("revision_check", "workflow", "检查修订状态", 
                                            details=f"验证状态: {validation_status}, 修订次数: {revision_count}")
                            
                            # 只有验证通过或达到最大修订次数时才认为是最终版本
                            if validation_status and validation_status.value == "validated":
                                is_final = True
                                log_workflow_event("revision_status", "workflow", "验证通过", 
                                                details="无需进一步修订")
                            elif revision_count >= 3:
                                is_final = True
                                log_workflow_event("revision_status", "workflow", "达到最大修订次数", 
                                                details=f"已完成 {revision_count} 次修订，停止修订")
                        
                        # 推送最终报告结果（只有在完成修订后）
                        if is_final and last_state_local and last_state_local.get("final_report"):
                            final_report_payload = {
                                "event": "final_report",
                                "content": last_state_local.get("final_report"),
                                "word_count": count_words(last_state_local.get("final_report", "")),
                                "target_word_limit": last_state_local.get("word_limit", 0),
                                "timestamp": datetime.now().isoformat()
                            }
                            q.put(json.dumps(final_report_payload, ensure_ascii=False))
                            
                            # 记录最终报告推送
                            log_workflow_event("final_report", "workflow", "推送最终报告", 
                                            details=f"字数: {final_report_payload['word_count']}")
                        
                        done_payload = {
                            "event": "done",
                            "success": True,
                            "message": "ok",
                            "final_report": last_state_local.get("final_report") if last_state_local else None,
                            "timestamp": datetime.now().isoformat(),
                        }
                        q.put(json.dumps(done_payload, ensure_ascii=False))
                        
                        # 记录工作流完成
                        log_workflow_event("workflow_completion", "workflow", "完成", 
                                        details=f"总步骤: {steps_done}")
                        
                    except Exception as e:
                        error_msg = str(e)
                        q.put(json.dumps({"event": "error", "message": error_msg}, ensure_ascii=False))
                        log_error("WORKFLOW_EXECUTION_ERROR", error_msg, traceback.format_exc())
                    finally:
                        stop_event.set()

                t1 = threading.Thread(target=tail_metrics, daemon=True)
                t2 = threading.Thread(target=run_workflow_thread, daemon=True)
                t1.start(); t2.start()

                try:
                    while True:
                        try:
                            item = q.get(timeout=0.5)
                            yield f"data: {item}\n\n"
                            if json.loads(item).get("event") == "done":
                                break
                        except queue.Empty:
                            if stop_event.is_set():
                                break
                            continue
                finally:
                    stop_event.set()
            return StreamingResponse(event_stream(), media_type="text/event-stream")

        # 非流式：一次性返回
        last_state: Optional[GlobalState] = None
        for output in app_graph.stream(state):
            for _, value in output.items():
                try:
                    save_checkpoint(value, req.checkpoint)
                    log_checkpoint_operation("save", req.checkpoint, True)
                except Exception as e:
                    log_checkpoint_operation("save", req.checkpoint, False, error=str(e))
                last_state = value

        if not last_state:
            log_error("WORKFLOW_ERROR", "执行未产生任何状态")
            return RunResponse(success=False, message="执行未产生任何状态")

        # 记录性能指标
        total_duration = time.time() - start_time
        log_performance_metric("workflow_execution_time", total_duration, "seconds")
        
        return RunResponse(
            success=True,
            message="ok",
            final_report=last_state.get("final_report") if last_state else None,
            state=last_state,
        )
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        log_error("API_ERROR", error_msg, traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)
