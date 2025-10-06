"""
Thinking Tools Agents

This module contains agents for all thinking tool analysis diagrams.
All thinking tools use the same mind map-like structure with specialized prompts.

@author lycosa9527
@made_by MindSpring Team
"""

from .factor_analysis_agent import FactorAnalysisAgent
from .three_position_analysis_agent import ThreePositionAnalysisAgent
from .perspective_analysis_agent import PerspectiveAnalysisAgent
from .goal_analysis_agent import GoalAnalysisAgent
from .possibility_analysis_agent import PossibilityAnalysisAgent
from .result_analysis_agent import ResultAnalysisAgent
from .five_w_one_h_agent import FiveWOneHAgent
from .whwm_analysis_agent import WHWMAnalysisAgent
from .four_quadrant_agent import FourQuadrantAgent

__all__ = [
    'FactorAnalysisAgent',
    'ThreePositionAnalysisAgent',
    'PerspectiveAnalysisAgent',
    'GoalAnalysisAgent',
    'PossibilityAnalysisAgent',
    'ResultAnalysisAgent',
    'FiveWOneHAgent',
    'WHWMAnalysisAgent',
    'FourQuadrantAgent',
]

