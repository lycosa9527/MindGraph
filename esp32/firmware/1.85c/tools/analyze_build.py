# SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

"""Generate a reproducible System Super build report inside an IDF build directory."""

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


REPORT_JSON = "brookesia_build_analysis.json"
REPORT_MARKDOWN = "brookesia_build_analysis.md"
CONFIGURATION_KEYS = (
    "BROOKESIA_CXX_JOBS",
    "BROOKESIA_FAST_COMPILE",
    "BROOKESIA_COMPILE_TUNING_INCLUDE_ESP_BOOST",
    "BROOKESIA_SUPER_CXX_JOBS",
    "BROOKESIA_SUPER_FAST_COMPILE",
    "CCACHE_ENABLE",
)


def load_json(path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def read_cache(build_dir):
    result = {}
    cache_path = build_dir / "CMakeCache.txt"
    if not cache_path.is_file():
        return result

    for line in cache_path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"([^#/:][^:]*)[^=]*=(.*)", line)
        if match and match.group(1) in CONFIGURATION_KEYS:
            result[match.group(1)] = match.group(2)
    return result


def component_from_output(output):
    normalized = output.replace("\\", "/")
    match = re.search(r"(?:^|/)esp-idf/([^/]+)/", normalized)
    return match.group(1) if match else "project/other"


def read_compile_database(build_dir):
    compile_path = build_dir / "compile_commands.json"
    if not compile_path.is_file():
        return {"total": 0, "languages": {}, "components": []}

    commands = load_json(compile_path)
    languages = Counter()
    components = defaultdict(Counter)
    for command in commands:
        source = str(command.get("file", "")).lower()
        suffix = Path(source).suffix
        if suffix in (".cc", ".cpp", ".cxx"):
            language = "C++"
        elif suffix == ".c":
            language = "C"
        elif suffix in (".s", ".asm"):
            language = "Assembly"
        else:
            language = "Other"
        component = component_from_output(str(command.get("output", "")))
        languages[language] += 1
        components[component][language] += 1

    component_rows = []
    for component, counts in components.items():
        row = {"component": component, "total": sum(counts.values())}
        row.update(dict(sorted(counts.items())))
        component_rows.append(row)
    component_rows.sort(key=lambda item: (-item["total"], item["component"]))
    return {
        "total": len(commands),
        "languages": dict(sorted(languages.items())),
        "components": component_rows,
    }


def read_ninja_log(build_dir):
    log_path = build_dir / ".ninja_log"
    if not log_path.is_file():
        return {"edge_count": 0, "components": [], "slowest_edges": []}

    latest_outputs = {}
    with log_path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 4:
                continue
            try:
                start_ms = int(fields[0])
                end_ms = int(fields[1])
            except ValueError:
                continue
            output = fields[3]
            latest_outputs[output] = max(0, end_ms - start_ms)

    component_durations = defaultdict(lambda: {"edge_count": 0, "duration_ms": 0})
    slowest_edges = []
    for output, duration_ms in latest_outputs.items():
        component = component_from_output(output)
        component_durations[component]["edge_count"] += 1
        component_durations[component]["duration_ms"] += duration_ms
        slowest_edges.append({
            "output": output,
            "component": component,
            "duration_ms": duration_ms,
        })

    component_rows = []
    for component, values in component_durations.items():
        row = {"component": component}
        row.update(values)
        component_rows.append(row)
    component_rows.sort(key=lambda item: (-item["duration_ms"], item["component"]))
    slowest_edges.sort(key=lambda item: (-item["duration_ms"], item["output"]))
    return {
        "edge_count": len(latest_outputs),
        "components": component_rows,
        "slowest_edges": slowest_edges[:20],
    }


def count_boost_consumers(build_dir):
    if not shutil.which("ninja") or not (build_dir / "build.ninja").is_file():
        return None

    process = subprocess.Popen(
        ["ninja", "-C", str(build_dir), "-t", "deps"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        errors="replace",
    )
    object_count = 0
    current_output = None
    current_uses_boost = False
    assert process.stdout is not None
    for line in process.stdout:
        if line and not line[0].isspace():
            if current_output and current_uses_boost:
                object_count += 1
            current_output = line.split(":", 1)[0]
            current_uses_boost = False
        elif "espressif__esp-boost" in line:
            current_uses_boost = True
    if current_output and current_uses_boost:
        object_count += 1
    return_code = process.wait()
    return object_count if return_code == 0 else None


def markdown_table(headers, rows):
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def write_markdown(path, report):
    project = report["project"]
    cache = report["configuration"]
    compile_data = report["translation_units"]
    timing = report["ninja_log"]

    lines = [
        "# ESP-Brookesia System Super Build Analysis",
        "",
        f"- Project: `{project['name']}`",
        f"- Target: `{project['target']}`",
        f"- Build components: {project['build_component_count']}",
        f"- Translation units: {compile_data['total']}",
        f"- Translation units including esp-boost headers: "
        f"{report['esp_boost_consumer_count'] if report['esp_boost_consumer_count'] is not None else 'unavailable'}",
        "",
        "## Configuration",
        "",
    ]
    lines.append(markdown_table(
        ["Option", "Value"],
        [[key, cache.get(key, "unknown")] for key in CONFIGURATION_KEYS],
    ))
    lines.extend(["", "## Translation Units", ""])
    lines.append(markdown_table(
        ["Language", "Count"],
        [[name, count] for name, count in compile_data["languages"].items()],
    ))
    lines.extend(["", "### Largest Components by Translation Units", ""])
    lines.append(markdown_table(
        ["Component", "Total", "C++", "C"],
        [[row["component"], row["total"], row.get("C++", 0), row.get("C", 0)]
         for row in compile_data["components"][:20]],
    ))
    lines.extend([
        "",
        "## Ninja Edge Durations",
        "",
        "Durations are accumulated CPU-facing edge times from the latest `.ninja_log` "
        "entry for each output. They are not wall-clock build time because Ninja runs edges in parallel.",
        "",
    ])
    lines.append(markdown_table(
        ["Component", "Edges", "Accumulated ms"],
        [[row["component"], row["edge_count"], row["duration_ms"]]
         for row in timing["components"][:20]],
    ))
    lines.extend(["", "### Slowest Edges", ""])
    lines.append(markdown_table(
        ["Duration ms", "Component", "Output"],
        [[row["duration_ms"], row["component"], f"`{row['output']}`"]
         for row in timing["slowest_edges"]],
    ))
    lines.extend([
        "",
        f"The machine-readable report is `{REPORT_JSON}` in the same build directory.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_dir", type=Path, help="configured ESP-IDF build directory")
    parser.add_argument(
        "--skip-deps",
        action="store_true",
        help="do not query Ninja dependencies for esp-boost header consumers",
    )
    args = parser.parse_args()
    build_dir = args.build_dir.expanduser().resolve()
    description_path = build_dir / "project_description.json"
    if not build_dir.is_dir() or not description_path.is_file():
        parser.error(f"not a configured ESP-IDF build directory: {build_dir}")

    description = load_json(description_path)
    report = {
        "project": {
            "name": description.get("project_name", "unknown"),
            "target": description.get("target", "unknown"),
            "build_dir": str(build_dir),
            "config_defaults": description.get("config_defaults", ""),
            "build_component_count": len(description.get("build_components", [])),
        },
        "configuration": read_cache(build_dir),
        "translation_units": read_compile_database(build_dir),
        "ninja_log": read_ninja_log(build_dir),
        "esp_boost_consumer_count": (
            None if args.skip_deps else count_boost_consumers(build_dir)
        ),
    }

    json_path = build_dir / REPORT_JSON
    markdown_path = build_dir / REPORT_MARKDOWN
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(markdown_path, report)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
