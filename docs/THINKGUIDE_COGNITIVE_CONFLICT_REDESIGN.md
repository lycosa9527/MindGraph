# ThinkGuide Cognitive Conflict Redesign

**New Vision**: ThinkGuide as a Cognitive Conflict Generator that streams 3 parallel examples from different LLMs.

---

## 🎯 User Experience

### Current Flow (OLD)
```
1. User opens ThinkGuide
2. Gets greeting message
3. User asks questions → Gets answers
```

### New Flow (REDESIGNED)
```
1. User opens ThinkGuide
2. Gets greeting message
3. **Immediately streams 3 cognitive conflict examples in parallel**
   - From qwen3-next-80b-a3b-instruct
   - From deepseek-v3.1 (thinking disabled)
   - From Moonshot-Kimi-K2-Instruct
4. User picks one example to explore
5. ThinkGuide continues conversation about chosen conflict
```

---

## 🖼️ Visual Design

### Vertical Stacking Layout (Narrow Panel Optimized)

**Like Node Palette's streaming pattern - batch of 3, then "More" button**

```
┌─────────────────────────────────────┐
│ ThinkGuide 💭                       │
├─────────────────────────────────────┤
│ 💡 Explore Cognitive Challenges     │
│    for "Photosynthesis"             │
├─────────────────────────────────────┤
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ 🟣 Qwen Next 80B                │ │
│ │                                 │ │
│ │ 🤔 Challenge #1:                │ │
│ │                                 │ │
│ │ Plants make oxygen through      │ │
│ │ photosynthesis, but they also   │ │
│ │ NEED oxygen to survive.         │ │
│ │                                 │ │
│ │ How does this work? 🌱💨        │ │
│ │                                 │ │
│ │         [Explore This] 💬        │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ 🔴 DeepSeek V3                  │ │
│ │                                 │ │
│ │ 🤔 Challenge #2:                │ │
│ │                                 │ │
│ │ Why do plants need sunlight if  │ │
│ │ they can store energy in        │ │
│ │ glucose? Can't they just use    │ │
│ │ stored glucose forever? 🔋⚡    │ │
│ │                                 │ │
│ │         [Explore This] 💬        │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ 🟡 Kimi K2                      │ │
│ │                                 │ │
│ │ 🤔 Challenge #3:                │ │
│ │                                 │ │
│ │ If photosynthesis happens       │ │
│ │ during the day, how do plants   │ │
│ │ survive through the night?      │ │
│ │ What process keeps them alive?🌙│ │
│ │                                 │ │
│ │         [Explore This] 💬        │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │      🔄 Load More Examples      │ │ ← Like Node Palette!
│ └─────────────────────────────────┘ │
│                                     │
│ Or ask your own question below ⬇️  │
├─────────────────────────────────────┤
│ [Type your question here...    ]🎤 │
└─────────────────────────────────────┘
```

### Streaming Animation (Like Node Palette)

```
First batch streaming:

┌─────────────────────────────────┐
│ 🟣 Qwen Next 80B                │
│ ⏳ Generating challenge...      │ ← Streaming...
│ Plants make oxygen through...   │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ 🔴 DeepSeek V3                  │
│ ⏳ Generating challenge...      │ ← Streaming...
│ Why do plants need...           │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ 🟡 Kimi K2                      │
│ ⏳ Generating challenge...      │ ← Streaming...
│ If photosynthesis happens...    │
└─────────────────────────────────┘

[All complete] → "Load More" button appears
```

---

## 🔧 Implementation

### 1. Update ThinkGuide Backend (`routers/thinking_mode.py`)

```python
from services.llm_service import llm_service

# New: Cognitive conflict generation endpoint
@router.post("/thinking_mode/generate_conflicts")
async def generate_cognitive_conflicts(request: Request):
    """Generate 3 parallel cognitive conflict examples"""
    
    data = await request.json()
    diagram_type = data.get('diagram_type', 'circle_map')
    center_topic = data.get('center_topic', 'unknown')
    diagram_data = data.get('diagram_data', {})
    language = data.get('language', 'en')
    
    # Build cognitive conflict prompt
    prompt = build_cognitive_conflict_prompt(
        diagram_type=diagram_type,
        center_topic=center_topic,
        diagram_data=diagram_data,
        language=language
    )
    
    # Stream from 3 LLMs in parallel
    return StreamingResponse(
        stream_three_llm_conflicts(prompt, language),
        media_type="text/event-stream"
    )


async def stream_three_llm_conflicts(prompt: str, language: str):
    """Stream cognitive conflicts from 3 LLMs simultaneously"""
    
    # LLM configurations
    llm_configs = [
        {
            'model': 'qwen',
            'actual_model': 'qwen3-next-80b-a3b-instruct',
            'label': 'Qwen Next 80B',
            'color': 'purple'
        },
        {
            'model': 'deepseek',
            'actual_model': 'deepseek-v3.1',
            'label': 'DeepSeek V3',
            'color': 'red',
            'extra_params': {'enable_thinking': False}  # Disable thinking!
        },
        {
            'model': 'kimi',
            'actual_model': 'Moonshot-Kimi-K2-Instruct',
            'label': 'Kimi K2',
            'color': 'yellow'
        }
    ]
    
    # Create 3 parallel tasks
    import asyncio
    tasks = []
    for config in llm_configs:
        task = asyncio.create_task(
            stream_single_llm_conflict(prompt, config, language)
        )
        tasks.append(task)
    
    # Yield results as they come in
    async for chunk in merge_streams(tasks):
        yield f"data: {json.dumps(chunk)}\n\n"
    
    yield "data: {\"event\": \"complete\"}\n\n"


async def stream_single_llm_conflict(prompt: str, config: dict, language: str):
    """Stream from a single LLM"""
    
    try:
        # Use LLM middleware
        response = await llm_service.chat(
            prompt=prompt,
            model=config['model'],
            temperature=0.8,  # Higher for creative conflicts
            max_tokens=300,  # Concise conflicts
            timeout=15.0,
            **config.get('extra_params', {})
        )
        
        # Stream chunks
        for chunk in response:
            yield {
                'event': 'chunk',
                'source': config['model'],
                'label': config['label'],
                'color': config['color'],
                'content': chunk
            }
            
    except Exception as e:
        logger.error(f"Error streaming from {config['model']}: {e}")
        yield {
            'event': 'error',
            'source': config['model'],
            'error': str(e)
        }


def build_cognitive_conflict_prompt(diagram_type, center_topic, diagram_data, language):
    """Build prompt for cognitive conflict generation"""
    
    if language == 'zh':
        return f"""你是一位资深的思维教学专家，擅长通过"认知冲突"激发学生深度思考。

学生正在创建关于"{center_topic}"的{diagram_type}图表。

请生成一个具体的、有启发性的认知冲突问题，要求：

1. **基于学生当前理解**：针对"{center_topic}"这个主题
2. **制造矛盾**：呈现一个看似矛盾但实际可解释的现象
3. **激发好奇心**：让学生想要探索答案
4. **适合K12**：语言简单，例子生动
5. **简洁**：3-4句话，包含一个emoji

格式示例：
🤔 Challenge: [呈现矛盾现象]
[提出引导性问题]

直接生成认知冲突，不要解释原理，不要说"根据"。"""
    
    else:  # English
        return f"""You are an expert teaching mentor who creates "Cognitive Conflicts" to spark deeper thinking.

The student is building a {diagram_type} about "{center_topic}".

Generate ONE specific, thought-provoking cognitive conflict question that:

1. **Based on current understanding**: Related to "{center_topic}"
2. **Creates contradiction**: Present a seemingly contradictory but explainable phenomenon
3. **Sparks curiosity**: Makes students want to explore the answer
4. **K12-appropriate**: Simple language, vivid examples
5. **Concise**: 3-4 sentences, include one emoji

Format example:
🤔 Challenge: [Present contradictory phenomenon]
[Ask guiding question]

Generate the conflict directly without explaining the principle."""


async def merge_streams(tasks):
    """Merge multiple async streams into one"""
    
    queues = [asyncio.Queue() for _ in tasks]
    
    # Consumer for each task
    async def consume(task, queue):
        async for chunk in task:
            await queue.put(chunk)
        await queue.put(None)  # Signal completion
    
    # Start consumers
    consumers = [
        asyncio.create_task(consume(task, queue))
        for task, queue in zip(tasks, queues)
    ]
    
    # Yield from all queues until all complete
    active = len(queues)
    while active > 0:
        for queue in queues:
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=0.1)
                if chunk is None:
                    active -= 1
                else:
                    yield chunk
            except asyncio.TimeoutError:
                continue
    
    # Wait for all consumers to finish
    await asyncio.gather(*consumers)
```

---

### 2. Update ThinkGuide Frontend (`static/js/editor/thinking-mode-manager.js`)

```javascript
class ThinkingModeManager {
    
    async openPanel() {
        // ... existing code ...
        
        // After greeting, generate cognitive conflicts
        await this.generateCognitiveConflicts();
    }
    
    async generateCognitiveConflicts() {
        this.logger.info('[ThinkGuide] Generating cognitive conflicts from 3 LLMs...');
        
        // Show 3-column layout
        this.showConflictLayout();
        
        // Extract diagram data
        const diagramData = this.extractDiagramData();
        
        try {
            const response = await auth.fetch('/thinking_mode/generate_conflicts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    diagram_type: this.diagramType,
                    center_topic: this.getCenterTopic(),
                    diagram_data: diagramData,
                    language: this.language
                })
            });
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            // Stream chunks from 3 LLMs
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = JSON.parse(line.slice(6));
                        this.handleConflictChunk(data);
                    }
                }
            }
            
            this.logger.info('[ThinkGuide] Cognitive conflicts generated');
            
        } catch (error) {
            this.logger.error('[ThinkGuide] Error generating conflicts:', error);
        }
    }
    
    showConflictLayout() {
        // Create vertical stacking layout (like Node Palette)
        const html = `
            <div class="cognitive-conflicts-container">
                <div class="conflicts-header">
                    <h3>💡 ${this.language === 'zh' ? '探索认知挑战' : 'Explore Cognitive Challenges'}</h3>
                    <p class="conflicts-topic">${this.language === 'zh' ? '关于' : 'for'} "${this.getCenterTopic()}"</p>
                </div>
                
                <!-- Scrollable conflict list (like Node Palette) -->
                <div class="conflicts-list" id="conflicts-list">
                    <!-- Conflicts will be added here as they stream -->
                </div>
                
                <!-- Load More button (like Node Palette) -->
                <div class="conflicts-footer">
                    <button class="load-more-btn" id="load-more-conflicts" style="display:none;">
                        🔄 ${this.language === 'zh' ? '加载更多示例' : 'Load More Examples'}
                    </button>
                    <p class="help-text">${this.language === 'zh' ? '或在下方提出你自己的问题 ⬇️' : 'Or ask your own question below ⬇️'}</p>
                </div>
            </div>
        `;
        
        this.chatHistory.innerHTML = html;
        
        // Store batch number
        this.conflictBatchNumber = 0;
        
        // Add click handler for "Load More" button
        document.getElementById('load-more-conflicts')?.addEventListener('click', () => {
            this.generateCognitiveConflicts();
        });
    }
    
    addConflictCard(source, label, color) {
        // Add a new conflict card to the list
        const conflictsList = document.getElementById('conflicts-list');
        if (!conflictsList) return;
        
        const conflictId = `conflict-${source}-${Date.now()}`;
        
        const card = document.createElement('div');
        card.className = 'conflict-card';
        card.dataset.source = source;
        card.innerHTML = `
            <div class="conflict-header ${source}-header">
                <span class="llm-badge">${label}</span>
            </div>
            <div class="conflict-content" id="${conflictId}">
                <div class="streaming-indicator">⏳ ${this.language === 'zh' ? '生成中...' : 'Generating...'}</div>
            </div>
            <button class="explore-btn" data-conflict-id="${conflictId}" style="display:none;">
                ${this.language === 'zh' ? '探索此挑战' : 'Explore This'} 💬
            </button>
        `;
        
        conflictsList.appendChild(card);
        
        // Add click handler
        card.querySelector('.explore-btn').addEventListener('click', (e) => {
            const conflictId = e.target.dataset.conflictId;
            this.exploreConflict(conflictId);
        });
        
        return conflictId;
    }
    
    handleConflictChunk(data) {
        const { event, source, content, label, color } = data;
        
        if (event === 'start') {
            // Create a new card for this LLM source
            const badge = {
                'qwen': '🟣 Qwen Next 80B',
                'deepseek': '🔴 DeepSeek V3',
                'kimi': '🟡 Kimi K2'
            }[source] || label;
            
            this.currentConflictId = this.addConflictCard(source, badge, color);
        }
        else if (event === 'chunk') {
            // Append to the current card
            const contentDiv = document.getElementById(this.currentConflictId);
            if (contentDiv) {
                // Remove "Generating..." indicator on first chunk
                const indicator = contentDiv.querySelector('.streaming-indicator');
                if (indicator) {
                    indicator.remove();
                    // Start with empty content
                    contentDiv.textContent = '';
                }
                
                // Append content
                contentDiv.textContent += content;
            }
        }
        else if (event === 'complete') {
            // Show the "Explore" button for this card
            const card = document.getElementById(this.currentConflictId)?.closest('.conflict-card');
            if (card) {
                const btn = card.querySelector('.explore-btn');
                if (btn) btn.style.display = 'block';
            }
        }
        else if (event === 'all_complete') {
            // All 3 conflicts generated - show "Load More" button
            const loadMoreBtn = document.getElementById('load-more-conflicts');
            if (loadMoreBtn) {
                loadMoreBtn.style.display = 'block';
            }
            this.conflictBatchNumber++;
        }
    }
    
    exploreConflict(conflictId) {
        // Get the conflict text
        const contentDiv = document.getElementById(conflictId);
        const conflictText = contentDiv?.textContent || '';
        
        if (!conflictText) return;
        
        // Close conflict layout and switch to chat mode
        this.closeConflictLayout();
        
        // Start conversation with this conflict
        const prompt = this.language === 'zh'
            ? `我想探索这个认知冲突：\n\n${conflictText}\n\n请帮我理解这个矛盾。`
            : `I want to explore this cognitive conflict:\n\n${conflictText}\n\nHelp me understand this contradiction.`;
        
        this.addUserMessage(prompt);
        this.sendMessage(prompt);
    }
    
    closeConflictLayout() {
        // Clear the conflicts layout and switch back to normal chat
        this.chatHistory.innerHTML = '';
        this.logger.info('[ThinkGuide] Closed conflict layout, switching to chat mode');
    }
}
```

---

### 3. Add Styles (`static/css/thinking-mode.css`)

```css
/* Cognitive Conflicts Layout (Vertical Stacking - Like Node Palette) */
.cognitive-conflicts-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 16px;
}

.conflicts-header {
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 2px solid #e5e7eb;
}

.conflicts-header h3 {
    font-size: 16px;
    color: #374151;
    font-weight: 600;
    margin: 0 0 4px 0;
}

.conflicts-topic {
    font-size: 13px;
    color: #6b7280;
    margin: 0;
}

/* Scrollable list (like Node Palette) */
.conflicts-list {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding-right: 4px;
    margin-bottom: 16px;
}

/* Individual conflict card (like Node Palette item) */
.conflict-card {
    background: white;
    border: 2px solid #e5e7eb;
    border-radius: 10px;
    margin-bottom: 12px;
    overflow: hidden;
    transition: all 0.3s ease;
    animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.conflict-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
    border-color: #3b82f6;
}

/* LLM Header */
.conflict-header {
    padding: 10px 12px;
    font-weight: 600;
    font-size: 13px;
}

.qwen-header {
    background: linear-gradient(135deg, #a78bfa 0%, #8b5cf6 100%);
    color: white;
}

.deepseek-header {
    background: linear-gradient(135deg, #f87171 0%, #ef4444 100%);
    color: white;
}

.kimi-header {
    background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
    color: white;
}

.llm-badge {
    font-size: 13px;
}

/* Conflict content */
.conflict-content {
    padding: 14px;
    min-height: 80px;
    font-size: 13px;
    line-height: 1.6;
    color: #374151;
    white-space: pre-wrap;
}

.streaming-indicator {
    color: #9ca3af;
    font-style: italic;
    animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* Explore button */
.explore-btn {
    width: 100%;
    padding: 10px;
    background: #3b82f6;
    color: white;
    border: none;
    cursor: pointer;
    font-weight: 600;
    font-size: 13px;
    transition: all 0.2s;
    border-top: 1px solid #e5e7eb;
}

.explore-btn:hover {
    background: #2563eb;
}

.explore-btn:active {
    transform: scale(0.98);
}

/* Footer with Load More button */
.conflicts-footer {
    margin-top: auto;
    padding-top: 12px;
    border-top: 2px solid #e5e7eb;
}

.load-more-btn {
    width: 100%;
    padding: 12px;
    background: #f3f4f6;
    color: #374151;
    border: 2px dashed #d1d5db;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 600;
    font-size: 14px;
    transition: all 0.2s;
    margin-bottom: 12px;
}

.load-more-btn:hover {
    background: #e5e7eb;
    border-color: #9ca3af;
    transform: translateY(-1px);
}

.load-more-btn:active {
    transform: translateY(0);
}

.help-text {
    text-align: center;
    margin: 0;
    padding: 8px;
    color: #6b7280;
    font-size: 12px;
    background: #f9fafb;
    border-radius: 6px;
}

/* Scrollbar styling */
.conflicts-list::-webkit-scrollbar {
    width: 6px;
}

.conflicts-list::-webkit-scrollbar-track {
    background: #f3f4f6;
    border-radius: 3px;
}

.conflicts-list::-webkit-scrollbar-thumb {
    background: #d1d5db;
    border-radius: 3px;
}

.conflicts-list::-webkit-scrollbar-thumb:hover {
    background: #9ca3af;
}
```

---

## 🎯 Next Steps

1. ✅ Create cognitive conflict prompts
2. ⏳ Implement parallel streaming backend
3. ⏳ Update frontend to display 3 columns
4. ⏳ Add CSS for visual design
5. ⏳ Test with real diagram topics
6. ⏳ Add "Regenerate" button for new conflicts

Ready to implement?

