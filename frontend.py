#!/usr/bin/env python3
import json
import os
import re
import time
from datetime import datetime

import requests
import streamlit as st



# 配置页面
st.set_page_config(
    page_title="Deep Researcher - 智能研究报告生成器",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .progress-container {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
    }
    .status-success {
        color: #28a745;
        font-weight: bold;
    }
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
    .status-warning {
        color: #ffc107;
        font-weight: bold;
    }
    .report-container {
        background-color: white;
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# 侧边栏配置
with st.sidebar:
    st.title("🔧 配置")
    
    # API配置
    api_url = st.text_input(
        "API地址",
        value="http://localhost:8000",
        help="Deep Researcher API服务器地址"
    )
    
    # 查询参数
    st.subheader("📝 查询设置")
    
    # 检查是否选择了恢复检查点
    resume_checkbox = st.checkbox("从检查点恢复", help="是否从之前的检查点继续执行")
    
    # 根据是否恢复检查点来决定是否显示查询输入框
    if resume_checkbox:
        st.info("🔄 已选择从检查点恢复，将使用检查点中保存的研究问题")
        query = ""  # 恢复模式下不需要用户输入
    else:
        query = st.text_area(
            "研究问题",
            placeholder="请输入您要研究的问题，例如：数字孪生技术在智慧城市管理中的应用价值评估",
            height=100
        )
    
    word_limit = st.number_input(
        "字数限制",
        min_value=500,
        max_value=10000,
        value=2000,
        step=500,
        help="生成报告的目标字数"
    )
    
    # 高级选项
    with st.expander("⚙️ 高级选项"):
        checkpoint_path = st.text_input(
            "检查点路径",
            value="research_result/checkpoint.json",
            help="检查点文件路径"
        )
        
        auto_refresh = st.checkbox(
            "自动刷新进度",
            value=True,
            help="自动检测并显示最新的研究进度"
        )
    
    # 执行按钮
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🚀 开始研究", type="primary", use_container_width=True):
            # 校验输入
            if not resume_checkbox and not query.strip():
                st.error("请输入研究问题")
            else:
                # 如果选择从检查点恢复，先校验检查点是否存在
                if resume_checkbox:
                    try:
                        resp = requests.get(
                            f"{api_url}/checkpoint/exists",
                            params={"path": checkpoint_path},
                            timeout=10,
                        )
                        if resp.status_code != 200 or not resp.json().get("exists", False):
                            st.error("未找到检查点文件，请确认路径或取消勾选'从检查点恢复'")
                            st.stop()
                    except Exception as e:
                        st.error(f"检查检查点失败：{e}")
                        st.stop()

                # 点击开始时彻底清理上一轮的状态并设置新的研究参数
                st.session_state.progress_data = []
                st.session_state.final_report = None
                st.session_state.error_message = None
                st.session_state.research_completed = False
                st.session_state.show_progress_history = False
                st.session_state.results_loaded = False
                st.session_state.last_metrics_mtime = 0
                st.session_state.last_status_check = 0
                st.session_state.last_auto_refresh = 0
                
                # 设置新的研究参数
                st.session_state.start_research = True
                st.session_state.query = query if not resume_checkbox else ""  # 恢复模式下查询为空
                st.session_state.word_limit = word_limit
                st.session_state.resume = resume_checkbox
                st.session_state.checkpoint_path = checkpoint_path
                st.session_state.api_url = api_url
                
                # 强制重新渲染，清理所有显示区域
                st.rerun()
    
    with col2:
        if st.button("📂", help="加载已有结果", use_container_width=True):
            # 重新加载已有结果
            st.session_state.results_loaded = False
            # 直接在这里重新加载，而不是调用函数
            try:
                # 尝试读取已存在的报告文件
                result_file = "research_result/result.txt"
                if os.path.exists(result_file):
                    with open(result_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            st.session_state.final_report = content
                            st.session_state.research_completed = True
                            
                # 尝试读取进度数据
                metrics_file = "research_result/metrics.jsonl"
                if os.path.exists(metrics_file):
                    progress_data = []
                    with open(metrics_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            try:
                                data = json.loads(line.strip())
                                if data.get('event') == 'user_progress':
                                    progress_data.append({
                                        'timestamp': data.get('ts', ''),
                                        'message': data.get('message', ''),
                                        'operation': data.get('operation', ''),
                                        'phase': data.get('phase', ''),
                                        'progress': 1.0 if data.get('phase') == '完成' else 0.5
                                    })
                            except json.JSONDecodeError:
                                continue
                    if progress_data:
                        st.session_state.progress_data = progress_data
                        
                st.session_state.results_loaded = True
                
                if st.session_state.final_report or st.session_state.progress_data:
                    st.success("已加载已有研究结果！")
                else:
                    st.info("未找到已有研究结果")
                    
            except Exception as e:
                st.error(f"加载结果时出错：{e}")
            st.rerun()
    
    with col3:
        if st.button("🗑️", help="清除历史", use_container_width=True):
            # 清除所有历史状态
            st.session_state.progress_data = []
            st.session_state.final_report = None
            st.session_state.error_message = None
            st.session_state.research_completed = False
            st.session_state.show_progress_history = False
            st.session_state.results_loaded = False
            st.session_state.last_metrics_mtime = 0
            st.session_state.last_status_check = 0
            st.session_state.last_auto_refresh = 0
            st.rerun()

# 主界面
st.markdown('<h1 class="main-header">🔬 Deep Researcher</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; font-size: 1.2rem; color: #666;">智能研究报告生成器</p>', unsafe_allow_html=True)

# 初始化会话状态
if 'start_research' not in st.session_state:
    st.session_state.start_research = False
if 'progress_data' not in st.session_state:
    st.session_state.progress_data = []
if 'final_report' not in st.session_state:
    st.session_state.final_report = None
if 'error_message' not in st.session_state:
    st.session_state.error_message = None
if 'research_completed' not in st.session_state:
    st.session_state.research_completed = False
if 'show_progress_history' not in st.session_state:
    st.session_state.show_progress_history = False
if 'results_loaded' not in st.session_state:
    st.session_state.results_loaded = False

def load_existing_results():
    """加载已存在的研究结果"""
    try:
        # 尝试读取已存在的报告文件
        result_file = "research_result/result.txt"
        if os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    st.session_state.final_report = content
                    st.session_state.research_completed = True
                    
        # 尝试读取进度数据
        metrics_file = "research_result/metrics.jsonl"
        if os.path.exists(metrics_file):
            progress_data = []
            with open(metrics_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if data.get('event') == 'user_progress':
                            progress_data.append({
                                'timestamp': data.get('ts', ''),
                                'message': data.get('message', ''),
                                'operation': data.get('operation', ''),
                                'phase': data.get('phase', ''),
                                'progress': 1.0 if data.get('phase') == '完成' else 0.5
                            })
                    except json.JSONDecodeError:
                        continue
            if progress_data:
                st.session_state.progress_data = progress_data
                
        st.session_state.results_loaded = True
        
    except Exception as e:
        pass  # 静默处理错误，避免影响界面

# 在页面加载时尝试加载已存在的结果
if not st.session_state.results_loaded:
    load_existing_results()

# 添加定时刷新机制
def setup_auto_refresh():
    """设置自动刷新"""
    # 在主界面添加一个不可见的刷新按钮
    if st.session_state.get('auto_refresh_enabled', True):
        # 每3秒自动刷新一次
        time.sleep(0.1)  # 短暂延迟避免过于频繁的检查

# 自动刷新进度功能
def check_and_refresh_progress():
    """检查并刷新进度，返回是否有更新"""
    try:
        # 检查是否启用了自动刷新
        if not st.session_state.get('auto_refresh_enabled', True):
            return False
            
        metrics_file = "research_result/metrics.jsonl"
        if not os.path.exists(metrics_file):
            return False
            
        # 获取文件的最后修改时间
        current_mtime = os.path.getmtime(metrics_file)
        last_mtime = st.session_state.get('last_metrics_mtime', 0)
        
        # 如果文件有更新
        if current_mtime > last_mtime:
            st.session_state.last_metrics_mtime = current_mtime
            
            # 重新加载进度数据
            progress_data = []
            with open(metrics_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if data.get('event') == 'user_progress':
                            progress_data.append({
                                'timestamp': data.get('ts', ''),
                                'message': data.get('message', ''),
                                'operation': data.get('operation', ''),
                                'phase': data.get('phase', ''),
                                'progress': 1.0 if data.get('phase') == '完成' else 0.5
                            })
                    except json.JSONDecodeError:
                        continue
            
            # 检查是否有新的进度
            if progress_data and len(progress_data) > len(st.session_state.get('progress_data', [])):
                st.session_state.progress_data = progress_data
                
                # 检查是否研究已完成（最新进度的阶段是"完成"）
                if progress_data:
                    latest = progress_data[-1]
                    if latest.get('phase') == '完成' and latest.get('operation') in ['内容修订', '生成报告']:
                        # 尝试加载最终报告
                        result_file = "research_result/result.txt"
                        if os.path.exists(result_file):
                            with open(result_file, 'r', encoding='utf-8') as f:
                                content = f.read().strip()
                                if content and content != st.session_state.get('final_report', ''):
                                    st.session_state.final_report = content
                                    st.session_state.research_completed = True
                
                # 刷新页面显示最新进度
                st.rerun()
                return True
                
        return False
                
    except Exception as e:
        return False  # 静默处理错误

# 在侧边栏设置自动刷新状态
if 'auto_refresh_enabled' not in st.session_state:
    st.session_state.auto_refresh_enabled = True

# 从侧边栏获取auto_refresh设置
try:
    if 'auto_refresh' in locals():
        st.session_state.auto_refresh_enabled = auto_refresh
except:
    pass

# 如果没有在进行新研究且启用了自动刷新，则检查进度更新
if (not st.session_state.get('start_research', False) and 
    st.session_state.get('auto_refresh_enabled', True)):
    
    # 在主界面顶部添加一个状态显示
    status_container = st.container()
    with status_container:
        col1, col2 = st.columns([3, 1])
        with col1:
            # 检查是否有正在进行的研究
            metrics_file = "research_result/metrics.jsonl"
            if os.path.exists(metrics_file):
                current_mtime = os.path.getmtime(metrics_file)
                last_check = st.session_state.get('last_status_check', 0)
                
                # 每次页面加载都检查一次
                if current_mtime > last_check:
                    st.session_state.last_status_check = time.time()
                    
                    # 读取最新的进度
                    try:
                        with open(metrics_file, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            if lines:
                                last_line = lines[-1]
                                data = json.loads(last_line.strip())
                                if data.get('event') == 'user_progress':
                                    latest_time = data.get('ts', '')
                                    latest_msg = data.get('message', '')
                                    latest_op = data.get('operation', '')
                                    
                                    # 计算时间差，判断是否是最近的活动
                                    if latest_time:
                                        from datetime import datetime
                                        try:
                                            latest_dt = datetime.fromisoformat(latest_time.replace('Z', '+00:00'))
                                            now = datetime.now(latest_dt.tzinfo)
                                            time_diff = (now - latest_dt).total_seconds()
                                            
                                            if time_diff < 300:  # 5分钟内的活动认为是"进行中"
                                                st.info(f"🔄 检测到研究进行中：{latest_op} - {latest_msg}")
                                        except:
                                            pass
                                            
                    except:
                        pass
        
        with col2:
            if st.button("🔄 手动刷新", help="手动刷新当前进度"):
                check_and_refresh_progress()
                st.rerun()
    
    # 定期检查进度更新
    check_and_refresh_progress()
    
    # 使用时间戳触发定期刷新
    current_time = time.time()
    last_refresh = st.session_state.get('last_auto_refresh', 0)
    
    # 每10秒自动刷新一次
    if current_time - last_refresh > 10:
        st.session_state.last_auto_refresh = current_time
        # 检查是否有新的进度更新
        if check_and_refresh_progress():
            pass  # check_and_refresh_progress内部会调用st.rerun()
        else:
            # 即使没有新进度，也刷新页面以检查其他更新
            time.sleep(0.1)
            st.rerun()

def stream_research_progress():
    """流式获取研究进度"""
    try:
        # 准备请求数据
        request_data = {
            "query": st.session_state.query,
            "word_limit": st.session_state.word_limit,
            "resume": st.session_state.resume,
            "checkpoint": st.session_state.checkpoint_path,
            "stream": True  # 使用流式模式
        }
        
        # 发送流式请求
        response = requests.post(
            f"{st.session_state.api_url}/run",
            json=request_data,
            stream=True,
            headers={"Accept": "text/event-stream"},
            timeout=600  # 10分钟超时
        )
        
        if response.status_code != 200:
            st.session_state.error_message = f"API请求失败: {response.status_code}"
            return
        
        # 处理流式响应
        progress_data = []
        final_report = None
        is_done = False
        
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])  # 移除 'data: ' 前缀
                        event_type = data.get('event')
                        
                        if event_type == 'progress':
                            # 用户友好的进度信息
                            progress_data.append({
                                'timestamp': data.get('timestamp', ''),
                                'message': data.get('message', ''),
                                'operation': data.get('operation', ''),
                                'phase': data.get('phase', ''),
                                'progress': data.get('progress', 0)
                            })
                            # 更新会话状态
                            st.session_state.progress_data = progress_data
                            
                        elif event_type == 'final_report':
                            # 最终报告（只有在修订完成后才会收到）
                            final_report = data.get('content', '')
                            st.session_state.final_report = final_report
                            st.session_state.research_completed = True
                            
                        elif event_type == 'done':
                            # 完成事件
                            is_done = True
                            if data.get('success'):
                                # 如果没有收到final_report事件，说明还在修订中
                                if not st.session_state.final_report:
                                    st.session_state.research_completed = False
                                else:
                                    st.session_state.research_completed = True
                            else:
                                st.session_state.error_message = data.get('message', '未知错误')
                            break
                            
                        elif event_type == 'error':
                            # 错误事件
                            st.session_state.error_message = data.get('message', '未知错误')
                            break
                            
                    except json.JSONDecodeError:
                        continue
                        
    except requests.exceptions.Timeout:
        st.session_state.error_message = "请求超时，请稍后重试"
    except Exception as e:
        st.session_state.error_message = f"连接错误: {str(e)}"

# 执行研究
if st.session_state.start_research:
    # 显示进度区域
    progress_display = st.empty()
    report_placeholder = st.empty()
    
    # 调用API并收集进度消息
    with st.spinner("正在执行研究..."):
        # 直接处理SSE消息，不使用线程（避免Streamlit线程问题）
        try:
            # 准备请求数据
            request_data = {
                "query": st.session_state.query,
                "word_limit": st.session_state.word_limit,
                "resume": st.session_state.resume,
                "checkpoint": st.session_state.checkpoint_path,
                "stream": True  # 使用流式模式
            }
            
            # 发送流式请求
            response = requests.post(
                f"{st.session_state.api_url}/run",
                json=request_data,
                stream=True,
                headers={"Accept": "text/event-stream"},
                timeout=600  # 10分钟超时
            )
            
            if response.status_code != 200:
                st.error(f"API请求失败: {response.status_code}")
                st.session_state.error_message = f"API请求失败: {response.status_code}"
            else:
                # 处理流式响应
                progress_messages = []
                seen_keys = set()
                final_report = None
                
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            try:
                                data = json.loads(line[6:])  # 移除 'data: ' 前缀
                                event_type = data.get('event')
                                
                                if event_type == 'progress':
                                    # 用户友好的进度信息
                                    # 操作与阶段中文映射（兜底）
                                    op_map = {
                                        'agent.problem_understanding': '问题理解',
                                        'agent.structure_planning': '结构规划',
                                        'agent.knowledge_retrieval': '知识检索',
                                        'agent.writing_polishing': '报告撰写',
                                        'agent.report_writing': '报告撰写',
                                        'agent.validation': '质量校验',
                                        'agent.revision': '内容修订',
                                        'agent.generate_report': '生成报告',
                                        'problem_understanding': '问题理解',
                                        'structure_planning': '结构规划',
                                        'knowledge_retrieval': '知识检索',
                                        'writing_polishing': '报告撰写',
                                        'validation': '质量校验',
                                        'revision': '内容修订',
                                        'generate_report': '生成报告',
                                        'quality.evaluation': '质量评估',
                                        'report_writing': '报告撰写',
                                    }
                                    phase_map = {
                                        'start': '开始',
                                        'llm_call': 'AI分析中',
                                        'parse_result': '解析结果',
                                        'done': '完成',
                                        'quality_evaluation': '质量评估',
                                        'validation': '质量校验',
                                    }
                                    operation_val = data.get('operation', '')
                                    phase_val = data.get('phase', '')
                                    progress_item = {
                                        'timestamp': data.get('timestamp', ''),
                                        'message': data.get('message', ''),
                                        'operation': op_map.get(operation_val, operation_val),
                                        'phase': phase_map.get(phase_val, phase_val),
                                        'progress': data.get('progress', 0)
                                    }
                                    # 去重：基于 timestamp/operation/phase/message/node 组合键
                                    # 优化：忽略timestamp，避免相同消息重复刷屏；并过滤连续相同message
                                    unique_key = (
                                        progress_item.get('operation', ''),
                                        progress_item.get('phase', ''),
                                        progress_item.get('message', ''),
                                        data.get('node', ''),
                                    )
                                    if unique_key not in seen_keys and not (
                                        progress_messages and progress_messages[-1].get('message') == progress_item.get('message')
                                    ):
                                        seen_keys.add(unique_key)
                                        progress_messages.append(progress_item)
                                    st.session_state.progress_data = progress_messages
                                    
                                    # 实时更新进度显示（只更新一次，避免重复）
                                    with progress_display.container():
                                        st.markdown('<div class="progress-container">', unsafe_allow_html=True)
                                        st.subheader("📊 研究进度")
                                        
                                        # 显示最新进度
                                        if progress_messages:
                                            latest = progress_messages[-1]
                                            if latest.get('message'):
                                                st.info(f"🔄 {latest['message']}")
                                            if latest.get('operation'):
                                                st.write(f"**操作**: {latest['operation']}")
                                            if latest.get('phase'):
                                                st.write(f"**阶段**: {latest['phase']}")
                                            if latest.get('progress'):
                                                st.progress(latest['progress'])
                                        
                                        # 在流式过程中展示详细进度历史（可折叠）
                                        if len(progress_messages) > 0:
                                            with st.expander("📋 详细进度历史", expanded=False):
                                                # 展示最近的若干条历史，避免列表过长
                                                max_history = 200
                                                for i, msg in enumerate(progress_messages[-max_history:]):
                                                    ts = msg.get('timestamp', '')
                                                    op = msg.get('operation') or ''
                                                    ph = msg.get('phase') or ''
                                                    text = msg.get('message') or ''
                                                    
                                                    prefix = " | ".join([p for p in [ts] if p])
                                                    if prefix:
                                                        st.write(f"{i+1}. {prefix} — {text}")
                                                    else:
                                                        st.write(f"{i+1}. {text}")
                                        
                                        st.markdown('</div>', unsafe_allow_html=True)
                                    
                                elif event_type == 'final_report':
                                    # 最终报告
                                    final_report = data.get('content', '')
                                    st.session_state.final_report = final_report
                                    st.session_state.research_completed = True
                                    # 不立刻中断，等待done事件以将进度条置为100%
                                
                                elif event_type == 'done':
                                    # 完成事件
                                    if data.get('success'):
                                        # 补一条“已完成”进度并将进度条置为100%
                                        done_item = {
                                            'timestamp': data.get('timestamp', ''),
                                            'message': '研究已完成',
                                            'operation': '完成',
                                            'phase': '完成',
                                            'progress': 1.0,
                                        }
                                        progress_messages.append(done_item)
                                        st.session_state.progress_data = progress_messages
                                        st.session_state.research_completed = True
                                    else:
                                        st.error(data.get('message', '未知错误'))
                                    break
                                    
                                elif event_type == 'error':
                                    # 错误事件
                                    st.error(data.get('message', '未知错误'))
                                    break
                                    
                            except json.JSONDecodeError:
                                continue
                                
        except requests.exceptions.Timeout:
            st.error("请求超时，请稍后重试")
        except Exception as e:
            st.error(f"连接错误: {str(e)}")

    # 清空实时进度显示容器，避免与下方持久区域重复
    try:
        progress_display.empty()
    except Exception:
        pass
    
    # 如果API调用完成但没有进度数据，显示默认进度区域
    if not st.session_state.progress_data:
        with progress_display.container():
            st.markdown('<div class="progress-container">', unsafe_allow_html=True)
            st.subheader("📊 研究进度")
            st.info("🚀 正在启动研究，请稍候...")
            st.markdown('</div>', unsafe_allow_html=True)
    
    # 显示结果并重置研究状态
    if st.session_state.research_completed and st.session_state.final_report:
        st.success("✅ 研究完成！")
        # 设置显示进度历史
        st.session_state.show_progress_history = True
        # 研究完成后重置状态
        st.session_state.start_research = False
    
    elif st.session_state.error_message:
        st.error(f"❌ 研究过程中出现错误: {st.session_state.error_message}")
        # 出错后重置状态
        st.session_state.start_research = False

# 显示研究进度（持久显示区域）
# 如果有进度数据且不在进行新研究，就显示
if (st.session_state.progress_data and 
    not st.session_state.get('start_research', False)):
    st.markdown('<div class="progress-container">', unsafe_allow_html=True)
    st.subheader("📊 研究进度")
    
    # 显示最新进度
    if st.session_state.progress_data:
        latest = st.session_state.progress_data[-1]
        if latest.get('message'):
            st.info(f"🔄 {latest['message']}")
        if latest.get('operation'):
            st.write(f"**操作**: {latest['operation']}")
        if latest.get('phase'):
            st.write(f"**阶段**: {latest['phase']}")
        if latest.get('progress'):
            st.progress(latest['progress'])
    
    # 显示所有进度历史
    if len(st.session_state.progress_data) > 1:
        with st.expander("📋 详细进度历史", expanded=False):
            for i, msg in enumerate(st.session_state.progress_data):
                if msg.get('message'):
                    st.write(f"{i+1}. {msg['message']}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("---")  # 分隔线

# 显示生成的报告（统一区域）
if st.session_state.final_report:
    st.markdown('<div class="report-container">', unsafe_allow_html=True)
    st.subheader("📄 生成的研究报告")
    
    
    # 报告内容
    st.markdown("### 报告内容")
    st.text_area(
        "完整报告",
        value=st.session_state.final_report,
        height=800,  # 增加高度显示更多内容
        disabled=True,
        key="main_report_text_area"  # 使用统一的key
    )
    
    # 下载按钮
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"research_report_{timestamp}.txt"
    st.download_button(
        label="📥 下载报告",
        data=st.session_state.final_report,
        file_name=filename,
        mime="text/plain",
        key="main_download_button"  # 使用统一的key
    )
    
    # 报告信息
    with st.expander("📋 报告信息"):
        st.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if st.session_state.get('query'):
            st.write(f"**研究问题**: {st.session_state.query}")
        if st.session_state.get('word_limit'):
            st.write(f"**字数限制**: {st.session_state.word_limit}")
    
    st.markdown('</div>', unsafe_allow_html=True)

# 页脚
st.markdown("---")
st.markdown(
    '<p style="text-align: center; color: #666;">🔬 Deep Researcher - 智能研究报告生成器</p>',
    unsafe_allow_html=True
)
