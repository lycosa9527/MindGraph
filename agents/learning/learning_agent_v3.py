"""
Learning Agent V3 - Full LangChain Agent with Prerequisite Testing

Implements the "Prerequisite-First Approach" intelligent tutoring system.
When a student answers incorrectly, the agent:
1. Identifies missing prerequisite knowledge
2. Tests that prerequisite with simpler questions
3. Teaches the prerequisite if needed
4. Returns to original question with enhanced understanding

@author lycosa9527
@made_by MindSpring Team
"""

import logging
from typing import Dict, Any, List, Optional
import json

# LangChain 1.0+ uses langgraph for agents
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agents.learning.qwen_langchain import QwenLLM
from agents.main_agent import QwenLLM as QwenLLMBase

logger = logging.getLogger(__name__)


class LearningAgentV3:
    """
    Advanced intelligent tutoring system with prerequisite knowledge testing.
    
    Uses LangChain agent with 5 tools:
    1. misconception_analyzer: Analyze what went wrong
    2. prerequisite_identifier: Identify missing foundational knowledge
    3. prerequisite_test_generator: Generate simpler test questions
    4. learning_material_generator: Create mini-lessons
    5. knowledge_base_search: Search for relevant teaching materials
    """
    
    def __init__(self, language: str = 'en'):
        """
        Initialize advanced learning agent.
        
        Args:
            language: 'en' or 'zh'
        """
        self.language = language
        self.llm = QwenLLM(model_type='generation')  # LangChain wrapper
        self.qwen_llm = QwenLLMBase(model_type='generation')  # Direct access for tools
        
        # Initialize tools
        self.tools = self._create_tools()
        
        # Create agent
        self.agent = self._create_agent()
        
        logger.info(f"[LRNG-V3] LearningAgentV3 initialized | Language: {language} | Tools: {len(self.tools)}")
    
    def _create_tools(self) -> List:
        """Create the 5 LangChain tools for the agent."""
        
        @tool
        def misconception_analyzer(
            correct_answer: str,
            student_answer: str,
            question_context: str
        ) -> str:
            """
            Analyze what misconception led to the wrong answer.
            
            Args:
                correct_answer: The correct answer
                student_answer: What the student answered
                question_context: Context about the question
            
            Returns:
                JSON string with misconception analysis
            """
            try:
                if self.language == 'zh':
                    prompt = f"""分析学生的误解类型和根本原因。

问题背景：{question_context}
正确答案：{correct_answer}
学生答案：{student_answer}

请以JSON格式回答：
{{
    "misconception_type": "混淆概念/因果倒置/记忆错误/其他",
    "diagnosis": "学生理解错误的诊断（一句话）",
    "mental_model": "学生当前的思维模型",
    "severity": "low/medium/high",
    "root_cause": "根本原因是什么？",
    "missing_prerequisite": "缺失的先验知识"
}}

分析："""
                else:
                    prompt = f"""Analyze the type of misconception and root cause.

Question context: {question_context}
Correct answer: {correct_answer}
Student answer: {student_answer}

Respond in JSON format:
{{
    "misconception_type": "concept_confusion/causal_reversal/memory_error/other",
    "diagnosis": "Diagnosis of student's misunderstanding (one sentence)",
    "mental_model": "Student's current mental model",
    "severity": "low/medium/high",
    "root_cause": "What is the root cause?",
    "missing_prerequisite": "Missing prerequisite knowledge"
}}

Analysis:"""
                
                response = self.qwen_llm._call(prompt)
                
                # Try to parse as JSON, if fails return as text
                try:
                    json.loads(response)
                    return response
                except:
                    # Wrap in JSON if not already
                    return json.dumps({"analysis": response.strip()})
                    
            except Exception as e:
                logger.error(f"[LRNG-V3] Error in misconception_analyzer: {str(e)}")
                return json.dumps({"error": str(e)})
        
        @tool
        def prerequisite_identifier(
            misconception: str,
            correct_answer: str,
            student_answer: str
        ) -> str:
            """
            Identify what prerequisite knowledge is missing.
            
            Args:
                misconception: JSON string from misconception_analyzer
                correct_answer: The correct answer
                student_answer: What the student answered
            
            Returns:
                JSON string with missing prerequisite identification
            """
            try:
                if self.language == 'zh':
                    prompt = f"""基于误解分析，识别学生缺失的先验知识。

误解分析：{misconception}
正确答案：{correct_answer}
学生答案：{student_answer}

请以JSON格式回答：
{{
    "missing_prerequisite": "缺失的核心先验知识（简洁名称）",
    "prerequisite_description": "这个先验知识是什么",
    "why_needed": "为什么需要这个先验知识来理解原问题",
    "cognitive_level_gap": 1-3,
    "test_strategy": "abstract_then_concrete/concrete_example/visual_aid"
}}

识别："""
                else:
                    prompt = f"""Based on misconception analysis, identify missing prerequisite knowledge.

Misconception analysis: {misconception}
Correct answer: {correct_answer}
Student answer: {student_answer}

Respond in JSON format:
{{
    "missing_prerequisite": "Core missing prerequisite (concise name)",
    "prerequisite_description": "What is this prerequisite knowledge",
    "why_needed": "Why is this prerequisite needed to understand the original question",
    "cognitive_level_gap": 1-3,
    "test_strategy": "abstract_then_concrete/concrete_example/visual_aid"
}}

Identification:"""
                
                response = self.qwen_llm._call(prompt)
                
                try:
                    json.loads(response)
                    return response
                except:
                    return json.dumps({"prerequisite": response.strip()})
                    
            except Exception as e:
                logger.error(f"[LRNG-V3] Error in prerequisite_identifier: {str(e)}")
                return json.dumps({"error": str(e)})
        
        @tool
        def prerequisite_test_generator(
            prerequisite_concept: str,
            original_question: str,
            test_strategy: str
        ) -> str:
            """
            Generate a simpler test question for the prerequisite concept.
            
            Args:
                prerequisite_concept: The prerequisite to test
                original_question: The original question student got wrong
                test_strategy: How to test (abstract_then_concrete/concrete_example/visual_aid)
            
            Returns:
                JSON string with test question
            """
            try:
                if self.language == 'zh':
                    prompt = f"""为先验知识生成一个简单的测试问题。

先验概念：{prerequisite_concept}
原问题：{original_question}
测试策略：{test_strategy}

要求：
1. 问题要比原问题简单2-3个认知层次
2. 使用领域无关的抽象例子（如 A+B→C+D）
3. 答案清晰明确
4. 帮助学生理解基础概念

请以JSON格式回答：
{{
    "test_question": "测试问题（简短清晰）",
    "correct_answer": "正确答案",
    "question_type": "text_input/multiple_choice",
    "options": ["选项A", "选项B", "选项C", "选项D"],
    "cognitive_level": "remember/understand/apply",
    "domain": "abstract/concrete",
    "explanation_if_correct": "答对时的解释",
    "explanation_if_wrong": "答错时的解释"
}}

测试问题："""
                else:
                    prompt = f"""Generate a simpler test question for the prerequisite concept.

Prerequisite concept: {prerequisite_concept}
Original question: {original_question}
Test strategy: {test_strategy}

Requirements:
1. Question should be 2-3 cognitive levels simpler than original
2. Use domain-independent abstract examples (e.g., A+B→C+D)
3. Clear, unambiguous answer
4. Helps student understand foundational concept

Respond in JSON format:
{{
    "test_question": "Test question (short and clear)",
    "correct_answer": "Correct answer",
    "question_type": "text_input/multiple_choice",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "cognitive_level": "remember/understand/apply",
    "domain": "abstract/concrete",
    "explanation_if_correct": "Explanation if correct",
    "explanation_if_wrong": "Explanation if wrong"
}}

Test question:"""
                
                response = self.qwen_llm._call(prompt)
                
                try:
                    json.loads(response)
                    return response
                except:
                    return json.dumps({"question": response.strip()})
                    
            except Exception as e:
                logger.error(f"[LRNG-V3] Error in prerequisite_test_generator: {str(e)}")
                return json.dumps({"error": str(e)})
        
        @tool
        def learning_material_generator(
            prerequisite_concept: str,
            student_confusion: str
        ) -> str:
            """
            Generate a mini-lesson to teach the prerequisite concept.
            
            Args:
                prerequisite_concept: The prerequisite to teach
                student_confusion: What the student is confused about
            
            Returns:
                JSON string with learning material
            """
            try:
                if self.language == 'zh':
                    prompt = f"""为先验概念生成简短的教学材料（微课程）。

先验概念：{prerequisite_concept}
学生困惑：{student_confusion}

要求：
1. 简短（1-2分钟阅读时间）
2. 使用简单的类比和例子
3. 包含视觉辅助建议
4. 语气友好、鼓励

请以JSON格式回答：
{{
    "material_type": "micro_lesson",
    "title": "微课标题",
    "explanation": "核心解释（2-3句话）",
    "visual_aid": {{
        "type": "simple_flow/comparison_table/diagram",
        "description": "视觉辅助的描述"
    }},
    "analogy": "日常生活类比",
    "key_principle": "记住的关键原则",
    "examples": ["例子1", "例子2"]
}}

教学材料："""
                else:
                    prompt = f"""Generate a short teaching material (micro-lesson) for the prerequisite concept.

Prerequisite concept: {prerequisite_concept}
Student confusion: {student_confusion}

Requirements:
1. Brief (1-2 minutes reading time)
2. Use simple analogies and examples
3. Include visual aid suggestions
4. Friendly, encouraging tone

Respond in JSON format:
{{
    "material_type": "micro_lesson",
    "title": "Micro-lesson title",
    "explanation": "Core explanation (2-3 sentences)",
    "visual_aid": {{
        "type": "simple_flow/comparison_table/diagram",
        "description": "Description of visual aid"
    }},
    "analogy": "Everyday life analogy",
    "key_principle": "Key principle to remember",
    "examples": ["Example 1", "Example 2"]
}}

Teaching material:"""
                
                response = self.qwen_llm._call(prompt)
                
                try:
                    json.loads(response)
                    return response
                except:
                    return json.dumps({"material": response.strip()})
                    
            except Exception as e:
                logger.error(f"[LRNG-V3] Error in learning_material_generator: {str(e)}")
                return json.dumps({"error": str(e)})
        
        @tool
        def knowledge_base_search(
            topic: str,
            misconception_type: str
        ) -> str:
            """
            Search knowledge base for relevant teaching materials and common errors.
            
            Args:
                topic: The topic being studied
                misconception_type: Type of misconception
            
            Returns:
                JSON string with search results
            """
            try:
                # For now, return a placeholder structure
                # In production, this would search a real knowledge base
                result = {
                    "found": True,
                    "common_errors": [
                        f"Common error patterns for {misconception_type}",
                        "Suggested teaching approach"
                    ],
                    "teaching_strategies": [
                        "Use concrete examples first",
                        "Build from simpler concepts",
                        "Test prerequisite knowledge"
                    ],
                    "prerequisite_map": {
                        topic: ["foundational_concept_1", "foundational_concept_2"]
                    }
                }
                
                return json.dumps(result)
                    
            except Exception as e:
                logger.error(f"[LRNG-V3] Error in knowledge_base_search: {str(e)}")
                return json.dumps({"error": str(e), "found": False})
        
        # Store tools as instance methods
        self.misconception_analyzer_tool = misconception_analyzer
        self.prerequisite_identifier_tool = prerequisite_identifier
        self.prerequisite_test_generator_tool = prerequisite_test_generator
        self.learning_material_generator_tool = learning_material_generator
        self.knowledge_base_search_tool = knowledge_base_search
        
        return [
            misconception_analyzer,
            prerequisite_identifier,
            prerequisite_test_generator,
            learning_material_generator,
            knowledge_base_search
        ]
    
    def _create_agent(self) -> Any:
        """Create the LangChain agent with tools (returns LangGraph CompiledGraph)."""
        
        # Agent system prompt
        if self.language == 'zh':
            system_prompt = """你是一个智能教学系统，使用"先验知识优先"的方法。

当学生答错时，你的流程：
1. 分析学生的误解（使用 misconception_analyzer）
2. 识别缺失的先验知识（使用 prerequisite_identifier）
3. 生成先验知识测试问题（使用 prerequisite_test_generator）
4. 如果学生答错先验测试，生成教学材料（使用 learning_material_generator）
5. 可选：搜索知识库获取教学策略（使用 knowledge_base_search）

你有这些工具：
{tools}

工具名称：
{tool_names}

请按照以下格式回答：

Question: 学生的问题或困惑
Thought: 你应该做什么
Action: 要使用的工具名称
Action Input: 工具的输入
Observation: 工具的输出
... (重复 Thought/Action/Action Input/Observation 直到得出结论)
Thought: 我现在知道最终答案了
Final Answer: 对学生的最终回复

开始！

Question: {input}
{agent_scratchpad}"""
        else:
            system_prompt = """You are an intelligent tutoring system using the "Prerequisite-First Approach".

When a student answers incorrectly, your workflow:
1. Analyze the student's misconception (use misconception_analyzer)
2. Identify missing prerequisite knowledge (use prerequisite_identifier)
3. Generate prerequisite test question (use prerequisite_test_generator)
4. If student fails prerequisite test, generate teaching material (use learning_material_generator)
5. Optional: Search knowledge base for teaching strategies (use knowledge_base_search)

You have these tools:
{tools}

Tool names:
{tool_names}

Use the following format:

Question: the student's question or confusion
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the student

Begin!

Question: {input}
{agent_scratchpad}"""
        
        # Simplify system prompt for LangGraph (remove template variables)
        simplified_prompt = system_prompt.split("You have these tools:")[0] if "You have these tools:" in system_prompt else system_prompt
        simplified_prompt = simplified_prompt.split("你有以下工具：")[0] if "你有以下工具：" in simplified_prompt else simplified_prompt
        simplified_prompt = simplified_prompt.replace("Begin!", "").replace("开始！", "").strip()
        
        # Create agent with LangGraph 1.0+ API
        agent_graph = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=simplified_prompt,
            debug=True
        )
        
        return agent_graph
    
    def process_wrong_answer(
        self,
        user_answer: str,
        correct_answer: str,
        question: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a wrong answer through the agent workflow.
        
        This triggers the full prerequisite testing workflow:
        1. Misconception analysis
        2. Prerequisite identification
        3. Generate prerequisite test
        4. (Optional) Generate learning materials
        
        Args:
            user_answer: Student's incorrect answer
            correct_answer: The correct answer
            question: The original question
            context: Question context
        
        Returns:
            Dict with agent's decision and prerequisite test or learning materials
        """
        try:
            # Prepare input for agent (LangGraph format uses messages)
            user_message = f"""Student answered WRONG.
                
Original question: {question}
Correct answer: {correct_answer}
Student answer: {user_answer}
Context: {json.dumps(context)}

Please analyze the misconception and determine if we need to test prerequisite knowledge."""
            
            agent_input = {
                "messages": [{"role": "user", "content": user_message}]
            }
            
            # Run agent
            result = self.agent.invoke(agent_input)
            
            # Extract final message from result
            messages = result.get("messages", [])
            final_message = messages[-1] if messages else None
            final_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
            
            logger.info(f"[LRNG-V3] Agent completed analysis | Total messages: {len(messages)}")
            
            return {
                "agent_response": final_content,
                "steps_taken": len(messages),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"[LRNG-V3] Error in agent workflow: {str(e)}", exc_info=True)
            return {
                "error": str(e),
                "success": False
            }

