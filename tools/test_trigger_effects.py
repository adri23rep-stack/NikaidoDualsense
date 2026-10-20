"""
Script de diagnostico para calibrar los efectos de vibracion del gatillo
adaptativo a mano, en el control fisico.

No es parte de la app -- corre aparte, con el control conectado, y te deja
probar distintos valores de posicion/fuerza/frecuencia para el modo
Pulse_A hasta que encuentres la sensacion correcta. Cuando encuentres algo
que se sienta bien, avisame los numeros y ajustamos _freq_to_255 /
_pos_9_to_255 en trigger_engine.py para que coincidan.

Uso:
    python tools/test_trigger_effects.py
"""
from pydualsense import pydualsense, TriggerModes


def probar(ds, trigger: str, pos: int, force1: int, force2: int):
    t = ds.triggerR if trigger == 'R' else ds.triggerL
    t.setMode(TriggerModes.Pulse_A)
    t.setForce(0, pos)
    t.setForce(1, force1)
    t.setForce(2, force2)
    print(f"[{trigger}] Pulse_A -> pos={pos} force1={force1} force2={force2}")


def apagar(ds, trigger: str):
    t = ds.triggerR if trigger == 'R' else ds.triggerL
    t.setMode(TriggerModes.Off)


def main():
    ds = pydualsense()
    ds.init()
    print("Control conectado. Presiona Ctrl+C para salir.\n")

    presets = [
        ("Original (bugueado)", 5, 255, 8),
        ("Ejemplo oficial pydualsense", 200, 255, 175),
        ("Suave", 60, 120, 60),
        ("Fuerte cerca del final", 220, 255, 200),
        ("Frecuencia alta", 100, 200, 240),
    ]

    try:
        while True:
            print("\n--- Presets ---")
            for i, (nombre, pos, f1, f2) in enumerate(presets):
                print(f"  {i}: {nombre}  (pos={pos}, force1={f1}, force2={f2})")
            print("  m: valores manuales")
            print("  o: apagar")
            print("  q: salir")

            choice = input("\nElegi una opcion: ").strip().lower()

            if choice == 'q':
                break
            elif choice == 'o':
                apagar(ds, 'R')
                print("Gatillo derecho apagado.")
            elif choice == 'm':
                pos = int(input("Posicion (0-255): "))
                f1 = int(input("Fuerza 1 (0-255): "))
                f2 = int(input("Fuerza 2 (0-255): "))
                probar(ds, 'R', pos, f1, f2)
            elif choice.isdigit() and int(choice) < len(presets):
                _, pos, f1, f2 = presets[int(choice)]
                probar(ds, 'R', pos, f1, f2)
            else:
                print("Opcion invalida.")

    except KeyboardInterrupt:
        pass
    finally:
        apagar(ds, 'R')
        apagar(ds, 'L')
        ds.close()
        print("\nListo, gatillos apagados y control cerrado.")


if __name__ == "__main__":
    main()
