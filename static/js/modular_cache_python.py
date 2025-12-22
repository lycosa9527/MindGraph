# Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
# All Rights Reserved
#
# Proprietary License - All use without explicit permission is prohibited.
# Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
#
# @author WANG CUNCHI

"""
Python Integration for Modular JavaScript Cache Manager

This module provides a Python wrapper for the modular JavaScript cache system,
enabling graph-type-specific JavaScript loading for optimal performance.

Performance Impact: 50-70% reduction in JavaScript loading per request
Implementation: Option 3 - Code Splitting by Graph Type
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables for logging configuration
load_dotenv()

logger = logging.getLogger(__name__)

class ModularJavaScriptManager:
    """
    Python interface for modular JavaScript loading based on graph types.
    
    This class manages the selection and loading of only the required JavaScript
    modules for specific graph types, significantly reducing the amount of code
    that needs to be embedded in each HTML generation.
    """
    
    def __init__(self):
        """Initialize the modular JavaScript manager."""
        self.base_path = Path(__file__).parent
        self.renderers_path = self.base_path / "renderers"
        
        # Graph type to renderer module mapping
        self.graph_type_to_modules = {
            'mindmap': ['shared-utilities', 'mind-map-renderer', 'renderer-dispatcher'],
            'concept_map': ['shared-utilities', 'concept-map-renderer', 'renderer-dispatcher'],
            'conceptmap': ['shared-utilities', 'concept-map-renderer', 'renderer-dispatcher'],
            'bubble_map': ['shared-utilities', 'bubble-map-renderer', 'renderer-dispatcher'],
            'double_bubble_map': ['shared-utilities', 'bubble-map-renderer', 'renderer-dispatcher'],
            'circle_map': ['shared-utilities', 'bubble-map-renderer', 'renderer-dispatcher'],
            'tree_map': ['shared-utilities', 'tree-renderer', 'renderer-dispatcher'],

            'flowchart': ['shared-utilities', 'flow-renderer', 'renderer-dispatcher'],
            'flow_map': ['shared-utilities', 'flow-renderer', 'renderer-dispatcher'],
            'multi_flow_map': ['shared-utilities', 'flow-renderer', 'renderer-dispatcher'],
            'bridge_map': ['shared-utilities', 'flow-renderer', 'renderer-dispatcher'],

        
            'brace_map': ['shared-utilities', 'brace-renderer', 'renderer-dispatcher'],

        }
        
        # File path mapping
        self.module_files = {
            'shared-utilities': 'shared-utilities.js',
            'mind-map-renderer': 'mind-map-renderer.js',
            'concept-map-renderer': 'concept-map-renderer.js',
            'bubble-map-renderer': 'bubble-map-renderer.js',
            'tree-renderer': 'tree-renderer.js',
            'flow-renderer': 'flow-renderer.js',
            'renderer-dispatcher': 'renderer-dispatcher.js',

        
            'brace-renderer': 'brace-renderer.js',
        
        }
        
        # Cache for loaded modules
        self._module_cache = {}
        self._cache_stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'bytes_saved': 0,
            'most_used_types': {}
        }
        
        # Load shared utilities and style manager (always needed)
        self._load_core_modules()
    
    def _load_core_modules(self):
        """Load core modules that are always needed."""
        try:
            # Load style manager (from parent directory)
            style_manager_path = self.base_path / 'style-manager.js'
            if style_manager_path.exists():
                with open(style_manager_path, 'r', encoding='utf-8') as f:
                    self._module_cache['style-manager'] = f.read()
                logger.info("Style manager loaded into cache")
            
            # Load theme config (from parent directory)
            theme_config_path = self.base_path / 'theme-config.js'
            if theme_config_path.exists():
                with open(theme_config_path, 'r', encoding='utf-8') as f:
                    self._module_cache['theme-config'] = f.read()
                logger.info("Theme config loaded into cache")
                
            # REMOVED: shared-utilities is NOT a core module - it contains renderer functions
            # that should be loaded on-demand to prevent conflicts
                
        except Exception as e:
            logger.error(f"Failed to load core modules: {e}")
            raise
    
    def normalize_graph_type(self, graph_type: str) -> str:
        """
        Normalize graph type to match our mapping.
        
        Args:
            graph_type: The input graph type
            
        Returns:
            str: Normalized graph type
        """
        if not graph_type:
            return 'mindmap'
        
        type_normalized = graph_type.lower().replace('-', '_').replace(' ', '_')
        
        # Handle common aliases
        aliases = {
            'mind_map': 'mindmap',
            'concept_maps': 'concept_map',
            'bubblemap': 'bubble_map',
            'doublebubblemap': 'double_bubble_map',
            'treemap': 'tree_map',

            'flow_chart': 'flowchart',

        }
        
        return aliases.get(type_normalized, type_normalized)
    
    def get_required_modules(self, graph_type: str) -> List[str]:
        """
        Get the list of required modules for a specific graph type.
        
        Args:
            graph_type: The graph type to get modules for
            
        Returns:
            List[str]: List of required module names
        """
        normalized_type = self.normalize_graph_type(graph_type)
        base_modules = self.graph_type_to_modules.get(normalized_type, ['shared-utilities'])
        
        # Always add renderer-dispatcher LAST so it can check if individual renderers exist
        if 'renderer-dispatcher' not in base_modules:
            base_modules.append('renderer-dispatcher')
        
        return base_modules
    
    def load_module(self, module_name: str) -> str:
        """
        Load a specific module, using cache if available.
        
        Args:
            module_name: Name of the module to load
            
        Returns:
            str: Module content
        """
        # Check cache first
        if module_name in self._module_cache:
            self._cache_stats['cache_hits'] += 1
            return self._module_cache[module_name]
        
        # Load from file
        self._cache_stats['cache_misses'] += 1
        
        try:
            if module_name in ['style-manager', 'theme-config']:
                # Core modules are in the parent directory
                file_path = self.base_path / f"{module_name.replace('-', '_')}.js"
            else:
                # Renderer modules are in the renderers directory
                filename = self.module_files.get(module_name, f"{module_name}.js")
                file_path = self.renderers_path / filename
            
            if not file_path.exists():
                logger.warning(f"Module file not found: {file_path}")
                return ""
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Cache the content
            self._module_cache[module_name] = content
            logger.debug(f"Loaded module: {module_name} ({len(content)} chars)")
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to load module {module_name}: {e}")
            return ""
    
    def get_javascript_for_graph_type(self, graph_type: str) -> Tuple[Dict[str, str], Dict]:
        """
        Get the JavaScript modules for a specific graph type, returned separately.
        
        Args:
            graph_type: The graph type to get JavaScript for
            
        Returns:
            Tuple[Dict[str, str], Dict]: (Module contents dict, Performance stats)
        """
        self._cache_stats['total_requests'] += 1
        
        # Track usage
        normalized_type = self.normalize_graph_type(graph_type)
        if normalized_type in self._cache_stats['most_used_types']:
            self._cache_stats['most_used_types'][normalized_type] += 1
        else:
            self._cache_stats['most_used_types'][normalized_type] = 1
        
        # Get required modules
        required_modules = self.get_required_modules(graph_type)
        
        # Build module list in correct order:
        # 1. Core modules (theme-config, style-manager)
        # 2. Shared utilities (must come before renderers)
        # 3. Specific renderer modules
        # 4. Renderer dispatcher (must come last)
        all_modules = ['theme-config', 'style-manager']
        
        # Add shared-utilities if it's in required modules (it should be)
        if 'shared-utilities' in required_modules:
            all_modules.append('shared-utilities')
            # Remove it from required_modules to avoid duplication
            required_modules = [m for m in required_modules if m != 'shared-utilities']
        
        # Add remaining renderer modules
        all_modules.extend(required_modules)
        
        # Load all modules separately
        module_contents = {}
        total_size = 0
        
        for module_name in all_modules:
            content = self.load_module(module_name)
            if content:
                module_contents[module_name] = content
                total_size += len(content)
        
        # Calculate savings compared to full d3-renderers.js
        full_renderer_size = 218174  # Size of full d3-renderers.js (updated with renderGraph extraction)
        savings = full_renderer_size - total_size
        savings_percent = (savings / full_renderer_size) * 100 if full_renderer_size > 0 else 0
        
        self._cache_stats['bytes_saved'] += savings
        
        # Performance stats
        stats = {
            'graph_type': graph_type,
            'normalized_type': normalized_type,
            'modules_loaded': len(all_modules),
            'module_names': all_modules,
            'total_size_bytes': total_size,
            'total_size_kb': round(total_size / 1024, 2),
            'savings_bytes': savings,
            'savings_percent': round(savings_percent, 1),
            'cache_hit_rate': round((self._cache_stats['cache_hits'] / max(1, self._cache_stats['cache_hits'] + self._cache_stats['cache_misses'])) * 100, 1)
        }
        
        logger.info(f"Generated JavaScript for {graph_type}: {stats['total_size_kb']}KB")
        
        return module_contents, stats
    
    def get_cache_statistics(self) -> Dict:
        """
        Get comprehensive cache statistics.
        
        Returns:
            Dict: Cache performance statistics
        """
        total_hits_misses = self._cache_stats['cache_hits'] + self._cache_stats['cache_misses']
        hit_rate = (self._cache_stats['cache_hits'] / max(1, total_hits_misses)) * 100
        
        return {
            'total_requests': self._cache_stats['total_requests'],
            'cache_hits': self._cache_stats['cache_hits'],
            'cache_misses': self._cache_stats['cache_misses'],
            'cache_hit_rate_percent': round(hit_rate, 1),
            'total_bytes_saved': self._cache_stats['bytes_saved'],
            'average_savings_per_request': round(self._cache_stats['bytes_saved'] / max(1, self._cache_stats['total_requests']), 0),
            'most_used_graph_types': dict(sorted(self._cache_stats['most_used_types'].items(), key=lambda x: x[1], reverse=True)[:5]),
            'cached_modules': list(self._module_cache.keys()),
            'supported_graph_types': list(self.graph_type_to_modules.keys())
        }
    
    def clear_cache(self):
        """Clear the module cache and reset statistics."""
        # Keep core modules in cache
        core_modules = {k: v for k, v in self._module_cache.items() if k in ['shared-utilities', 'style-manager', 'theme-config']}
        self._module_cache = core_modules
        
        # Reset stats
        self._cache_stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'bytes_saved': 0,
            'most_used_types': {}
        }
        
        logger.info("Module cache cleared (core modules retained)")
    
    def preload_common_modules(self):
        """Preload commonly used renderer modules."""
        # DISABLED: Preloading all renderers causes conflicts
        # Only load core modules, renderers will be loaded on-demand
        logger.info("Preloading disabled - renderers loaded on-demand to prevent conflicts")
        return
        
        # OLD CODE (DISABLED):
        # common_types = ['mindmap', 'concept_map', 'bubble_map', 'tree_map']
        # 
        # for graph_type in common_types:
        #     try:
        #         modules = self.get_required_modules(graph_type)
        #         for module in modules:
        #             if module not in self._module_cache:
        #                 self.load_module(module)
        #         logger.info(f"Preloaded modules for {graph_type}")
        #     except Exception as e:
        #         logger.warning(f"Failed to preload modules for {graph_type}: {e}")
        # 
        # logger.info("Common modules preloaded successfully")


# Global instance for use throughout the application
modular_js_manager = ModularJavaScriptManager()

def get_javascript_for_graph_type(graph_type: str) -> Tuple[Dict[str, str], Dict]:
    """
    Convenience function to get JavaScript for a graph type.
    
    Args:
        graph_type: The graph type to get JavaScript for
        
    Returns:
        Tuple[Dict[str, str], Dict]: (Module contents dict, Performance stats)
    """
    return modular_js_manager.get_javascript_for_graph_type(graph_type)

def get_modular_cache_stats() -> Dict:
    """
    Get modular cache statistics in the format expected by the API endpoint.
    
    Returns:
        Dict: Cache statistics with base_cache and modular sections
    """
    stats = modular_js_manager.get_cache_statistics()
    
    # Calculate cache hit rate
    cache_hit_rate = stats.get('cache_hit_rate_percent', 0)
    
    # Calculate compression ratio
    total_bytes_saved = stats.get('total_bytes_saved', 0)
    total_requests = stats.get('total_requests', 0)
    full_renderer_size = 218174  # Size of full d3-renderers.js
    avg_size_per_request = (full_renderer_size * total_requests - total_bytes_saved) / max(1, total_requests)
    compression_ratio = ((full_renderer_size - avg_size_per_request) / full_renderer_size * 100) if full_renderer_size > 0 else 0
    
    # Count cached modules
    cached_modules = stats.get('cached_modules', [])
    supported_types = stats.get('supported_graph_types', [])
    
    # Calculate total memory usage
    total_memory = sum(len(modular_js_manager._module_cache.get(module, '')) for module in cached_modules)
    
    return {
        'files_loaded': len(cached_modules),
        'total_memory_usage': total_memory,
        'cache_hit_rate': cache_hit_rate,
        'modular': {
            'compressionRatio': f'{compression_ratio:.1f}%',
            'supportedGraphTypes': supported_types,
            'availableModules': cached_modules,
            'totalRequests': total_requests,
            'cacheHits': stats.get('cache_hits', 0),
            'cacheMisses': stats.get('cache_misses', 0),
            'totalBytesSaved': total_bytes_saved
        }
    }

def get_modular_performance_summary() -> Dict:
    """
    Get modular cache performance summary in a human-readable format.
    
    Returns:
        Dict: Performance summary with status, improvement metrics, etc.
    """
    stats = modular_js_manager.get_cache_statistics()
    
    if stats['total_requests'] == 0:
        return {
            'status': 'No modular requests yet',
            'improvement': '0%',
            'averageLoadTime': 0,
            'bytesSaved': 0
        }
    
    # Calculate average improvement percentage
    avg_savings = stats.get('average_savings_per_request', 0)
    full_renderer_size = 218174  # Size of full d3-renderers.js
    avg_improvement = (avg_savings / full_renderer_size * 100) if full_renderer_size > 0 else 0
    
    # Get most used graph type
    most_used_types = stats.get('most_used_graph_types', {})
    most_used_renderer = max(most_used_types.items(), key=lambda x: x[1])[0] if most_used_types else 'None'
    
    return {
        'status': 'Optimal',
        'improvement': f'{avg_improvement:.1f}% size reduction',
        'averageLoadTime': 'N/A',  # Not tracked in Python version
        'bytesSaved': f'{stats.get("total_bytes_saved", 0):,} bytes',
        'mostUsedRenderer': most_used_renderer,
        'cacheHitRate': f'{stats.get("cache_hit_rate_percent", 0):.1f}%'
    }

def preload_common_renderers():
    """Preload commonly used renderer modules."""
    modular_js_manager.preload_common_modules()
