from flask import Blueprint, request, jsonify, send_file
import agent
import graph_specs
import logging
import tempfile
import asyncio
import re
import os
import atexit
from werkzeug.exceptions import HTTPException
from functools import wraps
from config import config

api = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

# Track temporary files for cleanup
temp_files = set()

def cleanup_temp_files():
    """Clean up temporary files on exit."""
    for temp_file in temp_files:
        try:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
        except OSError:
            pass

atexit.register(cleanup_temp_files)

def handle_api_errors(f):
    """Decorator for centralized API error handling with consistent error format."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            logger.error(f"API error in {f.__name__}: {e}", exc_info=True)
            return jsonify({
                'error': 'An unexpected error occurred. Please try again later.',
                'details': str(e) if config.DEBUG else None
            }), 500
    return decorated_function

def validate_request_data(data, required_fields=None):
    """Validate request data structure."""
    if not data:
        return False, "Missing request data"
    
    if required_fields:
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"
    
    return True, ""

def sanitize_prompt(prompt):
    """Enhanced sanitization with comprehensive security measures."""
    if not isinstance(prompt, str):
        return None
    prompt = prompt.strip()
    if not prompt:
        return None
    
    # Remove potentially dangerous patterns
    dangerous_patterns = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'<iframe[^>]*>.*?</iframe>',  # Iframe tags
        r'<object[^>]*>.*?</object>',  # Object tags
        r'<embed[^>]*>',  # Embed tags
        r'javascript:',  # JavaScript protocol
        r'data:',  # Data protocol
        r'vbscript:',  # VBScript protocol
        r'on\w+\s*=',  # Event handlers
        r'<[^>]*>',  # Any remaining HTML tags
        r'expression\s*\(',  # CSS expressions
        r'url\s*\(',  # CSS url functions
        r'import\s+',  # CSS imports
        r'@import',  # CSS @import
        r'\\',  # Backslashes
        r'<!--',  # HTML comments
        r'-->',  # HTML comments
    ]
    
    for pattern in dangerous_patterns:
        prompt = re.sub(pattern, '', prompt, flags=re.IGNORECASE | re.DOTALL)
    
    # HTML entity encoding for special characters
    html_entities = {
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '&': '&amp;',
        '/': '&#x2F;',
        '\\': '&#x5C;',
    }
    
    for char, entity in html_entities.items():
        prompt = prompt.replace(char, entity)
    
    # Remove control characters and normalize whitespace
    prompt = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', prompt)
    prompt = re.sub(r'\s+', ' ', prompt)
    
    # Limit length and ensure it's not empty after sanitization
    sanitized = prompt[:1000].strip()
    return sanitized if sanitized else None

@api.route('/generate_graph', methods=['POST'])
@handle_api_errors
def generate_graph():
    """Generate graph specification from user prompt."""
    # Input validation
    data = request.json
    valid, msg = validate_request_data(data, ['prompt'])
    if not valid:
        return jsonify({'error': msg}), 400
    
    prompt = sanitize_prompt(data['prompt'])
    if not prompt:
        return jsonify({'error': 'Invalid or empty prompt'}), 400
    
    language = data.get('language', 'zh')
    if not isinstance(language, str) or language not in ['zh', 'en']:
        return jsonify({'error': 'Invalid language. Must be "zh" or "en"'}), 400
    
    logger.info(f"Frontend /generate_graph: prompt={prompt!r}, language={language!r}")
    
    # Generate graph specification
    graph_type = agent.classify_graph_type_with_llm(prompt, language)
    spec = agent.generate_graph_spec(prompt, graph_type, language)
    
    # Validate the generated spec
    if hasattr(graph_specs, f'validate_{graph_type}'):
        validate_fn = getattr(graph_specs, f'validate_{graph_type}')
        valid, msg = validate_fn(spec)
        if not valid:
            logger.warning(f"Generated invalid spec for {graph_type}: {msg}")
            return jsonify({'error': f'Failed to generate valid graph specification: {msg}'}), 400
    
    return jsonify({'type': graph_type, 'spec': spec})

@api.route('/generate_png', methods=['POST'])
@handle_api_errors
def generate_png():
    """Generate PNG image from user prompt."""
    # Input validation
    data = request.json
    valid, msg = validate_request_data(data, ['prompt'])
    if not valid:
        return jsonify({'error': msg}), 400
    
    prompt = sanitize_prompt(data['prompt'])
    if not prompt:
        return jsonify({'error': 'Invalid or empty prompt'}), 400
    
    language = data.get('language', 'zh')
    if not isinstance(language, str) or language not in ['zh', 'en']:
        return jsonify({'error': 'Invalid language. Must be "zh" or "en"'}), 400
    
    logger.info(f"Frontend /generate_png: prompt={prompt!r}, language={language!r}")
    
    # Generate graph specification
    graph_type = agent.classify_graph_type_with_llm(prompt, language)
    spec = agent.generate_graph_spec(prompt, graph_type, language)
    
    # Validate the generated spec before rendering
    if hasattr(graph_specs, f'validate_{graph_type}'):
        validate_fn = getattr(graph_specs, f'validate_{graph_type}')
        valid, msg = validate_fn(spec)
        if not valid:
            logger.warning(f"Generated invalid spec for {graph_type}: {msg}")
            return jsonify({'error': f'Failed to generate valid graph specification: {msg}'}), 400
    
    # Check if spec has required structure for rendering
    if not spec or isinstance(spec, dict) and spec.get('error'):
        return jsonify({'error': 'Failed to generate valid graph specification'}), 400
    
    # Render SVG and convert to PNG using Playwright
    try:
        import nest_asyncio
        nest_asyncio.apply()
        import json
        from playwright.async_api import async_playwright
        
        async def render_svg_to_png(spec, graph_type):
            d3_renderers = '''
function renderDoubleBubbleMap(spec) {
    d3.select('#d3-container').html('');
    if (!spec || !spec.left || !spec.right || !Array.isArray(spec.similarities) || !Array.isArray(spec.left_differences) || !Array.isArray(spec.right_differences)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for double_bubble_map');
        return;
    }
    const baseWidth=700,baseHeight=500,padding=40;
    const getTextRadius = (text, fontSize, padding) => {
        var svg = d3.select('body').append('svg').style('position','absolute').style('visibility','hidden');
        var t = svg.append('text').attr('font-size', fontSize).text(text);
        var b = t.node().getBBox();
        var radius = Math.ceil(Math.sqrt(b.width*b.width+b.height*b.height)/2+(padding||12));
        svg.remove(); // Ensure cleanup
        return radius;
    };
    const THEME={topicFill:'#4e79a7',topicText:'#fff',topicStroke:'#35506b',topicStrokeWidth:3,simFill:'#a7c7e7',simText:'#333',simStroke:'#4e79a7',simStrokeWidth:2,diffFill:'#f4f6fb',diffText:'#4e79a7',diffStroke:'#4e79a7',diffStrokeWidth:2,fontTopic:18,fontSim:14,fontDiff:13};
    const leftTopicR=getTextRadius(spec.left,THEME.fontTopic,18),rightTopicR=getTextRadius(spec.right,THEME.fontTopic,18),topicR=Math.max(leftTopicR,rightTopicR,60);
    const simFontSize=THEME.fontSim,diffFontSize=THEME.fontDiff;
    const simR=Math.max(...spec.similarities.map(t=>getTextRadius(t,simFontSize,10)),28),leftDiffR=Math.max(...spec.left_differences.map(t=>getTextRadius(t,diffFontSize,8)),24),rightDiffR=Math.max(...spec.right_differences.map(t=>getTextRadius(t,diffFontSize,8)),24);
    const simCount=spec.similarities.length,leftDiffCount=spec.left_differences.length,rightDiffCount=spec.right_differences.length;
    const simColHeight=simCount>0?(simCount-1)*(simR*2+12)+simR*2:0,leftColHeight=leftDiffCount>0?(leftDiffCount-1)*(leftDiffR*2+10)+leftDiffR*2:0,rightColHeight=rightDiffCount>0?(rightDiffCount-1)*(rightDiffR*2+10)+rightDiffR*2:0,maxColHeight=Math.max(simColHeight,leftColHeight,rightColHeight,topicR*2),height=Math.max(baseHeight,maxColHeight+padding*2);
    const leftX=padding+topicR,rightX=baseWidth-padding-topicR,simX=(leftX+rightX)/2;
    const leftDiffX=leftX-topicR-90,rightDiffX=rightX+topicR+90;
    const minX=Math.min(leftDiffX-leftDiffR,leftX-topicR,simX-simR,rightX-topicR,rightDiffX-rightDiffR)-padding,maxX=Math.max(leftDiffX+leftDiffR,leftX+topicR,simX+simR,rightX+topicR,rightDiffX+rightDiffR)+padding,width=Math.max(baseWidth,maxX-minX),topicY=height/2;
    const svg=d3.select('#d3-container').append('svg').attr('width',width).attr('height',height).attr('viewBox',`${minX} 0 ${width} ${height}`).attr('preserveAspectRatio','xMinYMin meet');
    // --- Draw all lines first ---
    const simStartY=topicY-((simCount-1)*(simR*2+12))/2;
    for(let i=0;i<simCount;i++){
        const y=simStartY+i*(simR*2+12);
        let dxL=leftX-simX,dyL=topicY-y,distL=Math.sqrt(dxL*dxL+dyL*dyL),x1L=simX+(dxL/distL)*simR,y1L=y+(dyL/distL)*simR,x2L=leftX-(dxL/distL)*topicR,y2L=topicY-(dyL/distL)*topicR;
        svg.append('line').attr('x1',x1L).attr('y1',y1L).attr('x2',x2L).attr('y2',y2L).attr('stroke','#888').attr('stroke-width',2);
        let dxR=rightX-simX,dyR=topicY-y,distR=Math.sqrt(dxR*dxR+dyR*dyR),x1R=simX+(dxR/distR)*simR,y1R=y+(dyR/distR)*simR,x2R=rightX-(dxR/distR)*topicR,y2R=topicY-(dyR/distR)*topicR;
        svg.append('line').attr('x1',x1R).attr('y1',y1R).attr('x2',x2R).attr('y2',y2R).attr('stroke','#888').attr('stroke-width',2);
    }
    const leftDiffStartY=topicY-((leftDiffCount-1)*(leftDiffR*2+10))/2;
    for(let i=0;i<leftDiffCount;i++){
        const y=leftDiffStartY+i*(leftDiffR*2+10);
        let dx=leftX-leftDiffX,dy=topicY-y,dist=Math.sqrt(dx*dx+dy*dy),x1=leftDiffX+(dx/dist)*leftDiffR,y1=y+(dy/dist)*leftDiffR,x2=leftX-(dx/dist)*topicR,y2=topicY-(dy/dist)*topicR;
        svg.append('line').attr('x1',x1).attr('y1',y1).attr('x2',x2).attr('y2',y2).attr('stroke','#bbb').attr('stroke-width',2);
    }
    const rightDiffStartY=topicY-((rightDiffCount-1)*(rightDiffR*2+10))/2;
    for(let i=0;i<rightDiffCount;i++){
        const y=rightDiffStartY+i*(rightDiffR*2+10);
        let dx=rightX-rightDiffX,dy=topicY-y,dist=Math.sqrt(dx*dx+dy*dy),x1=rightDiffX+(dx/dist)*rightDiffR,y1=y+(dy/dist)*rightDiffR,x2=rightX-(dx/dist)*topicR,y2=topicY-(dy/dist)*topicR;
        svg.append('line').attr('x1',x1).attr('y1',y1).attr('x2',x2).attr('y2',y2).attr('stroke','#bbb').attr('stroke-width',2);
    }
    // --- Draw all circles next ---
    svg.append('circle').attr('cx',leftX).attr('cy',topicY).attr('r',topicR).attr('fill',THEME.topicFill).attr('opacity',0.9).attr('stroke',THEME.topicStroke).attr('stroke-width',THEME.topicStrokeWidth);
    svg.append('circle').attr('cx',rightX).attr('cy',topicY).attr('r',topicR).attr('fill',THEME.topicFill).attr('opacity',0.9).attr('stroke',THEME.topicStroke).attr('stroke-width',THEME.topicStrokeWidth);
    for(let i=0;i<simCount;i++){
        const y=simStartY+i*(simR*2+12);
        svg.append('circle').attr('cx',simX).attr('cy',y).attr('r',simR).attr('fill',THEME.simFill).attr('stroke',THEME.simStroke).attr('stroke-width',THEME.simStrokeWidth);
    }
    for(let i=0;i<leftDiffCount;i++){
        const y=leftDiffStartY+i*(leftDiffR*2+10);
        svg.append('circle').attr('cx',leftDiffX).attr('cy',y).attr('r',leftDiffR).attr('fill',THEME.diffFill).attr('stroke',THEME.diffStroke).attr('stroke-width',THEME.diffStrokeWidth);
    }
    for(let i=0;i<rightDiffCount;i++){
        const y=rightDiffStartY+i*(rightDiffR*2+10);
        svg.append('circle').attr('cx',rightDiffX).attr('cy',y).attr('r',rightDiffR).attr('fill',THEME.diffFill).attr('stroke',THEME.diffStroke).attr('stroke-width',THEME.diffStrokeWidth);
    }
    // --- Draw all text last ---
    svg.append('text').attr('x',leftX).attr('y',topicY).attr('text-anchor','middle').attr('dominant-baseline','middle').attr('fill',THEME.topicText).attr('font-size',THEME.fontTopic).attr('font-weight',600).text(spec.left);
    svg.append('text').attr('x',rightX).attr('y',topicY).attr('text-anchor','middle').attr('dominant-baseline','middle').attr('fill',THEME.topicText).attr('font-size',THEME.fontTopic).attr('font-weight',600).text(spec.right);
    for(let i=0;i<simCount;i++){
        const y=simStartY+i*(simR*2+12);
        svg.append('text').attr('x',simX).attr('y',y).attr('text-anchor','middle').attr('dominant-baseline','middle').attr('fill',THEME.simText).attr('font-size',THEME.fontSim).text(spec.similarities[i]);
    }
    for(let i=0;i<leftDiffCount;i++){
        const y=leftDiffStartY+i*(leftDiffR*2+10);
        svg.append('text').attr('x',leftDiffX).attr('y',y).attr('text-anchor','middle').attr('dominant-baseline','middle').attr('fill',THEME.diffText).attr('font-size',THEME.fontDiff).text(spec.left_differences[i]);
    }
    for(let i=0;i<rightDiffCount;i++){
        const y=rightDiffStartY+i*(rightDiffR*2+10);
        svg.append('text').attr('x',rightDiffX).attr('y',y).attr('text-anchor','middle').attr('dominant-baseline','middle').attr('fill',THEME.diffText).attr('font-size',THEME.fontDiff).text(spec.right_differences[i]);
    }
    // Watermark
    const w=+svg.attr('width'),h=+svg.attr('height');
    svg.append('text').attr('x',w-18).attr('y',h-18).attr('text-anchor','end').attr('fill','#888').attr('font-size',18).attr('font-family','Inter, Segoe UI, sans-serif').attr('opacity',0.35).attr('pointer-events','none').text('D3.js_Dify');
}

function renderBubbleMap(spec){
    d3.select('#d3-container').html('');
    var svg=d3.select('#d3-container').append('svg').attr('width',400).attr('height',300);
    svg.append('text').attr('x',200).attr('y',150).attr('text-anchor','middle').attr('fill','#333').attr('font-size',24).text('Bubble Map: '+spec.topic);
    const w=+svg.attr('width'),h=+svg.attr('height');
    svg.append('text').attr('x',w-18).attr('y',h-18).attr('text-anchor','end').attr('fill','#000').attr('font-size',18).attr('font-family','Inter, Segoe UI, sans-serif').attr('opacity',1).attr('pointer-events','none').text('D3.js_Dify');
}
function renderCircleMap(spec){
    d3.select('#d3-container').html('');
    var svg=d3.select('#d3-container').append('svg').attr('width',400).attr('height',300);
    svg.append('text').attr('x',200).attr('y',150).attr('text-anchor','middle').attr('fill','#333').attr('font-size',24).text('Circle Map: '+spec.topic);
    const w=+svg.attr('width'),h=+svg.attr('height');
    svg.append('text').attr('x',w-18).attr('y',h-18).attr('text-anchor','end').attr('fill','#000').attr('font-size',18).attr('font-family','Inter, Segoe UI, sans-serif').attr('opacity',1).attr('pointer-events','none').text('D3.js_Dify');
}
function renderTreeMap(spec){
    d3.select('#d3-container').html('');
    var svg=d3.select('#d3-container').append('svg').attr('width',400).attr('height',300);
    svg.append('text').attr('x',200).attr('y',150).attr('text-anchor','middle').attr('fill','#333').attr('font-size',24).text('Tree Map: '+spec.topic);
    const w=+svg.attr('width'),h=+svg.attr('height');
    svg.append('text').attr('x',w-18).attr('y',h-18).attr('text-anchor','end').attr('fill','#000').attr('font-size',18).attr('font-family','Inter, Segoe UI, sans-serif').attr('opacity',1).attr('pointer-events','none').text('D3.js_Dify');
}
function renderConceptMap(spec){
    d3.select('#d3-container').html('');
    var svg=d3.select('#d3-container').append('svg').attr('width',400).attr('height',300);
    svg.append('text').attr('x',200).attr('y',150).attr('text-anchor','middle').attr('fill','#333').attr('font-size',24).text('Concept Map: '+spec.topic);
    const w=+svg.attr('width'),h=+svg.attr('height');
    svg.append('text').attr('x',w-18).attr('y',h-18).attr('text-anchor','end').attr('fill','#000').attr('font-size',18).attr('font-family','Inter, Segoe UI, sans-serif').attr('opacity',1).attr('pointer-events','none').text('D3.js_Dify');
}
function renderMindMap(spec){
    d3.select('#d3-container').html('');
    var svg=d3.select('#d3-container').append('svg').attr('width',400).attr('height',300);
    svg.append('text').attr('x',200).attr('y',150).attr('text-anchor','middle').attr('fill','#333').attr('font-size',24).text('Mind Map: '+spec.topic);
    const w=+svg.attr('width'),h=+svg.attr('height');
    svg.append('text').attr('x',w-18).attr('y',h-18).attr('text-anchor','end').attr('fill','#000').attr('font-size',18).attr('font-family','Inter, Segoe UI, sans-serif').attr('opacity',1).attr('pointer-events','none').text('D3.js_Dify');
}
function renderGraph(type,spec){
    if(type==='double_bubble_map')renderDoubleBubbleMap(spec);
    else if(type==='bubble_map')renderBubbleMap(spec);
    else if(type==='circle_map')renderCircleMap(spec);
    else if(type==='tree_map')renderTreeMap(spec);
    else if(type==='concept_map')renderConceptMap(spec);
    else if(type==='mindmap')renderMindMap(spec);
}
'''
            html = f'''
            <html><head>
            <meta charset="utf-8">
            <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
            <style>body {{ margin:0; background:#fff; }}</style>
            </head><body>
            <div id="d3-container"></div>
            <script>
            window.spec = {json.dumps(spec, ensure_ascii=False)};
            window.graph_type = '{graph_type}';
            {d3_renderers}
            renderGraph(window.graph_type, window.spec);
            </script>
            </body></html>
            '''
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_content(html)
                await asyncio.sleep(1.5)
                element = await page.query_selector('svg')
                if element is None:
                    logger.error("SVG element not found in rendered page.")
                    raise ValueError("SVG element not found. The graph could not be rendered.")
                png_bytes = await element.screenshot(omit_background=False)
                await browser.close()
                return png_bytes
        
        loop = asyncio.get_event_loop()
        png_bytes = loop.run_until_complete(render_svg_to_png(spec, graph_type))
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png', mode='wb') as tmp:
                # Set restrictive permissions
                os.chmod(tmp.name, 0o600)
                temp_files.add(tmp.name)
                
                tmp.write(png_bytes)
                tmp.flush()
                tmp.seek(0)
                
                return send_file(
                    tmp.name, 
                    mimetype='image/png', 
                    as_attachment=True, 
                    download_name='graph.png'
                )
        except Exception as e:
            # Clean up temp file on error
            if 'tmp' in locals() and hasattr(tmp, 'name'):
                try:
                    os.unlink(tmp.name)
                    temp_files.discard(tmp.name)
                except OSError:
                    pass
            raise
    except Exception as e:
        logger.error(f"/generate_png failed: {e}", exc_info=True)
        # If the error is about missing SVG, return a specific message
        if isinstance(e, ValueError) and str(e).startswith("SVG element not found"):
            return jsonify({'error': 'Failed to render the graph: SVG element not found. Please check your input or try a different prompt.'}), 400
        return jsonify({'error': f'Failed to generate PNG: {e}'}), 500 