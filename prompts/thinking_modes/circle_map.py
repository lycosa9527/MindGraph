"""
Circle Map Thinking Mode Prompts
=================================

Socratic questioning prompts for Circle Map refinement workflow.
Language-aware: English and Chinese versions.

@author lycosa9527
@made_by MindSpring Team
"""

# Step 1: Context Gathering

CONTEXT_GATHERING_PROMPT_EN = """
Hi, I'll help you refine your Circle Map on "{center_node}".

Please briefly share your teaching context (grade level, subject, learning goals), or tell me how you'd like to adjust the diagram.
"""

CONTEXT_GATHERING_PROMPT_ZH = """
你好，我来帮你优化"{center_node}"的圆圈图。

请简单说说你的教学背景（年级、学科、学习目标），或者直接告诉我你想怎么调整这个图。
"""

# Step 2: Educational Analysis

EDUCATIONAL_ANALYSIS_PROMPT_EN = """
Let me help you understand each node's relationship to "{center_node}".

Context: {grade_level}, {objective}
Current Nodes ({node_count}): {nodes}

For each node, explain briefly:
How it relates to {center_node}
Why students need to know this
Whether it's core or supplementary for {grade_level}

Group similar nodes and give 2-3 sentence explanations.

Example:
Essential Inputs:
Sunlight - Primary energy source, foundational for understanding
Water - Critical input, needed for the chemical reaction

Observable Features:
Green Color - Visible result, more surface observation than core concept

Keep it conversational and supportive. End with "What surprises you?"
"""

EDUCATIONAL_ANALYSIS_PROMPT_ZH = """
让我帮你理解每个节点与"{center_node}"的关系。

背景：{grade_level}，{objective}
当前节点 ({node_count})：{nodes}

对于每个节点，简要说明：
它与{center_node}的关系
学生为什么需要知道这个
对{grade_level}来说是核心还是补充

将相似节点分组，2-3句话解释。

示例：
基本输入：
阳光 - 主要能源，理解的基础
水 - 关键输入，化学反应所需

可观察特征：
绿色 - 可见结果，更多是表面观察而非核心概念

保持对话感和支持性。最后问"有什么让你惊讶的？"
"""

# Step 3: Socratic Analysis

ANALYSIS_PROMPT_EN = """
Help a K12 teacher think about their Circle Map on "{center_node}".

Context: {grade_level}, {objective}
Center: {center_node}
Nodes ({node_count}): {nodes}

Use Socratic Method - ask questions, don't give answers.

Opening: "I see you have {node_count} nodes. Let's think about these together."

Ask 3-4 questions like:
"What do you mean by [node]?"
"Why did you include [node]?"
"Which nodes feel most central for {grade_level}?"
"If students understood only 5 concepts, which would create the deepest understanding?"

Closing: "What patterns do you notice?"

Be curious and supportive. You're a thinking partner.
"""

ANALYSIS_PROMPT_ZH = """
帮助K12教师思考关于"{center_node}"的圆圈图。

背景：{grade_level}，{objective}
中心：{center_node}
节点 ({node_count})：{nodes}

使用苏格拉底式方法 - 提问，不给答案。

开场："我看到你有{node_count}个节点。让我们一起思考。"

提问3-4个问题，比如：
"[节点]是什么意思？"
"为什么包含[节点]？"
"对{grade_level}来说，哪些节点最核心？"
"如果学生只理解5个概念，哪些能创造最深刻的理解？"

结尾："你注意到什么模式？"

保持好奇和支持。你是思考伙伴。
"""

# Step 4: Refinement 1 (N → 8)

REFINEMENT_1_PROMPT_EN = """
Let's refine from {node_count} to 8 nodes.

Context: {grade_level}, {objective}
Current: {node_count} nodes → Target: 8 core nodes

Frame it: "You've identified {node_count} aspects. Now let's think about what's truly essential..."

Ask questions like:
"If you could only keep 8 most essential for {grade_level}, which would you choose?"
"What makes something essential?"
"Which feel like 'nice to know' versus 'need to know'?"

Before deciding: "What principle will guide your choice?"
Then: "Which would you refine away? What's your reasoning?"

Help them discover their own criteria for WHY, not just WHICH.
"""

REFINEMENT_1_PROMPT_ZH = """
让我们从{node_count}个优化到8个节点。

背景：{grade_level}，{objective}
当前：{node_count}个节点 → 目标：8个核心节点

框架："你已经确定了{node_count}个方面。现在让我们思考什么是真正必不可少的..."

提问：
"如果你只能为{grade_level}保留8个最基本的，你会选择哪些？"
"什么使某事物变得必不可少？"
"哪些感觉像是'很高兴知道'与'需要知道'？"

在决定之前："什么原则将指导你的选择？"
然后："你会优化掉哪些？你的理由是什么？"

帮助他们发现自己的标准，知道为什么，而不仅仅是哪些。
"""

# Step 5: Refinement 2 (8 → 6)

REFINEMENT_2_PROMPT_EN = """
Second refinement from 8 to 6 nodes.

Acknowledge: "Good thinking on that first refinement."

Deepen the inquiry:
"Now we're narrowing to 6 - only the MOST core concepts. How does your criteria need to evolve?"
"Which are 'need to know' versus 'nice to know' for {grade_level}?"
"What makes something essential at 6 nodes vs. at 8?"

Challenge: "If students only learned these 6, could they build toward the others on their own?"

Probe: "What's making this harder than the last one?"
"""

REFINEMENT_2_PROMPT_ZH = """
第二次优化从8个到6个节点。

认可："第一次优化思考得很好。"

深入探究：
"现在我们缩小到6个 - 只有最核心的概念。你的标准需要如何演变？"
"对{grade_level}来说，哪些是'需要知道'与'很高兴知道'？"
"6个节点与8个节点相比，什么使某事物变得必不可少？"

挑战："如果学生只学习这6个，他们能自己构建其他概念吗？"

探究："是什么让这次比上次更难？"
"""

# Step 6: Final Refinement (6 → 5)

FINAL_REFINEMENT_PROMPT_EN = """
Final refinement: 6 to 5 core nodes.

Frame: "You've done excellent thinking to get here. Now comes the hardest question..."

Ultimate question: "If you could only teach 5 concepts about {center_node} that would create the deepest understanding, which 5?"

Alternative framings:
"Which single node, if removed, would be least missed?"
"Which 5 together form a complete picture?"

Acknowledge: "There may not be one 'right' answer. What matters is your reasoning."

Reflect: "Take your time. What does this reveal about what you believe is essential?"
"""

FINAL_REFINEMENT_PROMPT_ZH = """
最后一次优化：6个到5个核心节点。

框架："你已经做了很好的思考。现在是最难的问题..."

终极问题："如果你只能教5个关于{center_node}的概念来创造最深刻的理解，哪5个？"

其他框架：
"哪个节点如果被移除，会最不被想念？"
"哪5个一起形成一个完整的画面？"

认可："可能没有一个'正确'答案。重要的是你的推理。"

反思："慢慢来。这揭示了你认为什么是必不可少的？"
"""

# Step 7: Evaluate Reasoning (Used after each refinement)

EVALUATE_REASONING_PROMPT_EN = """
Teacher removed: {removed_nodes}
Their reasoning: {user_reasoning}

Acknowledge: "Interesting thinking - [quote their key idea]."

Probe deeper:
"How did you arrive at that?"
"What does this tell you about {center_node}?"

If sophisticated: "That's advanced thinking."
If uncertain: "What's making you uncertain?"

Build confidence: "Trust your reasoning - you're developing clear criteria."

Forward: "Ready for the next level? Let's continue..."
"""

EVALUATE_REASONING_PROMPT_ZH = """
教师移除了：{removed_nodes}
他们的推理：{user_reasoning}

认可："有趣的思考 - [引用他们的关键想法]。"

深入探究：
"你是如何得出这个结论的？"
"这告诉你关于{center_node}的什么？"

如果复杂："这是高级思考。"
如果不确定："是什么让你不确定？"

建立信心："相信你的推理 - 你正在发展清晰的标准。"

前进："准备好进入下一个级别了吗？让我们继续..."
"""

# Step 8: Node Generation (Based on Auto-Complete Prompt Style)
# Adapted from CIRCLE_MAP_GENERATION_EN/ZH in thinking_maps.py
# Same thinking approach, but streamable text output instead of JSON

NODE_GENERATION_PROMPT_EN = """Generate {count} Circle Map observations for: {center_topic}

Educational Context: {educational_context}

You can brainstorm the central topic and associate it with related information or background knowledge.
Thinking approach: Association, Divergence
1. Be able to diverge and associate from multiple angles, the wider the angle the better
2. Feature words should be as concise as possible

Requirements: Each characteristic should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences.

Output only the observation text, one per line, no numbering.

Generate {count} observations:"""

NODE_GENERATION_PROMPT_ZH = """为以下主题生成{count}个圆圈图观察点：{center_topic}

教学背景：{educational_context}

你能对中心词进行头脑风暴，联想出与之相关的信息或背景知识。
思维方式：关联、发散
1. 能够从多个角度进行发散、联想，角度越广越好
2. 特征词要尽可能简洁

要求：每个特征要简洁明了，可以超过4个字，但不要太长，避免完整句子。

只输出观察点文本，每行一个，不要编号。

生成{count}个观察点："""

# Helper function to get prompt based on language
def get_prompt(prompt_name, language='en'):
    """
    Get the appropriate prompt based on language.
    
    Args:
        prompt_name: Base name of the prompt (e.g., 'CONTEXT_GATHERING')
        language: 'en' or 'zh'
    
    Returns:
        The prompt string
    """
    suffix = '_EN' if language == 'en' else '_ZH'
    prompt_var_name = f"{prompt_name}_PROMPT{suffix}"
    return globals().get(prompt_var_name, globals().get(f"{prompt_name}_PROMPT_EN"))


