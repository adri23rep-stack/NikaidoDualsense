from src.edit_history import SnapshotHistory


def test_snapshot_history_undo_redo_and_deduplication():
    history = SnapshotHistory(limit=3)
    history.reset({"value": 1})
    assert history.push({"value": 1}) is False
    assert history.push({"value": 2}) is True
    assert history.push({"value": 3}) is True
    assert history.can_undo is True
    assert history.undo() == {"value": 2}
    assert history.undo() == {"value": 1}
    assert history.can_undo is False
    assert history.redo() == {"value": 2}


def test_snapshot_history_discards_redo_after_new_edit_and_respects_limit():
    history = SnapshotHistory(limit=2)
    history.reset(0)
    history.push(1)
    history.push(2)
    history.push(3)
    assert history.undo() == 2
    history.push(9)
    assert history.can_redo is False
    assert history.undo() == 2
    assert history.undo() == 1
    assert history.undo() is None
