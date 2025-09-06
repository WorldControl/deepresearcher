#!/usr/bin/env python3
"""
后端API日志记录模块
支持记录到指定文件和控制台
"""
import json
import logging
import os
import time
import traceback
from datetime import datetime
from functools import wraps
from typing import Optional, Dict, Any

class APILogger:
    """API日志记录器"""
    
    def __init__(self, name: str, log_file: Optional[str] = None, level: int = logging.INFO):
        """
        初始化API日志记录器
        
        Args:
            name: 日志记录器名称
            log_file: 日志文件路径，如果为None则只输出到控制台
            level: 日志级别
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # 清除已有的处理器
        self.logger.handlers.clear()
        
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 添加控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # 如果指定了日志文件，添加文件处理器
        if log_file:
            # 确保日志目录存在
            log_dir = os.path.dirname(log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def info(self, message: str):
        """记录信息日志"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """记录警告日志"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """记录错误日志"""
        self.logger.error(message)
    
    def debug(self, message: str):
        """记录调试日志"""
        self.logger.debug(message)
    
    def critical(self, message: str):
        """记录严重错误日志"""
        self.logger.critical(message)

# 全局API日志记录器实例
_api_logger = None

def get_api_logger(log_file: Optional[str] = None) -> APILogger:
    """
    获取API日志记录器
    
    Args:
        log_file: 日志文件路径，默认为 research_result/api.log
    
    Returns:
        APILogger实例
    """
    global _api_logger
    
    if _api_logger is None:
        if log_file is None:
            log_file = os.path.join(os.getcwd(), "research_result", "api.log")
        
        _api_logger = APILogger("api", log_file)
    
    return _api_logger

def log_api_request(method: str, endpoint: str, request_data: Dict[str, Any] = None, 
                   user_agent: str = None, client_ip: str = None):
    """
    记录API请求
    
    Args:
        method: HTTP方法
        endpoint: API端点
        request_data: 请求数据
        user_agent: 用户代理
        client_ip: 客户端IP
    """
    logger = get_api_logger()
    
    log_data = {
        "method": method,
        "endpoint": endpoint,
        "timestamp": datetime.now().isoformat(),
        "user_agent": user_agent,
        "client_ip": client_ip
    }
    
    if request_data:
        # 过滤敏感信息
        filtered_data = {}
        for key, value in request_data.items():
            if key.lower() in ['password', 'token', 'key', 'secret']:
                filtered_data[key] = '***'
            else:
                filtered_data[key] = value
        log_data["request_data"] = filtered_data
    
    logger.info(f"API请求: {json.dumps(log_data, ensure_ascii=False)}")

def log_api_response(method: str, endpoint: str, status_code: int, response_time: float,
                    response_size: int = None, error_message: str = None):
    """
    记录API响应
    
    Args:
        method: HTTP方法
        endpoint: API端点
        status_code: 响应状态码
        response_time: 响应时间（秒）
        response_size: 响应大小（字节）
        error_message: 错误消息
    """
    logger = get_api_logger()
    
    log_data = {
        "method": method,
        "endpoint": endpoint,
        "status_code": status_code,
        "response_time": f"{response_time:.3f}s",
        "timestamp": datetime.now().isoformat()
    }
    
    if response_size:
        log_data["response_size"] = f"{response_size} bytes"
    
    if error_message:
        log_data["error"] = error_message
        logger.error(f"API响应: {json.dumps(log_data, ensure_ascii=False)}")
    else:
        logger.info(f"API响应: {json.dumps(log_data, ensure_ascii=False)}")

def log_workflow_event(event_type: str, node_name: str, status: str, 
                      duration: float = None, details: str = None):
    """
    记录工作流事件
    
    Args:
        event_type: 事件类型
        node_name: 节点名称
        status: 状态
        duration: 耗时（秒）
        details: 详细信息
    """
    logger = get_api_logger()
    
    log_data = {
        "event_type": event_type,
        "node_name": node_name,
        "status": status,
        "timestamp": datetime.now().isoformat()
    }
    
    if duration:
        log_data["duration"] = f"{duration:.3f}s"
    
    if details:
        log_data["details"] = details
    
    logger.info(f"工作流事件: {json.dumps(log_data, ensure_ascii=False)}")

def log_checkpoint_operation(operation: str, checkpoint_path: str, 
                           success: bool, file_size: int = None, error: str = None):
    """
    记录检查点操作
    
    Args:
        operation: 操作类型（save/load）
        checkpoint_path: 检查点路径
        success: 是否成功
        file_size: 文件大小（字节）
        error: 错误信息
    """
    logger = get_api_logger()
    
    log_data = {
        "operation": operation,
        "checkpoint_path": checkpoint_path,
        "success": success,
        "timestamp": datetime.now().isoformat()
    }
    
    if file_size:
        log_data["file_size"] = f"{file_size} bytes"
    
    if error:
        log_data["error"] = error
        logger.error(f"检查点操作: {json.dumps(log_data, ensure_ascii=False)}")
    else:
        logger.info(f"检查点操作: {json.dumps(log_data, ensure_ascii=False)}")

def log_error(error_type: str, error_message: str, stack_trace: str = None, 
             context: Dict[str, Any] = None):
    """
    记录错误
    
    Args:
        error_type: 错误类型
        error_message: 错误消息
        stack_trace: 堆栈跟踪
        context: 上下文信息
    """
    logger = get_api_logger()
    
    log_data = {
        "error_type": error_type,
        "error_message": error_message,
        "timestamp": datetime.now().isoformat()
    }
    
    if context:
        log_data["context"] = context
    
    if stack_trace:
        log_data["stack_trace"] = stack_trace
    
    logger.error(f"错误: {json.dumps(log_data, ensure_ascii=False)}")

def log_performance_metric(metric_name: str, value: float, unit: str = None, 
                          context: Dict[str, Any] = None):
    """
    记录性能指标
    
    Args:
        metric_name: 指标名称
        value: 指标值
        unit: 单位
        context: 上下文信息
    """
    logger = get_api_logger()
    
    log_data = {
        "metric_name": metric_name,
        "value": value,
        "timestamp": datetime.now().isoformat()
    }
    
    if unit:
        log_data["unit"] = unit
    
    if context:
        log_data["context"] = context
    
    logger.info(f"性能指标: {json.dumps(log_data, ensure_ascii=False)}")

# 装饰器：自动记录API请求和响应
def log_api_call(log_file: Optional[str] = None):
    """
    装饰器：自动记录API调用的请求和响应
    
    Args:
        log_file: 日志文件路径
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            # 记录请求
            log_api_request("POST", "/run", kwargs)
            
            try:
                # 执行函数
                result = func(*args, **kwargs)
                
                # 记录成功响应
                response_time = time.time() - start_time
                log_api_response("POST", "/run", 200, response_time)
                
                return result
                
            except Exception as e:
                # 记录错误响应
                response_time = time.time() - start_time
                log_api_response("POST", "/run", 500, response_time, error_message=str(e))
                log_error("API_EXECUTION_ERROR", str(e), traceback.format_exc())
                raise
        
        return wrapper
    return decorator
