"""
WHWM Analysis Agent

Generates WHWM analysis diagrams using mind map structure.

@author lycosa9527
@made_by MindSpring Team
"""

from agents.mind_maps.mind_map_agent import MindMapAgent
from prompts.thinking_tools import THINKING_TOOLS_PROMPTS


class WHWMAnalysisAgent(MindMapAgent):
    """Agent for generating WHWM analysis diagrams."""
    
    def __init__(self):
        super().__init__()
        self.diagram_type = 'whwm_analysis'
    
    def get_prompt(self, language='en'):
        """Get the generation prompt for the specified language."""
        prompt_key = f"whwm_analysis_generation_{language}"
        return THINKING_TOOLS_PROMPTS.get(prompt_key, THINKING_TOOLS_PROMPTS['whwm_analysis_generation_en'])

