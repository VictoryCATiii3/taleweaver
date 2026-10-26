from types import SimpleNamespace

from backend.api.routes.adventures.logic import SESSION_MANIFEST_SNAPSHOT_KEY
from backend.api.routes.adventures.session_sequence_label import active_sequence_title

SEQUENCES = [
    {"id": "seq_2", "title": "The Descent", "order": 2},
    {"id": "seq_1", "title": "Arrival", "order": 1},
]


def _state(active_sequence_id=None, entity_states=None):
    return SimpleNamespace(active_sequence_id=active_sequence_id, entity_states=entity_states or {})


def test_returns_title_of_active_sequence():
    # Arrange
    template = SimpleNamespace(sequences=SEQUENCES)

    # Act
    title = active_sequence_title(template, _state("seq_2"))

    # Assert
    assert title == "The Descent"


def test_falls_back_to_first_ordered_sequence_when_id_unknown():
    # Arrange
    template = SimpleNamespace(sequences=SEQUENCES)

    # Act
    title = active_sequence_title(template, _state("missing"))

    # Assert
    assert title == "Arrival"


def test_uses_manifest_snapshot_when_template_is_gone():
    # Arrange
    state = _state(
        "seq_1", {SESSION_MANIFEST_SNAPSHOT_KEY: {"adventure": {"sequences": SEQUENCES}}}
    )

    # Act
    title = active_sequence_title(None, state)

    # Assert
    assert title == "Arrival"


def test_returns_none_without_state_or_sequences():
    # Arrange
    template = SimpleNamespace(sequences=[])

    # Act / Assert
    assert active_sequence_title(template, None) is None
    assert active_sequence_title(template, _state("seq_1")) is None
