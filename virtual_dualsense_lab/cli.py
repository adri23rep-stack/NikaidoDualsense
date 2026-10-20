"""CLI independiente de Virtual DualSense Lab."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

from .backend import BackendUnavailableError
from .diagnostics import DiagnosticReport, collect_diagnostics
from .hid_report import REPORT_SIZE, decode_input_report, encode_input_report
from .lab import run_alpha1_simulation
from .model import BUTTON_ORDER, ControllerState, DPad, Stick
from .native import NativeHidBackend
from .version import LAB_NAME, LAB_RELEASE, LAB_VERSION, PRODUCT_NAME


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _write_json_atomic(path: Path, value: Any) -> None:
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = (_json_text(value) + "\n").encode("utf-8")
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_name = handle.name
        os.replace(temporary_name, destination)
    finally:
        if temporary_name:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass


def _diagnostic_human(report: DiagnosticReport) -> str:
    lines = [
        f"{PRODUCT_NAME} {LAB_VERSION} {LAB_RELEASE} — {LAB_NAME}",
        "",
        "SIMULACIÓN: LISTA" if report.simulation_ready else "SIMULACIÓN: BLOQUEADA",
        "HID NATIVO: FUENTE INCLUIDA; COMPILACIÓN, FIRMA E INSTALACIÓN BLOQUEADAS",
        "",
    ]
    for check in report.checks:
        lines.append(f"[{check.status.value.upper():7}] {check.check_id}: {check.summary}")
    lines.extend(["", "Bloqueos nativos verificables:"])
    lines.extend(f"- {reason}" for reason in report.native_blockers)
    return "\n".join(lines)


def _self_test() -> dict[str, Any]:
    extreme = ControllerState(
        buttons=frozenset(BUTTON_ORDER),
        dpad=DPad.DOWN_LEFT,
        left_stick=Stick(-1.0, 1.0),
        right_stick=Stick(1.0, -1.0),
        left_trigger=1.0,
        right_trigger=0.5,
        sequence=1,
    )
    encoded = encode_input_report(extreme)
    decoded = decode_input_report(encoded, sequence=extreme.sequence)
    simulation = run_alpha1_simulation()
    checks = {
        "report_size": len(encoded) == REPORT_SIZE,
        "button_round_trip": decoded.buttons == extreme.buttons,
        "dpad_round_trip": decoded.dpad == extreme.dpad,
        "left_stick_extremes": decoded.left_stick == extreme.left_stick,
        "right_stick_extremes": decoded.right_stick == extreme.right_stick,
        "trigger_l_full": decoded.left_trigger == 1.0,
        "trigger_r_half": abs(decoded.right_trigger - 0.5) <= 1 / 65535,
        "simulation_ready": simulation["simulation_ready"],
        "clean_shutdown": simulation["final_status"] == "stopped",
        "neutral_on_shutdown": simulation["final_state_neutral"],
        "no_os_reports": simulation["reports_to_os"] is False,
        "no_dualsense_claim": simulation["dualsense_protocol"] is False,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "simulation": simulation,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="virtual-dualsense-lab",
        description="Laboratorio aislado y seguro para investigar un HID virtual.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{PRODUCT_NAME} {LAB_VERSION} {LAB_RELEASE} — {LAB_NAME}",
    )
    subparsers = parser.add_subparsers(dest="command")

    diagnose = subparsers.add_parser("diagnose", help="Diagnóstico de solo lectura")
    diagnose.add_argument("--json", action="store_true", help="Imprime JSON sanitizado")
    diagnose.add_argument("--output", type=Path, help="Guarda el JSON de forma atómica")

    simulate = subparsers.add_parser("simulate", help="Ejecuta todos los controles simulados")
    simulate.add_argument("--json", action="store_true", help="Imprime JSON")

    self_test = subparsers.add_parser("self-test", help="Autoprueba portable completa")
    self_test.add_argument("--json", action="store_true", help="Imprime JSON")

    native = subparsers.add_parser("native-status", help="Explica por qué el HID nativo está bloqueado")
    native.add_argument("--json", action="store_true", help="Imprime JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "diagnose"

    if command == "diagnose":
        report = collect_diagnostics()
        data = report.to_dict()
        if getattr(args, "output", None):
            _write_json_atomic(args.output, data)
        if getattr(args, "json", False) or getattr(args, "output", None):
            print(_json_text(data))
        else:
            print(_diagnostic_human(report))
        return 0 if report.simulation_ready else 3

    if command == "simulate":
        result = run_alpha1_simulation()
        if args.json:
            print(_json_text(result))
        else:
            print(f"Simulación: {'OK' if result['simulation_ready'] else 'ERROR'}")
            print(f"Reportes aceptados: {result['accepted_reports']}")
            print(f"Cierre neutral: {'sí' if result['final_state_neutral'] else 'no'}")
            print("Salida al sistema operativo: no")
        return 0 if result["simulation_ready"] and result["final_state_neutral"] else 4

    if command == "self-test":
        result = _self_test()
        if args.json:
            print(_json_text(result))
        else:
            print("Autoprueba Alpha 2.3.0: " + ("OK" if result["ok"] else "FALLO"))
            for name, passed in result["checks"].items():
                print(f"[{'OK' if passed else 'FAIL'}] {name}")
        return 0 if result["ok"] else 5

    if command == "native-status":
        report = collect_diagnostics()
        backend = NativeHidBackend(report)
        try:
            backend.start()
        except BackendUnavailableError as exc:
            data = {
                "native_hid": "blocked",
                "reason": str(exc),
                "driver_source_included": True,
                "compiled_driver_included": False,
                "mutations_performed": False,
                "driver_installed": False,
            }
            print(_json_text(data) if args.json else "HID nativo bloqueado: " + str(exc))
            return 0
        print("Error: el backend nativo no debió iniciar", file=sys.stderr)
        return 6

    parser.error(f"Comando desconocido: {command}")
    return 2
