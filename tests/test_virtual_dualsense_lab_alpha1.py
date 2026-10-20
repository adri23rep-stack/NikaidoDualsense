"""Regresiones portables heredadas por Nikaido DualSense 3.0.0 Alpha 2.3.0."""

from __future__ import annotations

import hashlib
import json
import math
import socket
import threading
from pathlib import Path

import pytest

from nikaido_version import APP_VERSION as STABLE_APP_VERSION
from virtual_dualsense_lab import (
    BUTTON_ORDER,
    GENERIC_GAMEPAD_REPORT_DESCRIPTOR,
    LAB_RELEASE,
    LAB_VERSION,
    BackendError,
    BackendStatus,
    BackendUnavailableError,
    Button,
    ControllerState,
    DPad,
    NativeHidBackend,
    SimulatedDualSenseBackend,
    StaleStateError,
    Stick,
    VirtualDualSenseLab,
    collect_diagnostics,
    decode_input_report,
    encode_input_report,
    run_alpha1_simulation,
)
from virtual_dualsense_lab.cli import main as cli_main
from virtual_dualsense_lab.hid_report import REPORT_ID, REPORT_SIZE


ROOT = Path(__file__).resolve().parents[1]


def state(sequence: int, **changes) -> ControllerState:
    values = {"sequence": sequence}
    values.update(changes)
    return ControllerState(**values)


def test_lab_identity_does_not_relabel_the_stable_application() -> None:
    assert LAB_VERSION == "3.0.0-alpha.2.3.0"
    assert LAB_RELEASE == "Alpha 2.3.0"
    assert STABLE_APP_VERSION == "2.9.8.13"


def test_state_is_immutable_and_accepts_documented_aliases() -> None:
    current = ControllerState(
        buttons={"cross", "share", "touchpad_click", "l2", "r2"},
        dpad="neutral",
        left_stick=(-1, 1),
        right_stick=(1, -1),
        left_trigger=0.25,
        right_trigger=0.75,
        sequence=4,
    )
    assert current.buttons == {
        Button.CROSS,
        Button.CREATE,
        Button.TOUCHPAD,
        Button.L2_BUTTON,
        Button.R2_BUTTON,
    }
    assert current.dpad == DPad.CENTER
    with pytest.raises(AttributeError):
        current.sequence = 5  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("left_trigger", -0.01, ValueError),
        ("right_trigger", 1.01, ValueError),
        ("left_trigger", math.inf, ValueError),
        ("right_trigger", True, TypeError),
        ("left_stick", (1.1, 0), ValueError),
        ("right_stick", (0, math.nan), ValueError),
        ("sequence", -1, ValueError),
        ("sequence", True, TypeError),
    ],
)
def test_state_rejects_invalid_or_non_finite_inputs(field, value, error) -> None:
    with pytest.raises(error):
        ControllerState(**{field: value})


def test_state_rejects_unknown_buttons_and_dpad() -> None:
    with pytest.raises(ValueError, match="Botón desconocido"):
        ControllerState(buttons={"turbo_unknown"})
    with pytest.raises(ValueError, match="D-pad"):
        ControllerState(dpad="sideways")


@pytest.mark.parametrize("direction", list(DPad))
def test_report_round_trip_covers_every_dpad_direction(direction: DPad) -> None:
    original = ControllerState(
        buttons=frozenset(BUTTON_ORDER),
        dpad=direction,
        left_stick=Stick(-1.0, 1.0),
        right_stick=Stick(1.0, -1.0),
        left_trigger=1.0,
        right_trigger=0.5,
        sequence=12,
    )
    report = encode_input_report(original)
    restored = decode_input_report(report, sequence=12)
    assert len(report) == REPORT_SIZE
    assert restored.buttons == original.buttons
    assert restored.dpad == direction
    assert restored.left_stick == original.left_stick
    assert restored.right_stick == original.right_stick
    assert restored.left_trigger == 1.0
    assert restored.right_trigger == pytest.approx(0.5, abs=1 / 65535)


def test_report_decoder_rejects_wrong_length_id_and_reserved_buttons() -> None:
    neutral = bytearray(encode_input_report(ControllerState.neutral()))
    with pytest.raises(ValueError, match="medir"):
        decode_input_report(neutral[:-1])
    wrong_id = bytearray(neutral)
    wrong_id[0] = REPORT_ID + 1
    with pytest.raises(ValueError, match="Report ID"):
        decode_input_report(wrong_id)
    reserved = bytearray(neutral)
    reserved[2] |= 0x80
    with pytest.raises(ValueError, match="reservados"):
        decode_input_report(reserved)


def test_descriptor_is_generic_and_contains_no_sony_identity() -> None:
    assert GENERIC_GAMEPAD_REPORT_DESCRIPTOR.startswith(b"\x05\x01\x09\x05")
    assert b"\x4c\x05" not in GENERIC_GAMEPAD_REPORT_DESCRIPTOR
    assert len(BUTTON_ORDER) == 14


def test_simulated_backend_lifecycle_is_idempotent_and_neutralizes() -> None:
    backend = SimulatedDualSenseBackend()
    first = backend.start()
    second = backend.start()
    assert first.session_id == second.session_id == 1
    backend.submit_state(
        state(
            1,
            buttons={Button.CROSS, Button.PS},
            dpad=DPad.RIGHT,
            left_stick=Stick(1, -1),
            left_trigger=1,
        )
    )
    stopped = backend.stop()
    again = backend.stop()
    assert stopped.status == again.status == BackendStatus.STOPPED
    assert stopped.current_state.buttons == frozenset()
    assert stopped.current_state.dpad == DPad.CENTER
    assert stopped.current_state.left_stick == Stick()
    assert stopped.current_state.left_trigger == 0
    assert stopped.neutralizations == 1
    assert [event.kind for event in backend.history()][-2:] == ["neutralized", "stopped"]


def test_three_consecutive_lab_start_and_stop_cycles() -> None:
    backend = SimulatedDualSenseBackend()
    observed_sessions = []
    for expected_session in range(1, 4):
        started = backend.start()
        observed_sessions.append(started.session_id)
        assert started.session_id == expected_session
        assert started.status == BackendStatus.RUNNING
        backend.submit_state(
            state(
                expected_session,
                buttons={Button.CROSS, Button.OPTIONS},
                dpad=DPad.UP,
                left_trigger=0.5,
                right_trigger=1.0,
            )
        )
        stopped = backend.stop()
        assert stopped.status == BackendStatus.STOPPED
        assert stopped.current_state.buttons == frozenset()
        assert stopped.current_state.dpad == DPad.CENTER
        assert stopped.current_state.left_stick == Stick()
        assert stopped.current_state.right_stick == Stick()
        assert stopped.current_state.left_trigger == 0.0
        assert stopped.current_state.right_trigger == 0.0
        assert stopped.current_state.sequence == expected_session + 1
        assert stopped.accepted_reports == 1
        assert stopped.neutralizations == 1
        assert [event.kind for event in backend.history()].count("started") == 1
        assert [event.kind for event in backend.history()].count("stopped") == 1

    assert observed_sessions == [1, 2, 3]


def test_simulated_backend_rejects_stale_sequence_without_corruption() -> None:
    backend = SimulatedDualSenseBackend()
    backend.start()
    accepted = backend.submit_state(state(1, buttons={Button.CIRCLE}))
    with pytest.raises(StaleStateError):
        backend.submit_state(state(1, buttons={Button.CROSS}))
    snapshot = backend.snapshot()
    assert snapshot.current_state == accepted.current_state
    assert snapshot.accepted_reports == 1
    assert snapshot.rejected_reports == 1


def test_subscriptions_unsubscribe_and_remove_failed_callbacks() -> None:
    backend = SimulatedDualSenseBackend()
    received = []
    unsubscribe = backend.subscribe(received.append)

    def broken(_event) -> None:
        raise RuntimeError("expected")

    backend.subscribe(broken)
    backend.start()
    assert [event.kind for event in received] == ["started"]
    assert backend.snapshot().callback_errors == 1
    assert backend.snapshot().subscriber_count == 1
    unsubscribe()
    unsubscribe()
    backend.submit_state(state(1))
    assert [event.kind for event in received] == ["started"]
    assert backend.snapshot().subscriber_count == 0


def test_fault_injection_fails_closed_and_can_stop_cleanly() -> None:
    backend = SimulatedDualSenseBackend(fail_after_reports=1)
    backend.start()
    backend.submit_state(state(1, buttons={Button.TRIANGLE}))
    with pytest.raises(BackendError, match="Fallo simulado"):
        backend.submit_state(state(2, buttons={Button.CROSS}))
    faulted = backend.snapshot()
    assert faulted.status == BackendStatus.FAULTED
    assert faulted.current_state.buttons == frozenset()
    stopped = backend.stop()
    assert stopped.status == BackendStatus.STOPPED
    assert stopped.current_state.buttons == frozenset()


def test_history_is_bounded() -> None:
    backend = SimulatedDualSenseBackend(history_limit=16)
    backend.start()
    for sequence in range(1, 41):
        backend.submit_state(state(sequence, left_trigger=sequence / 40))
    assert len(backend.history()) == 16
    assert backend.history()[-1].state.sequence == 40


def test_lab_serializes_concurrent_callers() -> None:
    lab = VirtualDualSenseLab()
    lab.start()
    failures = []
    barrier = threading.Barrier(5)

    def worker(offset: int) -> None:
        try:
            barrier.wait(2)
            for index in range(20):
                value = ((offset * 20 + index) % 100) / 100
                lab.set_inputs(left_trigger=value, right_trigger=1.0 - value)
        except Exception as exc:  # pragma: no cover - solo evidencia regresión
            failures.append(exc)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    barrier.wait(2)
    for thread in threads:
        thread.join(3)
    assert not failures
    snapshot = lab.snapshot()
    assert snapshot.accepted_reports == 80
    assert snapshot.current_state.sequence == 80
    assert lab.stop().status == BackendStatus.STOPPED


def test_alpha1_simulation_exercises_the_declared_scope() -> None:
    first = run_alpha1_simulation()
    second = run_alpha1_simulation()
    assert first["simulation_ready"] is True
    assert first["reports_to_os"] is False
    assert first["dualsense_protocol"] is False
    assert first["buttons_exercised"] == [button.value for button in BUTTON_ORDER]
    assert first["dpad_directions_exercised"] == [direction.value for direction in DPad]
    assert first["final_state_neutral"] is True
    assert first["final_status"] == "stopped"
    assert first["history_sha256"] == second["history_sha256"]
    assert len(first["history_sha256"]) == hashlib.sha256().digest_size * 2


def test_diagnostic_is_read_only_sanitized_and_blocks_native() -> None:
    report = collect_diagnostics()
    data = report.to_dict()
    text = json.dumps(data, ensure_ascii=False).lower()
    policy = data["safety_policy"]
    assert report.simulation_ready is True
    assert report.native_prototype_allowed is False
    assert data["native_hid"]["driver_included"] is False
    assert data["native_hid"]["driver_installed"] is False
    assert data["native_hid"]["driver_signed"] is False
    assert not any(policy.values())
    assert str(Path.home()).lower() not in text
    assert socket.gethostname().lower() not in text
    assert data["privacy"] == {
        "contains_username": False,
        "contains_hostname": False,
        "contains_private_paths": False,
        "contains_device_instance_ids": False,
    }


def test_native_backend_is_sealed_and_never_reports_active() -> None:
    backend = NativeHidBackend()
    assert backend.status == BackendStatus.STOPPED
    assert backend.capabilities.native is True
    assert backend.capabilities.reports_to_os is False
    with pytest.raises(BackendUnavailableError):
        backend.start()
    with pytest.raises(BackendUnavailableError):
        backend.submit_state(state(1))
    assert backend.stop().status == BackendStatus.STOPPED


def test_cli_diagnose_simulate_self_test_and_native_status(capsys) -> None:
    assert cli_main(["diagnose", "--json"]) == 0
    diagnostic = json.loads(capsys.readouterr().out)
    assert diagnostic["native_hid"]["status"] == "blocked"

    assert cli_main(["simulate", "--json"]) == 0
    simulation = json.loads(capsys.readouterr().out)
    assert simulation["final_state_neutral"] is True

    assert cli_main(["self-test", "--json"]) == 0
    self_test = json.loads(capsys.readouterr().out)
    assert self_test["ok"] is True

    assert cli_main(["native-status", "--json"]) == 0
    native = json.loads(capsys.readouterr().out)
    assert native["native_hid"] == "blocked"
    assert native["mutations_performed"] is False


def test_cli_can_atomically_export_a_sanitized_report(tmp_path, capsys) -> None:
    destination = tmp_path / "diagnostic.json"
    assert cli_main(["diagnose", "--output", str(destination)]) == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads(destination.read_text(encoding="utf-8"))
    assert saved == printed
    assert saved["privacy"]["contains_private_paths"] is False
    assert not list(tmp_path.glob("*.tmp"))


def test_lab_code_has_no_driver_install_or_security_downgrade_commands() -> None:
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "virtual_dualsense_lab").glob("*.py"))
    ).lower()
    forbidden = (
        "testsigning on",
        "nointegritychecks",
        "disable secure boot",
        "pnputil /add-driver",
        "sc create",
        "devcon install",
        "setupcopyoeminf",
    )
    assert not any(value in sources for value in forbidden)


def test_stable_modules_do_not_import_the_lab() -> None:
    stable_paths = [ROOT / "main.py", *(ROOT / "src").glob("*.py"), *(ROOT / "gui").rglob("*.py")]
    assert all(
        "virtual_dualsense_lab" not in path.read_text(encoding="utf-8-sig")
        for path in stable_paths
    )


def test_original_source_manifest_remains_valid() -> None:
    baseline_path = ROOT / "SOURCE_MANIFEST_BASE_2.9.8.9.json"
    baseline_hash = hashlib.sha256(baseline_path.read_bytes()).hexdigest()
    assert baseline_hash == "dac86adb96f5da531e303e1aa3f6fbff8207e0c1a604d0fa413a3c030f5e5fb9"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert baseline["version"] == "2.9.8.9"
    assert len(baseline["files"]) == 411

    current = json.loads((ROOT / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
    assert current["version"] == "2.9.8.13"
    assert current["generated_for"] == "source-integrity"
    assert len(current["files"]) == 458
    for item in current["files"]:
        target = ROOT / item["path"]
        assert target.is_file(), item["path"]
        assert target.stat().st_size == item["size"]
        assert hashlib.sha256(target.read_bytes()).hexdigest() == item["sha256"]


def test_windows_launcher_is_standalone_and_non_mutating() -> None:
    source = (ROOT / "INICIAR_VIRTUAL_DUALSENSE_LAB.bat").read_text(encoding="utf-8").lower()
    assert "-m virtual_dualsense_lab" in source
    assert "pip install" not in source
    assert "bcdedit" not in source
    assert "pnputil" not in source
    assert "devcon" not in source
    assert "runas" not in source
