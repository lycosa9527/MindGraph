#!/usr/bin/env python3
"""
Combine all prompts and extract agent responses to malfunctioned prompts.
"""

import re
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def parse_log_line(line):
    """Parse a log line and extract timestamp, level, component, and message."""
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

def extract_all_prompts_with_responses(log_file):
    """Extract all prompts and their agent responses."""
    all_entries = []

    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        entry = None

        # Extract unclear prompts with responses
        if "LLM explicitly returned 'unclear' for prompt:" in line:
            match = re.search(r"for prompt: '([^']+)'", line)
            if match:
                prompt = match.group(1)
                parsed = parse_log_line(line)

                # Look for agent response in nearby lines
                response = None
                clarity = None
                error_type = None

                # Check current and next few lines for responses
                for j in range(i, min(i + 10, len(lines))):
                    if "clarity:" in lines[j]:
                        clarity_match = re.search(r"clarity: (\w+)", lines[j])
                        if clarity_match:
                            clarity = clarity_match.group(1)
                    if "Prompt is too complex or unclear" in lines[j]:
                        error_type = "too_complex_or_unclear"
                    if "Unable to understand the request" in lines[j]:
                        error_type = "unable_to_understand"
                    if "Diagram generation failed" in lines[j]:
                        error_match = re.search(r"failed \| Error: (.+)", lines[j])
                        if error_match:
                            response = error_match.group(1)

                entry = {
                    'type': 'unclear_prompt',
                    'prompt': prompt,
                    'timestamp': parsed['time'] if parsed else None,
                    'request_id': parsed['request_id'] if parsed else None,
                    'clarity': clarity,
                    'error_type': error_type,
                    'agent_response': response or "Unable to understand the request",
                    'line': i + 1,
                    'file': log_file.name
                }

        # Extract GenerateDingTalk prompts (successful)
        elif "[GenerateDingTalk] Request: prompt=" in line:
            match = re.search(r"prompt='([^']+)'", line)
            if match:
                prompt = match.group(1)
                parsed = parse_log_line(line)

                # Check if it succeeded
                success = False
                for j in range(i, min(i + 5, len(lines))):
                    if "[GenerateDingTalk] Success:" in lines[j]:
                        success = True
                        break

                entry = {
                    'type': 'teacher_prompt',
                    'prompt': prompt,
                    'timestamp': parsed['time'] if parsed else None,
                    'request_id': parsed['request_id'] if parsed else None,
                    'status': 'success' if success else 'unknown',
                    'agent_response': 'Successfully generated diagram' if success else 'Unknown',
                    'line': i + 1,
                    'file': log_file.name,
                    'source': 'GenerateDingTalk'
                }

        # Extract topic extraction (successful prompts)
        elif "Topic extraction completed" in line:
            match = re.search(r"completed in [\d.]+s: '([^']+)'", line)
            if match:
                topic = match.group(1)
                parsed = parse_log_line(line)

                # Find original prompt
                original_prompt = None
                for j in range(max(0, i - 20), i):
                    if "for prompt:" in lines[j]:
                        prompt_match = re.search(r"for prompt: '([^']+)'", lines[j])
                        if prompt_match:
                            original_prompt = prompt_match.group(1)
                            break

                # Check diagram type
                diagram_type = None
                for j in range(max(0, i - 10), i):
                    if "Diagram type detection completed" in lines[j]:
                        type_match = re.search(r"completed in [\d.]+s: (\w+)", lines[j])
                        if type_match:
                            diagram_type = type_match.group(1)
                            break

                entry = {
                    'type': 'teacher_prompt',
                    'prompt': original_prompt or topic,
                    'extracted_topic': topic,
                    'timestamp': parsed['time'] if parsed else None,
                    'request_id': parsed['request_id'] if parsed else None,
                    'diagram_type': diagram_type,
                    'status': 'success',
                    'agent_response': f'Successfully extracted topic: {topic}' + (f', diagram type: {diagram_type}' if diagram_type else ''),
                    'line': i + 1,
                    'file': log_file.name
                }

        if entry:
            all_entries.append(entry)

    return all_entries

def main():
    log_dir = Path(r"C:\Users\roywa\Desktop\logs")
    output_dir = Path(r"C:\Users\roywa\Desktop\MG\extracted_prompts")
    output_dir.mkdir(exist_ok=True)

    all_entries = []

    log_files = sorted(log_dir.glob("app.*.log"))

    print(f"Processing {len(log_files)} log files...")

    for log_file in log_files:
        print(f"Processing {log_file.name}...")
        entries = extract_all_prompts_with_responses(log_file)
        all_entries.extend(entries)

    # Separate by type
    teacher_prompts = [e for e in all_entries if e['type'] == 'teacher_prompt']
    unclear_prompts = [e for e in all_entries if e['type'] == 'unclear_prompt']

    # Remove duplicates (same prompt, same file, similar timestamp)
    seen = set()
    unique_entries = []
    for entry in all_entries:
        key = (entry['prompt'], entry['file'], entry.get('timestamp', ''))
        if key not in seen:
            seen.add(key)
            unique_entries.append(entry)

    # Sort by timestamp
    unique_entries.sort(key=lambda x: (x.get('file', ''), x.get('timestamp', '')))

    # Save combined file
    with open(output_dir / "all_prompts_with_responses.txt", 'w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write("ALL PROMPTS WITH AGENT RESPONSES\n")
        f.write("=" * 100 + "\n\n")

        f.write(f"Total Entries: {len(unique_entries)}\n")
        f.write(f"  - Teacher Prompts (Successful): {len(teacher_prompts)}\n")
        f.write(f"  - Unclear Prompts (Failed): {len(unclear_prompts)}\n\n")
        f.write("=" * 100 + "\n\n")

        # Write all entries
        for entry in unique_entries:
            f.write(f"TYPE: {entry['type'].upper()}\n")
            f.write(f"PROMPT: {entry['prompt']}\n")

            if 'extracted_topic' in entry:
                f.write(f"EXTRACTED TOPIC: {entry['extracted_topic']}\n")
            if 'diagram_type' in entry and entry['diagram_type']:
                f.write(f"DIAGRAM TYPE: {entry['diagram_type']}\n")
            if 'clarity' in entry and entry['clarity']:
                f.write(f"CLARITY LEVEL: {entry['clarity']}\n")
            if 'error_type' in entry and entry['error_type']:
                f.write(f"ERROR TYPE: {entry['error_type']}\n")

            f.write(f"AGENT RESPONSE: {entry['agent_response']}\n")
            f.write(f"STATUS: {entry.get('status', 'unknown')}\n")
            f.write(f"TIMESTAMP: {entry['timestamp']}\n")
            f.write(f"REQUEST ID: {entry['request_id']}\n")
            f.write(f"FILE: {entry['file']}, LINE: {entry['line']}\n")
            if 'source' in entry:
                f.write(f"SOURCE: {entry['source']}\n")
            f.write("-" * 100 + "\n\n")

    # Save JSON
    results = {
        'summary': {
            'total_entries': len(unique_entries),
            'teacher_prompts': len(teacher_prompts),
            'unclear_prompts': len(unclear_prompts),
            'extraction_date': datetime.now().isoformat()
        },
        'all_prompts': unique_entries
    }

    json_file = output_dir / "all_prompts_with_responses.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Create summary of agent responses
    response_summary = defaultdict(int)
    for entry in unclear_prompts:
        response_summary[entry['agent_response']] += 1

    with open(output_dir / "agent_responses_summary.txt", 'w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write("AGENT RESPONSES TO MALFUNCTIONED PROMPTS\n")
        f.write("=" * 100 + "\n\n")

        f.write(f"Total Unclear Prompts: {len(unclear_prompts)}\n\n")
        f.write("Response Types:\n")
        f.write("-" * 100 + "\n")
        for response, count in sorted(response_summary.items(), key=lambda x: -x[1]):
            f.write(f"{response}: {count}\n")

        f.write("\n" + "=" * 100 + "\n")
        f.write("DETAILED BREAKDOWN\n")
        f.write("=" * 100 + "\n\n")

        for entry in unclear_prompts:
            f.write(f"PROMPT: {entry['prompt']}\n")
            f.write(f"AGENT RESPONSE: {entry['agent_response']}\n")
            if entry.get('clarity'):
                f.write(f"CLARITY: {entry['clarity']}\n")
            if entry.get('error_type'):
                f.write(f"ERROR TYPE: {entry['error_type']}\n")
            f.write(f"TIMESTAMP: {entry['timestamp']}\n")
            f.write(f"FILE: {entry['file']}\n")
            f.write("-" * 100 + "\n\n")

    print("\n" + "=" * 100)
    print("EXTRACTION SUMMARY")
    print("=" * 100)
    print(f"Total entries: {len(unique_entries)}")
    print(f"  - Teacher prompts (successful): {len(teacher_prompts)}")
    print(f"  - Unclear prompts (failed): {len(unclear_prompts)}")
    print(f"\nResults saved to: {output_dir}")
    print("  - all_prompts_with_responses.txt (combined file)")
    print("  - all_prompts_with_responses.json (JSON format)")
    print("  - agent_responses_summary.txt (agent response analysis)")

if __name__ == "__main__":
    main()






