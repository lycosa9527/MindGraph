/**
 * PCM Audio Processor Worklet
 * Captures audio from microphone and converts to PCM16 format
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * @author WANG CUNCHI
 */

class PCMProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.isRecording = true;
        
        // Listen for stop message
        this.port.onmessage = (event) => {
            if (event.data.command === 'stop') {
                this.isRecording = false;
            }
        };
    }
    
    process(inputs, outputs, parameters) {
        // If not recording, stop processing
        if (!this.isRecording) {
            return false;
        }
        
        const input = inputs[0];
        
        // Check if we have input data
        if (input && input.length > 0 && input[0].length > 0) {
            const inputData = input[0]; // First channel (mono)
            
            // Convert Float32 to Int16
            const pcm16 = new Int16Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
                const s = Math.max(-1, Math.min(1, inputData[i]));
                pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            
            // Send PCM data to main thread
            this.port.postMessage({
                type: 'audio',
                data: pcm16.buffer
            }, [pcm16.buffer]); // Transfer ownership for performance
        }
        
        // Return true to keep processor alive
        return true;
    }
}

registerProcessor('pcm-processor', PCMProcessor);


