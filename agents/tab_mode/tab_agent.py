"""
Tab Mode Agent
==============

Agent for generating tab completion suggestions and node expansions.
Uses LangChain with Qwen-plus for structured, tool-based context extraction.

@author MindGraph Team
"""

import logging
import json
import re
import time
from typing import Dict, List, Any, Optional
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field
from langgraph.prebuilt import create_react_agent

from ..core.base_agent import BaseAgent
from agents.learning.qwen_langchain import QwenLLM
from prompts import get_prompt
from services.llm_service import llm_service
from services.error_handler import LLMServiceError

logger = logging.getLogger(__name__)


# ============================================================================
# PYDANTIC MODELS FOR STRUCTURED OUTPUTS
# ============================================================================

class SuggestionItem(BaseModel):
    """Individual suggestion item"""
    text: str = Field(..., description="Suggestion text")
    confidence: float = Field(0.9, ge=0.0, le=1.0, description="Confidence score")


class SuggestionsResponse(BaseModel):
    """Structured response for suggestions"""
    suggestions: List[SuggestionItem] = Field(..., description="List of suggestions")


class ExpansionChild(BaseModel):
    """Child node for expansion"""
    text: str = Field(..., description="Child node text")
    id: str = Field(..., description="Child node ID")


class ExpansionResponse(BaseModel):
    """Structured response for expansion"""
    children: List[ExpansionChild] = Field(..., description="Generated child nodes")


# ============================================================================
# LANGCHAIN TOOLS FOR CONTEXT EXTRACTION
# ============================================================================

class TabAgent(BaseAgent):
    """
    Tab Agent using LangChain for structured context extraction and LLM calls.
    
    Uses tools for:
    - Diagram context extraction
    - Node information extraction
    - Spec structure parsing
    """
    
    def __init__(self, model='qwen-plus'):
        """
        Initialize Tab Agent with LangChain.
        
        Args:
            model: LLM model to use. Default 'qwen-plus' for generation tasks.
        """
        super().__init__(model=model)
        self.diagram_type = "tab_mode"
        
        # Initialize LangChain LLM wrapper
        self.llm = QwenLLM(model_type='generation')
        
        # Create tools
        self.tools = self._create_tools()
        
        # Create agent (for future multi-step workflows)
        # For now, we'll use tools directly, but agent is ready for expansion
        self.agent = None  # Can be created later if needed for complex workflows
        
        logger.info("TabAgent initialized", {
            'model': model,
            'diagram_type': self.diagram_type,
            'tools_count': len(self.tools) if self.tools else 0
        })
    
    def _create_tools(self) -> List:
        """Create LangChain tools for context extraction and processing."""
        
        @tool
        def extract_diagram_context(
            diagram_type: str,
            spec: Dict[str, Any]
        ) -> str:
            """
            Extract main topics and structure from diagram spec.
            
            Args:
                diagram_type: Type of diagram (mindmap, double_bubble_map, etc.)
                spec: Diagram specification dictionary
            
            Returns:
                JSON string with extracted context
            """
            try:
                logger.debug("TabAgent: Extracting diagram context", {
                    'diagram_type': diagram_type,
                    'spec_keys': list(spec.keys()) if isinstance(spec, dict) else []
                })
                
                context = {}
                
                if diagram_type == 'double_bubble_map':
                    context = {
                        'main_topics': [spec.get('left', ''), spec.get('right', '')],
                        'has_similarities': bool(spec.get('similarities')),
                        'has_left_differences': bool(spec.get('left_differences')),
                        'has_right_differences': bool(spec.get('right_differences'))
                    }
                elif diagram_type == 'mindmap':
                    context = {
                        'main_topic': spec.get('topic', ''),
                        'num_branches': len(spec.get('children', [])),
                        'has_children': any(
                            branch.get('children') 
                            for branch in spec.get('children', [])
                        )
                    }
                elif diagram_type == 'tree_map':
                    context = {
                        'main_topic': spec.get('topic', ''),
                        'num_categories': len(spec.get('children', [])),
                        'has_items': any(
                            cat.get('children')
                            for cat in spec.get('children', [])
                        )
                    }
                elif diagram_type == 'flow_map':
                    context = {
                        'title': spec.get('title', ''),
                        'num_steps': len(spec.get('steps', [])),
                        'has_substeps': any(
                            step.get('substeps')
                            for step in spec.get('steps', [])
                        )
                    }
                elif diagram_type == 'brace_map':
                    context = {
                        'whole': spec.get('whole', ''),
                        'num_parts': len(spec.get('parts', [])),
                        'has_subparts': any(
                            part.get('subparts')
                            for part in spec.get('parts', [])
                        )
                    }
                elif diagram_type == 'bubble_map':
                    context = {
                        'topic': spec.get('topic', ''),
                        'num_attributes': len(spec.get('attributes', []))
                    }
                elif diagram_type == 'circle_map':
                    context = {
                        'topic': spec.get('topic', ''),
                        'num_context': len(spec.get('context', []))
                    }
                elif diagram_type == 'bridge_map':
                    context = {
                        'dimension': spec.get('dimension', ''),
                        'num_analogies': len(spec.get('analogies', []))
                    }
                elif diagram_type == 'multi_flow_map':
                    context = {
                        'event': spec.get('event', ''),
                        'num_causes': len(spec.get('causes', [])),
                        'num_effects': len(spec.get('effects', []))
                    }
                else:
                    context = {
                        'main_topic': spec.get('topic', spec.get('title', '')),
                        'structure': 'generic'
                    }
                
                result = json.dumps(context, ensure_ascii=False)
                logger.debug("TabAgent: Diagram context extracted", {
                    'diagram_type': diagram_type,
                    'context_keys': list(context.keys()),
                    'context_preview': str(context)[:200]
                })
                return result
                
            except Exception as e:
                logger.error("TabAgent: Error extracting diagram context", {
                    'diagram_type': diagram_type,
                    'error': str(e)
                }, exc_info=True)
                return json.dumps({'error': str(e)})
        
        @tool
        def extract_node_info(
            node_id: str,
            node_type: str,
            diagram_type: str,
            spec: Dict[str, Any]
        ) -> str:
            """
            Extract node-specific information from spec.
            
            Args:
                node_id: Node ID (e.g., 'similarity_0', 'branch_1', 'child_1_2')
                node_type: Node type ('similarity', 'branch', 'child', etc.)
                diagram_type: Type of diagram
                spec: Diagram specification
            
            Returns:
                JSON string with node information
            """
            try:
                logger.debug("TabAgent: Extracting node info", {
                    'node_id': node_id,
                    'node_type': node_type,
                    'diagram_type': diagram_type
                })
                
                info = {
                    'node_id': node_id,
                    'node_type': node_type,
                    'diagram_type': diagram_type
                }
                
                # Parse node ID to extract indices
                if node_id.startswith('similarity_'):
                    idx = int(node_id.split('_')[1]) if len(node_id.split('_')) > 1 else 0
                    info['category'] = 'similarities'
                    info['index'] = idx
                    if diagram_type == 'double_bubble_map':
                        similarities = spec.get('similarities', [])
                        info['existing_nodes'] = [
                            s if isinstance(s, str) else s.get('text', '')
                            for s in similarities
                        ]
                        info['current_node_text'] = (
                            similarities[idx] if idx < len(similarities) else ''
                        )
                
                elif node_id.startswith('left_diff_'):
                    idx = int(node_id.split('_')[2]) if len(node_id.split('_')) > 2 else 0
                    info['category'] = 'left_differences'
                    info['index'] = idx
                    if diagram_type == 'double_bubble_map':
                        left_diffs = spec.get('left_differences', [])
                        info['existing_nodes'] = [
                            d if isinstance(d, str) else d.get('text', '')
                            for d in left_diffs
                        ]
                        info['current_node_text'] = (
                            left_diffs[idx] if idx < len(left_diffs) else ''
                        )
                
                elif node_id.startswith('right_diff_'):
                    idx = int(node_id.split('_')[2]) if len(node_id.split('_')) > 2 else 0
                    info['category'] = 'right_differences'
                    info['index'] = idx
                    if diagram_type == 'double_bubble_map':
                        right_diffs = spec.get('right_differences', [])
                        info['existing_nodes'] = [
                            d if isinstance(d, str) else d.get('text', '')
                            for d in right_diffs
                        ]
                        info['current_node_text'] = (
                            right_diffs[idx] if idx < len(right_diffs) else ''
                        )
                
                elif node_id.startswith('branch_'):
                    idx = int(node_id.split('_')[1]) if len(node_id.split('_')) > 1 else 0
                    info['branch_index'] = idx
                    if diagram_type == 'mindmap':
                        branches = spec.get('children', [])
                        if idx < len(branches):
                            branch = branches[idx]
                            info['branch_text'] = branch.get('label', branch.get('text', ''))
                            info['existing_children'] = [
                                c.get('label', c.get('text', ''))
                                for c in branch.get('children', [])
                            ]
                
                elif node_id.startswith('child_'):
                    # Format: child_{branch_idx}_{child_idx}
                    parts = node_id.split('_')
                    if len(parts) >= 3:
                        branch_idx = int(parts[1])
                        child_idx = int(parts[2])
                        info['branch_index'] = branch_idx
                        info['child_index'] = child_idx
                        if diagram_type == 'mindmap':
                            branches = spec.get('children', [])
                            if branch_idx < len(branches):
                                branch = branches[branch_idx]
                                children = branch.get('children', [])
                                if child_idx < len(children):
                                    info['current_node_text'] = (
                                        children[child_idx].get('label', 
                                        children[child_idx].get('text', ''))
                                    )
                
                elif node_id.startswith('tree-category-'):
                    idx = int(node_id.split('-')[2]) if len(node_id.split('-')) > 2 else 0
                    info['category_index'] = idx
                    if diagram_type == 'tree_map':
                        categories = spec.get('children', [])
                        if idx < len(categories):
                            category = categories[idx]
                            info['category_text'] = category.get('text', '')
                            info['existing_items'] = [
                                item.get('text', '')
                                for item in category.get('children', [])
                            ]
                
                result = json.dumps(info, ensure_ascii=False)
                logger.debug("TabAgent: Node info extracted", {
                    'node_id': node_id,
                    'info_keys': list(info.keys()),
                    'info_preview': str(info)[:200]
                })
                return result
                
            except Exception as e:
                logger.error("TabAgent: Error extracting node info", {
                    'node_id': node_id,
                    'node_type': node_type,
                    'error': str(e)
                }, exc_info=True)
                return json.dumps({'error': str(e)})
        
        return [extract_diagram_context, extract_node_info]
    
    async def generate_suggestions(
        self,
        diagram_type: str,
        main_topics: List[str],
        partial_input: str,
        node_category: Optional[str] = None,
        existing_nodes: Optional[List[str]] = None,
        language: str = "en",
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None
    ) -> List[str]:
        """
        Generate completion suggestions using LangChain with structured outputs.
        """
        try:
            logger.info("TabAgent: Generating suggestions", {
                'diagram_type': diagram_type,
                'node_category': node_category,
                'partial_input': partial_input[:50] if partial_input else '',
                'partial_input_length': len(partial_input) if partial_input else 0,
                'main_topics': main_topics,
                'existing_nodes_count': len(existing_nodes) if existing_nodes else 0,
                'existing_nodes_preview': existing_nodes[:3] if existing_nodes else [],
                'language': language,
                'user_id': user_id,
                'organization_id': organization_id
            })
            
            # Get prompt template
            prompt_key = f"tab_mode_{diagram_type}_autocomplete"
            logger.debug("TabAgent: Fetching prompt", {
                'prompt_key': prompt_key,
                'language': language
            })
            
            prompt_template = get_prompt(prompt_key, language, "suggestion")
            
            if not prompt_template:
                logger.warning("TabAgent: No prompt found, using generic", {
                    'prompt_key': prompt_key,
                    'language': language,
                    'diagram_type': diagram_type
                })
                prompt_template = self._get_generic_autocomplete_prompt(diagram_type, language)
            else:
                logger.debug("TabAgent: Prompt found", {
                    'prompt_key': prompt_key,
                    'prompt_length': len(prompt_template)
                })
            
            # Format prompt
            logger.debug("TabAgent: Formatting prompt")
            system_prompt = self._format_autocomplete_prompt(
                prompt_template,
                diagram_type,
                main_topics,
                partial_input,
                node_category,
                existing_nodes
            )
            
            logger.debug("TabAgent: Prompt formatted", {
                'system_prompt_length': len(system_prompt),
                'system_prompt_preview': system_prompt[:200]
            })
            
            # Use llm_service directly (maintains middleware benefits)
            logger.info("TabAgent: Calling LLM service", {
                'model': 'qwen-plus',
                'max_tokens': 100,
                'temperature': 0.3,
                'timeout': 15.0,
                'request_type': 'autocomplete',
                'endpoint_path': '/api/tab_suggestions'
            })
            
            import time
            start_time = time.time()
            
            response = await llm_service.chat(
                prompt=partial_input or "Provide suggestions",
                model='qwen-plus',
                system_message=system_prompt,
                max_tokens=100,
                temperature=0.3,
                timeout=15.0,
                user_id=user_id,
                organization_id=organization_id,
                request_type='autocomplete',
                endpoint_path='/api/tab_suggestions',
                diagram_type=diagram_type
            )
            
            elapsed_time = time.time() - start_time
            
            logger.info("TabAgent: LLM response received", {
                'response_length': len(response) if response else 0,
                'response_preview': response[:200] if response else None,
                'elapsed_time_seconds': round(elapsed_time, 2)
            })
            
            # Parse with structured output support
            logger.debug("TabAgent: Parsing suggestions from response")
            suggestions = self._parse_suggestions(response)
            
            logger.debug("TabAgent: Parsed suggestions", {
                'count_before_validation': len(suggestions),
                'suggestions_preview': suggestions[:5]
            })
            
            suggestions = self._validate_suggestions(suggestions)
            
            logger.info("TabAgent: Suggestions generated successfully", {
                'count': len(suggestions),
                'suggestions': suggestions[:5],  # Log first 5
                'all_suggestions': suggestions  # Log all for debugging
            })
            
            return suggestions[:5]
            
        except LLMServiceError as e:
            logger.error("TabAgent: LLM service error generating suggestions", {
                'error': str(e),
                'error_type': type(e).__name__,
                'diagram_type': diagram_type,
                'partial_input': partial_input[:50] if partial_input else ''
            }, exc_info=True)
            return []
        except ValueError as e:
            logger.error("TabAgent: Validation error generating suggestions", {
                'error': str(e),
                'error_type': type(e).__name__,
                'diagram_type': diagram_type
            }, exc_info=True)
            return []
        except Exception as e:
            logger.error("TabAgent: Unexpected error generating suggestions", {
                'error': str(e),
                'error_type': type(e).__name__,
                'diagram_type': diagram_type,
                'partial_input': partial_input[:50] if partial_input else ''
            }, exc_info=True)
            return []
    
    async def generate_expansion(
        self,
        diagram_type: str,
        node_text: str,
        main_topic: Optional[str] = None,
        node_type: str = "branch",
        existing_children: Optional[List[str]] = None,
        num_children: int = 4,
        language: str = "en",
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Generate child nodes for expansion using LangChain.
        """
        try:
            logger.debug("TabAgent: Generating expansion", {
                'diagram_type': diagram_type,
                'node_text': node_text,
                'num_children': num_children
            })
            
            # Get prompt template
            # Import registry first
            from prompts import PROMPT_REGISTRY
            
            # Normalize diagram type: enum might be "mind_map" but registry uses "mindmap"
            normalized_diagram_type = diagram_type
            if diagram_type == 'mind_map':
                normalized_diagram_type = 'mindmap'
            
            # Construct the full prompt key that matches the registry
            prompt_key = f"tab_mode_{normalized_diagram_type}_expansion_{language}"
            logger.debug("TabAgent: Fetching expansion prompt", {
                'prompt_key': prompt_key,
                'diagram_type': diagram_type,
                'normalized_diagram_type': normalized_diagram_type,
                'language': language,
                'registry_has_key': prompt_key in PROMPT_REGISTRY,
                'available_expansion_keys': [k for k in PROMPT_REGISTRY.keys() if 'expansion' in k]
            })
            
            # Get prompt directly from registry (not using get_prompt which expects different format)
            prompt_template = PROMPT_REGISTRY.get(prompt_key, "")
            
            if not prompt_template:
                logger.warning("TabAgent: No expansion prompt found", {
                    'prompt_key': prompt_key,
                    'language': language,
                    'diagram_type': diagram_type
                })
                return []
            else:
                logger.debug("TabAgent: Expansion prompt found", {
                    'prompt_key': prompt_key,
                    'prompt_length': len(prompt_template)
                })
            
            # Format prompt
            logger.debug("TabAgent: Formatting expansion prompt")
            system_prompt = prompt_template.format(
                main_topic=main_topic or "Main Topic",
                node_text=node_text,
                existing_children=", ".join(existing_children) if existing_children else "None",
                num_children=num_children
            )
            
            logger.debug("TabAgent: Expansion prompt formatted", {
                'system_prompt_length': len(system_prompt),
                'system_prompt_preview': system_prompt[:200]
            })
            
            # Use llm_service directly (maintains middleware)
            logger.info("TabAgent: Calling LLM service for expansion", {
                'model': 'qwen-plus',
                'max_tokens': 150,
                'temperature': 0.5,
                'timeout': 20.0,
                'request_type': 'autocomplete',
                'endpoint_path': '/api/tab_expand'
            })
            
            import time
            start_time = time.time()
            
            response = await llm_service.chat(
                prompt=f"Generate {num_children} child nodes for: {node_text}",
                model='qwen-plus',
                system_message=system_prompt,
                max_tokens=150,
                temperature=0.5,
                timeout=20.0,
                user_id=user_id,
                organization_id=organization_id,
                request_type='autocomplete',
                endpoint_path='/api/tab_expand',
                diagram_type=diagram_type
            )
            
            elapsed_time = time.time() - start_time
            
            logger.info("TabAgent: Expansion response received", {
                'response_length': len(response) if response else 0,
                'response_preview': response[:200] if response else None,
                'elapsed_time_seconds': round(elapsed_time, 2)
            })
            
            # Parse response
            logger.debug("TabAgent: Parsing expansion response")
            children_texts = self._parse_suggestions(response)
            
            logger.debug("TabAgent: Parsed children texts", {
                'count_before_validation': len(children_texts),
                'children_preview': children_texts[:5]
            })
            
            children_texts = self._validate_suggestions(children_texts)
            
            # Format as list of dicts
            children = []
            for idx, text in enumerate(children_texts[:num_children]):
                children.append({
                    "text": text,
                    "id": f"child_{idx}"
                })
            
            logger.info("TabAgent: Expansion generated successfully", {
                'count': len(children),
                'children': [c['text'] for c in children],
                'all_children': children  # Log all for debugging
            })
            
            return children
            
        except LLMServiceError as e:
            logger.error("TabAgent: LLM service error generating expansion", {
                'error': str(e),
                'error_type': type(e).__name__,
                'diagram_type': diagram_type,
                'node_text': node_text[:50] if node_text else ''
            }, exc_info=True)
            return []
        except ValueError as e:
            logger.error("TabAgent: Validation error generating expansion", {
                'error': str(e),
                'error_type': type(e).__name__,
                'diagram_type': diagram_type
            }, exc_info=True)
            return []
        except Exception as e:
            logger.error("TabAgent: Unexpected error generating expansion", {
                'error': str(e),
                'error_type': type(e).__name__,
                'diagram_type': diagram_type,
                'node_text': node_text[:50] if node_text else ''
            }, exc_info=True)
            return []
    
    def _format_autocomplete_prompt(
        self,
        prompt_template: str,
        diagram_type: str,
        main_topics: List[str],
        partial_input: str,
        node_category: Optional[str],
        existing_nodes: Optional[List[str]]
    ) -> str:
        """Format autocomplete prompt based on diagram type."""
        logger.debug("TabAgent: Formatting autocomplete prompt", {
            'diagram_type': diagram_type,
            'node_category': node_category,
            'main_topics_count': len(main_topics),
            'has_existing_nodes': bool(existing_nodes)
        })
        
        if diagram_type == 'mindmap' and node_category == 'children':
            branch_label = main_topics[1] if len(main_topics) > 1 and main_topics[1] else ""
            main_topic = main_topics[0] if len(main_topics) > 0 and main_topics[0] else ""
            return prompt_template.format(
                main_topic=main_topic,
                branch_label=branch_label,
                partial_input=partial_input or "",
                existing_children=", ".join(existing_nodes) if existing_nodes else "None"
            )
        elif diagram_type == 'double_bubble_map':
            return prompt_template.format(
                left_topic=main_topics[0] if len(main_topics) > 0 and main_topics[0] else "Topic 1",
                right_topic=main_topics[1] if len(main_topics) > 1 and main_topics[1] else "Topic 2",
                main_topic=main_topics[0] if len(main_topics) > 0 and main_topics[0] else "",
                node_category=node_category or "general",
                partial_input=partial_input or "",
                existing_nodes=", ".join(existing_nodes) if existing_nodes else "None"
            )
        else:
            return prompt_template.format(
                main_topic=main_topics[0] if len(main_topics) > 0 and main_topics[0] else "Main Topic",
                node_category=node_category or "general",
                partial_input=partial_input or "",
                existing_nodes=", ".join(existing_nodes) if existing_nodes else "None"
            )
    
    def _parse_suggestions(self, response: str) -> List[str]:
        """Parse LLM response into list of suggestions."""
        logger.debug("TabAgent: Parsing suggestions", {
            'response_type': type(response).__name__,
            'response_length': len(response) if response else 0,
            'response_preview': str(response)[:300] if response else None
        })
        
        if not response or not isinstance(response, str):
            logger.warning("TabAgent: Empty or invalid response for parsing")
            return []
        
        try:
            # Try JSON parsing
            parsed = json.loads(response)
            if isinstance(parsed, list):
                suggestions = [str(s).strip() for s in parsed if s]
                logger.debug("TabAgent: Parsed suggestions from JSON array", {
                    'count': len(suggestions),
                    'suggestions': suggestions
                })
                return suggestions
            elif isinstance(parsed, dict) and 'suggestions' in parsed:
                suggestions = parsed['suggestions']
                if isinstance(suggestions, list):
                    result = [s.get('text', str(s)) if isinstance(s, dict) else str(s) for s in suggestions]
                    logger.debug("TabAgent: Parsed suggestions from JSON object", {
                        'count': len(result),
                        'suggestions': result,
                        'parsed_keys': list(parsed.keys())
                    })
                    return result
        except Exception as e:
            logger.warning("TabAgent: JSON parsing failed, using fallback", {
                'error': str(e),
                'error_type': type(e).__name__
            })
        
        # Fallback: text parsing
        logger.debug("TabAgent: Using fallback text parsing")
        cleaned = response.strip()
        if '```' in cleaned:
            cleaned = re.sub(r'```(?:json)?\s*\n(.*?)\n```', r'\1', cleaned, flags=re.DOTALL)
            logger.debug("TabAgent: Removed code block markers")
        
        lines = []
        for line in cleaned.split('\n'):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('---') or line.startswith('```'):
                continue
            # Remove list markers
            original_line = line
            line = re.sub(r'^\d+[\.\)]\s*', '', line)
            line = re.sub(r'^[-*]\s+', '', line)
            line = line.strip()
            if line and len(line) > 0 and len(line) <= 100:
                lines.append(line)
        
        logger.debug("TabAgent: Parsed suggestions from text lines (fallback)", {
            'count': len(lines),
            'lines': lines
        })
        return lines
    
    def _validate_suggestions(self, suggestions: List[str]) -> List[str]:
        """Validate and clean suggestions."""
        logger.debug("TabAgent: Validating suggestions", {
            'input_count': len(suggestions),
            'input_preview': suggestions[:5]
        })
        
        validated = []
        invalid_count = 0
        for s in suggestions:
            if not s or not isinstance(s, str):
                invalid_count += 1
                continue
            s = s.strip()
            if 1 <= len(s) <= 100:
                validated.append(s)
            else:
                invalid_count += 1
        
        logger.debug("TabAgent: Validation complete", {
            'validated_count': len(validated),
            'invalid_count': invalid_count,
            'validated_preview': validated[:5]
        })
        
        return validated
    
    def _get_generic_autocomplete_prompt(self, diagram_type: str, language: str) -> str:
        """Fallback generic prompt."""
        if language == 'zh':
            return """根据上下文提供3-5个补全建议。只返回JSON数组。"""
        else:
            return """Provide 3-5 completion suggestions based on context. Return only JSON array."""
    
    # BaseAgent interface
    def generate_graph(self, user_prompt: str, language: str = 'zh') -> Dict[str, Any]:
        """Stub implementation for BaseAgent interface."""
        logger.warning("TabAgent: generate_graph() called but Tab Agent doesn't generate full graphs")
        return {
            'success': False,
            'error': 'Tab Agent does not generate full graphs. Use generate_suggestions() or generate_expansion() instead.'
        }

