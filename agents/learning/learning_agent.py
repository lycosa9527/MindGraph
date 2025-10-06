"""
Learning Agent - Intelligent Tutoring System

Uses Qwen LLM to generate contextual questions, validate answers,
provide adaptive hints, and analyze misconceptions.

Phase 2: Intelligent Question Generation + Answer Validation + Adaptive Hints
Phase 3 (Future): Full LangChain agent with prerequisite testing

@author lycosa9527
@made_by MindSpring Team
"""

import logging
from typing import Dict, Any, List, Optional
import json

from agents.main_agent import QwenLLM

logger = logging.getLogger(__name__)


class LearningAgent:
    """
    Intelligent tutoring system agent for Learning Mode.
    
    Capabilities:
    - Generate contextual questions based on node relationships
    - Validate answers with semantic similarity
    - Provide progressive hints (3 levels)
    - Analyze misconceptions
    """
    
    def __init__(self, language: str = 'en'):
        """
        Initialize learning agent.
        
        Args:
            language: 'en' or 'zh'
        """
        self.language = language
        self.llm = QwenLLM(model_type='generation')  # Use generation model
        logger.info(f"[LRNG] LearningAgent initialized | Language: {language}")
    
    def generate_question(
        self,
        node_id: str,
        diagram_type: str,
        spec: Dict[str, Any],
        language: str = 'en'
    ) -> Dict[str, Any]:
        """
        Generate intelligent question for a knocked-out node.
        
        Args:
            node_id: Node ID (e.g., 'attribute_3')
            diagram_type: Type of diagram
            spec: Full diagram specification
            language: 'en' or 'zh'
        
        Returns:
            {
                "node_id": "attribute_3",
                "question": "这个与'光合作用'相连的空白节点代表什么？",
                "context": {
                    "parent": "光合作用",
                    "siblings": ["水", "二氧化碳"],
                    "diagram_type": "bubble_map"
                },
                "difficulty": "medium"
            }
        """
        try:
            # Extract context from diagram
            context = self._extract_node_context(node_id, diagram_type, spec)
            
            # Build prompt for question generation
            prompt = self._build_question_prompt(node_id, context, diagram_type, language)
            
            # Generate question with LLM
            response = self.llm._call(prompt)
            
            # Parse response
            question_text = response.strip()
            
            # Determine difficulty based on context
            difficulty = self._assess_difficulty(context, diagram_type)
            
            result = {
                "node_id": node_id,
                "question": question_text,
                "context": context,
                "difficulty": difficulty
            }
            
            logger.info(f"[LRNG] Generated question for {node_id} | {difficulty} | {language}")
            
            return result
            
        except Exception as e:
            logger.error(f"[LRNG] Error generating question: {str(e)}", exc_info=True)
            # Fallback to simple question
            return {
                "node_id": node_id,
                "question": self._get_fallback_question(node_id, language),
                "context": {},
                "difficulty": "easy"
            }
    
    def validate_answer(
        self,
        user_answer: str,
        correct_answer: str,
        question: str,
        context: Dict[str, Any],
        language: str = 'en'
    ) -> Dict[str, Any]:
        """
        Validate user answer with semantic similarity check.
        
        Args:
            user_answer: User's answer
            correct_answer: Correct answer
            question: The question asked
            context: Node context
            language: 'en' or 'zh'
        
        Returns:
            {
                "correct": true/false,
                "confidence": 0.95,
                "message": "...",
                "proceed_to_next": true/false,
                "misconception_analysis": {...}  # If wrong
            }
        """
        try:
            # First check exact match (case-insensitive, trimmed)
            if self._is_exact_match(user_answer, correct_answer):
                return {
                    "correct": True,
                    "confidence": 1.0,
                    "message": self._get_correct_message(language),
                    "proceed_to_next": True
                }
            
            # Use LLM for semantic validation
            is_correct, confidence = self._semantic_validation(
                user_answer, correct_answer, question, context, language
            )
            
            if is_correct:
                return {
                    "correct": True,
                    "confidence": confidence,
                    "message": self._get_correct_message(language),
                    "proceed_to_next": True
                }
            else:
                # Analyze misconception
                misconception = self._analyze_misconception(
                    user_answer, correct_answer, question, context, language
                )
                
                return {
                    "correct": False,
                    "confidence": confidence,
                    "user_answer": user_answer,
                    "correct_answer": correct_answer,
                    "message": self._get_incorrect_message(correct_answer, language),
                    "proceed_to_next": False,
                    "misconception_analysis": misconception
                }
            
        except Exception as e:
            logger.error(f"[LRNG] Error validating answer: {str(e)}", exc_info=True)
            # Fallback to exact match
            is_correct = self._is_exact_match(user_answer, correct_answer)
            return {
                "correct": is_correct,
                "confidence": 1.0 if is_correct else 0.5,
                "message": self._get_correct_message(language) if is_correct else self._get_incorrect_message(correct_answer, language),
                "proceed_to_next": is_correct
            }
    
    def generate_hint(
        self,
        correct_answer: str,
        question: str,
        context: Dict[str, Any],
        hint_level: int = 1,
        language: str = 'en'
    ) -> Dict[str, Any]:
        """
        Generate progressive hint based on level.
        
        Args:
            correct_answer: The correct answer
            question: The question
            context: Node context
            hint_level: 1 (vague) to 3 (explicit)
            language: 'en' or 'zh'
        
        Returns:
            {
                "hint": "...",
                "hint_level": 2,
                "max_hints": 3
            }
        """
        try:
            # Build prompt for hint generation
            prompt = self._build_hint_prompt(correct_answer, question, context, hint_level, language)
            
            # Generate hint with LLM
            response = self.llm._call(prompt)
            
            hint_text = response.strip()
            
            logger.info(f"[LRNG] Generated hint level {hint_level}/3 | {language}")
            
            return {
                "hint": hint_text,
                "hint_level": hint_level,
                "max_hints": 3
            }
            
        except Exception as e:
            logger.error(f"[LRNG] Error generating hint: {str(e)}", exc_info=True)
            # Fallback to simple hint
            return {
                "hint": self._get_fallback_hint(correct_answer, hint_level, language),
                "hint_level": hint_level,
                "max_hints": 3
            }
    
    def verify_understanding(
        self,
        user_answer: str,
        correct_answer: str,
        verification_question: str,
        language: str = 'en'
    ) -> Dict[str, Any]:
        """
        Verify understanding after learning material.
        
        Args:
            user_answer: User's answer to verification question
            correct_answer: Correct answer
            verification_question: The verification question
            language: 'en' or 'zh'
        
        Returns:
            {
                "understanding_verified": true/false,
                "confidence": 0.92,
                "message": "..."
            }
        """
        try:
            # Similar to validate_answer but with understanding focus
            is_correct, confidence = self._semantic_validation(
                user_answer, correct_answer, verification_question, {}, language
            )
            
            if is_correct:
                message = "✅ " + ("理解已验证！你已经掌握了这个概念。" if language == 'zh' else "Understanding verified! You've mastered this concept.")
            else:
                message = "⚠️ " + ("让我们换个角度再试试..." if language == 'zh' else "Let's try a different approach...")
            
            return {
                "understanding_verified": is_correct,
                "confidence": confidence,
                "message": message
            }
            
        except Exception as e:
            logger.error(f"[LRNG] Error verifying understanding: {str(e)}", exc_info=True)
            return {
                "understanding_verified": False,
                "confidence": 0.5,
                "message": "Error verifying understanding"
            }
    
    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================
    
    def _extract_node_context(
        self,
        node_id: str,
        diagram_type: str,
        spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract contextual information about a node from the diagram.
        
        Returns:
            {
                "parent": "...",
                "siblings": [...],
                "position": "...",
                "diagram_type": "..."
            }
        """
        context = {
            "diagram_type": diagram_type,
            "node_id": node_id
        }
        
        try:
            if diagram_type == 'bubble_map':
                # Extract topic and sibling attributes
                topic = spec.get('topic', 'Central Topic')
                # Handle both string and dict formats
                if isinstance(topic, dict):
                    context['parent'] = topic.get('text', 'Central Topic')
                else:
                    context['parent'] = str(topic)
                
                # Get all attributes
                attributes = spec.get('attributes', [])
                siblings = []
                for attr in attributes:
                    if isinstance(attr, dict):
                        siblings.append(attr.get('text', ''))
                    else:
                        siblings.append(str(attr))
                
                # Remove the current node from siblings
                node_idx = int(node_id.split('_')[-1])
                if node_idx < len(siblings):
                    siblings_filtered = siblings[:node_idx] + siblings[node_idx+1:]
                    context['siblings'] = siblings_filtered
                    context['position'] = f"{node_idx + 1} of {len(attributes)}"
            
            elif diagram_type == 'mind_map':
                # Extract branches and children
                if 'branch' in node_id:
                    # It's a branch
                    main_topic = spec.get('mainTopic', 'Main Topic')
                    if isinstance(main_topic, dict):
                        context['parent'] = main_topic.get('text', 'Main Topic')
                    else:
                        context['parent'] = str(main_topic)
                    branches = spec.get('branches', [])
                    siblings = []
                    for b in branches:
                        if isinstance(b, dict):
                            siblings.append(b.get('text', ''))
                        else:
                            siblings.append(str(b))
                    context['siblings'] = siblings
                elif 'child' in node_id:
                    # It's a child
                    parts = node_id.split('_')
                    if len(parts) >= 3:
                        branch_idx = int(parts[1])
                        branches = spec.get('branches', [])
                        if branch_idx < len(branches):
                            branch = branches[branch_idx]
                            context['parent'] = branch.get('text', 'Branch')
                            children = branch.get('children', [])
                            context['siblings'] = [c.get('text', '') for c in children]
            
            # Add more diagram types as needed
            
        except Exception as e:
            logger.error(f"[LRNG] Error extracting node context: {str(e)}")
        
        return context
    
    def _build_question_prompt(
        self,
        node_id: str,
        context: Dict[str, Any],
        diagram_type: str,
        language: str
    ) -> str:
        """
        Build prompt for generating a contextual question.
        """
        if language == 'zh':
            parent = context.get('parent', '主题')
            siblings = context.get('siblings', [])
            siblings_text = '、'.join(siblings[:3]) if siblings else '其他节点'
            
            prompt = f"""你是一个教育专家，正在帮助学生通过主动回忆来学习图示内容。

图示类型：{diagram_type}
中心主题：{parent}
相关节点：{siblings_text}

请为一个被隐藏的节点生成一个简短、清晰的问题，帮助学生回忆这个节点的内容。

要求：
1. 问题要简短（不超过30个字）
2. 提供足够的上下文提示，但不直接给出答案
3. 使用"这个节点"、"这个与...相连的节点"等表达
4. 语气友好、鼓励性
5. 只输出问题本身，不要包含任何其他内容

问题："""
        
        else:  # English
            parent = context.get('parent', 'topic')
            siblings = context.get('siblings', [])
            siblings_text = ', '.join(siblings[:3]) if siblings else 'other nodes'
            
            prompt = f"""You are an educational expert helping students learn through active recall.

Diagram type: {diagram_type}
Central topic: {parent}
Related nodes: {siblings_text}

Generate a short, clear question to help the student recall the hidden node's content.

Requirements:
1. Keep question concise (under 30 words)
2. Provide sufficient context without giving away the answer
3. Use phrases like "this node", "the node connected to..."
4. Friendly, encouraging tone
5. Output ONLY the question, nothing else

Question:"""
        
        return prompt
    
    def _build_hint_prompt(
        self,
        correct_answer: str,
        question: str,
        context: Dict[str, Any],
        hint_level: int,
        language: str
    ) -> str:
        """
        Build prompt for generating progressive hints.
        """
        level_descriptions = {
            1: ("subtle, without giving away much", "微妙的提示，不要透露太多"),
            2: ("clearer hint with some specific clues", "更清晰的提示，包含一些具体线索"),
            3: ("explicit hint that almost gives the answer", "明确的提示，几乎给出答案")
        }
        
        level_desc = level_descriptions[hint_level][1] if language == 'zh' else level_descriptions[hint_level][0]
        
        if language == 'zh':
            prompt = f"""你是一个教育专家，正在为学生提供渐进式提示。

问题：{question}
正确答案：{correct_answer}
当前提示级别：{hint_level}/3

请生成一个{level_desc}。

要求：
1. 级别1：只提供概念类别或领域的提示
2. 级别2：提供更具体的特征或关联
3. 级别3：几乎直接点明答案，但不要完全说出来
4. 保持简短（不超过40个字）
5. 语气友好、鼓励
6. 只输出提示本身，不要包含"提示："等前缀

提示："""
        
        else:  # English
            prompt = f"""You are an educational expert providing progressive hints to a student.

Question: {question}
Correct answer: {correct_answer}
Current hint level: {hint_level}/3

Generate a {level_desc}.

Requirements:
1. Level 1: Provide category or domain hints only
2. Level 2: Give more specific characteristics or associations
3. Level 3: Almost reveal the answer without saying it directly
4. Keep it concise (under 40 words)
5. Friendly, encouraging tone
6. Output ONLY the hint, no prefix like "Hint:"

Hint:"""
        
        return prompt
    
    def _semantic_validation(
        self,
        user_answer: str,
        correct_answer: str,
        question: str,
        context: Dict[str, Any],
        language: str
    ) -> tuple[bool, float]:
        """
        Use LLM to validate if user answer is semantically correct.
        
        Returns:
            (is_correct, confidence)
        """
        try:
            if language == 'zh':
                prompt = f"""判断学生的答案是否与标准答案在语义上一致。

问题：{question}
标准答案：{correct_answer}
学生答案：{user_answer}

请判断学生答案是否正确。考虑：
1. 同义词（例如："太阳"="阳光"）
2. 不同表达方式（例如："H2O"="水"）
3. 拼写或标点的小错误
4. 但注意：概念性错误不算正确（例如："氧气"≠"阳光"）

请严格按照以下格式回答：
正确性：正确/错误
置信度：0.0-1.0的数字
理由：简短说明（一句话）

回答："""
            
            else:  # English
                prompt = f"""Judge if the student's answer is semantically equivalent to the correct answer.

Question: {question}
Correct answer: {correct_answer}
Student answer: {user_answer}

Consider:
1. Synonyms (e.g., "sun" = "sunlight")
2. Different expressions (e.g., "H2O" = "water")
3. Minor spelling or punctuation errors
4. BUT: Conceptual errors don't count (e.g., "oxygen" ≠ "sunlight")

Respond STRICTLY in this format:
Correctness: correct/incorrect
Confidence: number between 0.0-1.0
Reason: brief explanation (one sentence)

Answer:"""
            
            response = self.llm._call(prompt)
            
            # Parse response
            lines = response.strip().split('\n')
            is_correct = False
            confidence = 0.5
            
            for line in lines:
                line = line.strip()
                if ('正确性' in line or 'Correctness' in line) and '正确' in line:
                    is_correct = True
                elif ('置信度' in line or 'Confidence' in line):
                    try:
                        confidence = float(line.split(':')[-1].strip())
                    except:
                        confidence = 0.8 if is_correct else 0.5
            
            return is_correct, confidence
            
        except Exception as e:
            logger.error(f"[LRNG] Error in semantic validation: {str(e)}")
            # Fallback to exact match
            return self._is_exact_match(user_answer, correct_answer), 0.5
    
    def _analyze_misconception(
        self,
        user_answer: str,
        correct_answer: str,
        question: str,
        context: Dict[str, Any],
        language: str
    ) -> Dict[str, Any]:
        """
        Analyze what misconception led to the wrong answer.
        """
        try:
            if language == 'zh':
                prompt = f"""分析学生的误解类型。

问题：{question}
正确答案：{correct_answer}
学生答案：{user_answer}

请分析学生可能有什么误解，并提供简短的诊断。

回答格式：
误解类型：[混淆概念/因果倒置/记忆错误/其他]
诊断：[一句话说明学生的理解错误]

回答："""
            
            else:  # English
                prompt = f"""Analyze the type of misconception.

Question: {question}
Correct answer: {correct_answer}
Student answer: {user_answer}

Analyze what misconception the student might have and provide a brief diagnosis.

Format:
Misconception type: [concept_confusion/causal_reversal/memory_error/other]
Diagnosis: [one sentence explaining the student's misunderstanding]

Answer:"""
            
            response = self.llm._call(prompt)
            
            # Parse response
            lines = response.strip().split('\n')
            misconception_type = "other"
            diagnosis = response.strip()
            
            for line in lines:
                if '误解类型' in line or 'Misconception type' in line:
                    misconception_type = line.split(':')[-1].strip()
                elif '诊断' in line or 'Diagnosis' in line:
                    diagnosis = line.split(':')[-1].strip()
            
            return {
                "type": misconception_type,
                "diagnosis": diagnosis,
                "severity": "medium",
                "user_answer": user_answer,
                "correct_answer": correct_answer
            }
            
        except Exception as e:
            logger.error(f"[LRNG] Error analyzing misconception: {str(e)}")
            return {
                "type": "unknown",
                "diagnosis": "Unable to analyze misconception",
                "severity": "medium"
            }
    
    def _assess_difficulty(self, context: Dict[str, Any], diagram_type: str) -> str:
        """
        Assess question difficulty based on context.
        """
        # Simple heuristic for now
        if context.get('siblings') and len(context.get('siblings', [])) > 5:
            return "hard"
        elif context.get('siblings') and len(context.get('siblings', [])) > 2:
            return "medium"
        else:
            return "easy"
    
    def _is_exact_match(self, user_answer: str, correct_answer: str) -> bool:
        """
        Check if answers match exactly (case-insensitive, trimmed).
        """
        return user_answer.lower().strip().replace(' ', '') == correct_answer.lower().strip().replace(' ', '')
    
    def _get_correct_message(self, language: str) -> str:
        """
        Get encouraging message for correct answer.
        """
        if language == 'zh':
            messages = [
                "✅ 完全正确！",
                "✅ 太棒了！",
                "✅ 你理解得很好！",
                "✅ 答对了！"
            ]
        else:
            messages = [
                "✅ Correct!",
                "✅ Excellent!",
                "✅ Well done!",
                "✅ That's right!"
            ]
        
        import random
        return random.choice(messages)
    
    def _get_incorrect_message(self, correct_answer: str, language: str) -> str:
        """
        Get message for incorrect answer.
        """
        if language == 'zh':
            return f"❌ 不完全正确。正确答案是：{correct_answer}"
        else:
            return f"❌ Not quite. The correct answer is: {correct_answer}"
    
    def _get_fallback_question(self, node_id: str, language: str) -> str:
        """
        Get simple fallback question if LLM fails.
        """
        if language == 'zh':
            return f"请填写节点 {node_id} 的内容"
        else:
            return f"What is the content of node {node_id}?"
    
    def _get_fallback_hint(self, correct_answer: str, hint_level: int, language: str) -> str:
        """
        Get simple fallback hint if LLM fails.
        """
        if hint_level == 3:
            # Level 3: Give first character and length
            if language == 'zh':
                return f"💡 答案以「{correct_answer[0]}」开头，共{len(correct_answer)}个字。"
            else:
                return f"💡 The answer starts with '{correct_answer[0]}' and has {len(correct_answer)} characters."
        elif hint_level == 2:
            # Level 2: Give first character
            if language == 'zh':
                return f"💡 答案以「{correct_answer[0]}」开头。"
            else:
                return f"💡 The answer starts with '{correct_answer[0]}'."
        else:
            # Level 1: Give category hint
            if language == 'zh':
                return "💡 想想图示的主题和这个节点的位置。"
            else:
                return "💡 Think about the diagram's theme and this node's position."

