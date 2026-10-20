"""
Nikaido DualSense - Punto de Entrada Principal
Aplicacion de control para PlayStation 5 DualSense en Windows.

Funcionalidades:
  - Deteccion automatica de conexion USB/Bluetooth
  - Monitor de bateria y estado de carga
  - Motor de efectos de gatillo (haptic feedback)
  - Perfiles de armas preconfigurados
  - Interfaz grafica moderna (modo oscuro)
  - Guardado de configuraciones en JSON
  - Modo bandeja del sistema
  - Reparación Bluetooth conservadora vía PowerShell del sistema

Uso:
    python main.py
    python main.py --minimized  (Inicia minimizado a bandeja)
    python main.py --no-gui     (Modo consola solo)
"""

import argparse
import json
import logging
import os
import sys
import time
import signal
from pathlib import Path
from logging.handlers import RotatingFileHandler

# La distribución de código fuente usa un entorno local. Esto debe ejecutarse
# antes de importar Qt, HID, Core Audio o cualquier otro paquete externo.
from src.runtime_bootstrap import bootstrap_local_venv

bootstrap_local_venv(Path(__file__).resolve().parent)

from nikaido_version import APP_NAME, APP_VERSION  # noqa: E402
from src.security_utils import harden_private_file, redact_private_text  # noqa: E402

# Agregar directorio src al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class RedactingFormatter(logging.Formatter):
    """Evita que rutas personales terminen en logs compartidos por soporte."""

    def format(self, record):
        return redact_private_text(super().format(record))


def setup_logging():
    """Configura logging sin convertir una carpeta no escribible en fallo de arranque."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if any(getattr(handler, "_nikaido_handler", False) for handler in root_logger.handlers):
        return logging.getLogger(__name__)

    formatter = RedactingFormatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler._nikaido_handler = True
    root_logger.addHandler(stream_handler)

    log_error = None
    try:
        log_dir = (
            Path(os.environ.get('APPDATA', os.path.expanduser('~')))
            / 'DualSenseController'
            / 'logs'
        )
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f'dualsense_{time.strftime("%Y%m%d")}.log'
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=2_000_000,
            backupCount=4,
            encoding='utf-8',
        )
        file_handler.setFormatter(formatter)
        file_handler._nikaido_handler = True
        root_logger.addHandler(file_handler)
        try:
            harden_private_file(log_file)
        except OSError as exc:
            logging.getLogger(__name__).warning(
                "No se pudieron ajustar los permisos del log: %s", exc
            )
    except OSError as exc:
        log_error = exc

    if log_error is not None:
        logging.getLogger(__name__).warning(
            "La carpeta de logs no está disponible; se continuará con salida de consola: %s",
            log_error,
        )

    return logging.getLogger(__name__)


def parse_arguments():
    """Parsea los argumentos de linea de comandos."""
    parser = argparse.ArgumentParser(
        description='Nikaido - Panel de control DualSense para Windows'
    )
    parser.add_argument(
        '--minimized', '-m',
        action='store_true',
        help='Inicia la aplicacion minimizada a la bandeja del sistema'
    )
    parser.add_argument(
        '--no-gui', '-c',
        action='store_true',
        help='Ejecuta en modo consola sin interfaz grafica'
    )
    parser.add_argument(
        '--profile', '-p',
        type=str,
        default=None,
        help='ID del perfil a aplicar automaticamente al conectar'
    )
    parser.add_argument(
        '--reset-bt',
        action='store_true',
        help='Reinicia el Bluetooth al inicio'
    )
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Activa el modo debug con logging verboso'
    )
    parser.add_argument(
        '--self-test-hid',
        action='store_true',
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--self-test-output',
        type=str,
        default='',
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


class DualSenseApp:
    """
    Aplicacion principal que orquesta todos los modulos.
    """

    def __init__(self, args):
        self.args = args
        self.logger = logging.getLogger(__name__)

        # Modulos
        self.connection_manager = None
        self.trigger_engine = None
        self.profile_manager = None
        self.update_manager = None
        self.macro_engine = None
        self.light_effect_engine = None
        self.player_led_controller = None
        self.audio_manager = None
        self.game_profile_watcher = None
        self.virtual_feedback_bridge = None
        self.hidhide_manager = None
        self.touchpad_mouse = None
        self.advanced_mapper = None
        self.keyboard_gamepad = None
        self.gyro_engine = None
        self.input_studio = None
        self.diagnostic_engine = None
        self.tray_manager = None
        self.gui = None

        self._running = False
        self._shutdown_requested = False
        self._shutdown_started = False
        self._gui_subscriptions = []
        self._backend_subscriptions = []

    def _track_subscription(self, unsubscribe):
        """Registra bajas ofrecidas por backends nuevos sin romper backends antiguos."""
        if callable(unsubscribe):
            self._backend_subscriptions.append(unsubscribe)

    def initialize(self):
        """Inicializa todos los modulos de la aplicacion."""
        self.logger.info("=" * 50)
        self.logger.info("%s v%s - Iniciando", APP_NAME, APP_VERSION)
        self.logger.info("=" * 50)

        try:
            from src.connection_manager import ConnectionManager
            from src.trigger_engine import TriggerEngine
            from src.profile_manager import ProfileManager
            from src.update_manager import UpdateManager
            from src.system_tray import TrayManager
            from src.macro_engine import MacroEngine
            from src.light_effects import LightEffectEngine
            from src.player_led_battery import PlayerLedBatteryController
            from src.audio_manager import AudioManager
            from src.game_profile_watcher import GameProfileWatcher
            from src.virtual_feedback import VirtualFeedbackBridge
            from src.hidhide_manager import HidHideManager
            from src.touchpad_mouse import TouchpadMouseController
            from src.gyro_engine import GyroEngine
            from src.input_studio import InputStudioEngine
            from src.advanced_mapping import AdvancedMapper
            from src.keyboard_gamepad import KeyboardGamepadEngine
            from src.diagnostics import DiagnosticEngine

            # 1. Profile Manager (primero para cargar configuracion)
            self.logger.info("Inicializando ProfileManager...")
            self.profile_manager = ProfileManager()
            self.logger.info("Inicializando UpdateManager...")
            self.update_manager = UpdateManager(self.profile_manager)

            # 2. Connection Manager
            self.logger.info("Inicializando ConnectionManager...")
            self.connection_manager = ConnectionManager()

            # 2.1 Feedback del juego y protección contra doble entrada. Ambos
            # módulos son observadores; no bloquean el arranque si sus drivers
            # opcionales todavía no están instalados.
            self.logger.info("Inicializando VirtualFeedbackBridge...")
            self.virtual_feedback_bridge = VirtualFeedbackBridge(
                self.connection_manager.emulator,
                self.connection_manager,
                self.profile_manager.get_setting('virtual_feedback', {}),
            )
            self.logger.info("Inicializando HidHideManager...")
            self.hidhide_manager = HidHideManager()

            # 3. Trigger Engine
            self.logger.info("Inicializando TriggerEngine...")
            self.trigger_engine = TriggerEngine(self.connection_manager)

            # 4. Motor de luces RGB y animaciones
            self.logger.info("Inicializando LightEffectEngine...")
            self.light_effect_engine = LightEffectEngine(self.connection_manager)
            self.light_effect_engine.load_custom_effects(
                self.profile_manager.get_setting('custom_light_effects', {})
            )
            self.light_effect_engine.set_control_mode(
                self.profile_manager.get_setting('light_control_mode', 'nikaido')
            )

            # 4.05 Indicadores blancos: batería, jugador, juego o apagado.
            player_led_config = self.profile_manager.get_setting('player_led', {})
            if not isinstance(player_led_config, dict):
                player_led_config = {}
            player_led_config = dict(player_led_config)
            player_led_config.setdefault(
                'player_number', self.profile_manager.get_setting('player_number', 1)
            )
            self.logger.info("Inicializando PlayerLedBatteryController...")
            self.player_led_controller = PlayerLedBatteryController(
                self.connection_manager,
                player_led_config,
            )

            # 4.1 Audio de Windows + botón MIC del DualSense. Core Audio se
            # ejecuta en su propio hilo para no entrar jamás en la ruta HID.
            self.logger.info("Inicializando AudioManager...")
            self.audio_manager = AudioManager(
                self.connection_manager,
                self.profile_manager.get_setting('audio', {}),
            )

            # 5. Macro Engine (graba y reproduce combos de botones)
            self.logger.info("Inicializando MacroEngine...")
            self.macro_engine = MacroEngine(self.connection_manager, self.connection_manager.emulator)
            self.macro_engine.load_macros(self.profile_manager.get_macros())
            self.macro_engine.set_enabled(self.profile_manager.get_setting('macros_enabled', True))

            # 5. Touchpad como mouse
            self.logger.info("Inicializando TouchpadMouseController...")
            self.touchpad_mouse = TouchpadMouseController(self.connection_manager)
            self.touchpad_mouse.set_sensitivity(
                self.profile_manager.get_setting('touchpad_mouse.sensitivity', 2.5)
            )
            self.touchpad_mouse.set_enabled(
                self.profile_manager.get_setting('touchpad_mouse.enabled', False)
            )

            # 6. Game Profile Watcher (perfil automatico por juego)
            self.logger.info("Inicializando GameProfileWatcher...")
            self.game_profile_watcher = GameProfileWatcher(self.trigger_engine)
            self.game_profile_watcher.set_mapping(self.profile_manager.get_game_profiles())
            self.game_profile_watcher.set_rules(
                self.profile_manager.get_setting('game_profile_rules', [])
            )
            self.game_profile_watcher.set_enabled(
                self.profile_manager.get_setting('game_profiles_enabled', True)
            )
            # Distingue cambios manuales de los aplicados por automatización y
            # permite restaurar el perfil que el usuario tenía antes del juego.
            self._track_subscription(
                self.trigger_engine.on_profile_change(
                    self.game_profile_watcher.observe_profile_change
                )
            )

            # 7. System Tray
            self.logger.info("Inicializando TrayManager...")
            self.tray_manager = TrayManager()
            self._track_subscription(
                self.connection_manager.on_connect(
                    lambda connection: self.tray_manager.set_status(
                        f"Conectado · {connection.value.upper()}"
                    )
                )
            )
            self._track_subscription(
                self.connection_manager.on_disconnect(
                    lambda: self.tray_manager.set_status("Desconectado")
                )
            )
            self._track_subscription(
                self.connection_manager.on_battery_change(
                    lambda level, status: self.tray_manager.set_battery(
                        level,
                        getattr(status, 'value', '')
                        in ('cargando', 'cargado completo'),
                    )
                )
            )
            self._track_subscription(
                self.trigger_engine.on_profile_change(
                    lambda profile_id: self.tray_manager.set_current_profile(profile_id)
                )
            )

            # 8. Cargar perfiles personalizados guardados
            custom_profiles = self.profile_manager.get_custom_profiles()
            if custom_profiles:
                self.logger.info(f"Cargando {len(custom_profiles)} perfiles personalizados")
                self.trigger_engine.load_profiles_from_dict(custom_profiles)

            self.trigger_engine.load_profile_overrides(
                self.profile_manager.get_setting('profile_overrides', {})
            )

            # Las preferencias de vibracion de gatillos se guardan aparte para
            # que tambien puedan personalizarse los perfiles predefinidos sin
            # tener que duplicarlos como perfiles personalizados.
            self.trigger_engine.load_vibration_overrides(
                self.profile_manager.get_setting('profile_trigger_vibration', {})
            )
            self.trigger_engine.load_gyro_overrides(
                self.profile_manager.get_setting('profile_gyro', {})
            )

            # 9. Motor de giroscopio. Procesa el estado antes de que el mismo
            # tick sea enviado al gamepad virtual, sin crear otro escritor ViGEm.
            self.logger.info("Inicializando GyroEngine...")
            self.gyro_engine = GyroEngine(self.connection_manager, self.connection_manager.emulator)

            def apply_profile_gyro(profile_id):
                config = self.trigger_engine.get_profile_gyro_config(profile_id)
                self.gyro_engine.apply_config(config, profile_id)

            def persist_profile_gyro(profile_id, config):
                if profile_id:
                    self.trigger_engine.update_profile_gyro_config(profile_id, config)

            self._track_subscription(
                self.trigger_engine.on_profile_change(apply_profile_gyro)
            )
            self._track_subscription(
                self.gyro_engine.on_config_change(persist_profile_gyro)
            )

            # 10. Input Studio vive en el mismo camino de salida que ViGEm.
            # Por eso filtra la entrada sin crear un segundo escritor virtual
            # y puede previsualizar exactamente el resultado por perfil.
            self.logger.info("Inicializando Nikaido Input Studio...")
            self.input_studio = InputStudioEngine()
            self.input_studio.load_profiles(
                self.profile_manager.get_setting('profile_input_studio', {})
            )
            for profile_id, profile in self.trigger_engine.get_all_profiles().items():
                if profile.input_studio_config:
                    self.input_studio.set_profile_config(
                        profile_id, profile.input_studio_config
                    )
            self.connection_manager.emulator.set_input_processor(self.input_studio)

            def apply_profile_input(profile_id):
                self.input_studio.apply_profile(profile_id)

            self._track_subscription(
                self.trigger_engine.on_profile_change(apply_profile_input)
            )

            runtime_state = {"audio_profile_id": None}

            def apply_profile_runtime(profile_id):
                profile = self.trigger_engine.get_profile(profile_id)
                if not profile:
                    return
                if self.macro_engine:
                    self.macro_engine.set_active_profile(profile_id)
                    self.macro_engine.set_enabled(bool(profile.macros_enabled))
                if self.light_effect_engine:
                    self.light_effect_engine.apply_config(profile.light_config)
                if self.audio_manager:
                    # TriggerEngine también reaplica el mismo perfil al editar
                    # gatillos o reconectar el control. Volumen/mute solo deben
                    # forzarse cuando el perfil realmente cambia.
                    changed = runtime_state["audio_profile_id"] != profile_id
                    self.audio_manager.apply_config(
                        profile.audio_config,
                        profile_id,
                        apply_profile_state=changed,
                    )
                    runtime_state["audio_profile_id"] = profile_id

            self._track_subscription(
                self.trigger_engine.on_profile_change(apply_profile_runtime)
            )
            self._track_subscription(
                self.connection_manager.on_connect(
                    lambda _connection: self.light_effect_engine.apply_config(
                        self.light_effect_engine.get_config()
                    )
                    if self.light_effect_engine
                    else None
                )
            )
            initial_profile = (
                self.args.profile
                or self.profile_manager.get_active_profile()
                or 'assault_rifle'
            )
            if not self.trigger_engine.apply_profile(initial_profile):
                initial_profile = 'assault_rifle'
                self.trigger_engine.apply_profile(initial_profile)

            # Los efectos físicos deben reaplicarse cuando el control aparece,
            # aunque haya tardado más de unos segundos en conectarse.
            self._track_subscription(
                self.connection_manager.on_connect(
                    lambda _connection: self.trigger_engine.apply_profile(
                        self.trigger_engine.get_current_profile() or initial_profile
                    )
                )
            )

            # 11. Cargar remapeo basico de botones guardado. Se mantiene por
            # compatibilidad; el motor avanzado puede bloquearlo o sumarle
            # acciones por capa sin destruir configuraciones anteriores.
            self.connection_manager.emulator.set_button_map(self.profile_manager.get_button_map())

            # 12. Remapeo avanzado: se suscribe al mismo tick HID antes de
            # que el emulador escriba a ViGEm. Puede emitir teclado/raton,
            # macros, turbo, gestos y cambios temporales de perfil/capa.
            self.logger.info("Inicializando AdvancedMapper...")
            self.advanced_mapper = AdvancedMapper(
                self.connection_manager,
                self.connection_manager.emulator,
                self.macro_engine,
                profile_getter=self.trigger_engine.get_current_profile,
                profile_applier=self.trigger_engine.apply_profile,
                gyro_engine=self.gyro_engine,
            )
            legacy_advanced_mapping = self.profile_manager.get_advanced_mapping()
            active_profile_object = self.trigger_engine.get_profile(
                self.trigger_engine.get_current_profile() or initial_profile
            )
            initial_mapping = (
                active_profile_object.advanced_mapping_config
                if active_profile_object and active_profile_object.advanced_mapping_config
                else legacy_advanced_mapping
            )
            self.advanced_mapper.set_config(initial_mapping)

            def apply_profile_mapping(profile_id):
                profile = self.trigger_engine.get_profile(profile_id)
                config = (
                    profile.advanced_mapping_config
                    if profile and profile.advanced_mapping_config
                    else legacy_advanced_mapping
                )
                self.advanced_mapper.queue_profile_config(config)

            self._track_subscription(
                self.trigger_engine.on_profile_change(apply_profile_mapping)
            )

            # 13. Nikaido KeyBridge usa el mismo EmulatorManager/ViGEm que el
            # DualSense, pero reserva la fuente virtual mientras está activo.
            # Así teclado y mouse pueden convertirse en Xbox 360 o DS4 incluso
            # sin un control físico conectado, sin crear dos escritores.
            self.logger.info("Inicializando Nikaido KeyBridge...")
            self.keyboard_gamepad = KeyboardGamepadEngine(
                self.connection_manager.emulator,
                self.profile_manager.get_setting('keyboard_gamepad', {}),
            )

            # Ctrl+M es una pausa de sesión. No se persiste como "apagado"
            # porque la siguiente pulsación debe volver a armar la captura y el
            # perfil del usuario debe conservar Mouse → Stick/Gyro activado.

            # 14. Diagnóstico observa la ruta ya procesada y nunca escribe en
            # HID/ViGEm. Así puede medir, capturar y exportar reportes sin
            # añadir latencia al control virtual.
            self.logger.info("Inicializando DiagnosticEngine...")
            self.diagnostic_engine = DiagnosticEngine(
                connection_manager=self.connection_manager,
                emulator=self.connection_manager.emulator,
                gyro_engine=self.gyro_engine,
                advanced_mapper=self.advanced_mapper,
                macro_engine=self.macro_engine,
                profile_manager=self.profile_manager,
                trigger_engine=self.trigger_engine,
                virtual_feedback_bridge=self.virtual_feedback_bridge,
                game_profile_watcher=self.game_profile_watcher,
                hidhide_manager=self.hidhide_manager,
                update_manager=self.update_manager,
            )

            self.logger.info("Todos los modulos inicializados correctamente")
            return True

        except Exception as e:
            self.logger.error(f"Error inicializando modulos: {e}", exc_info=True)
            return False

    def start(self):
        """Inicia la aplicacion."""
        if not self.initialize():
            self.logger.error("No se pudieron inicializar los módulos. Cerrando lo ya iniciado.")
            self.shutdown()
            raise RuntimeError("Nikaido no pudo inicializar sus módulos")

        self._running = True

        # Configurar signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Iniciar modulos de backend
        if self.virtual_feedback_bridge:
            self.virtual_feedback_bridge.start()
        if self.audio_manager:
            # El perfil activo ya quedó cargado durante initialize(); el worker
            # lo aplica una sola vez al abrir Core Audio.
            self.audio_manager.start()
        if self.gyro_engine:
            self.gyro_engine.start()
        if not self.profile_manager.get_setting('auto_connect', True):
            self.connection_manager.disconnect()
        self.connection_manager.start()
        if self.keyboard_gamepad and self.keyboard_gamepad.get_config().get('enabled'):
            if not self.keyboard_gamepad.start():
                self.logger.warning(
                    "KeyBridge no pudo iniciarse automáticamente: %s",
                    self.keyboard_gamepad.last_error,
                )
        self.tray_manager.start()
        if self.game_profile_watcher:
            self.game_profile_watcher.start()

        # Cargar perfiles en el tray menu
        if self.trigger_engine:
            profiles = self.trigger_engine.get_profile_names()
            self.tray_manager.set_profiles(profiles)
            self.tray_manager.set_current_profile(
                self.trigger_engine.get_current_profile()
            )

        # Reiniciar Bluetooth si se solicito
        if self.args.reset_bt:
            self.logger.info("Reiniciando Bluetooth como se solicito...")
            self.connection_manager.perform_bluetooth_reset()

        # Iniciar GUI o modo consola
        if self.args.no_gui:
            self._run_console_mode()
        else:
            self._run_gui_mode()

    def _run_gui_mode(self):
        """Ejecuta en modo grafico."""
        try:
            from gui.modern_app import DualSenseGUI

            self.logger.info("Iniciando interfaz grafica...")

            self.gui = DualSenseGUI(
                connection_manager=self.connection_manager,
                trigger_engine=self.trigger_engine,
                profile_manager=self.profile_manager,
                tray_manager=self.tray_manager,
                macro_engine=self.macro_engine,
                game_profile_watcher=self.game_profile_watcher,
                touchpad_mouse=self.touchpad_mouse,
                gyro_engine=self.gyro_engine,
                input_studio=self.input_studio,
                advanced_mapper=self.advanced_mapper,
                keyboard_gamepad=self.keyboard_gamepad,
                diagnostic_engine=self.diagnostic_engine,
                light_effect_engine=self.light_effect_engine,
                player_led_controller=self.player_led_controller,
                audio_manager=self.audio_manager,
                virtual_feedback_bridge=self.virtual_feedback_bridge,
                hidhide_manager=self.hidhide_manager,
                update_manager=self.update_manager,
            )

            # Conectar tray callbacks
            # pystray ejecuta acciones en su propio hilo. El adaptador Qt
            # las reenvía mediante señales para que nunca se toque la ventana
            # desde fuera del hilo principal.
            for unsubscribe in (
                self.tray_manager.on_show_window(self.gui.show_window),
                self.tray_manager.on_exit(self.gui.exit_app),
                self.tray_manager.on_profile_select(self.gui.select_profile),
                self.tray_manager.on_low_profile(self.gui.enter_low_profile),
            ):
                if callable(unsubscribe):
                    self._gui_subscriptions.append(unsubscribe)

            self.gui.on_close(self.shutdown)

            # Iniciar minimizado solo si existe una bandeja desde la cual
            # recuperar la ventana. Así nunca queda invisible por accidente.
            start_minimized = bool(
                self.args.minimized
                or self.profile_manager.get_setting('start_minimized', False)
            )
            if start_minimized and self.tray_manager.is_visible():
                self.logger.info("Iniciando minimizado a bandeja")
                self.gui.call_later(100, self.gui.hide_window)
            elif start_minimized:
                self.logger.warning("No hay bandeja disponible; se mostrará la ventana")

            # Ejecutar interfaz. Si Qt termina por una ruta externa (por
            # ejemplo cierre de sesión de Windows), apagamos igualmente todos
            # los motores antes de devolver el control al proceso.
            self.gui.run()
            if not self._shutdown_started:
                self.shutdown()

        except Exception as e:
            self.logger.error(f"Error en modo gráfico: {e}", exc_info=True)
            interactive_console = bool(
                not getattr(sys, "frozen", False)
                and sys.stdin is not None
                and getattr(sys.stdin, "isatty", lambda: False)()
            )
            if interactive_console:
                self.logger.info("Cayendo a modo consola porque hay una terminal disponible...")
                self._run_console_mode()
                return

            # Un ejecutable --noconsole no puede pedir comandos por input().
            # Antes quedaba abierto e invisible después de un fallo de Qt.
            self.shutdown()
            # La capa superior distingue este fallo de un paquete ausente y
            # devuelve código 1. Silenciarlo aquí hacía que el launcher creyera
            # que un cierre de Qt durante el arranque había sido exitoso.
            raise RuntimeError("La interfaz gráfica no pudo iniciar") from e

    def _run_console_mode(self):
        """Ejecuta en modo consola (sin GUI)."""
        self.logger.info("Ejecutando en modo consola")
        print("\n" + "=" * 50)
        print("Nikaido DualSense - Modo Consola")
        print("=" * 50)
        print("Comandos disponibles:")
        print("  connect    - Intentar conectar el control")
        print("  disconnect - Desconectar el control")
        print("  status     - Mostrar estado actual")
        print("  battery    - Mostrar nivel de bateria")
        print("  profiles   - Listar perfiles disponibles")
        print("  apply <id> - Aplicar un perfil")
        print("  reset-bt   - Reiniciar Bluetooth")
        print("  led <r> <g> <b> - Cambiar color LED")
        print("  mic        - Alternar mute del micrófono")
        print("  mic on/off - Silenciar o activar el micrófono")
        print("  mics       - Listar micrófonos de Windows")
        print("  exit       - Salir")
        print("=" * 50 + "\n")

        # Esperar conexion automatica si esta configurada
        if self.profile_manager.get_setting('auto_connect', True):
            print("Esperando conexion automatica del DualSense...")

        # Callbacks para mostrar en consola
        self._track_subscription(
            self.connection_manager.on_connect(self._on_console_connect)
        )
        self._track_subscription(
            self.connection_manager.on_disconnect(self._on_console_disconnect)
        )
        self._track_subscription(
            self.connection_manager.on_battery_change(self._on_console_battery)
        )

        # Bucle de comandos
        while self._running:
            try:
                command = input("dualsense> ").strip().lower()

                if command == 'exit':
                    break
                elif command == 'connect':
                    self.connection_manager.request_connect()
                    print("Buscando DualSense...")
                elif command == 'disconnect':
                    self.connection_manager.disconnect()
                    print("Desconectado. Reconexión automática pausada.")
                elif command == 'status':
                    self._print_status()
                elif command == 'battery':
                    level, status = self.connection_manager.get_battery_info()
                    print(f"Bateria: {level}% - {status.value}")
                elif command == 'profiles':
                    self._print_profiles()
                elif command.startswith('apply '):
                    profile_id = command.split(' ', 1)[1]
                    if self.trigger_engine:
                        success = self.trigger_engine.apply_profile(profile_id)
                        print(f"Perfil {'aplicado' if success else 'no encontrado'}")
                elif command == 'reset-bt':
                    print("Reiniciando Bluetooth...")
                    self.connection_manager.perform_bluetooth_reset()
                elif command.startswith('led '):
                    parts = command.split()
                    if len(parts) == 4:
                        r, g, b = int(parts[1]), int(parts[2]), int(parts[3])
                        self.connection_manager.set_led_color(r, g, b)
                        print(f"LED establecido a RGB({r},{g},{b})")
                elif command == 'mic' and self.audio_manager:
                    self.audio_manager.toggle_mute()
                    print("Alternando micrófono...")
                elif command in ('mic on', 'mic off') and self.audio_manager:
                    self.audio_manager.set_muted(command == 'mic off')
                    print("Micrófono silenciado" if command == 'mic off' else "Micrófono activado")
                elif command == 'mics' and self.audio_manager:
                    devices = self.audio_manager.refresh_devices(wait=True)
                    for device in devices:
                        marker = " [PREDETERMINADO]" if device.get('is_default') else ""
                        print(f"  {device.get('name', 'Micrófono')}{marker}")
                elif command == '':
                    continue
                else:
                    print(f"Comando desconocido: {command}")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

        self.shutdown()

    def _print_status(self):
        """Imprime el estado actual en consola."""
        state = self.connection_manager.state
        print(f"\nConectado: {'Si' if state.connected else 'No'}")
        print(f"Tipo: {state.connection_type.value}")
        print(f"Bateria: {state.battery_level}% - {state.charging_status.value}")
        print(f"L2: {state.left_trigger}/255")
        print(f"R2: {state.right_trigger}/255")
        print()

    def _print_profiles(self):
        """Imprime los perfiles disponibles en consola."""
        if not self.trigger_engine:
            return

        print("\nPerfiles disponibles:")
        for pid, name in self.trigger_engine.get_profile_names():
            profile = self.trigger_engine.get_profile(pid)
            current = " [ACTIVO]" if pid == self.trigger_engine.get_current_profile() else ""
            print(f"  {pid:<20} - {name}{current}")
            if profile:
                print(f"      {profile.description}")
        print()

    def _on_console_connect(self, connection_type):
        """Callback de conexion para modo consola."""
        print(f"\n[+] DualSense conectado via {connection_type.value.upper()}")

        # Aplicar perfil por defecto
        if self.trigger_engine:
            target = self.args.profile or self.profile_manager.get_active_profile()
            self.trigger_engine.apply_profile(target)
            print(f"[+] Perfil aplicado: {target}")

    def _on_console_disconnect(self):
        """Callback de desconexion para modo consola."""
        print("\n[-] DualSense desconectado")

    def _on_console_battery(self, level, status):
        """Callback de bateria para modo consola."""
        print(f"\n[Battery] {level}% - {status.value}")

    def _signal_handler(self, signum, frame):
        """Maneja señales de sistema."""
        self.logger.info(f"Señal recibida: {signum}")
        self._shutdown_requested = True
        self.shutdown()

    def shutdown(self):
        """Apaga todos los módulos aunque el inicio haya quedado incompleto."""
        if self._shutdown_started:
            return
        self._shutdown_started = True

        self.logger.info("Cerrando aplicación...")
        self._running = False

        def persist(name, action):
            try:
                action()
            except Exception:
                self.logger.exception("No se pudo guardar %s durante el cierre", name)

        if self.macro_engine and self.profile_manager:
            persist(
                "macros",
                lambda: self.profile_manager.set_macros(
                    self.macro_engine.export_macros()
                ),
            )
        if self.trigger_engine and self.profile_manager:
            persist(
                "vibración de gatillos",
                lambda: self.profile_manager.set_setting(
                    'profile_trigger_vibration',
                    self.trigger_engine.export_vibration_overrides(),
                ),
            )
            persist(
                "giroscopio por perfil",
                lambda: self.profile_manager.set_setting(
                    'profile_gyro', self.trigger_engine.export_gyro_overrides()
                ),
            )
            persist(
                "ajustes de perfiles incluidos",
                lambda: self.profile_manager.set_setting(
                    'profile_overrides', self.trigger_engine.export_profile_overrides()
                ),
            )
            persist(
                "perfiles personales",
                lambda: self.profile_manager.set_custom_profiles(
                    self.trigger_engine.export_custom_profiles_to_dict()
                ),
            )
        if self.input_studio and self.profile_manager:
            persist(
                "Input Studio",
                lambda: self.profile_manager.set_setting(
                    'profile_input_studio', self.input_studio.export_profiles()
                ),
            )
        if self.light_effect_engine and self.profile_manager:
            persist(
                "efectos de luz",
                lambda: self.profile_manager.set_setting(
                    'custom_light_effects',
                    self.light_effect_engine.export_custom_effects(),
                ),
            )
        if self.audio_manager and self.profile_manager:
            persist(
                "audio",
                lambda: self.profile_manager.set_setting(
                    'audio', self.audio_manager.get_config()
                ),
            )
        if self.keyboard_gamepad and self.profile_manager:
            persist(
                "KeyBridge",
                lambda: self.profile_manager.set_setting(
                    'keyboard_gamepad', self.keyboard_gamepad.get_config()
                ),
            )
        if self.virtual_feedback_bridge and self.profile_manager:
            persist(
                "feedback virtual",
                lambda: self.profile_manager.set_setting(
                    'virtual_feedback', self.virtual_feedback_bridge.get_config()
                ),
            )
        if self.game_profile_watcher and self.profile_manager:
            persist(
                "reglas de perfiles automáticos",
                lambda: self.profile_manager.set_setting(
                    'game_profile_rules', self.game_profile_watcher.get_rules()
                ),
            )
            persist(
                "estado de perfiles automáticos",
                lambda: self.profile_manager.set_setting(
                    'game_profiles_enabled', self.game_profile_watcher.is_enabled()
                ),
            )
        # Desde 2.1 el mapa avanzado pertenece al perfil y ya quedó incluido
        # en ``profile_overrides`` / ``custom_profiles`` arriba. El mapa global
        # legado se conserva como respaldo de migración.
        if self.profile_manager:
            persist("configuración", self.profile_manager.save_config)

        subscriptions = self._backend_subscriptions + self._gui_subscriptions
        self._backend_subscriptions = []
        self._gui_subscriptions = []
        for unsubscribe in subscriptions:
            try:
                unsubscribe()
            except Exception:
                self.logger.exception("No se pudo retirar una suscripción de la bandeja")

        # Primero se detienen las fuentes de trabajo y la bandeja; Qt se
        # cierra al final. Así ningún callback puede volver a esconder o
        # mantener viva la aplicación durante el apagado.
        shutdown_steps = (
            ("macros", lambda: self.macro_engine.stop() if self.macro_engine else None),
            ("giroscopio", lambda: self.gyro_engine.stop() if self.gyro_engine else None),
            ("luces", lambda: self.light_effect_engine.shutdown() if self.light_effect_engine else None),
            ("indicador de batería", lambda: self.player_led_controller.stop() if self.player_led_controller else None),
            ("gatillos", lambda: self.trigger_engine.stop() if self.trigger_engine else None),
            ("touchpad", lambda: self.touchpad_mouse.stop() if self.touchpad_mouse else None),
            ("KeyBridge", lambda: self.keyboard_gamepad.stop() if self.keyboard_gamepad else None),
            ("mapper", lambda: self.advanced_mapper.stop() if self.advanced_mapper else None),
            ("perfiles por juego", lambda: self.game_profile_watcher.stop() if self.game_profile_watcher else None),
            ("feedback virtual", lambda: self.virtual_feedback_bridge.stop() if self.virtual_feedback_bridge else None),
            ("audio", lambda: self.audio_manager.stop() if self.audio_manager else None),
            ("conexión", lambda: self.connection_manager.stop() if self.connection_manager else None),
            ("bandeja", lambda: self.tray_manager.stop() if self.tray_manager else None),
            ("interfaz", lambda: self.gui.stop() if self.gui else None),
        )
        for name, stop in shutdown_steps:
            try:
                stop()
            except Exception:
                self.logger.exception("Error deteniendo %s", name)

        self.logger.info("Aplicación cerrada correctamente")


def run_hid_self_test(output_path: str = "") -> int:
    """Comprueba el backend HID dentro del ejecutable sin requerir un control."""
    result = {
        "ok": False,
        "backend": "unavailable",
        "fallback": False,
        "pydualsense_imported": False,
        "enumeration_ok": False,
        "sony_devices": 0,
        "tray_imported": False,
        "tray_backend_imported": False,
        "tray_icon_rendered": False,
        "audio_imported": False,
        "error": "",
    }
    try:
        from src.hid_backend import ensure_hidapi_backend

        status = ensure_hidapi_backend()
        result["backend"] = status.name
        result["fallback"] = status.fallback
        if not status.available:
            raise RuntimeError(status.error or "backend HID no disponible")

        import hidapi
        import pydualsense  # noqa: F401
        import pydualsense.hidguardian  # noqa: F401
        import comtypes  # noqa: F401
        import pycaw.constants  # noqa: F401
        import pycaw.pycaw  # noqa: F401

        result["pydualsense_imported"] = True
        result["audio_imported"] = True
        devices = list(hidapi.enumerate(vendor_id=0x054C))
        result["enumeration_ok"] = True
        result["sony_devices"] = len(devices)

        # La bandeja es parte esencial de la experiencia del EXE. Renderizar
        # un icono aquí detecta Pillow/pystray ausentes antes de entregar el ZIP.
        from src.system_tray import PIL_AVAILABLE, PYSTRAY_AVAILABLE, TrayManager

        if not PIL_AVAILABLE or not PYSTRAY_AVAILABLE:
            raise RuntimeError("backend de bandeja no disponible")
        import pystray  # noqa: F401
        if os.name == "nt":
            import pystray._win32  # noqa: F401
        result["tray_backend_imported"] = True
        tray = TrayManager()
        tray_image = tray._create_icon_image(
            battery_level=75, charging=False, connected=True
        )
        result["tray_imported"] = True
        result["tray_icon_rendered"] = bool(
            getattr(tray_image, "size", None) == (64, 64)
        )
        if not result["tray_icon_rendered"]:
            raise RuntimeError("el icono dinámico de batería no pudo renderizarse")

        result["ok"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    if output_path:
        try:
            destination = Path(output_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            return 2
    return 0 if result["ok"] else 1


def main():
    """Punto de entrada principal."""
    args = parse_arguments()

    if args.self_test_hid:
        raise SystemExit(run_hid_self_test(args.self_test_output))

    # Configurar logging y protección de ejecución.
    logger = setup_logging()
    data_dir = Path(os.environ.get('APPDATA', os.path.expanduser('~'))) / 'DualSenseController'
    from src.crash_reporting import install_exception_hook
    from src.single_instance import SingleInstance, notify_already_running

    install_exception_hook(data_dir / 'crashes', app_version=APP_VERSION)
    instance = SingleInstance('NikaidoDualSense')
    if not instance.acquire():
        logger.warning("Se evitó una segunda instancia de Nikaido")
        notify_already_running()
        return

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Modo DEBUG activado")

    # Verificar que estamos en Windows
    if sys.platform != 'win32':
        logger.warning("Esta aplicacion esta diseñada para Windows. Algunas funciones pueden no funcionar.")

    # Crear y ejecutar aplicacion
    app = DualSenseApp(args)

    try:
        app.start()
    except Exception as e:
        logger.critical(f"Error fatal: {e}", exc_info=True)
        from src.crash_reporting import show_fatal_error

        show_fatal_error(
            "Nikaido no pudo iniciar. Revisa los reportes dentro de "
            "AppData\\DualSenseController\\crashes y la carpeta de logs.\n\n"
            f"Detalle: {type(e).__name__}: {e}",
            title=APP_NAME,
        )
        sys.exit(1)
    finally:
        instance.release()


if __name__ == "__main__":
    main()
