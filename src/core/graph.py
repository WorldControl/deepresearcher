from langgraph.graph import START, END, StateGraph
from src.core.state import GlobalState, ValidationStatus

from src.agents.problem_understanding_agent import problem_understanding_node
from src.agents.structure_planning_agent import structure_planning_node
from src.agents.knowledge_retrieval_agent import knowledge_retrieval_node
from src.agents.writing_polishing_agent import writing_polishing_node
from src.agents.report_validation_agent import validation_node
from src.agents.revision_agent import revision_node
from src.agents.generate_report_agent import generate_report_node


def should_revision(state: GlobalState):
    # 如果验证通过，直接生成报告
    if state['validation_status'] == ValidationStatus.VALIDATED:
        return 'generate_report'
    
    # 如果需要修订且未达到最大修订次数，则修订
    if (state['validation_status'] == ValidationStatus.NEEDS_REVISION and 
        state.get('revision_count', 0) < 3):
        return 'revision'
    
    # 其他情况（包括达到最大修订次数）都生成报告
    return 'generate_report'


def create_graph():
    workflow = StateGraph(GlobalState)

    workflow.add_node('problem_understanding', problem_understanding_node)
    workflow.add_node('structure_planning', structure_planning_node)
    workflow.add_node('knowledge_retrieval', knowledge_retrieval_node)
    workflow.add_node('writing_polishing', writing_polishing_node)
    workflow.add_node('validation', validation_node)
    workflow.add_node('revision', revision_node)
    workflow.add_node('generate_report', generate_report_node)

    workflow.add_edge(START, 'problem_understanding')
    workflow.add_edge('problem_understanding', 'structure_planning')
    workflow.add_edge('structure_planning', 'knowledge_retrieval')
    workflow.add_edge('knowledge_retrieval', 'writing_polishing')
    workflow.add_edge('writing_polishing', 'validation')
    workflow.add_conditional_edges('validation', should_revision, ['revision', 'generate_report'])
    workflow.add_edge('revision', 'validation')
    workflow.add_edge('generate_report', END)

    app = workflow.compile()
    return app