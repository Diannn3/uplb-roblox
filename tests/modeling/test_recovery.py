from tools.modeling.registry import load_registry
from tools.modeling.source_recovery import build_recovery_queue


def test_recovery_queue_puts_priority_a_first() -> None:
    registry = load_registry()
    queue = build_recovery_queue(registry.buildings, registry.sources)
    assert queue
    assert queue[0].priority == "A"
    assert any(row.action == "request-2014-original-model" for row in queue)
    assert any(row.action == "request-scan-license-and-original" for row in queue)
