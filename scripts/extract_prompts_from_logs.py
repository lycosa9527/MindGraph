#!/usr/bin/env python3
"""
Extract teacher prompts, diagram agent prompts, and unclear intention cases from log files.
"""

import re
import json
from pathlib import Path
from datetime import datetime

def parse_log_line(line):
    """Parse a log line and extract timestamp, level, component, and message."""
    # Pattern: [HH:MM:SS] LEVEL | COMP | [ID] message
    # Example: [08:02:35] [32mINFO [0m | AGNT | [1128770] Diagram type detection completed...
    pattern = r'\[(\d{2}:\d{2}:\d{2})\]\s+.*?(\w+)\s+\|\s+(\w+)\s+\|\s+(?:\[(\d+)\]\s+)?(.+)'
    match = re.match(pattern, line)
    if match:
        time_str, level, comp, req_id, message = match.groups()
        return {
            'time': time_str,
            'level': level,
            'component': comp,
            'request_id': req_id,
            'message': message
        }
    return None

def extract_teacher_prompts(log_file):
    """Extract teacher prompts from log file."""
    teacher_prompts = []
    unclear_prompts = []
    original_prompts = []  # From GenerateDingTalk logs

    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        for line_num, line in enumerate(lines, 1):
            # Extract prompts from GenerateDingTalk logs (these are original teacher prompts)
            if "[GenerateDingTalk] Request: prompt=" in line:
                match = re.search(r"prompt='([^']+)'", line)
                if match:
                    prompt = match.group(1)
                    parsed = parse_log_line(line)
                    original_prompts.append({
                        'prompt': prompt,
                        'timestamp': parsed['time'] if parsed else None,
                        'request_id': parsed['request_id'] if parsed else None,
                        'line': line_num,
                        'file': log_file.name,
                        'source': 'GenerateDingTalk'
                    })

            # Extract prompts marked as unclear
            if "LLM explicitly returned 'unclear' for prompt:" in line:
                match = re.search(r"for prompt: '([^']+)'", line)
                if match:
                    prompt = match.group(1)
                    parsed = parse_log_line(line)
                    unclear_prompts.append({
                        'prompt': prompt,
                        'timestamp': parsed['time'] if parsed else None,
                        'request_id': parsed['request_id'] if parsed else None,
                        'line': line_num,
                        'file': log_file.name
                    })

            # Extract "Prompt is too complex or unclear"
            if "Prompt is too complex or unclear:" in line:
                match = re.search(r"unclear: '([^']+)'", line)
                if match:
                    prompt = match.group(1)
                    parsed = parse_log_line(line)
                    unclear_prompts.append({
                        'prompt': prompt,
                        'timestamp': parsed['time'] if parsed else None,
                        'request_id': parsed['request_id'] if parsed else None,
                        'line': line_num,
                        'file': log_file.name,
                        'type': 'too_complex'
                    })

            # Extract successful topic extraction (these are teacher prompts that worked)
            if "Topic extraction completed" in line:
                match = re.search(r"completed in [\d.]+s: '([^']+)'", line)
                if match:
                    topic = match.group(1)
                    parsed = parse_log_line(line)
                    # Try to find the original prompt in previous lines
                    original_prompt = None
                    for j in range(max(0, line_num - 20), line_num):
                        if "for prompt:" in lines[j]:
                            prompt_match = re.search(r"for prompt: '([^']+)'", lines[j])
                            if prompt_match:
                                original_prompt = prompt_match.group(1)
                                break

                    teacher_prompts.append({
                        'topic': topic,
                        'original_prompt': original_prompt,
                        'timestamp': parsed['time'] if parsed else None,
                        'request_id': parsed['request_id'] if parsed else None,
                        'line': line_num,
                        'file': log_file.name
                    })

    # Combine original prompts with teacher prompts
    all_teacher_prompts = teacher_prompts + original_prompts

    return all_teacher_prompts, unclear_prompts

def extract_diagram_agent_prompts(log_file):
    """Extract prompts sent to diagram agents."""
    diagram_prompts = []

    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            # Look for diagram generation started
            if "[AutoComplete] Started:" in line:
                match = re.search(r"Started: User (\d+), Diagram: (\w+), Model: (\w+)", line)
                if match:
                    user_id, diagram_type, model = match.groups()
                    parsed = parse_log_line(line)
                    # Try to find the prompt in nearby lines
                    prompt = None
                    for j in range(max(0, i-20), i):
                        if "for prompt:" in lines[j] or "Topic extraction completed" in lines[j]:
                            prompt_match = re.search(r": '([^']+)'", lines[j])
                            if prompt_match:
                                prompt = prompt_match.group(1)
                                break

                    diagram_prompts.append({
                        'user_id': user_id,
                        'diagram_type': diagram_type,
                        'model': model,
                        'prompt': prompt,
                        'timestamp': parsed['time'] if parsed else None,
                        'request_id': parsed['request_id'] if parsed else None,
                        'line': i + 1,
                        'file': log_file.name
                    })

    return diagram_prompts

def extract_unclear_intentions(log_file):
    """Extract cases where agent cannot understand teacher's intention."""
    unclear_cases = []

    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            # Look for "Unable to understand the request"
            if "Unable to understand the request" in line:
                parsed = parse_log_line(line)
                # Find the prompt that caused this error
                prompt = None
                # Read previous lines to find the prompt
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f2:
                    all_lines = f2.readlines()
                    for j in range(max(0, line_num - 30), line_num):
                        if "for prompt:" in all_lines[j]:
                            match = re.search(r"for prompt: '([^']+)'", all_lines[j])
                            if match:
                                prompt = match.group(1)
                                break

                unclear_cases.append({
                    'prompt': prompt,
                    'timestamp': parsed['time'] if parsed else None,
                    'request_id': parsed['request_id'] if parsed else None,
                    'line': line_num,
                    'file': log_file.name,
                    'error': 'Unable to understand the request'
                })

            # Look for clarity: very_unclear
            if "clarity: very_unclear" in line:
                parsed = parse_log_line(line)
                # Find the prompt
                prompt = None
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f2:
                    all_lines = f2.readlines()
                    for j in range(max(0, line_num - 10), line_num):
                        if "for prompt:" in all_lines[j]:
                            match = re.search(r"for prompt: '([^']+)'", all_lines[j])
                            if match:
                                prompt = match.group(1)
                                break

                unclear_cases.append({
                    'prompt': prompt,
                    'timestamp': parsed['time'] if parsed else None,
                    'request_id': parsed['request_id'] if parsed else None,
                    'line': line_num,
                    'file': log_file.name,
                    'error': 'very_unclear'
                })

    return unclear_cases

def main():
    log_dir = Path(r"C:\Users\roywa\Desktop\logs")
    output_dir = Path(r"C:\Users\roywa\Desktop\MG\extracted_prompts")
    output_dir.mkdir(exist_ok=True)

    all_teacher_prompts = []
    all_unclear_prompts = []
    all_diagram_prompts = []
    all_unclear_intentions = []

    log_files = sorted(log_dir.glob("app.*.log"))

    print(f"Processing {len(log_files)} log files...")

    for log_file in log_files:
        print(f"Processing {log_file.name}...")
        teacher_prompts, unclear_prompts = extract_teacher_prompts(log_file)
        diagram_prompts = extract_diagram_agent_prompts(log_file)
        unclear_intentions = extract_unclear_intentions(log_file)

        all_teacher_prompts.extend(teacher_prompts)
        all_unclear_prompts.extend(unclear_prompts)
        all_diagram_prompts.extend(diagram_prompts)
        all_unclear_intentions.extend(unclear_intentions)

    # Remove duplicates from unclear prompts (same prompt, same file)
    seen_unclear = set()
    unique_unclear = []
    for item in all_unclear_prompts:
        key = (item['prompt'], item['file'])
        if key not in seen_unclear:
            seen_unclear.add(key)
            unique_unclear.append(item)

    # Remove duplicates from unclear intentions
    seen_intentions = set()
    unique_intentions = []
    for item in all_unclear_intentions:
        if item['prompt']:
            key = (item['prompt'], item['file'])
            if key not in seen_intentions:
                seen_intentions.add(key)
                unique_intentions.append(item)

    # Save results
    results = {
        'summary': {
            'total_teacher_prompts': len(all_teacher_prompts),
            'total_unclear_prompts': len(unique_unclear),
            'total_diagram_prompts': len(all_diagram_prompts),
            'total_unclear_intentions': len(unique_intentions),
            'extraction_date': datetime.now().isoformat()
        },
        'teacher_prompts': all_teacher_prompts,
        'unclear_prompts': unique_unclear,
        'diagram_agent_prompts': all_diagram_prompts,
        'unclear_intentions': unique_intentions
    }

    # Save as JSON
    json_file = output_dir / "extracted_prompts.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Save as plain text files
    with open(output_dir / "teacher_prompts.txt", 'w', encoding='utf-8') as f:
        f.write("=== TEACHER PROMPTS ===\n\n")
        for item in all_teacher_prompts:
            if 'prompt' in item:
                f.write(f"Prompt: {item['prompt']}\n")
            if 'topic' in item:
                f.write(f"Topic: {item['topic']}\n")
            if 'original_prompt' in item and item['original_prompt']:
                f.write(f"Original Prompt: {item['original_prompt']}\n")
            f.write(f"Time: {item['timestamp']}\n")
            f.write(f"Request ID: {item['request_id']}\n")
            if 'source' in item:
                f.write(f"Source: {item['source']}\n")
            f.write(f"File: {item['file']}, Line: {item['line']}\n")
            f.write("-" * 80 + "\n\n")

    with open(output_dir / "unclear_prompts.txt", 'w', encoding='utf-8') as f:
        f.write("=== UNCLEAR PROMPTS (Agent Could Not Understand) ===\n\n")
        for item in unique_unclear:
            f.write(f"Prompt: {item['prompt']}\n")
            f.write(f"Time: {item['timestamp']}\n")
            f.write(f"Request ID: {item['request_id']}\n")
            f.write(f"File: {item['file']}, Line: {item['line']}\n")
            if 'type' in item:
                f.write(f"Type: {item['type']}\n")
            f.write("-" * 80 + "\n\n")

    with open(output_dir / "diagram_agent_prompts.txt", 'w', encoding='utf-8') as f:
        f.write("=== DIAGRAM AGENT PROMPTS ===\n\n")
        for item in all_diagram_prompts:
            f.write(f"User ID: {item['user_id']}\n")
            f.write(f"Diagram Type: {item['diagram_type']}\n")
            f.write(f"Model: {item['model']}\n")
            if item['prompt']:
                f.write(f"Prompt/Topic: {item['prompt']}\n")
            f.write(f"Time: {item['timestamp']}\n")
            f.write(f"Request ID: {item['request_id']}\n")
            f.write(f"File: {item['file']}, Line: {item['line']}\n")
            f.write("-" * 80 + "\n\n")

    with open(output_dir / "unclear_intentions.txt", 'w', encoding='utf-8') as f:
        f.write("=== UNCLEAR INTENTIONS (Agent Cannot Get Teacher's Intention) ===\n\n")
        for item in unique_intentions:
            if item['prompt']:
                f.write(f"Prompt: {item['prompt']}\n")
            f.write(f"Error Type: {item['error']}\n")
            f.write(f"Time: {item['timestamp']}\n")
            f.write(f"Request ID: {item['request_id']}\n")
            f.write(f"File: {item['file']}, Line: {item['line']}\n")
            f.write("-" * 80 + "\n\n")

    # Print summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    print(f"Total teacher prompts (with topic extraction): {len(all_teacher_prompts)}")
    print(f"Total unclear prompts: {len(unique_unclear)}")
    print(f"Total diagram agent prompts: {len(all_diagram_prompts)}")
    print(f"Total unclear intentions: {len(unique_intentions)}")
    print(f"\nResults saved to: {output_dir}")
    print("  - extracted_prompts.json (complete data)")
    print("  - teacher_prompts.txt")
    print("  - unclear_prompts.txt")
    print("  - diagram_agent_prompts.txt")
    print("  - unclear_intentions.txt")

if __name__ == "__main__":
    main()

