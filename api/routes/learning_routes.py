"""
Learning Mode API Routes

Handles LangChain-powered intelligent tutoring system endpoints.

@author lycosa9527
@made_by MindSpring Team
"""

from flask import Blueprint, request, jsonify
import logging
from typing import Dict, Any
import json

from agents.learning.learning_agent import LearningAgent
from agents.learning.learning_agent_v3 import LearningAgentV3

logger = logging.getLogger(__name__)

# Create blueprint
learning_bp = Blueprint('learning', __name__)

# Global session storage (in production, use Redis or database)
learning_sessions = {}


@learning_bp.route('/start_session', methods=['POST'])
def start_session():
    """
    Initialize a new learning session with intelligent question generation.
    
    POST /api/learning/start_session
    Body: {
        "diagram_type": "bubble_map",
        "spec": {...},
        "knocked_out_nodes": ["attribute_3", "attribute_5"],
        "language": "zh"
    }
    """
    try:
        data = request.get_json()
        
        diagram_type = data.get('diagram_type')
        spec = data.get('spec')
        knocked_out_nodes = data.get('knocked_out_nodes', [])
        language = data.get('language', 'en')
        
        if not diagram_type or not spec or not knocked_out_nodes:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: diagram_type, spec, knocked_out_nodes'
            }), 400
        
        # Create learning agents (V2 for questions, V3 for prerequisite testing)
        agent_v2 = LearningAgent(language=language)
        agent_v3 = LearningAgentV3(language=language)
        
        # Generate session ID
        import time, random
        session_id = f"learning_{int(time.time())}_{random.randint(1000, 9999)}"
        
        # Generate intelligent questions for each knocked-out node
        questions = []
        for node_id in knocked_out_nodes:
            question_data = agent_v2.generate_question(
                node_id=node_id,
                diagram_type=diagram_type,
                spec=spec,
                language=language
            )
            questions.append(question_data)
        
        # Store session
        learning_sessions[session_id] = {
            'session_id': session_id,
            'diagram_type': diagram_type,
            'spec': spec,
            'knocked_out_nodes': knocked_out_nodes,
            'questions': questions,
            'language': language,
            'agent_v2': agent_v2,  # For question generation
            'agent_v3': agent_v3,  # For prerequisite testing
            'answers': {},  # Track user answers
            'prerequisite_tests': {},  # Track prerequisite test results
            'created_at': time.time()
        }
        
        logger.info(f"[LRNG] Created learning session: {session_id} | {len(questions)} questions | Lang: {language}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'questions': questions,
            'total_questions': len(questions)
        })
        
    except Exception as e:
        logger.error(f"[LRNG] Error starting session: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@learning_bp.route('/validate_answer', methods=['POST'])
def validate_answer():
    """
    Validate user answer with LangChain agent analysis.
    
    POST /api/learning/validate_answer
    Body: {
        "session_id": "learning_123",
        "node_id": "attribute_3",
        "user_answer": "氧气",
        "question": "...",
        "context": {...},
        "language": "zh"
    }
    """
    try:
        data = request.get_json()
        
        session_id = data.get('session_id')
        node_id = data.get('node_id')
        user_answer = data.get('user_answer')
        question = data.get('question')
        context = data.get('context', {})
        language = data.get('language', 'en')
        
        if not session_id or not node_id or not user_answer:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: session_id, node_id, user_answer'
            }), 400
        
        # Get session
        session = learning_sessions.get(session_id)
        if not session:
            return jsonify({
                'success': False,
                'error': 'Session not found or expired'
            }), 404
        
        # Get correct answer from spec
        correct_answer = _extract_node_text(node_id, session['spec'], session['diagram_type'])
        
        if not correct_answer:
            return jsonify({
                'success': False,
                'error': 'Node not found in diagram spec'
            }), 404
        
        # Get agents
        agent_v2 = session['agent_v2']
        agent_v3 = session['agent_v3']
        
        # Validate answer with V2 agent
        validation_result = agent_v2.validate_answer(
            user_answer=user_answer,
            correct_answer=correct_answer,
            question=question,
            context=context,
            language=language
        )
        
        # Store answer
        session['answers'][node_id] = {
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': validation_result['correct'],
            'attempts': session['answers'].get(node_id, {}).get('attempts', 0) + 1
        }
        
        # If answer is WRONG, trigger V3 agent for prerequisite testing
        if not validation_result['correct']:
            logger.info(f"[LRNG] Answer WRONG - Triggering V3 agent for prerequisite analysis")
            
            try:
                # Run V3 agent to analyze misconception and generate prerequisite test
                agent_workflow = agent_v3.process_wrong_answer(
                    user_answer=user_answer,
                    correct_answer=correct_answer,
                    question=question,
                    context=context
                )
                
                # Add agent workflow results to validation result
                validation_result['agent_workflow'] = agent_workflow
                validation_result['prerequisite_testing_enabled'] = True
                
                # Try to parse prerequisite test from agent response
                try:
                    agent_response = agent_workflow.get('agent_response', '')
                    # Look for JSON blocks in the response
                    if '{' in agent_response and '}' in agent_response:
                        # Extract JSON (this is a simple extraction, could be improved)
                        start_idx = agent_response.find('{')
                        end_idx = agent_response.rfind('}') + 1
                        json_str = agent_response[start_idx:end_idx]
                        prerequisite_data = json.loads(json_str)
                        validation_result['prerequisite_test'] = prerequisite_data
                except Exception as json_error:
                    logger.warning(f"[LRNG] Could not parse prerequisite test from agent response: {str(json_error)}")
                
                logger.info(f"[LRNG] V3 Agent workflow completed | Steps: {agent_workflow.get('steps_taken', 0)}")
                
            except Exception as agent_error:
                logger.error(f"[LRNG] V3 Agent error: {str(agent_error)}", exc_info=True)
                validation_result['agent_error'] = str(agent_error)
                validation_result['prerequisite_testing_enabled'] = False
        
        logger.info(f"[LRNG] Answer validation: {session_id} | {node_id} | "
                   f"{'✓' if validation_result['correct'] else '✗'} | {user_answer} vs {correct_answer}")
        
        return jsonify(validation_result)
        
    except Exception as e:
        logger.error(f"[LRNG] Error validating answer: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@learning_bp.route('/get_hint', methods=['POST'])
def get_hint():
    """
    Get intelligent hint from LangChain agent.
    
    POST /api/learning/get_hint
    Body: {
        "session_id": "learning_123",
        "node_id": "attribute_3",
        "question": "...",
        "context": {...},
        "hint_level": 1,
        "language": "zh"
    }
    """
    try:
        data = request.get_json()
        
        session_id = data.get('session_id')
        node_id = data.get('node_id')
        question = data.get('question')
        context = data.get('context', {})
        hint_level = data.get('hint_level', 1)
        language = data.get('language', 'en')
        
        if not session_id or not node_id:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: session_id, node_id'
            }), 400
        
        # Get session
        session = learning_sessions.get(session_id)
        if not session:
            return jsonify({
                'success': False,
                'error': 'Session not found or expired'
            }), 404
        
        # Get correct answer
        correct_answer = _extract_node_text(node_id, session['spec'], session['diagram_type'])
        
        # Get agent (V2 for hint generation)
        agent_v2 = session['agent_v2']
        
        # Generate hint
        hint_data = agent_v2.generate_hint(
            correct_answer=correct_answer,
            question=question,
            context=context,
            hint_level=hint_level,
            language=language
        )
        
        logger.info(f"[LRNG] Hint requested: {session_id} | {node_id} | Level {hint_level}")
        
        return jsonify(hint_data)
        
    except Exception as e:
        logger.error(f"[LRNG] Error generating hint: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@learning_bp.route('/verify_understanding', methods=['POST'])
def verify_understanding():
    """
    Verify understanding with multi-angle question after learning material.
    
    POST /api/learning/verify_understanding
    Body: {
        "session_id": "learning_123",
        "node_id": "attribute_3",
        "user_answer": "阳光",
        "verification_question": "...",
        "language": "zh"
    }
    """
    try:
        data = request.get_json()
        
        session_id = data.get('session_id')
        node_id = data.get('node_id')
        user_answer = data.get('user_answer')
        verification_question = data.get('verification_question')
        language = data.get('language', 'en')
        
        if not session_id or not node_id or not user_answer:
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
        
        # Get session
        session = learning_sessions.get(session_id)
        if not session:
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404
        
        # Get correct answer
        correct_answer = _extract_node_text(node_id, session['spec'], session['diagram_type'])
        
        # Get agent (V2 for verification)
        agent_v2 = session['agent_v2']
        
        # Verify understanding
        verification_result = agent_v2.verify_understanding(
            user_answer=user_answer,
            correct_answer=correct_answer,
            verification_question=verification_question,
            language=language
        )
        
        logger.info(f"[LRNG] Understanding verification: {session_id} | {node_id} | "
                   f"{'✓ Verified' if verification_result['understanding_verified'] else '✗ Not verified'}")
        
        return jsonify(verification_result)
        
    except Exception as e:
        logger.error(f"[LRNG] Error verifying understanding: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _extract_node_text(node_id: str, spec: Dict[str, Any], diagram_type: str) -> str:
    """
    Extract node text from diagram specification.
    
    Args:
        node_id: Node ID (e.g., 'attribute_3', 'branch_1')
        spec: Diagram specification
        diagram_type: Type of diagram
    
    Returns:
        Node text or empty string if not found
    """
    try:
        # Handle special case: topic_center (central node)
        if node_id == 'topic_center' and diagram_type == 'bubble_map':
            topic = spec.get('topic', '')
            if isinstance(topic, dict):
                return topic.get('text', '')
            else:
                return str(topic)
        
        # Parse node ID (e.g., 'attribute_3' -> type='attribute', index=3)
        parts = node_id.rsplit('_', 1)
        if len(parts) != 2:
            return ''
        
        node_type, index_str = parts
        try:
            index = int(index_str)
        except ValueError:
            return ''
        
        # Extract text based on diagram type and node type
        if diagram_type == 'bubble_map' and node_type == 'attribute':
            if 'attributes' in spec and index < len(spec['attributes']):
                attr = spec['attributes'][index]
                # Handle both string and dict formats
                if isinstance(attr, dict):
                    return attr.get('text', '')
                else:
                    return str(attr)
        
        elif diagram_type == 'mind_map':
            if node_type == 'branch' and 'branches' in spec and index < len(spec['branches']):
                branch = spec['branches'][index]
                if isinstance(branch, dict):
                    return branch.get('text', '')
                else:
                    return str(branch)
            elif node_type == 'child':
                # Parse child index (e.g., 'child_0_1' -> branch 0, child 1)
                child_parts = node_id.split('_')
                if len(child_parts) == 3:
                    branch_idx = int(child_parts[1])
                    child_idx = int(child_parts[2])
                    if 'branches' in spec and branch_idx < len(spec['branches']):
                        branch = spec['branches'][branch_idx]
                        if isinstance(branch, dict) and 'children' in branch and child_idx < len(branch['children']):
                            child = branch['children'][child_idx]
                            if isinstance(child, dict):
                                return child.get('text', '')
                            else:
                                return str(child)
        
        # Add more diagram types as needed
        
        return ''
        
    except Exception as e:
        logger.error(f"[LRNG] Error extracting node text: {str(e)}")
        return ''

