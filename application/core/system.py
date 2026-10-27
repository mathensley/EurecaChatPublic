from langgraph.checkpoint.base import BaseCheckpointSaver

from application.config import agent_model, check_msg_model, summary_config, tool_selector_config
from src.agents.eureca_chat import EurecaChat

def build_system(saver: BaseCheckpointSaver):
    """
    Constrói instância do EurecaChat com checkpointer
    """
    
    return EurecaChat(
        agent_model=agent_model,
        guardrail_model=check_msg_model,
        summary_config= summary_config,
        tool_selector_config=tool_selector_config,
        checkpointer=saver,
        debug_agent=False # temporário
    ).build()