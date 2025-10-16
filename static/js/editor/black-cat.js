/**
 * Black Cat VoiceAgent Character
 * Animated visual representation of VoiceAgent
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
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
        this.canvas.width = 160;
        this.canvas.height = 160;
        this.canvas.style.width = '80px';
        this.canvas.style.height = '80px';
        
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
        
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
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
        const centerX = 80;
        const centerY = 90;
        
        this.breatheOffset = Math.sin(Date.now() / 1000) * 2;
        
        // Body
        ctx.fillStyle = '#000';
        ctx.beginPath();
        ctx.ellipse(centerX, centerY + this.breatheOffset, 35, 40, 0, 0, Math.PI * 2);
        ctx.fill();
        
        // Head
        ctx.beginPath();
        ctx.arc(centerX, centerY - 35 + this.breatheOffset, 30, 0, Math.PI * 2);
        ctx.fill();
        
        // Ears
        this.drawEars(centerX, centerY - 35 + this.breatheOffset, 0);
        
        // Eyes
        this.blinkTimer++;
        const eyeOpen = this.blinkTimer % 200 < 195 ? 1 : 0;
        this.drawEyes(centerX, centerY - 35 + this.breatheOffset, eyeOpen);
        
        // Tail
        this.drawTail(centerX + 30, centerY + 20, 0);
    }
    
    drawListening() {
        const ctx = this.ctx;
        const centerX = 80;
        const centerY = 90;
        
        // Glow effect
        ctx.save();
        ctx.shadowColor = '#667eea';
        ctx.shadowBlur = 20;
        
        ctx.fillStyle = '#000';
        ctx.beginPath();
        ctx.ellipse(centerX, centerY, 35, 40, 0, 0, Math.PI * 2);
        ctx.fill();
        
        ctx.restore();
        
        ctx.fillStyle = '#000';
        ctx.beginPath();
        ctx.arc(centerX, centerY - 35, 30, 0, Math.PI * 2);
        ctx.fill();
        
        this.earAngle = Math.min(this.earAngle + 0.1, Math.PI / 6);
        this.drawEars(centerX, centerY - 35, -this.earAngle);
        this.drawEyes(centerX, centerY - 35, 1, 1.2);
        this.drawTail(centerX + 30, centerY + 20, Math.sin(Date.now() / 200) * 0.2);
    }
    
    drawThinking() {
        this.drawListening();
        
        const ctx = this.ctx;
        ctx.fillStyle = '#667eea';
        ctx.font = 'bold 24px Arial';
        ctx.fillText('?', 120, 40);
    }
    
    drawSpeaking() {
        const ctx = this.ctx;
        const centerX = 80;
        const centerY = 90;
        
        ctx.fillStyle = '#000';
        ctx.beginPath();
        ctx.ellipse(centerX, centerY, 35, 40, 0, 0, Math.PI * 2);
        ctx.fill();
        
        ctx.beginPath();
        ctx.arc(centerX, centerY - 35, 30, 0, Math.PI * 2);
        ctx.fill();
        
        this.drawEars(centerX, centerY - 35, 0);
        this.drawEyes(centerX, centerY - 35, 1);
        
        this.mouthOpen = Math.abs(Math.sin(Date.now() / 100));
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(centerX, centerY - 30, 8, 0, Math.PI * this.mouthOpen);
        ctx.stroke();
        
        this.drawSoundWaves(centerX + 40, centerY - 35);
    }
    
    drawCelebrating() {
        const ctx = this.ctx;
        const centerX = 80;
        const bounce = Math.abs(Math.sin(Date.now() / 200)) * 10;
        const centerY = 80 - bounce;
        
        ctx.fillStyle = '#000';
        ctx.beginPath();
        ctx.ellipse(centerX, centerY, 35, 40, 0, 0, Math.PI * 2);
        ctx.fill();
        
        ctx.beginPath();
        ctx.arc(centerX, centerY - 35, 30, 0, Math.PI * 2);
        ctx.fill();
        
        this.drawEars(centerX, centerY - 35, Math.PI / 8);
        
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(centerX - 10, centerY - 40, 5, 0, Math.PI);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(centerX + 10, centerY - 40, 5, 0, Math.PI);
        ctx.stroke();
        
        this.updateSparkles();
        this.drawSparkles();
        
        this.drawTail(centerX + 30, centerY + 20, Math.sin(Date.now() / 100) * 0.5);
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
        
        ctx.save();
        ctx.translate(x - 20, y - 25);
        ctx.rotate(-Math.PI / 4 + angle);
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(-10, -20);
        ctx.lineTo(10, -15);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
        
        ctx.save();
        ctx.translate(x + 20, y - 25);
        ctx.rotate(Math.PI / 4 - angle);
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(10, -20);
        ctx.lineTo(-10, -15);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    }
    
    drawEyes(x, y, open = 1, scale = 1) {
        const ctx = this.ctx;
        ctx.fillStyle = open > 0 ? '#FFD700' : '#000';
        
        ctx.beginPath();
        ctx.ellipse(x - 10, y - 5, 4 * scale, 6 * open, 0, 0, Math.PI * 2);
        ctx.fill();
        
        ctx.beginPath();
        ctx.ellipse(x + 10, y - 5, 4 * scale, 6 * open, 0, 0, Math.PI * 2);
        ctx.fill();
    }
    
    drawTail(x, y, angle) {
        const ctx = this.ctx;
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 8;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.quadraticCurveTo(x + 20, y - 20 + angle * 20, x + 30, y - 10);
        ctx.stroke();
    }
    
    drawSoundWaves(x, y) {
        const ctx = this.ctx;
        ctx.strokeStyle = 'rgba(102, 126, 234, 0.6)';
        ctx.lineWidth = 2;
        
        for (let i = 0; i < 3; i++) {
            const offset = (Date.now() / 200 + i * 0.5) % 2;
            ctx.beginPath();
            ctx.arc(x, y, 10 + offset * 10, 0, Math.PI * 2);
            ctx.stroke();
        }
    }
    
    updateSparkles() {
        if (this.sparkles.length < 10 && Math.random() > 0.7) {
            this.sparkles.push({
                x: 80 + (Math.random() - 0.5) * 60,
                y: 50 + (Math.random() - 0.5) * 60,
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
            ctx.arc(s.x, s.y, 3, 0, Math.PI * 2);
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

