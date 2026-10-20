import time
from types import SimpleNamespace

from src.macro_engine import (
    Macro,
    MacroEngine,
    MacroStep,
    MacroTrigger,
    StepType,
    TriggerEdge,
    TriggerKind,
)


class FakeConnection:
    def __init__(self):
        self.callbacks = []

    def on_state_update(self, callback):
        self.callbacks.append(callback)

    def emit(self, **kwargs):
        state = SimpleNamespace(
            buttons=kwargs.get("buttons", {}),
            left_stick_x=kwargs.get("left_stick_x", 128),
            left_stick_y=kwargs.get("left_stick_y", 128),
            right_stick_x=kwargs.get("right_stick_x", 128),
            right_stick_y=kwargs.get("right_stick_y", 128),
            left_trigger=kwargs.get("left_trigger", 0),
            right_trigger=kwargs.get("right_trigger", 0),
        )
        for callback in list(self.callbacks):
            callback(state)


class FakeEmulator:
    def __init__(self):
        self.events = []

    def macro_press(self, button):
        self.events.append(("press", button))

    def macro_release(self, button):
        self.events.append(("release", button))

    def macro_set_stick(self, stick, x, y):
        self.events.append(("stick", stick, round(x, 2), round(y, 2)))

    def macro_clear_stick(self, stick):
        self.events.append(("clear_stick", stick))

    def macro_clear_sticks(self):
        self.events.append(("clear_sticks",))

    def macro_set_trigger(self, trigger, value):
        self.events.append(("trigger", trigger, value))

    def macro_clear_trigger(self, trigger):
        self.events.append(("clear_trigger", trigger))

    def macro_clear_triggers(self):
        self.events.append(("clear_triggers",))

    def macro_clear(self):
        self.events.append(("clear",))


def wait_until(predicate, timeout=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def build_engine():
    connection = FakeConnection()
    emulator = FakeEmulator()
    return MacroEngine(connection, emulator), connection, emulator


def test_old_trigger_button_is_migrated():
    macro = Macro.from_dict(
        {
            "id": "old",
            "name": "Vieja",
            "trigger_button": "square",
            "steps": [{"type": "press", "button": "cross"}],
        }
    )
    assert macro.trigger.kind == TriggerKind.BUTTON
    assert macro.trigger.buttons == ["square"]
    assert macro.trigger_button == "square"


def test_macro_roundtrip_keeps_analog_steps_and_profiles():
    macro = Macro(
        id="analog",
        name="Movimiento",
        trigger=MacroTrigger(
            kind=TriggerKind.STICK,
            stick="right",
            direction="up_right",
            threshold=0.7,
        ),
        profile_ids=["fps", "racing"],
        steps=[
            MacroStep(StepType.STICK, stick="left", x=0.5, y=-1.0, ms=120),
            MacroStep(StepType.TRIGGER, trigger="right", value=200, ms=90),
        ],
        cooldown_ms=400,
    )
    restored = Macro.from_dict(macro.to_dict())
    assert restored.trigger.kind == TriggerKind.STICK
    assert restored.trigger.direction == "up_right"
    assert restored.profile_ids == ["fps", "racing"]
    assert restored.steps[0].stick == "left"
    assert restored.steps[1].value == 200
    assert restored.cooldown_ms == 400


def test_combo_trigger_obeys_profile_and_only_fires_on_edge():
    engine, connection, emulator = build_engine()
    engine.save_macro(
        Macro(
            id="combo",
            name="Combo",
            trigger=MacroTrigger(kind=TriggerKind.COMBO, buttons=["L1", "square"]),
            profile_ids=["fps"],
            cooldown_ms=0,
            steps=[
                MacroStep(StepType.PRESS, button="cross"),
                MacroStep(StepType.RELEASE, button="cross"),
            ],
        )
    )

    engine.set_active_profile("racing")
    connection.emit(buttons={"L1": True, "square": True})
    time.sleep(0.02)
    assert not emulator.events

    connection.emit(buttons={})
    engine.set_active_profile("fps")
    connection.emit(buttons={"L1": True, "square": True})
    assert wait_until(lambda: ("press", "cross") in emulator.events)
    first_count = emulator.events.count(("press", "cross"))

    connection.emit(buttons={"L1": True, "square": True})
    time.sleep(0.02)
    assert emulator.events.count(("press", "cross")) == first_count

    connection.emit(buttons={})
    connection.emit(buttons={"L1": True, "square": True})
    assert wait_until(lambda: emulator.events.count(("press", "cross")) == first_count + 1)


def test_stick_direction_can_trigger_macro():
    engine, connection, emulator = build_engine()
    engine.set_active_profile("fps")
    engine.save_macro(
        Macro(
            id="flick",
            name="Flick",
            trigger=MacroTrigger(
                kind=TriggerKind.STICK, stick="right", direction="right", threshold=0.6
            ),
            steps=[
                MacroStep(StepType.PRESS, button="R1"),
                MacroStep(StepType.RELEASE, button="R1"),
            ],
            cooldown_ms=0,
        )
    )
    connection.emit(right_stick_x=220, right_stick_y=128)
    assert wait_until(lambda: ("press", "R1") in emulator.events)


def test_playback_applies_and_clears_sticks_and_triggers():
    engine, _connection, emulator = build_engine()
    engine.save_macro(
        Macro(
            id="analog",
            name="Analog",
            steps=[
                MacroStep(StepType.STICK, stick="left", x=1.0, y=-0.5, ms=5),
                MacroStep(StepType.TRIGGER, trigger="right", value=180, ms=5),
            ],
        )
    )
    assert engine.play_macro("analog")
    assert wait_until(lambda: not engine.is_playing("analog"))
    assert ("stick", "left", 1.0, -0.5) in emulator.events
    assert ("trigger", "right", 180) in emulator.events
    assert ("clear_stick", "left") in emulator.events
    assert ("clear_trigger", "right") in emulator.events


def test_duplicate_clears_trigger_but_keeps_steps():
    engine, _connection, _emulator = build_engine()
    engine.save_macro(
        Macro(
            id="base",
            name="Base",
            trigger=MacroTrigger(kind=TriggerKind.BUTTON, buttons=["circle"]),
            steps=[MacroStep(StepType.WAIT, ms=50)],
        )
    )
    duplicate = engine.duplicate_macro("base")
    assert duplicate is not None
    assert duplicate.id != "base"
    assert duplicate.name.endswith("copia")
    assert duplicate.trigger.kind == TriggerKind.MANUAL
    assert duplicate.steps[0].ms == 50


def test_recording_can_capture_stick_motion():
    engine, connection, _emulator = build_engine()
    engine.start_recording(include_sticks=True)
    connection.emit(right_stick_x=128, right_stick_y=128)
    time.sleep(engine.ANALOG_SAMPLE_SECONDS + 0.01)
    connection.emit(right_stick_x=255, right_stick_y=128)
    steps = engine.stop_recording()
    assert any(
        step.type == StepType.STICK and step.stick == "right" and step.x > 0.8 for step in steps
    )


def test_tap_step_and_action_delay_roundtrip():
    step = MacroStep(StepType.TAP, button="cross", ms=65, after_ms=90)
    restored = MacroStep.from_dict(step.to_dict())
    assert restored.type == StepType.TAP
    assert restored.ms == 65
    assert restored.after_ms == 90
    macro = Macro(id="timed", name="Timed", steps=[restored], repeat=2)
    assert macro.duration_ms() == 310


def test_legacy_delay_ms_is_migrated_to_after_ms():
    restored = MacroStep.from_dict(
        {
            "type": "press",
            "button": "square",
            "delay_ms": 125,
        }
    )
    assert restored.after_ms == 125


def test_timed_analog_actions_clear_before_next_button():
    engine, _connection, emulator = build_engine()
    engine.save_macro(
        Macro(
            id="timed_analog",
            name="Timed analog",
            steps=[
                MacroStep(StepType.STICK, stick="left", x=1.0, y=0.0, ms=5, after_ms=5),
                MacroStep(StepType.TRIGGER, trigger="right", value=220, ms=5, after_ms=5),
                MacroStep(StepType.TAP, button="cross", ms=5),
            ],
        )
    )
    assert engine.play_macro("timed_analog")
    assert wait_until(lambda: not engine.is_playing("timed_analog"))
    assert emulator.events.index(("clear_stick", "left")) < emulator.events.index(
        ("trigger", "right", 220)
    )
    assert emulator.events.index(("clear_trigger", "right")) < emulator.events.index(
        ("press", "cross")
    )
    assert ("release", "cross") in emulator.events


def test_analog_trigger_can_fire_when_released():
    engine, connection, emulator = build_engine()
    engine.set_active_profile("fps")
    engine.save_macro(
        Macro(
            id="l2_release",
            name="L2 release",
            trigger=MacroTrigger(
                kind=TriggerKind.TRIGGER,
                analog_trigger="left",
                threshold=0.5,
                edge=TriggerEdge.RELEASE,
            ),
            profile_ids=["fps"],
            cooldown_ms=0,
            steps=[MacroStep(StepType.TAP, button="circle", ms=1)],
        )
    )
    connection.emit(left_trigger=200)
    time.sleep(0.01)
    assert ("press", "circle") not in emulator.events
    connection.emit(left_trigger=0)
    assert wait_until(lambda: ("press", "circle") in emulator.events)


def test_while_held_trigger_can_repeat_after_macro_finishes():
    engine, connection, emulator = build_engine()
    engine.save_macro(
        Macro(
            id="rapid",
            name="Rapid",
            trigger=MacroTrigger(
                kind=TriggerKind.BUTTON,
                buttons=["R1"],
                edge=TriggerEdge.WHILE_HELD,
            ),
            cooldown_ms=0,
            steps=[MacroStep(StepType.TAP, button="cross", ms=2)],
        )
    )
    connection.emit(buttons={"R1": True})
    assert wait_until(lambda: emulator.events.count(("press", "cross")) >= 1)
    assert wait_until(lambda: not engine.is_playing("rapid"))
    connection.emit(buttons={"R1": True})
    assert wait_until(lambda: emulator.events.count(("press", "cross")) >= 2)


def test_recording_compacts_button_timing_and_captures_trigger():
    engine, connection, _emulator = build_engine()
    engine.start_recording(include_sticks=True)
    connection.emit(buttons={"square": True})
    time.sleep(0.02)
    connection.emit(buttons={})
    time.sleep(engine.ANALOG_SAMPLE_SECONDS + 0.01)
    connection.emit(right_trigger=180)
    steps = engine.stop_recording()
    press = next(step for step in steps if step.type == StepType.PRESS and step.button == "square")
    assert press.after_ms >= 10
    assert not any(step.type == StepType.WAIT for step in steps)
    assert any(
        step.type == StepType.TRIGGER and step.trigger == "right" and step.value == 180
        for step in steps
    )


def test_empty_trigger_object_still_uses_legacy_button():
    macro = Macro.from_dict(
        {
            "id": "legacy_empty",
            "name": "Legacy empty",
            "trigger": {},
            "trigger_button": "triangle",
            "steps": [{"type": "press", "button": "cross"}],
        }
    )
    assert macro.trigger.kind == TriggerKind.BUTTON
    assert macro.trigger.buttons == ["triangle"]


def test_playback_sleeps_for_duration_and_after_each_action():
    engine, _connection, emulator = build_engine()
    sleeps = []
    engine._sleep = lambda _cancel, milliseconds: sleeps.append(milliseconds) or True
    macro = Macro(
        id="sleep_order",
        name="Sleep order",
        steps=[
            MacroStep(StepType.TAP, button="cross", ms=40, after_ms=70),
            MacroStep(StepType.STICK, stick="left", x=0.5, y=0.0, ms=90, after_ms=30),
        ],
    )
    import threading

    engine._playing.add(macro.id)
    engine._cancel_events[macro.id] = threading.Event()
    engine._run_macro(macro, engine._cancel_events[macro.id])
    assert sleeps == [40, 70, 90, 30]
    assert ("release", "cross") in emulator.events


def test_profile_manager_persists_advanced_macro(tmp_path):
    from src.profile_manager import ProfileManager

    manager = ProfileManager(config_dir=str(tmp_path))
    macro = Macro(
        id="persisted",
        name="Persisted",
        trigger=MacroTrigger(
            kind=TriggerKind.TRIGGER,
            analog_trigger="right",
            threshold=0.72,
            edge=TriggerEdge.WHILE_HELD,
        ),
        profile_ids=["fps"],
        steps=[MacroStep(StepType.TAP, button="cross", ms=45, after_ms=55)],
    )
    manager.set_macros({macro.id: macro.to_dict()})
    assert manager.save_config()

    restored_manager = ProfileManager(config_dir=str(tmp_path))
    restored = Macro.from_dict(restored_manager.get_macros()["persisted"])
    assert restored.trigger.kind == TriggerKind.TRIGGER
    assert restored.trigger.edge == TriggerEdge.WHILE_HELD
    assert restored.profile_ids == ["fps"]
    assert restored.steps[0].after_ms == 55


def test_recording_snapshot_is_live_and_cannot_mutate_engine_state():
    engine, connection, _emulator = build_engine()
    engine.start_recording(include_sticks=False)
    connection.emit(buttons={"cross": True})
    snapshot = engine.get_recording_steps()
    assert snapshot and snapshot[0].button == "cross"
    snapshot[0].button = "circle"
    fresh = engine.get_recording_steps()
    assert fresh[0].button == "cross"
    engine.stop_recording()


def test_profile_change_cancels_macro_from_previous_profile():
    engine, _connection, emulator = build_engine()
    engine.set_active_profile("fps")
    engine.save_macro(
        Macro(
            id="long_profile_macro",
            name="Long profile macro",
            profile_ids=["fps"],
            steps=[MacroStep(StepType.PRESS, button="cross"), MacroStep(StepType.WAIT, ms=5_000)],
        )
    )
    assert engine.play_macro("long_profile_macro")
    assert wait_until(lambda: ("press", "cross") in emulator.events)

    engine.set_active_profile("racing")

    assert wait_until(lambda: not engine.is_playing("long_profile_macro"))
    assert ("release", "cross") in emulator.events
    assert ("clear",) in emulator.events


def test_recording_ignores_wall_clock_jumps(monkeypatch):
    import src.macro_engine as macro_engine_module

    engine, connection, _emulator = build_engine()
    engine.start_recording(include_sticks=False)
    monkeypatch.setattr(macro_engine_module.time, "time", lambda: 10**12)

    connection.emit(buttons={"cross": True})

    assert engine.is_recording
    steps = engine.stop_recording()
    assert any(step.type == StepType.PRESS and step.button == "cross" for step in steps)


def test_macro_parser_keeps_valid_steps_when_one_step_is_corrupt():
    macro = Macro.from_dict(
        {
            "id": "mixed_steps",
            "name": "Mezclada",
            "steps": [
                {"type": "press", "button": "cross"},
                {"type": "future_unknown_step", "button": "circle"},
                {"type": "release", "button": "cross"},
            ],
        }
    )

    assert [step.type.value for step in macro.steps] == ["press", "release"]
    assert [step.button for step in macro.steps] == ["cross", "cross"]


def test_macro_parser_aggregates_corrupt_step_warnings(caplog):
    payload = {
        "id": "noisy_corrupt_macro",
        "steps": [
            {"type": "press", "button": "cross"},
            *[{"type": "unknown_future_step"} for _ in range(50)],
            *[None for _ in range(50)],
            {"type": "release", "button": "cross"},
        ],
    }

    with caplog.at_level("WARNING"):
        macro = Macro.from_dict(payload)

    messages = [
        record.getMessage()
        for record in caplog.records
        if "noisy_corrupt_macro" in record.getMessage()
    ]
    assert len(messages) == 1
    assert "100 paso(s) inválido(s)" in messages[0]
    assert [step.type for step in macro.steps] == [StepType.PRESS, StepType.RELEASE]
