/**
 * ModalManager - Cute and friendly modal dialogs for user guidance
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class ModalManager {
    constructor() {
        this.currentModal = null;
        this.initializeStyles();
    }
    
    /**
     * Initialize CSS styles for modals
     */
    initializeStyles() {
        if (!document.getElementById('modal-manager-styles')) {
            const style = document.createElement('style');
            style.id = 'modal-manager-styles';
            style.textContent = `
                .modal-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.5);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 10000;
                    opacity: 0;
                    animation: fadeIn 0.3s ease forwards;
                }
                
                @keyframes fadeIn {
                    to { opacity: 1; }
                }
                
                @keyframes fadeOut {
                    to { opacity: 0; }
                }
                
                @keyframes modalSlideIn {
                    from {
                        transform: scale(0.8) translateY(-20px);
                        opacity: 0;
                    }
                    to {
                        transform: scale(1) translateY(0);
                        opacity: 1;
                    }
                }
                
                .modal-container {
                    background: white;
                    border-radius: 20px;
                    max-width: 500px;
                    width: 90%;
                    max-height: 80vh;
                    overflow-y: auto;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                    animation: modalSlideIn 0.4s ease;
                }
                
                .modal-header {
                    padding: 30px 30px 20px 30px;
                    border-bottom: 2px solid #f0f0f0;
                    text-align: center;
                }
                
                .modal-icon {
                    font-size: 48px;
                    margin-bottom: 15px;
                }
                
                .modal-title {
                    font-size: 24px;
                    font-weight: bold;
                    color: #2c3e50;
                    margin: 0 0 10px 0;
                }
                
                .modal-subtitle {
                    font-size: 14px;
                    color: #7f8c8d;
                    margin: 0;
                }
                
                .modal-body {
                    padding: 25px 30px;
                }
                
                .modal-section {
                    margin-bottom: 20px;
                }
                
                .modal-section-title {
                    font-size: 16px;
                    font-weight: 600;
                    color: #34495e;
                    margin: 0 0 12px 0;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                
                .modal-list {
                    list-style: none;
                    padding: 0;
                    margin: 0;
                }
                
                .modal-list li {
                    padding: 10px 15px;
                    background: #f8f9fa;
                    border-radius: 8px;
                    margin-bottom: 8px;
                    color: #555;
                    line-height: 1.5;
                    display: flex;
                    align-items: flex-start;
                    gap: 10px;
                }
                
                .modal-list li:before {
                    content: '→';
                    color: #667eea;
                    font-weight: bold;
                    flex-shrink: 0;
                }
                
                .modal-examples {
                    background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
                    border-left: 4px solid #667eea;
                    padding: 15px;
                    border-radius: 8px;
                    margin-top: 15px;
                }
                
                .modal-examples-title {
                    font-weight: 600;
                    color: #667eea;
                    margin: 0 0 10px 0;
                    font-size: 14px;
                }
                
                .modal-example {
                    background: white;
                    padding: 8px 12px;
                    border-radius: 6px;
                    margin-bottom: 6px;
                    font-size: 13px;
                    color: #555;
                }
                
                .modal-example:last-child {
                    margin-bottom: 0;
                }
                
                .modal-footer {
                    padding: 20px 30px 30px 30px;
                    text-align: center;
                }
                
                .modal-button {
                    padding: 12px 30px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    border-radius: 25px;
                    font-size: 15px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: transform 0.2s, box-shadow 0.2s;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
                }
                
                .modal-button:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
                }
                
                .modal-button:active {
                    transform: translateY(0);
                }
            `;
            document.head.appendChild(style);
        }
    }
    
    /**
     * Show guidance modal for unclear prompts
     * @param {string} language - 'zh' or 'en'
     */
    showPromptGuidance(language = 'en') {
        // Close any existing modal
        this.close();
        
        const isZh = language === 'zh';
        
        const content = isZh ? {
            icon: '🤔',
            title: '让我来帮你优化一下指令',
            subtitle: '简单明确的指令能帮助我更好地理解你的需求',
            sections: [
                {
                    title: '📝 好的指令应该包含：',
                    items: [
                        '明确的主题或概念（例如："太阳系"、"光合作用"）',
                        '想要做什么（例如："比较"、"分析"、"列举特点"）',
                        '想要的图表类型（可选，例如："思维导图"、"气泡图"）'
                    ]
                }
            ],
            examples: {
                title: '💡 试试这些例子：',
                items: [
                    '"生成光合作用的气泡图"',
                    '"比较猫和狗"',
                    '"创建关于太阳系的思维导图"',
                    '"分析工业革命的原因"'
                ]
            },
            button: '好的，我明白了'
        } : {
            icon: '🤔',
            title: 'Let me help you improve your prompt',
            subtitle: 'Clear and simple instructions help me understand your needs better',
            sections: [
                {
                    title: '📝 A good prompt should include:',
                    items: [
                        'A clear topic or concept (e.g., "Solar System", "Photosynthesis")',
                        'What you want to do (e.g., "compare", "analyze", "list features")',
                        'Desired diagram type (optional, e.g., "mind map", "bubble map")'
                    ]
                }
            ],
            examples: {
                title: '💡 Try these examples:',
                items: [
                    '"Generate a bubble map about photosynthesis"',
                    '"Compare cats and dogs"',
                    '"Create a mind map about the Solar System"',
                    '"Analyze causes of the Industrial Revolution"'
                ]
            },
            button: 'Got it, thanks!'
        };
        
        this.show(content);
    }
    
    /**
     * Show a custom modal with content
     * @param {Object} content - Modal content configuration
     */
    show(content) {
        // Create overlay
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        
        // Create container
        const container = document.createElement('div');
        container.className = 'modal-container';
        
        // Header
        const header = document.createElement('div');
        header.className = 'modal-header';
        
        const icon = document.createElement('div');
        icon.className = 'modal-icon';
        icon.textContent = content.icon || '💡';
        
        const title = document.createElement('h2');
        title.className = 'modal-title';
        title.textContent = content.title;
        
        const subtitle = document.createElement('p');
        subtitle.className = 'modal-subtitle';
        subtitle.textContent = content.subtitle;
        
        header.appendChild(icon);
        header.appendChild(title);
        header.appendChild(subtitle);
        
        // Body
        const body = document.createElement('div');
        body.className = 'modal-body';
        
        // Sections
        if (content.sections) {
            content.sections.forEach(section => {
                const sectionDiv = document.createElement('div');
                sectionDiv.className = 'modal-section';
                
                const sectionTitle = document.createElement('div');
                sectionTitle.className = 'modal-section-title';
                sectionTitle.textContent = section.title;
                
                const list = document.createElement('ul');
                list.className = 'modal-list';
                
                section.items.forEach(item => {
                    const li = document.createElement('li');
                    li.textContent = item;
                    list.appendChild(li);
                });
                
                sectionDiv.appendChild(sectionTitle);
                sectionDiv.appendChild(list);
                body.appendChild(sectionDiv);
            });
        }
        
        // Examples
        if (content.examples) {
            const examplesDiv = document.createElement('div');
            examplesDiv.className = 'modal-examples';
            
            const examplesTitle = document.createElement('div');
            examplesTitle.className = 'modal-examples-title';
            examplesTitle.textContent = content.examples.title;
            examplesDiv.appendChild(examplesTitle);
            
            content.examples.items.forEach(example => {
                const exampleDiv = document.createElement('div');
                exampleDiv.className = 'modal-example';
                exampleDiv.textContent = example;
                examplesDiv.appendChild(exampleDiv);
            });
            
            body.appendChild(examplesDiv);
        }
        
        // Footer
        const footer = document.createElement('div');
        footer.className = 'modal-footer';
        
        const button = document.createElement('button');
        button.className = 'modal-button';
        button.textContent = content.button || 'OK';
        button.onclick = () => this.close();
        
        footer.appendChild(button);
        
        // Assemble
        container.appendChild(header);
        container.appendChild(body);
        container.appendChild(footer);
        overlay.appendChild(container);
        
        // Close on overlay click
        overlay.onclick = (e) => {
            if (e.target === overlay) {
                this.close();
            }
        };
        
        // Add to DOM
        document.body.appendChild(overlay);
        this.currentModal = overlay;
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
    }
    
    /**
     * Close current modal
     */
    close() {
        if (this.currentModal) {
            const overlay = this.currentModal;
            overlay.style.animation = 'fadeOut 0.3s ease';
            
            setTimeout(() => {
                if (document.body.contains(overlay)) {
                    document.body.removeChild(overlay);
                }
                this.currentModal = null;
                
                // Restore body scroll
                document.body.style.overflow = '';
            }, 300);
        }
    }
}

// Create global singleton instance
if (typeof window !== 'undefined') {
    window.modalManager = new ModalManager();
    logger.debug('ModalManager', 'Global instance created');
}



















