/**
 * Black Cat VoiceAgent Character
 * Animated visual representation of VoiceAgent
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class BlackCat {
    constructor() {
        this.container = null;
        this.canvas = null;
        this.ctx = null;
        this.state = 'idle';  // idle, listening, thinking, speaking, celebrating, error
        this.animationFrame = null;
        this.onClick = null;
        
        // Animation parameters
        this.breatheOffset = 0;
        this.blinkTimer = 0;
        this.earAngle = 0;
        this.mouthOpen = 0;
        this.sparkles = [];
        
        this.logger = window.logger || console;
    }
    
    init(parentElement = document.body) {
        // Create container
        this.container = document.createElement('div');
        this.container.className = 'black-cat-container';
        this.container.title = 'Click me to talk';
        
        // Create canvas
        this.canvas = document.createElement('canvas');
        this.canvas.width = 240;  // 2x for retina
        this.canvas.height = 240;  // 2x for retina
        this.canvas.style.width = '120px';
        this.canvas.style.height = '120px';
        
        this.ctx = this.canvas.getContext('2d');
        
        // Add click handler
        this.container.addEventListener('click', () => {
            if (this.onClick) {
                this.onClick();
            }
        });
        
        this.container.appendChild(this.canvas);
        parentElement.appendChild(this.container);
        
        // Start animation
        this.animate();
        
        this.logger.info('BlackCat', 'Initialized');
    }
    
    animate() {
        this.animationFrame = requestAnimationFrame(() => this.animate());
        
        this.ctx.clearRect(0, 0, 240, 240);
        
        // Enable antialiasing for smoother rendering
        this.ctx.imageSmoothingEnabled = true;
        this.ctx.imageSmoothingQuality = 'high';
        
        switch (this.state) {
            case 'idle':
                this.drawIdle();
                break;
            case 'listening':
                this.drawListening();
                break;
            case 'thinking':
                this.drawThinking();
                break;
            case 'speaking':
                this.drawSpeaking();
                break;
            case 'celebrating':
                this.drawCelebrating();
                break;
            case 'error':
                this.drawError();
                break;
        }
    }
    
    drawIdle() {
        const ctx = this.ctx;
        const centerX = 120;  // Scaled for 240px canvas
        const centerY = 135;  // Scaled for 240px canvas
        
        this.breatheOffset = Math.sin(Date.now() / 1000) * 2;
        
        // Body
        ctx.fillStyle = '#000';
        ctx.beginPath();
        ctx.ellipse(centerX, centerY + this.breatheOffset, 52, 60, 0, 0, Math.PI * 2);  // Scaled 1.5x
        ctx.fill();
        
        // Head
        ctx.beginPath();
        ctx.arc(centerX, centerY - 52 + this.breatheOffset, 45, 0, Math.PI * 2);  // Scaled 1.5x
        ctx.fill();
        
        // Ears
        this.drawEars(centerX, centerY - 52 + this.breatheOffset, 0);
        
        // Eyes
        this.blinkTimer++;
        const eyeOpen = this.blinkTimer % 200 < 195 ? 1 : 0;
        this.drawEyes(centerX, centerY - 52 + this.breatheOffset, eyeOpen);
        
        // Nose
        this.drawNose(centerX, centerY - 48 + this.breatheOffset);
        
        // Tail
        this.drawTail(centerX + 45, centerY + 30, 0);
    }
    
    drawListening() {
        const ctx = this.ctx;
        const centerX = 120;
        const centerY = 135;
        
        // Glow effect
        ctx.save();
        ctx.shadowColor = '#667eea';
        ctx.shadowBlur = 30;  // Scaled 1.5x
        
        ctx.fillStyle = '#000';
        ctx.beginPath();
        ctx.ellipse(centerX, centerY, 52, 60, 0, 0, Math.PI * 2);  // Scaled 1.5x
        ctx.fill();
        
        ctx.restore();
        
        ctx.fillStyle = '#000';
        ctx.beginPath();
        ctx.arc(centerX, centerY - 52, 45, 0, Math.PI * 2);  // Scaled 1.5x
        ctx.fill();
        
        this.earAngle = Math.min(this.earAngle + 0.1, Math.PI / 6);
        this.drawEars(centerX, centerY - 52, -this.earAngle);
        this.drawEyes(centerX, centerY - 52, 1, 1.2);
        this.drawNose(centerX, centerY - 48);
        this.drawTail(centerX + 45, centerY + 30, Math.sin(Date.now() / 200) * 0.2);
    }
    
    drawThinking() {
        this.drawListening();
        
        const ctx = this.ctx;
        ctx.fillStyle = '#667eea';
        ctx.font = 'bold 36px Arial';  // Scaled 1.5x
        ctx.fillText('?', 180, 60);  // Scaled 1.5x
    }
    
    drawSpeaking() {
        const ctx = this.ctx;
        const centerX = 120;
        const centerY = 135;
        
        ctx.fillStyle = '#000';
        ctx.beginPath();
        ctx.ellipse(centerX, centerY, 52, 60, 0, 0, Math.PI * 2);  // Scaled 1.5x
        ctx.fill();
        
        ctx.beginPath();
        ctx.arc(centerX, centerY - 52, 45, 0, Math.PI * 2);  // Scaled 1.5x
        ctx.fill();
        
        this.drawEars(centerX, centerY - 52, 0);
        this.drawEyes(centerX, centerY - 52, 1);
        this.drawNose(centerX, centerY - 48);
        
        this.mouthOpen = Math.abs(Math.sin(Date.now() / 100));
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(centerX, centerY - 42, 12, 0, Math.PI * this.mouthOpen);
        ctx.stroke();
        
        this.drawSoundWaves(centerX + 60, centerY - 52);
    }
    
    drawCelebrating() {
        const ctx = this.ctx;
        const centerX = 120;
        const bounce = Math.abs(Math.sin(Date.now() / 200)) * 15;  // Scaled 1.5x
        const centerY = 120 - bounce;  // Scaled 1.5x
        
        ctx.fillStyle = '#000';
        ctx.beginPath();
        ctx.ellipse(centerX, centerY, 52, 60, 0, 0, Math.PI * 2);  // Scaled 1.5x
        ctx.fill();
        
        ctx.beginPath();
        ctx.arc(centerX, centerY - 52, 45, 0, Math.PI * 2);  // Scaled 1.5x
        ctx.fill();
        
        this.drawEars(centerX, centerY - 52, Math.PI / 8);
        
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 4;  // Scaled 1.5x
        ctx.beginPath();
        ctx.arc(centerX - 15, centerY - 60, 7, 0, Math.PI);  // Scaled 1.5x
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(centerX + 15, centerY - 60, 7, 0, Math.PI);  // Scaled 1.5x
        ctx.stroke();
        
        this.updateSparkles();
        this.drawSparkles();
        
        this.drawTail(centerX + 45, centerY + 30, Math.sin(Date.now() / 100) * 0.5);  // Scaled 1.5x
    }
    
    drawError() {
        // Similar to idle but with red tint
        this.drawIdle();
        const ctx = this.ctx;
        ctx.fillStyle = 'rgba(255, 0, 0, 0.2)';
        ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }
    
    drawEars(x, y, angle) {
        const ctx = this.ctx;
        ctx.fillStyle = '#000';
        
        // Left ear - smooth rounded triangle
        ctx.save();
        ctx.translate(x - 28, y - 38);
        ctx.rotate(-Math.PI / 6 + angle);
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.quadraticCurveTo(-8, -18, -10, -28);
        ctx.quadraticCurveTo(-5, -30, 0, -28);
        ctx.quadraticCurveTo(5, -26, 10, -20);
        ctx.quadraticCurveTo(8, -10, 0, 0);
        ctx.closePath();
        ctx.fill();
        
        // Inner ear detail (pink)
        ctx.fillStyle = '#FF69B4';
        ctx.beginPath();
        ctx.moveTo(2, -4);
        ctx.quadraticCurveTo(0, -16, -2, -20);
        ctx.quadraticCurveTo(3, -18, 5, -12);
        ctx.quadraticCurveTo(5, -8, 2, -4);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
        
        // Right ear - smooth rounded triangle
        ctx.save();
        ctx.translate(x + 28, y - 38);
        ctx.rotate(Math.PI / 6 - angle);
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.quadraticCurveTo(8, -18, 10, -28);
        ctx.quadraticCurveTo(5, -30, 0, -28);
        ctx.quadraticCurveTo(-5, -26, -10, -20);
        ctx.quadraticCurveTo(-8, -10, 0, 0);
        ctx.closePath();
        ctx.fill();
        
        // Inner ear detail (pink)
        ctx.fillStyle = '#FF69B4';
        ctx.beginPath();
        ctx.moveTo(-2, -4);
        ctx.quadraticCurveTo(0, -16, 2, -20);
        ctx.quadraticCurveTo(-3, -18, -5, -12);
        ctx.quadraticCurveTo(-5, -8, -2, -4);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    }
    
    drawEyes(x, y, open = 1, scale = 1) {
        const ctx = this.ctx;
        ctx.fillStyle = open > 0 ? '#FFD700' : '#000';
        
        ctx.beginPath();
        ctx.ellipse(x - 15, y - 7, 6 * scale, 9 * open, 0, 0, Math.PI * 2);
        ctx.fill();
        
        ctx.beginPath();
        ctx.ellipse(x + 15, y - 7, 6 * scale, 9 * open, 0, 0, Math.PI * 2);
        ctx.fill();
        
        // Add pupils for more life
        if (open > 0.5) {
            ctx.fillStyle = '#000';
            ctx.beginPath();
            ctx.arc(x - 15, y - 7, 3 * scale, 0, Math.PI * 2);
            ctx.fill();
            ctx.beginPath();
            ctx.arc(x + 15, y - 7, 3 * scale, 0, Math.PI * 2);
            ctx.fill();
        }
    }
    
    drawNose(x, y) {
        const ctx = this.ctx;
        
        // Pink triangular nose
        ctx.fillStyle = '#FF69B4';
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x - 4, y - 6);
        ctx.lineTo(x + 4, y - 6);
        ctx.closePath();
        ctx.fill();
        
        // Nose highlight for depth
        ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
        ctx.beginPath();
        ctx.moveTo(x - 1, y - 2);
        ctx.lineTo(x - 3, y - 5);
        ctx.lineTo(x + 1, y - 5);
        ctx.closePath();
        ctx.fill();
    }
    
    drawTail(x, y, angle) {
        const ctx = this.ctx;
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 12;  // Scaled 1.5x
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.quadraticCurveTo(x + 30, y - 30 + angle * 30, x + 45, y - 15);  // Scaled 1.5x
        ctx.stroke();
    }
    
    drawSoundWaves(x, y) {
        const ctx = this.ctx;
        ctx.strokeStyle = 'rgba(102, 126, 234, 0.6)';
        ctx.lineWidth = 3;  // Scaled 1.5x
        
        for (let i = 0; i < 3; i++) {
            const offset = (Date.now() / 200 + i * 0.5) % 2;
            ctx.beginPath();
            ctx.arc(x, y, 15 + offset * 15, 0, Math.PI * 2);  // Scaled 1.5x
            ctx.stroke();
        }
    }
    
    updateSparkles() {
        if (this.sparkles.length < 10 && Math.random() > 0.7) {
            this.sparkles.push({
                x: 120 + (Math.random() - 0.5) * 90,  // Scaled 1.5x
                y: 75 + (Math.random() - 0.5) * 90,  // Scaled 1.5x
                life: 1
            });
        }
        
        this.sparkles = this.sparkles.filter(s => s.life > 0);
        this.sparkles.forEach(s => s.life -= 0.02);
    }
    
    drawSparkles() {
        const ctx = this.ctx;
        this.sparkles.forEach(s => {
            ctx.fillStyle = `rgba(255, 215, 0, ${s.life})`;
            ctx.beginPath();
            ctx.arc(s.x, s.y, 4.5, 0, Math.PI * 2);  // Scaled 1.5x
            ctx.fill();
        });
    }
    
    setState(newState) {
        if (this.state === newState) return;
        
        this.logger.info('BlackCat', 'State:', this.state, '->', newState);
        this.state = newState;
        
        const tooltips = {
            idle: 'Click me to talk',
            listening: "I'm listening...",
            thinking: 'Thinking...',
            speaking: 'Speaking...',
            celebrating: 'Success!',
            error: 'Oops! Something went wrong'
        };
        this.container.title = tooltips[newState] || '';
        
        if (newState === 'idle') {
            this.earAngle = 0;
            this.sparkles = [];
        }
    }
    
    destroy() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
        if (this.container && this.container.parentElement) {
            this.container.parentElement.removeChild(this.container);
        }
    }
}

window.BlackCat = BlackCat;

