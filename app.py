import argparse
import os
from datetime import datetime

from dotenv import load_dotenv

from src.core.graph import create_graph
from src.core.state import GlobalState, ValidationStatus, AgentName
from src.utils.checkpoint import save_checkpoint, load_checkpoint

load_dotenv()

def create_init_state(user_query: str) -> GlobalState:
    now = datetime.now()
    return GlobalState(**{
        "user_query": user_query,
        "requirements": None,
        "structure": None,
        "knowledge_base": {},
        "draft_report": None,
        "final_report": None,
        "validation_status": ValidationStatus.PENDING,
        "revision_count": 0,
        "current_agent": AgentName.COORDINATOR,
        "active_section": None,
        "processed_sections": [],
        "start_time": now,
        "last_updated": now,
        "error_message": None,
        "warnings": [],
        "quality_metrics": {},
        "processing_time": None,
        'word_limit': 1091
    })


def main():
    """主函数"""
    print("🚀 启动Deep Researcher系统...")

    parser = argparse.ArgumentParser(description="Deep Researcher")
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=os.environ.get("DR_CHECKPOINT", os.path.join(os.getcwd(), "research_result", "checkpoint.json")),
        help="checkpoint 文件路径（默认: research_result/checkpoint.json）",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="从 checkpoint 恢复继续运行",
    )
    parser.add_argument(
        "--query",
        type=str,
        default="Analysis of the Changing Global Semiconductor Supply Chain Landscape and Geopolitical Impacts in 2025",
        help="用户查询文本（仅在不恢复时生效）",
    )
    args = parser.parse_args()

    # 创建工作流
    app = create_graph()

    # 初始/恢复状态
    if args.resume and os.path.exists(args.checkpoint):
        print(f"从 checkpoint 恢复: {args.checkpoint}")
        initial_state = load_checkpoint(args.checkpoint)
    else:
        initial_state = create_init_state(args.query)

    # 执行工作流并在每步保存 checkpoint
    print("\n开始执行工作流...")
    try:
        os.makedirs(os.path.dirname(args.checkpoint), exist_ok=True)
        for output in app.stream(initial_state):
            for node, value in output.items():
                print("=" * 40)
                print(f"✅ 执行节点: '{node}'")
                print(f"   当前智能体: {value['current_agent']}")
                print(f"   验证状态: {value['validation_status']}")
                error_msg = value.get("error_message")
                if error_msg:
                    print(f"❌ 错误: {error_msg}")

                # 保存 checkpoint
                save_checkpoint(value, args.checkpoint)

        print("\n🎉 工作流执行完成！")

    except Exception as e:
        print(f"❌ 执行过程中出现错误: {str(e)}")


if __name__ == "__main__":
    main()
