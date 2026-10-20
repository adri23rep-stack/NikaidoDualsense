"""
Gestor de Perfiles - Sistema de Guardado/Carga
Maneja la persistencia de configuraciones en archivos JSON.
"""

import base64
import copy
import json
import logging
import os
import re
import shutil
import threading
import time
import zipfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any

from nikaido_version import APP_VERSION, CONFIG_VERSION, NIKA_FORMAT_VERSION
from .profile_catalog import (
    DEFAULT_PROFILE_ID,
    PROFILE_CATALOG_REVISION,
    RESERVED_PROFILE_IDS,
    canonical_profile_id,
    remap_profile_id_list,
)
from .security_utils import (
    SecurityValidationError,
    harden_private_file,
    read_json_file_limited,
    safe_json_loads,
    validate_json_complexity,
    validate_zip_member_name,
)

logger = logging.getLogger(__name__)

MAX_NIKA_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_NIKA_MEMBER_BYTES = 10 * 1024 * 1024
MAX_NIKA_MEMBERS = 32
MAX_NIKA_MACROS = 256
MAX_NIKA_LIGHT_EFFECTS = 128
MAX_CONFIG_BYTES = 20 * 1024 * 1024
MAX_NIKA_COMPRESSION_RATIO = 250
MAX_USER_IMAGE_PIXELS = 40_000_000


class ProfileManager:
    """
    Gestiona el guardado y carga de perfiles de configuracion.
    Almacena todo en un archivo JSON estructurado.
    """

    DEFAULT_CONFIG = {
        'version': CONFIG_VERSION,
        'active_profile': DEFAULT_PROFILE_ID,
        'profiles': {},  # Se llenan desde TriggerEngine
        'settings': {
            'start_minimized': False,
            # Desde 2.3.1 la bandeja pertenece al botón minimizar. Cerrar (×)
            # siempre termina Nikaido y libera los motores.
            'minimize_to_tray': True,
            'low_profile_on_minimize': True,
            'auto_connect': True,
            'onboarding': {
                'completed': False,
                'version': 0,
                'language_confirmed': False,
            },
            'assistant': {
                'enabled': False,
                'choice_made': False,
                'tips_enabled': True,
                'tip_sounds_enabled': True,
                'tip_interval_minutes': 12,
                'tip_remaining': [],
                'last_tip_id': '',
            },
            'led_color': [0, 100, 255],  # RGB
            'light_control_mode': 'nikaido',
            # ``player_number`` se conserva para migrar instalaciones viejas.
            'player_number': 1,
            'player_led': {
                'mode': 'battery',
                'player_number': 1,
                'charging_animation': True,
                'critical_blink': True,
                'critical_percent': 10,
            },
            'vibration_enabled': True,
            'trigger_intensity_multiplier': 1.0,
            'trigger_linked': False,
            'profile_gyro': {},
            # Ajustes de Nikaido Input Studio. Se mantienen fuera de los
            # perfiles de gatillo para poder personalizar tambien los perfiles
            # predefinidos sin duplicarlos.
            'profile_input_studio': {},
            'profile_overrides': {},
            'profile_library': {
                'revision': PROFILE_CATALOG_REVISION,
                'view': 'grid',
                'sort': 'recommended',
                'disclaimer_visible': True,
            },
            'dashboard': {
                'favorite_tabs': [],
            },
            'updates': {
                'check_on_startup': True,
                'check_interval_hours': 24,
                'channel': 'beta',
                'manifest_url': '',
                'last_check_unix': 0.0,
                'skipped_version': '',
            },
            'custom_light_effects': {},
            # Respaldo global de AudioManager. Cada perfil puede sobrescribir
            # estos valores dentro de ``audio_config`` y exportarlos en .Nika.
            'audio': {
                'enabled': True,
                'button_enabled': True,
                'target_mode': 'all',
                'device_id': 'default',
                'led_sync': True,
                'apply_volume': False,
                'volume': 100,
                'profile_mute_mode': 'keep',
            },
            # Remapeo avanzado: capas y bindings por gesto. El mapa basico
            # ``button_map`` se conserva abajo para instalaciones existentes.
            'advanced_mapping': {},
            'touchpad_mouse': {
                'enabled': False,
                'sensitivity': 2.5,
            },
            # Vibración enviada por el juego al control virtual y devuelta al
            # DualSense físico. El puente usa timeout para que ningún motor se
            # quede activo si ViGEm o un juego dejan de responder.
            'virtual_feedback': {
                'enabled': True,
                'strength': 1.0,
                'large_motor_scale': 1.0,
                'small_motor_scale': 1.0,
                'swap_motors': False,
                'smoothing_ms': 18,
                'idle_timeout_ms': 350,
                'minimum_output': 0,
            },
            # Reglas avanzadas de perfil por juego. ``game_profiles`` se
            # conserva fuera de settings como formato legado compatible.
            'game_profile_rules': [],
            'hidhide': {
                'auto_scan': True,
            },
            # Nikaido KeyBridge: teclado/mouse como control virtual Xbox 360
            # o DualShock 4. El motor sanitiza y migra este bloque al cargarlo.
            'keyboard_gamepad': {
                'version': 1,
                'enabled': False,
                'mode': 'xbox',
                'mapping': {},
                'poll_hz': 250,
                'stick_ramp_ms': 55,
                'stick_release_ms': 45,
                'trigger_ramp_ms': 35,
                'mouse_stick_enabled': True,
                'mouse_sensitivity': 0.045,
                'mouse_smoothing': 35,
                'mouse_decay_ms': 55,
                'mouse_invert_x': False,
                'mouse_invert_y': False,
                'normalize_diagonals': True,
                'ignore_when_nikaido_focused': True,
                'pause_hotkey': 'F8',
            },
            'bluetooth_auto_reset': False,
            'theme': 'dark',
            'appearance': {
                'background_enabled': False,
                'background_path': '',
                'background_dim': 58,
                'background_zoom': 100,
                'background_fit': 'cover',
                'background_position': 'center',
                'background_vignette': 18,
                'panel_opacity': 88,
                'sidebar_opacity': 94,
                'button_opacity': 92,
                'accent_style': 'violet',
                'ui_density': 'comfortable',
                'reduce_motion': False,
                'sidebar_collapsed': False,
            },
            'language': 'es',
            'ui_custom_enabled': False,
            'ui_layout_path': '',
            'window_geometry': {
                'width': 900,
                'height': 650,
                'x': None,
                'y': None,
            }
        },
        'custom_profiles': {},
        'macros': {},
        'button_map': {},
        'game_profiles': {},
        'favorites': ['assault_rifle', 'racing', 'bow'],
    }

    def __init__(self, config_dir: Optional[str] = None):
        # Directorio de configuracion
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            # %APPDATA%/DualSenseController
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            self.config_dir = Path(appdata) / 'DualSenseController'

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / 'profiles.json'
        self.backup_dir = self.config_dir / 'backups'
        self.backup_dir.mkdir(exist_ok=True)
        # ``profile_images`` es la ubicación histórica de iconos cuadrados.
        # Se conserva para no romper rutas guardadas antes de 2.9.8.7.
        self.profile_images_dir = self.config_dir / 'profile_images'
        self.profile_images_dir.mkdir(exist_ok=True)
        self.profile_banners_dir = self.config_dir / 'profile_banners'
        self.profile_banners_dir.mkdir(exist_ok=True)
        self.ui_backgrounds_dir = self.config_dir / 'ui_backgrounds'
        self.ui_backgrounds_dir.mkdir(exist_ok=True)

        # Estado en memoria. El lock protege guardados solicitados desde la
        # interfaz y desde callbacks de los motores.
        self._lock = threading.RLock()
        self._config: Dict[str, Any] = {}
        self._last_saved_payload: Optional[str] = None
        self._profile_catalog_migrated = False
        self._load_config()

    def _load_config(self) -> None:
        """Carga la configuracion desde el archivo JSON."""
        if self.config_file.exists():
            try:
                loaded = read_json_file_limited(
                    self.config_file,
                    label='La configuración de Nikaido',
                    max_bytes=MAX_CONFIG_BYTES,
                    max_nodes=160_000,
                    max_collection_items=20_000,
                )
                if not isinstance(loaded, dict):
                    raise SecurityValidationError('La configuración debe ser un objeto JSON.')

                # Fusionar con defaults (para nuevas claves)
                self._config = self._merge_with_defaults(loaded)
                logger.info(f"Configuracion cargada desde: {self.config_file}")
                if self._profile_catalog_migrated:
                    # Conserva un backup del archivo anterior y persiste la
                    # migración para que no se repita en cada inicio.
                    self.save_config(force=True, create_backup=True)

            except SecurityValidationError as e:
                logger.error("Configuración rechazada por seguridad: %s", e)
                self._restore_backup()
            except Exception as e:
                logger.error(f"Error cargando configuracion: {e}")
                self._config = copy.deepcopy(self.DEFAULT_CONFIG)
        else:
            logger.info("No se encontro configuracion previa. Usando defaults.")
            self._config = copy.deepcopy(self.DEFAULT_CONFIG)
            self.save_config(force=True, create_backup=False)

    def _merge_with_defaults(self, loaded: dict) -> dict:
        """Fusiona configuracion cargada con valores por defecto."""
        merged = copy.deepcopy(self.DEFAULT_CONFIG)

        def deep_merge(base: dict, override: dict) -> dict:
            result = copy.deepcopy(base)
            for key, value in override.items():
                if key not in result:
                    # Datos de plugins/versiones futuras se conservan.
                    result[key] = copy.deepcopy(value)
                    continue

                expected = result[key]
                if isinstance(expected, dict):
                    if isinstance(value, dict):
                        result[key] = deep_merge(expected, value)
                    else:
                        logger.warning(
                            "Configuración reparada: %s debía ser un objeto, no %s",
                            key,
                            type(value).__name__,
                        )
                    continue
                if isinstance(expected, list) and not isinstance(value, list):
                    logger.warning(
                        "Configuración reparada: %s debía ser una lista, no %s",
                        key,
                        type(value).__name__,
                    )
                    continue
                result[key] = copy.deepcopy(value)
            return result

        merged = deep_merge(merged, loaded)
        # La versión describe el esquema ya migrado, no la antigüedad del
        # archivo de origen. Los datos desconocidos se conservan arriba.
        merged['version'] = CONFIG_VERSION
        self._profile_catalog_migrated = self._migrate_profile_catalog(merged)
        return merged

    @staticmethod
    def _remap_profile_keyed_dict(value: Any) -> Dict[str, Any]:
        """Remapea claves de perfil y evita duplicar aliases retirados."""
        if not isinstance(value, dict):
            return {}
        result: Dict[str, Any] = {}
        # Las claves canónicas ganan sobre aliases si ambas existen.
        ordered = sorted(
            value.items(),
            key=lambda item: canonical_profile_id(item[0]) != str(item[0]),
        )
        for raw_id, payload in ordered:
            profile_id = canonical_profile_id(raw_id)
            if profile_id and profile_id not in result:
                result[profile_id] = copy.deepcopy(payload)
        return result

    @classmethod
    def _migrate_profile_catalog(cls, config: Dict[str, Any]) -> bool:
        """Migra 2.9.8.3 a la biblioteca de ocho perfiles de juego.

        Los perfiles personalizados se conservan completos. Para los perfiles
        de fábrica se restauran gatillos, RGB, nombre e identidad nuevos, pero
        se preservan imágenes personales, Input Studio, mapeo y audio.
        """
        settings = config.setdefault('settings', {})
        if not isinstance(settings, dict):
            settings = {}
            config['settings'] = settings
        library = settings.setdefault('profile_library', {})
        if not isinstance(library, dict):
            library = {}
            settings['profile_library'] = library
        try:
            revision = int(library.get('revision', 0))
        except (TypeError, ValueError, OverflowError):
            revision = 0
        if revision >= PROFILE_CATALOG_REVISION:
            return False

        config['active_profile'] = canonical_profile_id(
            config.get('active_profile', DEFAULT_PROFILE_ID)
        ) or DEFAULT_PROFILE_ID
        config['favorites'] = remap_profile_id_list(config.get('favorites', []))

        game_profiles = config.get('game_profiles', {})
        if isinstance(game_profiles, dict):
            config['game_profiles'] = {
                str(executable): canonical_profile_id(profile_id)
                for executable, profile_id in game_profiles.items()
                if str(executable).strip() and canonical_profile_id(profile_id)
            }

        rules = settings.get('game_profile_rules', [])
        if isinstance(rules, list):
            migrated_rules = []
            for raw in rules:
                if not isinstance(raw, dict):
                    continue
                item = copy.deepcopy(raw)
                if 'profile_id' in item:
                    item['profile_id'] = canonical_profile_id(item.get('profile_id'))
                migrated_rules.append(item)
            settings['game_profile_rules'] = migrated_rules

        macros = config.get('macros', {})
        if isinstance(macros, dict):
            for macro in macros.values():
                if isinstance(macro, dict) and isinstance(macro.get('profile_ids'), list):
                    macro['profile_ids'] = remap_profile_id_list(macro['profile_ids'])

        # Ajustes que sí pertenecen al usuario se remapean y conservan.
        for key in ('profile_input_studio', 'profile_gyro'):
            settings[key] = cls._remap_profile_keyed_dict(settings.get(key, {}))

        # La vibración de los perfiles integrados formaba parte del catálogo
        # anterior; se elimina para que entren las sensaciones nuevas.
        vibration = cls._remap_profile_keyed_dict(
            settings.get('profile_trigger_vibration', {})
        )
        settings['profile_trigger_vibration'] = {
            profile_id: payload
            for profile_id, payload in vibration.items()
            if profile_id not in RESERVED_PROFILE_IDS
        }

        overrides = cls._remap_profile_keyed_dict(settings.get('profile_overrides', {}))
        migrated_overrides: Dict[str, Any] = {}
        preservable = ('image_path', 'icon_path', 'banner_path', 'input_studio', 'advanced_mapping', 'audio_config')
        for profile_id, payload in overrides.items():
            if profile_id not in RESERVED_PROFILE_IDS:
                migrated_overrides[profile_id] = copy.deepcopy(payload)
                continue
            if not isinstance(payload, dict):
                continue
            kept = {
                key: copy.deepcopy(payload[key])
                for key in preservable
                if key in payload and payload[key] not in ('', None, {}, [])
            }
            if kept:
                migrated_overrides[profile_id] = kept
        settings['profile_overrides'] = migrated_overrides

        library['revision'] = PROFILE_CATALOG_REVISION
        library.setdefault('view', 'grid')
        library.setdefault('sort', 'recommended')
        library.setdefault('disclaimer_visible', True)
        logger.info(
            "Configuración migrada a la biblioteca de perfiles revisión %s",
            PROFILE_CATALOG_REVISION,
        )
        return True

    def _serialize_config(self) -> str:
        """Serializa con un formato estable para detectar cambios reales."""
        return json.dumps(self._config, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    def save_config(self, *, force: bool = False, create_backup: bool = True) -> bool:
        """Guarda la configuración de forma atómica y solo si cambió.

        Antes se creaba un backup y se reescribía todo el JSON con cada paso
        de un slider. Además de trabar la interfaz, eso podía dejar un archivo
        incompleto si Windows cerraba la aplicación durante la escritura.
        """
        temp_file = self.config_file.with_suffix(self.config_file.suffix + '.tmp')
        try:
            with self._lock:
                payload = self._serialize_config()
                if not force and payload == self._last_saved_payload:
                    return True

                previous = None
                if self.config_file.exists():
                    try:
                        previous = self.config_file.read_text(encoding='utf-8')
                    except OSError:
                        previous = None
                if not force and previous == payload:
                    self._last_saved_payload = payload
                    return True

                if create_backup and previous is not None and previous != payload:
                    self._create_backup()

                with open(temp_file, 'w', encoding='utf-8', newline='') as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())

                # Antivirus, indexadores y sincronizadores pueden retener el
                # archivo unos milisegundos en Windows. Reintentar evita perder
                # un guardado válido por una carrera externa muy breve.
                replace_error = None
                for attempt in range(4):
                    try:
                        os.replace(temp_file, self.config_file)
                        replace_error = None
                        break
                    except OSError as exc:
                        replace_error = exc
                        if attempt >= 3:
                            break
                        time.sleep(0.025 * (attempt + 1))
                if replace_error is not None:
                    raise replace_error
                harden_private_file(self.config_file)
                self._last_saved_payload = payload

            logger.debug("Configuración guardada exitosamente")
            return True
        except Exception as e:
            logger.error("Error guardando configuración: %s", e)
            try:
                temp_file.unlink(missing_ok=True)
            except OSError:
                pass
            return False

    def _create_backup(self) -> None:
        """Crea un backup de la configuracion actual."""
        try:
            if self.config_file.exists():
                from datetime import datetime

                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                backup_file = self.backup_dir / f'profiles_backup_{timestamp}.json'

                shutil.copy2(self.config_file, backup_file)
                harden_private_file(backup_file)

                # Mantener solo los ultimos 10 backups
                backups = sorted(self.backup_dir.glob('profiles_backup_*.json'))
                if len(backups) > 10:
                    for old_backup in backups[:-10]:
                        old_backup.unlink()

        except Exception as e:
            logger.warning(f"No se pudo crear backup: {e}")

    def _restore_backup(self) -> None:
        """Restaura el backup más reciente y reemplaza el JSON dañado."""
        try:
            backups = sorted(self.backup_dir.glob('profiles_backup_*.json'), reverse=True)
            restored = None
            for backup in backups:
                try:
                    candidate = read_json_file_limited(
                        backup,
                        label='El respaldo de configuración',
                        max_bytes=MAX_CONFIG_BYTES,
                        max_nodes=160_000,
                        max_collection_items=20_000,
                    )
                    if isinstance(candidate, dict):
                        restored = self._merge_with_defaults(candidate)
                        logger.info("Configuración restaurada desde backup: %s", backup)
                        break
                except (OSError, SecurityValidationError, TypeError) as exc:
                    logger.warning("Backup ignorado por estar dañado (%s): %s", backup, exc)
            self._config = restored or copy.deepcopy(self.DEFAULT_CONFIG)
            # El archivo principal seguía corrupto y volvía a fallar en cada
            # inicio. Se reemplaza sin crear otro backup de ese contenido.
            self._last_saved_payload = None
            self.save_config(force=True, create_backup=False)
        except Exception as e:
            logger.error("Error restaurando backup: %s", e)
            self._config = copy.deepcopy(self.DEFAULT_CONFIG)

    # ===== Getters =====

    def get_active_profile(self) -> str:
        """Devuelve el ID del perfil activo."""
        with self._lock:
            return canonical_profile_id(self._config.get('active_profile', DEFAULT_PROFILE_ID)) or DEFAULT_PROFILE_ID

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Obtiene un valor de configuracion."""
        keys = key.split('.')
        with self._lock:
            value = self._config.get('settings', {})
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k)
                else:
                    return copy.deepcopy(default)
            return copy.deepcopy(value if value is not None else default)

    def get_custom_profiles(self) -> Dict[str, dict]:
        """Devuelve los perfiles personalizados guardados."""
        with self._lock:
            value = self._config.get('custom_profiles', {})
            return copy.deepcopy(value) if isinstance(value, dict) else {}

    def get_macros(self) -> Dict[str, dict]:
        """Devuelve las macros guardadas."""
        with self._lock:
            value = self._config.get('macros', {})
            return copy.deepcopy(value) if isinstance(value, dict) else {}

    def get_button_map(self) -> Dict[str, str]:
        """Devuelve el remapeo de botones guardado (fisico -> salida)."""
        with self._lock:
            value = self._config.get('button_map', {})
            return copy.deepcopy(value) if isinstance(value, dict) else {}

    def get_advanced_mapping(self) -> Dict[str, Any]:
        """Devuelve capas y bindings del remapeo avanzado."""
        return self.get_setting('advanced_mapping', {})

    def get_game_profiles(self) -> Dict[str, str]:
        """Devuelve el mapa exe -> perfil con IDs antiguos ya resueltos."""
        with self._lock:
            value = self._config.get('game_profiles', {})
            if not isinstance(value, dict):
                return {}
            return {
                str(executable): canonical_profile_id(profile_id)
                for executable, profile_id in value.items()
                if str(executable).strip() and canonical_profile_id(profile_id)
            }

    def get_favorites(self) -> list:
        """Devuelve la lista de perfiles favoritos."""
        with self._lock:
            value = self._config.get('favorites', [])
            source = value if isinstance(value, list) else self.DEFAULT_CONFIG['favorites']
            return remap_profile_id_list(source)

    # ===== Setters =====

    def set_active_profile(self, profile_id: str) -> None:
        """Establece el perfil activo."""
        with self._lock:
            self._config['active_profile'] = canonical_profile_id(profile_id) or DEFAULT_PROFILE_ID

    def set_setting(self, key: str, value: Any) -> None:
        """Establece un valor de configuracion."""
        keys = key.split('.')
        if not keys or not keys[-1]:
            raise ValueError("La clave de configuración no puede estar vacía")
        with self._lock:
            settings = self._config.setdefault('settings', {})
            if not isinstance(settings, dict):
                settings = {}
                self._config['settings'] = settings
            for k in keys[:-1]:
                child = settings.get(k)
                if not isinstance(child, dict):
                    child = {}
                    settings[k] = child
                settings = child
            settings[keys[-1]] = copy.deepcopy(value)

    def set_custom_profiles(self, profiles: Dict[str, dict]) -> None:
        """Guarda perfiles personalizados."""
        with self._lock:
            self._config['custom_profiles'] = copy.deepcopy(profiles)

    def set_macros(self, macros: Dict[str, dict]) -> None:
        """Guarda las macros."""
        with self._lock:
            self._config['macros'] = copy.deepcopy(macros)

    def set_button_map(self, mapping: Dict[str, str]) -> None:
        """Guarda el remapeo de botones."""
        with self._lock:
            self._config['button_map'] = copy.deepcopy(mapping)

    def set_advanced_mapping(self, mapping: Dict[str, Any]) -> None:
        """Guarda capas y bindings del remapeo avanzado."""
        self.set_setting('advanced_mapping', mapping)

    def set_game_profiles(self, mapping: Dict[str, str]) -> None:
        """Guarda el mapa de exe -> profile_id con IDs canónicos."""
        parsed = {
            str(executable): canonical_profile_id(profile_id)
            for executable, profile_id in (mapping.items() if isinstance(mapping, dict) else [])
            if str(executable).strip() and canonical_profile_id(profile_id)
        }
        with self._lock:
            self._config['game_profiles'] = parsed

    @staticmethod
    def _optimized_image_copy(
        source_path: str,
        destination_stem: Path,
        *,
        source_limit: int,
        max_size: tuple[int, int],
        jpeg_quality: int = 91,
    ) -> str:
        """Valida, orienta y limita una imagen antes de guardarla.

        Evita fondos gigantes que disparen el consumo de RAM y no elimina la
        imagen anterior hasta que la nueva copia se haya escrito completa.
        """
        source = Path(source_path)
        if not source.is_file() or source.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}:
            return ''
        try:
            from PIL import Image, ImageOps, UnidentifiedImageError
        except ImportError as exc:
            logger.error('Pillow no está disponible para procesar imágenes: %s', exc)
            return ''
        try:
            if source.stat().st_size > source_limit:
                return ''

            with Image.open(source) as probe:
                width, height = probe.size
                if width <= 0 or height <= 0 or width * height > MAX_USER_IMAGE_PIXELS:
                    return ''
                probe.verify()
            with Image.open(source) as opened:
                image = ImageOps.exif_transpose(opened)
                image.load()
                image = image.copy()

            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            has_alpha = image.mode in {'RGBA', 'LA'} or (
                image.mode == 'P' and 'transparency' in image.info
            )
            extension = '.png' if has_alpha else '.jpg'
            destination = destination_stem.with_suffix(extension)
            temp = destination.with_suffix(destination.suffix + '.tmp')
            destination.parent.mkdir(parents=True, exist_ok=True)
            if has_alpha:
                if image.mode not in {'RGBA', 'LA'}:
                    image = image.convert('RGBA')
                image.save(temp, format='PNG', optimize=True)
            else:
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                image.save(
                    temp,
                    format='JPEG',
                    quality=max(75, min(95, int(jpeg_quality))),
                    optimize=True,
                    progressive=True,
                )
            os.replace(temp, destination)
            for old in destination.parent.glob(f'{destination_stem.name}.*'):
                if old != destination and old.is_file():
                    try:
                        old.unlink()
                    except OSError:
                        pass
            return str(destination)
        except (OSError, ValueError, UnidentifiedImageError) as exc:
            logger.warning('Imagen rechazada o ilegible (%s): %s', source, exc)
            return ''
        except Exception as exc:
            logger.error('No se pudo optimizar la imagen %s: %s', source, exc)
            return ''

    @staticmethod
    def _is_valid_image_file(path: Path, *, size_limit: int = MAX_NIKA_MEMBER_BYTES) -> bool:
        if not path.is_file() or path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}:
            return False
        try:
            if path.stat().st_size > size_limit:
                return False
            from PIL import Image

            with Image.open(path) as image:
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > MAX_USER_IMAGE_PIXELS:
                    return False
                image.verify()
            return True
        except Exception:
            return False

    def validate_profile_image(self, source_path: str) -> bool:
        """Valida una imagen antes de permitir que Qt la muestre o la guarde."""
        return self._is_valid_image_file(Path(source_path), size_limit=MAX_NIKA_MEMBER_BYTES)

    @staticmethod
    def _safe_profile_asset_id(profile_id: str) -> str:
        return re.sub(r'[^a-zA-Z0-9_-]+', '_', str(profile_id)).strip('_') or 'profile'

    def store_profile_icon(self, source_path: str, profile_id: str) -> str:
        """Guarda el icono cuadrado del perfil en la ubicación histórica segura."""
        safe_id = self._safe_profile_asset_id(profile_id)
        return self._optimized_image_copy(
            source_path,
            self.profile_images_dir / safe_id,
            source_limit=MAX_NIKA_MEMBER_BYTES,
            max_size=(1024, 1024),
            jpeg_quality=91,
        )

    def store_profile_banner(self, source_path: str, profile_id: str) -> str:
        """Guarda una portada horizontal optimizada para la galería."""
        safe_id = self._safe_profile_asset_id(profile_id)
        return self._optimized_image_copy(
            source_path,
            self.profile_banners_dir / safe_id,
            source_limit=MAX_NIKA_MEMBER_BYTES,
            max_size=(2560, 1440),
            jpeg_quality=92,
        )

    def store_profile_image(self, source_path: str, profile_id: str) -> str:
        """Alias compatible de versiones anteriores: la imagen es el icono."""
        return self.store_profile_icon(source_path, profile_id)

    def remove_profile_icon(self, profile_id: str) -> None:
        safe_id = self._safe_profile_asset_id(profile_id)
        for image in self.profile_images_dir.glob(f'{safe_id}.*'):
            try:
                image.unlink()
            except OSError:
                pass

    def remove_profile_banner(self, profile_id: str) -> None:
        safe_id = self._safe_profile_asset_id(profile_id)
        for image in self.profile_banners_dir.glob(f'{safe_id}.*'):
            try:
                image.unlink()
            except OSError:
                pass

    def remove_profile_image(self, profile_id: str) -> None:
        """Alias compatible de versiones anteriores."""
        self.remove_profile_icon(profile_id)

    def store_ui_background(self, source_path: str) -> str:
        """Guarda un fondo validado, orientado y optimizado en AppData."""
        stored = self._optimized_image_copy(
            source_path,
            self.ui_backgrounds_dir / 'background',
            source_limit=20 * 1024 * 1024,
            max_size=(4096, 4096),
            jpeg_quality=92,
        )
        if not stored:
            logger.warning('No se pudo guardar el fondo de interfaz: %s', source_path)
        else:
            # Una imagen propia reemplaza cualquier fondo incluido recordado.
            self.set_setting('ui_wallpaper_key', '')
        return stored

    def store_bundled_wallpaper(self, key: str) -> str:
        """Aplica uno de los fondos incluidos y recuerda cuál se eligió."""
        from .wallpapers import find_wallpaper, image_path

        wallpaper = find_wallpaper(key)
        if wallpaper is None:
            return ''
        stored = self.store_ui_background(str(image_path(wallpaper)))
        if stored:
            self.set_setting('ui_wallpaper_key', wallpaper.key)
        return stored

    def current_wallpaper_key(self) -> str:
        """Clave del fondo incluido activo, o '' si es una imagen propia o ninguno."""
        from .wallpapers import find_wallpaper

        key = str(self.get_setting('ui_wallpaper_key', '') or '')
        return key if find_wallpaper(key) else ''

    def remove_ui_background(self) -> None:
        self.set_setting('ui_wallpaper_key', '')
        for image in self.ui_backgrounds_dir.glob('background.*'):
            try:
                image.unlink()
            except OSError:
                pass
        self.set_setting('appearance.background_enabled', False)
        self.set_setting('appearance.background_path', '')

    def add_favorite(self, profile_id: str) -> None:
        """Agrega un perfil a favoritos usando su ID canónico."""
        resolved = canonical_profile_id(profile_id)
        if not resolved:
            return
        with self._lock:
            favorites = self._config.setdefault('favorites', [])
            favorites[:] = remap_profile_id_list(favorites)
            if resolved not in favorites:
                favorites.append(resolved)

    def remove_favorite(self, profile_id: str) -> None:
        """Elimina un perfil de favoritos aunque llegue un alias antiguo."""
        resolved = canonical_profile_id(profile_id)
        with self._lock:
            favorites = self._config.setdefault('favorites', [])
            favorites[:] = remap_profile_id_list(favorites)
            if resolved in favorites:
                favorites.remove(resolved)

    def save_window_geometry(self, width: int, height: int, x: Optional[int], y: Optional[int]) -> None:
        """Guarda la geometria de la ventana."""
        self.set_setting('window_geometry.width', width)
        self.set_setting('window_geometry.height', height)
        self.set_setting('window_geometry.x', x)
        self.set_setting('window_geometry.y', y)

    def get_window_geometry(self) -> Dict[str, Optional[int]]:
        """Obtiene la geometria guardada de la ventana."""
        return {
            'width': self.get_setting('window_geometry.width', 900),
            'height': self.get_setting('window_geometry.height', 650),
            'x': self.get_setting('window_geometry.x'),
            'y': self.get_setting('window_geometry.y'),
        }

    # ===== Import/Export =====

    @staticmethod
    def _advanced_mapping_payload(profile: Dict[str, Any]) -> Dict[str, Any]:
        mapping = profile.get('advanced_mapping', profile.get('advanced_mapping_config', {}))
        return mapping if isinstance(mapping, dict) else {}

    @classmethod
    def _iter_advanced_bindings(cls, profile: Dict[str, Any]):
        mapping = cls._advanced_mapping_payload(profile)
        layers = mapping.get('layers', {})
        if not isinstance(layers, dict):
            return
        for layer_map in layers.values():
            if not isinstance(layer_map, dict):
                continue
            for bindings in layer_map.values():
                if isinstance(bindings, dict):
                    bindings = [bindings]
                if not isinstance(bindings, list):
                    continue
                for binding in bindings:
                    if isinstance(binding, dict):
                        yield binding

    @classmethod
    def _referenced_macro_ids(cls, profile: Dict[str, Any]) -> set[str]:
        return {
            str(binding.get('value', '') or '')
            for binding in cls._iter_advanced_bindings(profile)
            if str(binding.get('action_type', '')).lower() == 'macro'
            and str(binding.get('value', '') or '')
        }

    @classmethod
    def _rewrite_imported_references(
        cls,
        profile: Dict[str, Any],
        *,
        macro_id_map: Dict[str, str],
        source_profile_id: str,
        imported_profile_id: str,
    ) -> None:
        """Actualiza enlaces internos después de generar IDs libres de colisión."""
        for binding in cls._iter_advanced_bindings(profile):
            action_type = str(binding.get('action_type', '')).lower()
            value = str(binding.get('value', '') or '')
            if action_type == 'macro' and value in macro_id_map:
                binding['value'] = macro_id_map[value]
            elif action_type == 'profile' and source_profile_id and value == source_profile_id:
                binding['value'] = imported_profile_id

    def _store_imported_profile_asset(
        self,
        blob: bytes,
        archive_name: str,
        profile_id: str,
        *,
        kind: str,
    ) -> str:
        """Valida y guarda un icono o banner incrustado en un paquete .Nika."""
        extension = Path(archive_name).suffix.lower()
        if extension not in {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}:
            return ''
        if len(blob) > MAX_NIKA_MEMBER_BYTES:
            raise ValueError('La imagen del perfil supera el límite de 10 MB')
        target_dir = self.profile_banners_dir if kind == 'banner' else self.profile_images_dir
        temporary = target_dir / f'.{profile_id}_{kind}_import{extension}'
        try:
            temporary.write_bytes(blob)
            stored = (
                self.store_profile_banner(str(temporary), profile_id)
                if kind == 'banner'
                else self.store_profile_icon(str(temporary), profile_id)
            )
            if not stored:
                raise ValueError(f'El {kind} incluido en el perfil no es válido')
            return stored
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _store_imported_profile_image(
        self, image_blob: bytes, image_file: str, profile_id: str
    ) -> str:
        """Alias legado para paquetes que solo contenían ``image_file``."""
        return self._store_imported_profile_asset(
            image_blob, image_file, profile_id, kind='icon'
        )

    def export_profile(
        self,
        profile_id: str,
        file_path: str,
        profile_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Exporta un perfil con icono, banner, ajustes, macros y luces."""
        temp_target: Optional[Path] = None
        try:
            with self._lock:
                config_snapshot = copy.deepcopy(self._config)
            all_profiles = {
                **config_snapshot.get('profiles', {}),
                **config_snapshot.get('custom_profiles', {}),
            }
            raw_profile = copy.deepcopy(profile_data or all_profiles.get(profile_id))
            if not isinstance(raw_profile, dict):
                logger.warning("Perfil no encontrado: %s", profile_id)
                return False

            icon_path = Path(
                str(raw_profile.get('icon_path') or raw_profile.get('image_path') or '')
            )
            banner_path = Path(str(raw_profile.get('banner_path') or ''))
            selected_profile = copy.deepcopy(raw_profile)
            selected_profile['image_path'] = ''
            selected_profile['icon_path'] = ''
            selected_profile['banner_path'] = ''

            target = Path(file_path)
            if target.suffix.lower() == '.json':
                payload: Dict[str, Any] = {'version': '2.0', 'profile': selected_profile}
                if self._is_valid_image_file(icon_path):
                    encoded = base64.b64encode(icon_path.read_bytes()).decode('ascii')
                    payload['image_name'] = icon_path.name
                    payload['image_data'] = encoded
                    payload['icon_name'] = icon_path.name
                    payload['icon_data'] = encoded
                if self._is_valid_image_file(banner_path):
                    payload['banner_name'] = banner_path.name
                    payload['banner_data'] = base64.b64encode(
                        banner_path.read_bytes()
                    ).decode('ascii')
                temp_target = target.with_suffix(target.suffix + '.tmp')
                temp_target.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False) + '\n',
                    encoding='utf-8',
                )
                os.replace(temp_target, target)
                return True

            if target.suffix.lower() != '.nika':
                target = target.with_suffix('.Nika')
            target.parent.mkdir(parents=True, exist_ok=True)

            macros: Dict[str, Any] = {}
            referenced_macros = self._referenced_macro_ids(selected_profile)
            for macro_id, payload in config_snapshot.get('macros', {}).items():
                if not isinstance(payload, dict):
                    continue
                assigned = payload.get('profile_ids', payload.get('profiles', []))
                if isinstance(assigned, str):
                    assigned = [assigned]
                if profile_id in (assigned or []) or str(macro_id) in referenced_macros:
                    macros[str(macro_id)] = copy.deepcopy(payload)

            light_config = selected_profile.get('light_config', {}) or {}
            custom_effects: Dict[str, Any] = {}
            custom_id = str(light_config.get('custom_id', '') or '')
            if custom_id:
                effect = self.get_setting('custom_light_effects', {}).get(custom_id)
                if isinstance(effect, dict):
                    custom_effects[custom_id] = copy.deepcopy(effect)

            manifest: Dict[str, Any] = {
                'format': 'Nikaido Profile Package',
                'format_version': NIKA_FORMAT_VERSION,
                'app_version': APP_VERSION,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'profile_id': profile_id,
                'profile_name': selected_profile.get('name', profile_id),
                'contents': {
                    'profile': True,
                    # image se mantiene para lectores antiguos.
                    'image': False,
                    'icon': False,
                    'banner': False,
                    'macros': len(macros),
                    'custom_light_effects': len(custom_effects),
                    'advanced_mapping': bool(
                        selected_profile.get('advanced_mapping')
                        or selected_profile.get('advanced_mapping_config')
                    ),
                    'audio': bool(selected_profile.get('audio_config')),
                },
            }

            temp_target = target.with_suffix(target.suffix + '.tmp')
            with zipfile.ZipFile(
                temp_target, 'w', compression=zipfile.ZIP_DEFLATED
            ) as archive:
                if self._is_valid_image_file(icon_path):
                    icon_name = 'assets/profile' + icon_path.suffix.lower()
                    archive.write(icon_path, icon_name)
                    manifest['contents']['image'] = True
                    manifest['contents']['icon'] = True
                    manifest['image_file'] = icon_name
                    manifest['icon_file'] = icon_name
                if self._is_valid_image_file(banner_path):
                    banner_name = 'assets/banner' + banner_path.suffix.lower()
                    archive.write(banner_path, banner_name)
                    manifest['contents']['banner'] = True
                    manifest['banner_file'] = banner_name
                archive.writestr(
                    'profile.json',
                    json.dumps(selected_profile, ensure_ascii=False, indent=2),
                )
                archive.writestr(
                    'macros.json', json.dumps(macros, ensure_ascii=False, indent=2)
                )
                archive.writestr(
                    'light_effects.json',
                    json.dumps(custom_effects, ensure_ascii=False, indent=2),
                )
                archive.writestr(
                    'manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2)
                )
            os.replace(temp_target, target)
            logger.info("Perfil .Nika exportado a: %s", target)
            return True
        except Exception as exc:
            logger.error("Error exportando perfil: %s", exc)
            try:
                if temp_target is not None:
                    temp_target.unlink(missing_ok=True)
            except OSError:
                pass
            return False

    def import_profile(self, file_path: str) -> Optional[str]:
        """Importa .Nika de forma transaccional con icono y banner separados."""
        stored_icon = ''
        stored_banner = ''
        try:
            source = Path(file_path)
            if not source.is_file():
                raise ValueError('El archivo de perfil no existe')
            if source.stat().st_size > MAX_NIKA_ARCHIVE_BYTES:
                raise ValueError('El archivo de perfil supera el límite de 25 MB')

            source_profile_id = ''
            icon_blob = None
            banner_blob = None
            icon_file = ''
            banner_file = ''
            legacy_single_image = False
            if source.suffix.lower() == '.nika' or zipfile.is_zipfile(source):
                with zipfile.ZipFile(source, 'r') as archive:
                    infos = archive.infolist()
                    if len(infos) > MAX_NIKA_MEMBERS:
                        raise ValueError('El paquete .Nika contiene demasiados archivos')
                    if any(info.flag_bits & 0x1 for info in infos):
                        raise ValueError('Los paquetes .Nika cifrados no son compatibles')
                    if any(info.file_size > MAX_NIKA_MEMBER_BYTES for info in infos):
                        raise ValueError('El paquete .Nika contiene un archivo demasiado grande')
                    if sum(info.file_size for info in infos) > MAX_NIKA_ARCHIVE_BYTES:
                        raise ValueError('El contenido descomprimido del paquete .Nika es demasiado grande')
                    names = [
                        validate_zip_member_name(info.filename, label='paquete .Nika')
                        for info in infos
                        if not info.is_dir()
                    ]
                    if len(set(names)) != len(names):
                        raise ValueError('El paquete .Nika contiene nombres de archivo duplicados')
                    for info in infos:
                        if info.is_dir() or info.file_size <= 0:
                            continue
                        compressed = max(1, int(info.compress_size or 0))
                        if info.file_size / compressed > MAX_NIKA_COMPRESSION_RATIO:
                            raise ValueError('El paquete .Nika contiene compresión sospechosa')
                    available = set(names)
                    if 'manifest.json' not in available or 'profile.json' not in available:
                        raise ValueError('El paquete .Nika no contiene manifest.json y profile.json')

                    def read_json(name: str, fallback: Any = None) -> Any:
                        if name not in available:
                            return copy.deepcopy(fallback)
                        return safe_json_loads(
                            archive.read(name),
                            label=f'{name} del paquete .Nika',
                            max_bytes=MAX_NIKA_MEMBER_BYTES,
                            max_nodes=80_000,
                            max_collection_items=10_000,
                        )

                    manifest = read_json('manifest.json', {})
                    if not isinstance(manifest, dict) or manifest.get('format') != 'Nikaido Profile Package':
                        raise ValueError('Formato .Nika no reconocido')
                    if int(manifest.get('format_version', 1)) > NIKA_FORMAT_VERSION:
                        raise ValueError('Este paquete .Nika requiere una versión más nueva de Nikaido')
                    source_profile_id = str(manifest.get('profile_id', '') or '')
                    profile = read_json('profile.json', {})
                    macros = read_json('macros.json', {})
                    custom_effects = read_json('light_effects.json', {})

                    legacy_single_image = (
                        not manifest.get('icon_file')
                        and bool(manifest.get('image_file'))
                        and not manifest.get('banner_file')
                    )
                    icon_file = str(
                        manifest.get('icon_file', manifest.get('image_file', '')) or ''
                    )
                    banner_file = str(manifest.get('banner_file', '') or '')
                    if icon_file:
                        icon_file = validate_zip_member_name(icon_file, label='paquete .Nika')
                    if banner_file:
                        banner_file = validate_zip_member_name(banner_file, label='paquete .Nika')
                    if icon_file and icon_file in available:
                        icon_blob = archive.read(icon_file)
                    if banner_file and banner_file in available:
                        banner_blob = archive.read(banner_file)
            else:
                data = read_json_file_limited(
                    source,
                    label='El perfil JSON',
                    max_bytes=MAX_NIKA_ARCHIVE_BYTES,
                    max_nodes=100_000,
                    max_collection_items=10_000,
                )
                if not isinstance(data, dict):
                    raise ValueError('Archivo de perfil inválido')
                profile = copy.deepcopy(data.get('profile'))
                macros, custom_effects = {}, {}
                legacy_single_image = (
                    'icon_data' not in data
                    and bool(data.get('image_data'))
                    and not data.get('banner_data')
                )
                icon_file = str(data.get('icon_name', data.get('image_name', '')) or '')
                banner_file = str(data.get('banner_name', '') or '')
                encoded_icon = data.get('icon_data', data.get('image_data'))
                encoded_banner = data.get('banner_data')
                if encoded_icon:
                    icon_blob = base64.b64decode(encoded_icon, validate=True)
                if encoded_banner:
                    banner_blob = base64.b64decode(encoded_banner, validate=True)

            if not isinstance(profile, dict):
                raise ValueError('Archivo de perfil inválido')
            if macros is not None and not isinstance(macros, dict):
                raise ValueError('La biblioteca de macros del paquete es inválida')
            if custom_effects is not None and not isinstance(custom_effects, dict):
                raise ValueError('Los efectos de luz del paquete son inválidos')
            validate_json_complexity(
                profile,
                label='El perfil importado',
                max_nodes=60_000,
                max_collection_items=8_000,
                max_string_length=32_768,
            )
            macros = macros or {}
            custom_effects = custom_effects or {}
            if len(macros) > MAX_NIKA_MACROS:
                raise ValueError('El paquete .Nika contiene demasiadas macros')
            if len(custom_effects) > MAX_NIKA_LIGHT_EFFECTS:
                raise ValueError('El paquete .Nika contiene demasiados efectos de luz')

            profile = copy.deepcopy(profile)
            profile_name = str(profile.get('name', 'Imported')).strip()[:120] or 'Imported'
            profile['name'] = profile_name
            safe_name = re.sub(r'[^a-z0-9]+', '_', profile_name.lower()).strip('_') or 'profile'
            profile_id = f"imported_{safe_name}_{uuid.uuid4().hex[:6]}"

            imported_macros: Dict[str, Dict[str, Any]] = {}
            macro_id_map: Dict[str, str] = {}
            from .macro_engine import Macro

            for old_id, payload in macros.items():
                if not isinstance(payload, dict):
                    continue
                old_key = str(old_id)
                new_id = f"macro_{uuid.uuid4().hex[:10]}"
                macro_id_map[old_key] = new_id
                imported = copy.deepcopy(payload)
                imported['id'] = new_id
                imported['profile_ids'] = [profile_id]
                imported_macros[new_id] = Macro.from_dict(imported).to_dict()

            self._rewrite_imported_references(
                profile,
                macro_id_map=macro_id_map,
                source_profile_id=source_profile_id,
                imported_profile_id=profile_id,
            )

            from .trigger_engine import WeaponProfile
            from .light_effects import LightEffectEngine

            raw_advanced_mapping = profile.get(
                'advanced_mapping', profile.get('advanced_mapping_config', {})
            )
            profile = WeaponProfile.from_dict(profile).to_dict()
            if (
                isinstance(raw_advanced_mapping, dict)
                and isinstance(raw_advanced_mapping.get('layers', {}), dict)
            ):
                profile['advanced_mapping'] = copy.deepcopy(raw_advanced_mapping)
            custom_effects = LightEffectEngine.sanitize_custom_effects(custom_effects)

            with self._lock:
                current_effects = copy.deepcopy(
                    self._config.get('settings', {}).get('custom_light_effects', {})
                )
            if not isinstance(current_effects, dict):
                current_effects = {}
            light_config = profile.get('light_config')
            for effect_id, payload in custom_effects.items():
                if not isinstance(payload, dict):
                    continue
                original_id = str(effect_id)[:120]
                if not original_id:
                    continue
                imported_id = original_id
                existing = current_effects.get(imported_id)
                if existing is not None and existing != payload:
                    imported_id = f"{original_id}_{uuid.uuid4().hex[:6]}"
                current_effects[imported_id] = copy.deepcopy(payload)
                if (
                    imported_id != original_id
                    and isinstance(light_config, dict)
                    and str(light_config.get('custom_id', '')) == original_id
                ):
                    light_config['custom_id'] = imported_id

            if icon_blob:
                stored_icon = self._store_imported_profile_asset(
                    icon_blob, icon_file, profile_id, kind='icon'
                )
            if banner_blob:
                stored_banner = self._store_imported_profile_asset(
                    banner_blob, banner_file, profile_id, kind='banner'
                )
            elif legacy_single_image and icon_blob:
                # Las versiones anteriores usaban una sola imagen como icono
                # y portada. Se guarda una copia física separada para que las
                # ediciones futuras sean independientes.
                stored_banner = self._store_imported_profile_asset(
                    icon_blob, icon_file, profile_id, kind='banner'
                )
            profile['image_path'] = stored_icon
            profile['icon_path'] = stored_icon
            profile['banner_path'] = stored_banner

            with self._lock:
                self._config.setdefault('custom_profiles', {})[profile_id] = profile
                self._config.setdefault('macros', {}).update(imported_macros)
                settings = self._config.setdefault('settings', {})
                if not isinstance(settings, dict):
                    settings = {}
                    self._config['settings'] = settings
                settings['custom_light_effects'] = current_effects
            logger.info("Perfil importado desde paquete: %s", profile_id)
            return profile_id
        except Exception as exc:
            logger.error("Error importando perfil: %s", exc)
            for stored in (stored_icon, stored_banner):
                if stored:
                    try:
                        Path(stored).unlink(missing_ok=True)
                    except OSError:
                        pass
            return None

    def reset_to_defaults(self, *, purge_assets: bool = False) -> None:
        """Restaura la configuración y opcionalmente elimina recursos huérfanos."""
        with self._lock:
            self._config = copy.deepcopy(self.DEFAULT_CONFIG)
            self._last_saved_payload = None
        if purge_assets:
            for directory in (self.profile_images_dir, self.profile_banners_dir, self.ui_backgrounds_dir):
                for asset in directory.iterdir():
                    if asset.is_file():
                        try:
                            asset.unlink()
                        except OSError:
                            logger.warning("No se pudo eliminar recurso durante el reset: %s", asset)
        self.save_config(force=True)
        logger.info("Configuración restaurada a valores por defecto")

    def get_config_file_path(self) -> str:
        """Devuelve la ruta del archivo de configuracion."""
        return str(self.config_file)

    def get_config_dir(self) -> str:
        """Devuelve el directorio de configuracion."""
        return str(self.config_dir)
