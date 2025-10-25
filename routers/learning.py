"""
Learning Mode API Routes (FastAPI)
===================================

LangChain-powered intelligent tutoring system endpoints.
Migrated from Flask Blueprint to FastAPI Router.

Author: lycosa9527
Made by: MindSpring Team
"""

import logging
import time
import random
import json
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse

# Import authentication
from models.auth import User
from utils.auth import get_current_user

from models import (
    LearningStartSessionRequest,
    LearningValidateAnswerRequest,
    LearningHintRequest,
    LearningVerifyUnderstandingRequest,
    Messages,
    get_request_language,
)
from agents.learning.learning_agent import LearningAgent
from agents.learning.learning_agent_v3 import LearningAgentV3

logger = logging.getLogger(__name__)

# Create FastAPI router
router = APIRouter(prefix="/learning", tags=["learning"])

# Global session storage (in production, use Redis or database)
learning_sessions: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# Helper Functions
# ============================================================================

def _extract_node_text(node_id: str, spec: Dict, diagram_type: str) -> str:
    """Extract node text from diagram spec by node_id."""
    try:
        if diagram_type == 'bubble_map':
            attributes = spec.get('attributes', [])
            # Match attribute_0, attribute_1, etc.
            if node_id.startswith('attribute_'):
                try:
                    index = int(node_id.split('_')[1])
                    if 0 <= index < len(attributes):
                        return attributes[index]
                except (IndexError, ValueError):
                    pass
        
        elif diagram_type == 'circle_map':
            context = spec.get('context', [])
            if node_id.startswith('context_'):
                try:
                    index = int(node_id.split('_')[1])
                    if 0 <= index < len(context):
                        return context[index]
                except (IndexError, ValueError):
                    pass
        
        elif diagram_type == 'tree_map':
            # Tree maps have nested children structure
            children = spec.get('children', [])
            for branch in children:
                branch_children = branch.get('children', [])
                for i, leaf in enumerate(branch_children):
                    if leaf.get('id') == node_id or f"leaf_{i}" == node_id:
                        return leaf.get('text', '')
        
        # Add more diagram types as needed
        
        return ""
        
    except Exception as e:
        logger.error(f"Error extracting node text: {e}")
        return ""


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/start_session")
async def start_session(
    request: Request,
    req: LearningStartSessionRequest,
    current_user: User = Depends(get_current_user)
) -> JSONResponse:
    """
    Initialize a new learning session with intelligent question generation.
    
    POST /api/learning/start_session
    """
    try:
        language_code = get_request_language(
            language_header=request.headers.get("X-Language"),
            accept_language=request.headers.get("Accept-Language")
        )
        
        diagram_type = req.diagram_type
        spec = req.spec
        knocked_out_nodes = req.knocked_out_nodes
        language = req.language.value
        
        # Create learning agents (V2 for questions, V3 for prerequisite testing)
        agent_v2 = LearningAgent(language=language)
        agent_v3 = LearningAgentV3(language=language)
        
        # Generate session ID
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
            'agent_v2': agent_v2,
            'agent_v3': agent_v3,
            'answers': {},
            'prerequisite_tests': {},
            'created_at': time.time()
        }
        
        logger.info(f"[LRNG] Created session: {session_id} | {len(questions)} questions | Lang: {language}")
        
        return JSONResponse(content={
            'success': True,
            'session_id': session_id,
            'questions': questions,
            'total_questions': len(questions)
        })
        
    except Exception as e:
        logger.error(f"[LRNG] Error starting session: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error('learning_session_start_failed', language_code)
        )


@router.post("/validate_answer")
async def validate_answer(
    request: Request,
    req: LearningValidateAnswerRequest,
    current_user: User = Depends(get_current_user)
) -> JSONResponse:
    """
    Validate user answer with LangChain agent analysis.
    
    POST /api/learning/validate_answer
    """
    try:
        language_code = get_request_language(
            language_header=request.headers.get("X-Language"),
            accept_language=request.headers.get("Accept-Language")
        )
        
        session_id = req.session_id
        node_id = req.node_id
        user_answer = req.user_answer
        question = req.question
        context = req.context
        language = req.language.value
        
        # Get session
        session = learning_sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=Messages.error('learning_session_not_found', language_code)
            )
        
        # Get correct answer from spec
        correct_answer = _extract_node_text(node_id, session['spec'], session['diagram_type'])
        
        if not correct_answer:
            raise HTTPException(
                status_code=404,
                detail=Messages.error('learning_node_not_found', language_code)
            )
        
        # Get agents
        agent_v2 = session['agent_v2']
        agent_v3 = session['agent_v3']
        
        # Validate answer with V2 agent
        validation_result = agent_v2.validate_answer(
            user_answer=user_answer,
            correct_answer=correct_answer,
            question=question or "",
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
                # Run V3 agent to analyze misconception
                agent_workflow = agent_v3.process_wrong_answer(
                    user_answer=user_answer,
                    correct_answer=correct_answer,
                    question=question or "",
                    context=context
                )
                
                validation_result['agent_workflow'] = agent_workflow
                validation_result['prerequisite_testing_enabled'] = True
                
                # Try to parse prerequisite test from agent response
                try:
                    agent_response = agent_workflow.get('agent_response', '')
                    if '{' in agent_response and '}' in agent_response:
                        start_idx = agent_response.find('{')
                        end_idx = agent_response.rfind('}') + 1
                        json_str = agent_response[start_idx:end_idx]
                        prerequisite_test = json.loads(json_str)
                        validation_result['prerequisite_test'] = prerequisite_test
                        
                        # Store prerequisite test in session
                        session['prerequisite_tests'][node_id] = prerequisite_test
                        
                except json.JSONDecodeError as json_err:
                    logger.warning(f"[LRNG] Could not parse prerequisite test JSON: {json_err}")
            
            except Exception as v3_err:
                logger.error(f"[LRNG] V3 agent error: {v3_err}", exc_info=True)
                validation_result['prerequisite_testing_enabled'] = False
        
        logger.info(f"[LRNG] Validated answer: {session_id} | Node: {node_id} | Correct: {validation_result['correct']}")
        
        return JSONResponse(content=validation_result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LRNG] Error validating answer: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error('learning_validation_failed', language_code)
        )


@router.post("/get_hint")
async def get_hint(
    request: Request,
    req: LearningHintRequest,
    current_user: User = Depends(get_current_user)
) -> JSONResponse:
    """
    Generate intelligent hint for a question.
    
    POST /api/learning/get_hint
    """
    try:
        language_code = get_request_language(
            language_header=request.headers.get("X-Language"),
            accept_language=request.headers.get("Accept-Language")
        )
        
        session_id = req.session_id
        node_id = req.node_id
        question = req.question
        context = req.context
        hint_level = req.hint_level
        language = req.language.value
        
        # Get session
        session = learning_sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=Messages.error('learning_session_not_found', language_code)
            )
        
        # Get correct answer from spec
        correct_answer = _extract_node_text(node_id, session['spec'], session['diagram_type'])
        
        if not correct_answer:
            raise HTTPException(
                status_code=404,
                detail=Messages.error('learning_node_not_found', language_code)
            )
        
        # Get agent
        agent_v2 = session['agent_v2']
        
        # Generate hint
        hint_result = agent_v2.generate_hint(
            node_id=node_id,
            correct_answer=correct_answer,
            question=question,
            context=context,
            hint_level=hint_level,
            language=language
        )
        
        logger.info(f"[LRNG] Generated hint: {session_id} | Node: {node_id} | Level: {hint_level}")
        
        return JSONResponse(content=hint_result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LRNG] Error generating hint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error('learning_hint_failed', language_code)
        )


@router.post("/verify_understanding")
async def verify_understanding(
    request: Request,
    req: LearningVerifyUnderstandingRequest,
    current_user: User = Depends(get_current_user)
) -> JSONResponse:
    """
    Verify user's understanding with deep explanation analysis.
    
    POST /api/learning/verify_understanding
    """
    try:
        language_code = get_request_language(
            language_header=request.headers.get("X-Language"),
            accept_language=request.headers.get("Accept-Language")
        )
        
        session_id = req.session_id
        node_id = req.node_id
        user_explanation = req.user_explanation
        language = req.language.value
        
        # Get session
        session = learning_sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=Messages.error('learning_session_not_found', language_code)
            )
        
        # Get correct answer from spec
        correct_answer = _extract_node_text(node_id, session['spec'], session['diagram_type'])
        
        if not correct_answer:
            raise HTTPException(
                status_code=404,
                detail=Messages.error('learning_node_not_found', language_code)
            )
        
        # Get agent
        agent_v2 = session['agent_v2']
        
        # Verify understanding
        verification_result = agent_v2.verify_understanding(
            user_explanation=user_explanation,
            correct_answer=correct_answer,
            node_id=node_id,
            diagram_spec=session['spec'],
            language=language
        )
        
        logger.info(f"[LRNG] Verified understanding: {session_id} | Node: {node_id}")
        
        return JSONResponse(content=verification_result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LRNG] Error verifying understanding: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error('learning_verification_failed', language_code)
        )

