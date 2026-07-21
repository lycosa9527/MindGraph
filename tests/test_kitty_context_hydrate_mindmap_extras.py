"""Library hydrate must keep mindmap live-spec extras for loadFromSpec visuals."""

from services.kitty.infra.bootstrap.kitty_context_hydrate import diagram_data_from_saved_spec


def test_diagram_data_from_saved_spec_keeps_mindmap_extras() -> None:
    """Mindmap hydrate keeps style/theme/collapse extras and stable node uids."""
    spec = {
        "nodes": [
            {"id": "topic", "text": "中心主题", "type": "topic"},
            {
                "id": "branch-r-1-0",
                "text": "分支1",
                "type": "branch",
                "data": {
                    "mindMapUid": "uid-branch-1",
                    "estimatedWidth": 120,
                    "label": "分支1",
                },
            },
        ],
        "connections": [{"id": "c0", "source": "topic", "target": "branch-r-1-0"}],
        "_mindmap_diagram_style": "classic",
        "_mindmap_theme": "ocean",
        "_node_styles": {"branch-r-1-0": {"nodeShape": "rounded"}},
        "_collapsed_paths": ["r/0"],
        "_mindmap_canvas": {"v2": {"theme": "ocean"}},
    }

    diagram_data = diagram_data_from_saved_spec(spec, "mindmap")

    assert diagram_data["_mindmap_diagram_style"] == "classic"
    assert diagram_data["_mindmap_theme"] == "ocean"
    assert diagram_data["_node_styles"] == {"branch-r-1-0": {"nodeShape": "rounded"}}
    assert diagram_data["_collapsed_paths"] == ["r/0"]
    assert diagram_data["_mindmap_canvas"] == {"v2": {"theme": "ocean"}}
    assert diagram_data["nodes"][0]["id"] == "topic"
    branch = diagram_data["nodes"][1]
    assert branch["id"] == "branch-r-1-0"
    assert branch["data"] == {"mindMapUid": "uid-branch-1"}


def test_diagram_data_from_saved_spec_skips_extras_for_non_mindmap() -> None:
    """Non-mindmap diagrams do not inherit mindmap live-spec extras."""
    spec = {
        "nodes": [{"id": "topic", "text": "T", "type": "topic"}],
        "_mindmap_diagram_style": "classic",
    }
    diagram_data = diagram_data_from_saved_spec(spec, "circle_map")
    assert "_mindmap_diagram_style" not in diagram_data
