"""
Interfaz Grafica - DualSense Controller
Aplicacion de escritorio moderna usando CustomTkinter.
Modo oscuro, esquinas redondeadas, indicadores visuales en tiempo real.
"""

import logging
import math
import re
import time
import tkinter as tk
import unicodedata
from pathlib import Path
from tkinter import messagebox, filedialog, colorchooser
from typing import Any, Optional, Callable, Dict, List

try:
    from src.emulator import EmulationMode
except ImportError:
    class EmulationMode:
        NONE = "none"
        XBOX = "xbox"
        PS4 = "ps4"

try:
    import customtkinter as ctk
    from customtkinter import (
        CTk, CTkFrame, CTkLabel, CTkButton, CTkSlider, CTkSwitch,
        CTkProgressBar, CTkOptionMenu, CTkTabview, CTkSegmentedButton, CTkEntry,
        CTkScrollableFrame, CTkImage
    )
    CUSTOMTK_AVAILABLE = True
except ImportError:
    CUSTOMTK_AVAILABLE = False
    # Fallback a tkinter estandar
    from tkinter import ttk
    CTk = tk.Tk
    CTkFrame = tk.Frame
    CTkLabel = tk.Label
    CTkButton = tk.Button
    CTkSlider = tk.Scale
    CTkSwitch = tk.Checkbutton
    CTkProgressBar = ttk.Progressbar
    CTkOptionMenu = ttk.Combobox
    CTkTabview = ttk.Notebook
    CTkEntry = tk.Entry
    CTkScrollableFrame = tk.Frame

from PIL import Image, ImageDraw, ImageFont
try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None

logger = logging.getLogger(__name__)


class DualSenseGUI:
    """
    Interfaz grafica principal para el controlador DualSense.
    """

    # Colores del tema — grafito calido con acento indigo (identidad propia,
    # no el azul/negro clonado de GitHub) y un ambar/cobre exclusivo para los
    # gatillos adaptativos, la funcion insignia de la app.
    COLORS = {
        'bg_primary': '#131316',
        'bg_secondary': '#1a1a1f',
        'bg_card': '#201f26',
        'accent': '#7C6FF0',
        'accent_hover': '#8F84F5',
        'trigger_accent': '#E8A33D',
        'trigger_accent_hover': '#F0B65C',
        'success': '#4FAE84',
        'warning': '#E8A33D',
        'warning_hover': '#F0B65C',
        'danger': '#E5484D',
        'danger_hover': '#F0666B',
        'text_primary': '#F2F1F5',
        'text_secondary': '#8B8B96',
        'border': '#2C2B33',
        'battery_high': '#4FAE84',
        'battery_medium': '#E8A33D',
        'battery_low': '#E5484D',
    }

    # Escala tipografica: Segoe UI (nativa de Windows 11) para texto de UI,
    # Consolas para lecturas numericas/telemetria (posicion de gatillos,
    # bateria) dandole un aire de consola de diagnostico HID, y Segoe UI
    # Emoji para que los iconos se vean a color en Windows 11.
    FONTS = {
        'display': ("Segoe UI Semibold", 20),
        'display_sm': ("Segoe UI Semibold", 18),
        'title': ("Segoe UI Semibold", 16),
        'title_sm': ("Segoe UI Semibold", 14),
        'subtitle': ("Segoe UI Semibold", 13),
        'body_bold': ("Segoe UI Semibold", 12),
        'body': ("Segoe UI", 12),
        'small_bold': ("Segoe UI Semibold", 11),
        'small': ("Segoe UI", 11),
        'caption': ("Segoe UI", 10),
        'micro': ("Segoe UI", 9),
        'mono': ("Consolas", 12),
        'mono_bold': ("Consolas", 12, "bold"),
        'icon_xl': ("Segoe UI Emoji", 28),
        'icon_lg': ("Segoe UI Emoji", 24),
        'icon_md': ("Segoe UI Emoji", 16),
        'icon': ("Segoe UI Emoji", 14),
    }

    # Geometria del canvas del editor visual de curva de gatillo
    CURVE_CANVAS_W = 600
    CURVE_CANVAS_H = 200
    CURVE_MARGIN_X = 40
    CURVE_MARGIN_Y = 20

    def __init__(self, connection_manager=None, trigger_engine=None, profile_manager=None, tray_manager=None, macro_engine=None, game_profile_watcher=None, touchpad_mouse=None, gyro_engine=None, input_studio=None, advanced_mapper=None):
        self.connection_manager = connection_manager
        self.trigger_engine = trigger_engine
        self.profile_manager = profile_manager
        self.tray_manager = tray_manager
        self.macro_engine = macro_engine
        self.game_profile_watcher = game_profile_watcher
        self.touchpad_mouse = touchpad_mouse
        self.gyro_engine = gyro_engine
        self.input_studio = input_studio
        self.advanced_mapper = advanced_mapper

        # Estado de la UI
        self._running = False
        self._minimized_to_tray = False
        self._update_interval = 50  # ms
        self._after_id: Optional[str] = None

        # Estado de la interfaz personalizada. El renderer vive separado del
        # panel clásico para que un tema defectuoso nunca destruya la UI base.
        self._custom_ui_renderer = None
        self._custom_ui_layout = None
        self._custom_ui_active = False
        self._interface_editor_window = None
        self._last_status_message = "Iniciando..."
        self._last_battery_level: Optional[int] = None
        self._last_charging = False
        self._last_l2 = 0
        self._last_r2 = 0

        # Callbacks para comunicacion con main
        self._on_close: List[Callable[[], None]] = []
        self._on_minimize_tray: List[Callable[[], None]] = []

        # Inicializar ventana
        self._init_window()
        self._build_ui()
        self._setup_callbacks()
        self.root.bind("<F12>", self._toggle_custom_ui, add="+")
        self.root.after(150, self._restore_custom_ui_preference)

    def _init_window(self) -> None:
        """Inicializa la ventana principal."""
        if CUSTOMTK_AVAILABLE:
            # Configurar tema oscuro de CustomTkinter
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("dark-blue")

            self.root = ctk.CTk()
        else:
            self.root = tk.Tk()
            self.root.configure(bg=self.COLORS['bg_primary'])

        self.root.title("DualSense Controller - Panel de Control")
        self.root.geometry("950x700")
        self.root.minsize(800, 600)

        # Centrar ventana
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

        # Icono de la ventana (dibujado proceduralmente)
        self._set_window_icon()

        # Protocolo de cierre
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)

    def _set_window_icon(self) -> None:
        """Crea y establece un icono para la ventana."""
        try:
            if ImageTk is None:
                return

            icon = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(icon)

            # Forma del control
            draw.rounded_rectangle([4, 16, 60, 56], radius=8, fill=(0, 150, 255, 255))
            draw.ellipse([12, 24, 22, 34], fill=(255, 255, 255, 255))  # Boton izq
            draw.ellipse([42, 24, 52, 34], fill=(255, 255, 255, 255))  # Boton der
            draw.ellipse([26, 36, 38, 48], fill=(255, 255, 255, 255))  # Stick

            photo = ImageTk.PhotoImage(icon)
            self.root.iconphoto(True, photo)
            self._icon_photo = photo  # Mantener referencia para evitar GC
        except Exception:
            pass

    def _build_ui(self) -> None:
        """Construye todos los elementos de la interfaz."""
        # Frame principal
        if CUSTOMTK_AVAILABLE:
            self.main_frame = ctk.CTkFrame(self.root, fg_color=self.COLORS['bg_primary'])
        else:
            self.main_frame = tk.Frame(self.root, bg=self.COLORS['bg_primary'])

        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ===== Header =====
        self._build_header()

        # ===== Contenido Principal (Tabs) =====
        self._build_tabs()

        # ===== Barra de Estado =====
        self._build_status_bar()

    def _build_header(self) -> None:
        """Construye el header con titulo e indicadores de estado."""
        header = CTkFrame(self.main_frame, fg_color=self.COLORS['bg_secondary'],
                          corner_radius=12, height=70)
        self.header = header
        header.pack(fill=tk.X, pady=(0, 10))
        header.pack_propagate(False)

        # Titulo
        title_frame = CTkFrame(header, fg_color="transparent")
        title_frame.pack(side=tk.LEFT, padx=15, pady=10)

        CTkLabel(title_frame, text="🎮", font=self.FONTS['icon_lg']).pack(side=tk.LEFT)

        title_label = CTkLabel(
            title_frame,
            text="DualSense Controller",
            font=self.FONTS['display_sm'],
            text_color=self.COLORS['text_primary']
        )
        title_label.pack(side=tk.LEFT, padx=(5, 0))

        version_label = CTkLabel(
            title_frame,
            text="v1.0",
            font=self.FONTS['caption'],
            text_color=self.COLORS['text_secondary']
        )
        version_label.pack(side=tk.LEFT, padx=(10, 0))

        # Indicadores de estado (derecha)
        self.indicators_frame = CTkFrame(header, fg_color="transparent")
        self.indicators_frame.pack(side=tk.RIGHT, padx=15, pady=10)

        # Indicador de conexion
        self.connection_indicator = self._create_indicator(
            self.indicators_frame, "●", "Desconectado", self.COLORS['danger']
        )
        self.connection_indicator.pack(side=tk.LEFT, padx=5)

        # Indicador de tipo de conexion
        self.type_indicator = self._create_indicator(
            self.indicators_frame, "", "", self.COLORS['text_secondary']
        )
        self.type_indicator.pack(side=tk.LEFT, padx=5)

        # Indicador de bateria
        self.battery_frame = CTkFrame(self.indicators_frame, fg_color="transparent")
        self.battery_frame.pack(side=tk.LEFT, padx=10)

        self.battery_icon = CTkLabel(
            self.battery_frame, text="🔋",
            font=self.FONTS['icon'], text_color=self.COLORS['text_secondary']
        )
        self.battery_icon.pack(side=tk.LEFT)

        self.battery_label = CTkLabel(
            self.battery_frame, text="--%",
            font=self.FONTS['mono_bold'],
            text_color=self.COLORS['text_secondary']
        )
        self.battery_label.pack(side=tk.LEFT, padx=(3, 0))

        self.battery_bar = CTkProgressBar(
            self.battery_frame, width=50, height=8,
            progress_color=self.COLORS['battery_high'],
            fg_color=self.COLORS['bg_card']
        )
        self.battery_bar.pack(side=tk.LEFT, padx=(5, 0))
        self.battery_bar.set(0)

    def _create_indicator(self, parent, symbol: str, text: str, color: str):
        """Crea un indicador visual de estado."""
        frame = CTkFrame(parent, fg_color="transparent")

        dot = CTkLabel(
            frame, text=symbol,
            font=self.FONTS['icon_md'], text_color=color
        )
        dot.pack(side=tk.LEFT)

        label = CTkLabel(
            frame, text=text,
            font=self.FONTS['small'],
            text_color=self.COLORS['text_secondary']
        )
        label.pack(side=tk.LEFT, padx=(2, 0))

        # Guardar referencias para actualizacion
        frame.dot = dot
        frame.label = label

        return frame

    def _build_tabs(self) -> None:
        """Construye el sistema de pestañas."""
        if CUSTOMTK_AVAILABLE:
            self.tabs = ctk.CTkTabview(
                self.main_frame,
                fg_color=self.COLORS['bg_secondary'],
                segmented_button_fg_color=self.COLORS['bg_card'],
                segmented_button_selected_color=self.COLORS['accent'],
                segmented_button_selected_hover_color=self.COLORS['accent_hover'],
                segmented_button_unselected_color=self.COLORS['bg_card'],
                segmented_button_unselected_hover_color=self.COLORS['border'],
                text_color=self.COLORS['text_primary'],
                corner_radius=12,
            )
        else:
            style = ttk.Style()
            style.configure('Custom.TNotebook', background=self.COLORS['bg_primary'])
            self.tabs = ttk.Notebook(self.main_frame)

        self.tabs.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # ===== Tab: Perfiles =====
        self._build_profiles_tab()

        # ===== Tab: Botones =====
        self._build_buttons_tab()

        # ===== Tab: Gatillos =====
        self._build_triggers_tab()

        # ===== Tab: Macros =====
        self._build_macros_tab()

        # ===== Tab: Giroscopio =====
        self._build_gyro_tab()

        # ===== Tab: Nikaido Input Studio =====
        self._build_input_studio_tab()

        # ===== Tab: Configuracion =====
        self._build_settings_tab()

    def _build_profiles_tab(self) -> None:
        """Construye la pestaña de perfiles de armas."""
        if CUSTOMTK_AVAILABLE:
            profiles_tab = self.tabs.add("Perfiles")
        else:
            profiles_tab = CTkFrame(self.tabs, fg_color=self.COLORS['bg_secondary'])

        # Header de la pestaña
        header_frame = CTkFrame(
            profiles_tab,
            fg_color=self.COLORS['bg_card'],
            corner_radius=16,
            border_width=1,
            border_color=self.COLORS['border'],
        )
        header_frame.pack(fill=tk.X, padx=15, pady=15)

        header_copy = CTkFrame(header_frame, fg_color="transparent")
        header_copy.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=16, pady=14)

        CTkLabel(
            header_copy,
            text="Arsenal de perfiles",
            font=self.FONTS['display'],
            text_color=self.COLORS['text_primary']
        ).pack(anchor="w")

        CTkLabel(
            header_copy,
            text="Crea tu propio preset, duplícalo desde una base y aplícalo al instante.",
            font=self.FONTS['small'],
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", pady=(2, 0))

        self.profile_collection_label = CTkLabel(
            header_copy,
            text="Cargando colección…",
            font=self.FONTS['micro'],
            text_color=self.COLORS['trigger_accent'],
        )
        self.profile_collection_label.pack(anchor="w", pady=(8, 0))

        header_actions = CTkFrame(header_frame, fg_color="transparent")
        header_actions.pack(side=tk.RIGHT, padx=14, pady=14)
        CTkButton(
            header_actions,
            text="Importar",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['bg_secondary'],
            hover_color=self.COLORS['border'],
            corner_radius=8,
            height=34,
            width=92,
            command=self._import_profile,
        ).pack(side=tk.LEFT, padx=(0, 8))
        CTkButton(
            header_actions,
            text="+ Nuevo perfil",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['accent_hover'],
            corner_radius=8,
            height=34,
            width=124,
            command=self._open_weapon_profile_creator,
        ).pack(side=tk.LEFT)

        # Grid de perfiles
        self.profiles_grid = CTkScrollableFrame(
            profiles_tab,
            fg_color=self.COLORS['bg_secondary'],
            scrollbar_button_color=self.COLORS['border'],
            scrollbar_button_hover_color=self.COLORS['accent']
        )
        self.profiles_grid.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # Frame de info del perfil activo
        self.profile_info_frame = CTkFrame(
            profiles_tab,
            fg_color=self.COLORS['bg_card'],
            corner_radius=12,
            border_width=1,
            border_color=self.COLORS['border'],
        )
        self.profile_info_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        self.active_profile_label = CTkLabel(
            self.profile_info_frame,
            text="EN USO  ·  Ninguno",
            font=self.FONTS['subtitle'],
            text_color=self.COLORS['accent']
        )
        self.active_profile_label.pack(side=tk.LEFT, padx=15, pady=10)

        self.profile_desc_label = CTkLabel(
            self.profile_info_frame,
            text="Selecciona un perfil para ver su descripcion",
            font=self.FONTS['small'],
            text_color=self.COLORS['text_secondary']
        )
        self.profile_desc_label.pack(side=tk.LEFT, padx=15, pady=10)

        # Agregar tab (solo para tkinter estandar)
        if not CUSTOMTK_AVAILABLE:
            self.tabs.add(profiles_tab, text="Perfiles")

        # Poblar perfiles
        self._populate_profiles_grid()

    def _populate_profiles_grid(self) -> None:
        """Llena la grid con las tarjetas de perfiles."""
        if not self.trigger_engine:
            return

        # Limpiar grid existente
        for widget in self.profiles_grid.winfo_children():
            widget.destroy()

        profiles = self.trigger_engine.get_all_profiles()
        categories: Dict[str, List] = {}
        custom_count = sum(
            1 for profile_id in profiles
            if self.trigger_engine.is_custom_profile(profile_id)
        )

        if hasattr(self, 'profile_collection_label'):
            self.profile_collection_label.configure(
                text=f"{len(profiles)} perfiles disponibles  ·  {custom_count} personalizados"
            )

        current_profile_id = self.trigger_engine.get_current_profile()
        current_profile = self.trigger_engine.get_profile(current_profile_id) if current_profile_id else None
        if current_profile:
            self.active_profile_label.configure(text=f"EN USO  ·  {current_profile.name}")
            self.profile_desc_label.configure(text=current_profile.description)

        # Agrupar por categoria
        for pid, profile in profiles.items():
            cat = profile.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((pid, profile))

        row = 0
        for category, profile_list in sorted(categories.items()):
            # Titulo de categoria
            cat_label = CTkLabel(
                self.profiles_grid,
                text=f"▰  {category.upper()}  ·  {len(profile_list)} perfiles",
                font=self.FONTS['title_sm'],
                text_color=self.COLORS['accent']
            )
            cat_label.grid(row=row, column=0, columnspan=3, sticky="w", pady=(10, 5), padx=5)
            row += 1

            # Tarjetas de perfiles (3 por fila)
            col = 0
            for pid, profile in profile_list:
                card = self._create_profile_card(self.profiles_grid, pid, profile)
                card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

                col += 1
                if col >= 3:
                    col = 0
                    row += 1

            if col > 0:
                row += 1

        # Configurar pesos de columnas
        for i in range(3):
            self.profiles_grid.grid_columnconfigure(i, weight=1)

    def _create_profile_card(self, parent, profile_id: str, profile) -> CTkFrame:
        """Crea una tarjeta visual con acciones seguras para un perfil."""
        is_custom = self.trigger_engine.is_custom_profile(profile_id)
        is_active = self.trigger_engine.get_current_profile() == profile_id
        card_accent = (
            self.COLORS['accent'] if is_active
            else self.COLORS['success'] if is_custom
            else self.COLORS['border']
        )
        card = CTkFrame(
            parent,
            fg_color=self.COLORS['bg_card'],
            corner_radius=14,
            border_width=2 if is_active else 1,
            border_color=card_accent
        )

        # Icono y nombre
        top_frame = CTkFrame(card, fg_color="transparent")
        top_frame.pack(fill=tk.X, padx=12, pady=(12, 5))

        CTkLabel(
            top_frame,
            text=profile.icon,
            font=self.FONTS['icon_xl']
        ).pack(side=tk.LEFT)

        CTkLabel(
            top_frame,
            text=profile.name,
            font=self.FONTS['title_sm'],
            text_color=self.COLORS['text_primary']
        ).pack(side=tk.LEFT, padx=(8, 0))

        badge_text = "PERSONAL" if is_custom else "INCLUIDO"
        badge_color = self.COLORS['success'] if is_custom else self.COLORS['bg_secondary']
        CTkLabel(
            top_frame,
            text=badge_text,
            font=self.FONTS['micro'],
            text_color=self.COLORS['bg_primary'] if is_custom else self.COLORS['text_secondary'],
            fg_color=badge_color,
            corner_radius=7,
            height=20,
        ).pack(side=tk.RIGHT)

        # Descripcion
        desc = CTkLabel(
            card,
            text=profile.description,
            font=self.FONTS['caption'],
            text_color=self.COLORS['text_secondary'],
            wraplength=200,
            justify="left"
        )
        desc.pack(fill=tk.X, padx=12, pady=(0, 8))

        # Info de efectos
        effects_frame = CTkFrame(card, fg_color="transparent")
        effects_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        CTkLabel(
            effects_frame,
            text=f"L2: {profile.left_trigger.name}",
            font=self.FONTS['micro'],
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w")

        CTkLabel(
            effects_frame,
            text=f"R2: {profile.right_trigger.name}",
            font=self.FONTS['micro'],
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w")

        vibration_settings = (
            self.trigger_engine.get_profile_vibration_settings(profile_id)
            if self.trigger_engine else None
        ) or {}
        left_vibration = vibration_settings.get('left', {})
        right_vibration = vibration_settings.get('right', {})
        vibration_parts = []
        if left_vibration.get('enabled'):
            vibration_parts.append(
                f"L2 {left_vibration.get('intensity', 0)}/255 · {left_vibration.get('frequency', 25)} Hz"
            )
        if right_vibration.get('enabled'):
            vibration_parts.append(
                f"R2 {right_vibration.get('intensity', 0)}/255 · {right_vibration.get('frequency', 25)} Hz"
            )
        CTkLabel(
            effects_frame,
            text="Vibracion gatillos: " + (" | ".join(vibration_parts) if vibration_parts else "Desactivada"),
            font=self.FONTS['micro'],
            text_color=self.COLORS['trigger_accent'] if vibration_parts else self.COLORS['text_secondary'],
            wraplength=220,
            justify="left"
        ).pack(anchor="w", pady=(3, 0))

        # Barra de intensidad de los motores normales del control
        intensity_label = CTkLabel(
            card,
            text=f"Motores del mando: {profile.rumble_intensity}/255",
            font=self.FONTS['micro'],
            text_color=self.COLORS['text_secondary']
        )
        intensity_label.pack(anchor="w", padx=12, pady=(0, 5))

        intensity_bar = CTkProgressBar(
            card, height=4,
            progress_color=self.COLORS['accent'],
            fg_color=self.COLORS['bg_secondary']
        )
        intensity_bar.pack(fill=tk.X, padx=12, pady=(0, 10))
        intensity_bar.set(profile.rumble_intensity / 255)

        # Acciones secundarias y accion principal. Mantener "Eliminar" solo
        # en perfiles personales evita borrar por accidente una base incluida.
        profile_actions = CTkFrame(card, fg_color="transparent")
        profile_actions.pack(fill=tk.X, padx=12, pady=(0, 12))

        secondary_actions = CTkFrame(profile_actions, fg_color="transparent")
        secondary_actions.pack(fill=tk.X, pady=(0, 7))

        CTkButton(
            secondary_actions,
            text="Vibracion",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['bg_secondary'],
            hover_color=self.COLORS['border'],
            corner_radius=8,
            height=32,
            width=92,
            command=lambda pid=profile_id: self._open_profile_vibration_editor(pid)
        ).pack(side=tk.LEFT, padx=(0, 6))

        CTkButton(
            secondary_actions,
            text="Duplicar",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['bg_secondary'],
            hover_color=self.COLORS['border'],
            corner_radius=8,
            height=32,
            width=82,
            command=lambda pid=profile_id: self._open_weapon_profile_creator(pid)
        ).pack(side=tk.LEFT)

        if is_custom:
            CTkButton(
                secondary_actions,
                text="Eliminar",
                font=self.FONTS['small_bold'],
                fg_color="transparent",
                text_color=self.COLORS['danger'],
                hover_color=self.COLORS['bg_secondary'],
                corner_radius=8,
                height=32,
                width=76,
                command=lambda pid=profile_id: self._delete_weapon_profile(pid)
            ).pack(side=tk.RIGHT)

        apply_btn = CTkButton(
            profile_actions,
            text="Aplicado" if is_active else "Aplicar perfil",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['success'] if is_active else self.COLORS['accent'],
            hover_color=self.COLORS['accent_hover'],
            corner_radius=8,
            height=32,
            command=lambda pid=profile_id: self._apply_profile(pid)
        )
        apply_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Guardar referencia para resaltar activo
        card.profile_id = profile_id
        card.apply_btn = apply_btn

        return card

    def _persist_custom_weapon_profiles(self) -> None:
        """Guarda exclusivamente los perfiles personales, sin clonar bases."""
        if not (self.profile_manager and self.trigger_engine):
            return
        self.profile_manager.set_custom_profiles(
            self.trigger_engine.export_custom_profiles_to_dict()
        )
        self.profile_manager.save_config()

    def _refresh_weapon_profile_views(self) -> None:
        """Sincroniza las superficies que presentan perfiles tras un cambio."""
        self._populate_profiles_grid()
        if self.tray_manager and self.trigger_engine:
            self.tray_manager.set_profiles(self.trigger_engine.get_profile_names())
        if hasattr(self, 'input_profile_menu'):
            self._input_refresh_profiles()
        if hasattr(self, 'game_profiles_list_frame'):
            self._populate_game_profiles_list()

    def _make_custom_profile_id(self, name: str) -> str:
        """Genera un ID legible, estable y que no colisiona con el arsenal."""
        normalized = unicodedata.normalize('NFKD', name)
        ascii_name = normalized.encode('ascii', 'ignore').decode('ascii').lower()
        slug = re.sub(r'[^a-z0-9]+', '_', ascii_name).strip('_') or 'perfil'
        base = f"custom_{slug[:36]}"
        profile_ids = set(self.trigger_engine.get_all_profiles()) if self.trigger_engine else set()
        candidate = base
        suffix = 2
        while candidate in profile_ids:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    def _open_weapon_profile_creator(self, source_profile_id: Optional[str] = None) -> None:
        """Abre un dialogo para crear o duplicar un perfil de arma."""
        if not self.trigger_engine:
            messagebox.showerror("Perfiles", "El motor de perfiles no esta disponible.")
            return

        profiles = self.trigger_engine.get_all_profiles()
        if not profiles:
            messagebox.showerror("Perfiles", "No hay perfiles base disponibles.")
            return

        current_id = self.trigger_engine.get_current_profile()
        source_id = source_profile_id if source_profile_id in profiles else current_id
        if source_id not in profiles:
            source_id = next(iter(profiles))
        source = profiles[source_id]
        is_duplicate = source_profile_id is not None

        if CUSTOMTK_AVAILABLE:
            win = ctk.CTkToplevel(self.root, fg_color=self.COLORS['bg_primary'])
        else:
            win = tk.Toplevel(self.root, bg=self.COLORS['bg_primary'])
        win.title("Duplicar perfil" if is_duplicate else "Nuevo perfil de arma")
        win.geometry("560x550")
        win.resizable(False, False)
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass

        body = CTkFrame(win, fg_color="transparent")
        body.pack(fill=tk.BOTH, expand=True, padx=22, pady=20)

        CTkLabel(
            body,
            text="Duplicar perfil" if is_duplicate else "Crear perfil de arma",
            font=self.FONTS['display_sm'],
            text_color=self.COLORS['text_primary'],
        ).pack(anchor="w")
        CTkLabel(
            body,
            text="La base aporta sus efectos de gatillo; nombre, categoria e icono seran tuyos.",
            font=self.FONTS['caption'],
            text_color=self.COLORS['text_secondary'],
            wraplength=500,
            justify="left",
        ).pack(anchor="w", pady=(3, 16))

        form = CTkFrame(
            body, fg_color=self.COLORS['bg_card'], corner_radius=12,
            border_width=1, border_color=self.COLORS['border'],
        )
        form.pack(fill=tk.X)

        def add_label(text: str) -> None:
            CTkLabel(
                form, text=text, font=self.FONTS['small_bold'],
                text_color=self.COLORS['text_secondary'],
            ).pack(anchor="w", padx=14, pady=(10, 4))

        source_by_label = {
            f"{profile.name}  ·  {profile_id}": profile_id
            for profile_id, profile in profiles.items()
        }
        source_label = next(
            label for label, profile_id in source_by_label.items() if profile_id == source_id
        )
        source_var = tk.StringVar(value=source_label)
        add_label("Basado en")
        CTkOptionMenu(
            form, values=list(source_by_label), variable=source_var,
            fg_color=self.COLORS['bg_secondary'], button_color=self.COLORS['accent'],
            button_hover_color=self.COLORS['accent_hover'],
        ).pack(fill=tk.X, padx=14)

        add_label("Nombre")
        name_entry = CTkEntry(
            form, placeholder_text="Ej.: Francotirador silencioso",
            fg_color=self.COLORS['bg_secondary'], border_color=self.COLORS['border'],
            text_color=self.COLORS['text_primary'], height=34,
        )
        name_entry.pack(fill=tk.X, padx=14)
        if is_duplicate:
            name_entry.insert(0, f"{source.name} copia")

        add_label("Descripcion")
        description_entry = CTkEntry(
            form, placeholder_text="Una nota corta para reconocerlo rapidamente",
            fg_color=self.COLORS['bg_secondary'], border_color=self.COLORS['border'],
            text_color=self.COLORS['text_primary'], height=34,
        )
        description_entry.pack(fill=tk.X, padx=14)
        if is_duplicate:
            description_entry.insert(0, source.description)

        metadata_row = CTkFrame(form, fg_color="transparent")
        metadata_row.pack(fill=tk.X, padx=14, pady=(0, 12))
        category_values = ["Personalizado", "FPS", "Competitivo", "Aventura", "Carreras", "Accesibilidad"]
        if source.category not in category_values:
            category_values.insert(0, source.category)
        category_var = tk.StringVar(value=source.category if is_duplicate else "Personalizado")
        icon_entry = CTkEntry(
            metadata_row, width=74, justify="center",
            fg_color=self.COLORS['bg_secondary'], border_color=self.COLORS['border'],
            text_color=self.COLORS['text_primary'], height=34,
        )
        icon_entry.insert(0, source.icon if is_duplicate else "🎮")
        CTkLabel(metadata_row, text="Icono", font=self.FONTS['small_bold'],
                 text_color=self.COLORS['text_secondary']).pack(side=tk.LEFT, pady=(12, 0))
        icon_entry.pack(side=tk.LEFT, padx=(6, 16), pady=(12, 0))
        CTkLabel(metadata_row, text="Categoria", font=self.FONTS['small_bold'],
                 text_color=self.COLORS['text_secondary']).pack(side=tk.LEFT, pady=(12, 0))
        CTkOptionMenu(
            metadata_row, values=category_values, variable=category_var, width=170,
            fg_color=self.COLORS['bg_secondary'], button_color=self.COLORS['accent'],
            button_hover_color=self.COLORS['accent_hover'],
        ).pack(side=tk.LEFT, padx=(6, 0), pady=(12, 0))

        footer = CTkFrame(body, fg_color="transparent")
        footer.pack(fill=tk.X, pady=(16, 0))

        def close_window() -> None:
            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()

        def save_profile() -> None:
            name = name_entry.get().strip()
            description = description_entry.get().strip()
            icon = icon_entry.get().strip() or "🎮"
            selected_id = source_by_label.get(source_var.get(), source_id)
            base_profile = self.trigger_engine.get_profile(selected_id)
            if not name:
                messagebox.showwarning("Perfiles", "Escribe un nombre para el perfil.", parent=win)
                name_entry.focus_set()
                return
            if len(name) > 60 or len(description) > 180:
                messagebox.showwarning(
                    "Perfiles", "El nombre admite hasta 60 caracteres y la descripcion hasta 180.", parent=win
                )
                return
            if not base_profile:
                messagebox.showerror("Perfiles", "La base seleccionada ya no existe.", parent=win)
                return

            from src.trigger_engine import WeaponProfile
            profile_data = base_profile.to_dict()
            profile_data.update({
                'name': name,
                'description': description or "Perfil personalizado de Nikaido.",
                'icon': icon,
                'category': category_var.get().strip() or "Personalizado",
            })
            profile_id = self._make_custom_profile_id(name)
            if not self.trigger_engine.add_custom_profile(profile_id, WeaponProfile.from_dict(profile_data)):
                messagebox.showerror("Perfiles", "No se pudo crear el perfil. Prueba con otro nombre.", parent=win)
                return
            self._persist_custom_weapon_profiles()
            self._refresh_weapon_profile_views()
            self._set_status(f"Perfil creado: {name}")
            close_window()

        CTkButton(
            footer, text="Cancelar", width=96, height=34,
            font=self.FONTS['small_bold'], fg_color=self.COLORS['bg_secondary'],
            hover_color=self.COLORS['border'], corner_radius=8, command=close_window,
        ).pack(side=tk.LEFT)
        CTkButton(
            footer, text="Guardar perfil", width=130, height=34,
            font=self.FONTS['small_bold'], fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['accent_hover'], corner_radius=8, command=save_profile,
        ).pack(side=tk.RIGHT)
        win.protocol("WM_DELETE_WINDOW", close_window)
        name_entry.focus_set()

    def _delete_weapon_profile(self, profile_id: str) -> None:
        """Elimina un perfil personal y limpia las referencias que deja atras."""
        if not self.trigger_engine or not self.trigger_engine.is_custom_profile(profile_id):
            messagebox.showinfo(
                "Perfiles incluidos",
                "Los perfiles incluidos no se eliminan. Puedes duplicarlos y editar tu propia copia.",
            )
            return
        profile = self.trigger_engine.get_profile(profile_id)
        if not profile:
            return
        if not messagebox.askyesno(
            "Eliminar perfil",
            f'¿Eliminar "{profile.name}"? Esta accion tambien borrara sus ajustes de Input Studio.',
            parent=self.root,
        ):
            return

        was_active = self.trigger_engine.get_current_profile() == profile_id
        if not self.trigger_engine.remove_profile(profile_id):
            messagebox.showerror("Perfiles", "No se pudo eliminar el perfil.", parent=self.root)
            return

        if self.input_studio:
            self.input_studio.remove_profile(profile_id)

        if self.profile_manager:
            custom_profiles = dict(self.profile_manager.get_custom_profiles())
            custom_profiles.pop(profile_id, None)
            self.profile_manager.set_custom_profiles(custom_profiles)
            self.profile_manager.remove_favorite(profile_id)
            mapping = {
                executable: mapped_profile
                for executable, mapped_profile in self.profile_manager.get_game_profiles().items()
                if mapped_profile != profile_id
            }
            self.profile_manager.set_game_profiles(mapping)
            if self.input_studio:
                self.profile_manager.set_setting(
                    'profile_input_studio', self.input_studio.export_profiles()
                )
            self.profile_manager.save_config()
            if self.game_profile_watcher:
                self.game_profile_watcher.set_mapping(mapping)

        if was_active:
            available = self.trigger_engine.get_all_profiles()
            fallback = 'assault_rifle' if 'assault_rifle' in available else next(iter(available), None)
            if fallback:
                self._apply_profile(fallback)

        self._refresh_weapon_profile_views()
        self._set_status(f"Perfil eliminado: {profile.name}")

    def _create_vibration_slider(
        self, parent, title: str, minimum: int, maximum: int,
        value: int, steps: int
    ):
        """Crea un slider compacto con lectura numerica para los dialogos."""
        CTkLabel(
            parent, text=title,
            font=self.FONTS['small'],
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=12, pady=(8, 0))

        row = CTkFrame(parent, fg_color="transparent")
        row.pack(fill=tk.X, padx=12, pady=(2, 4))

        value_label = CTkLabel(
            row, text=str(int(value)), width=42,
            font=self.FONTS['mono'],
            text_color=self.COLORS['text_primary']
        )
        value_label.pack(side=tk.RIGHT, padx=(6, 0))

        slider = CTkSlider(
            row,
            from_=minimum, to=maximum,
            number_of_steps=max(1, steps),
            command=lambda v: value_label.configure(text=str(int(round(float(v))))),
            fg_color=self.COLORS['bg_secondary'],
            progress_color=self.COLORS['trigger_accent'],
            button_color=self.COLORS['trigger_accent'],
            button_hover_color=self.COLORS['trigger_accent_hover'],
        )
        slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        slider.set(max(minimum, min(maximum, value)))
        return slider

    def _persist_profile_trigger_vibration(self) -> None:
        """Guarda las preferencias editables de vibracion de todos los perfiles."""
        if not (self.profile_manager and self.trigger_engine):
            return
        self.profile_manager.set_setting(
            'profile_trigger_vibration',
            self.trigger_engine.export_vibration_overrides()
        )
        self.profile_manager.save_config()

    def _open_profile_vibration_editor(self, profile_id: str) -> None:
        """Edita y prueba la vibracion de L2/R2 de un perfil concreto."""
        if not self.trigger_engine:
            messagebox.showerror("Vibracion de gatillos", "El motor de gatillos no esta disponible.")
            return

        profile = self.trigger_engine.get_profile(profile_id)
        settings = self.trigger_engine.get_profile_vibration_settings(profile_id)
        if not profile or not settings:
            messagebox.showerror("Vibracion de gatillos", "No se encontro el perfil seleccionado.")
            return

        if CUSTOMTK_AVAILABLE:
            win = ctk.CTkToplevel(self.root, fg_color=self.COLORS['bg_primary'])
        else:
            win = tk.Toplevel(self.root, bg=self.COLORS['bg_primary'])

        win.title(f"Vibracion de gatillos - {profile.name}")
        win.geometry("720x590")
        win.minsize(650, 540)
        win.transient(self.root)
        win.grab_set()

        CTkLabel(
            win, text=profile.name,
            font=self.FONTS['display'],
            text_color=self.COLORS['text_primary']
        ).pack(anchor="w", padx=18, pady=(16, 2))
        CTkLabel(
            win,
            text=(
                "La resistencia base se conserva. Al presionar hasta la zona de inicio, "
                "el gatillo cambia a vibracion y vuelve al efecto del perfil al soltar."
            ),
            font=self.FONTS['caption'],
            text_color=self.COLORS['text_secondary'],
            wraplength=675,
            justify="left"
        ).pack(anchor="w", padx=18, pady=(0, 12))

        columns = CTkFrame(win, fg_color="transparent")
        columns.pack(fill=tk.BOTH, expand=True, padx=12)
        columns.grid_columnconfigure(0, weight=1)
        columns.grid_columnconfigure(1, weight=1)
        columns.grid_rowconfigure(0, weight=1)

        controls = {}

        def run_test(trigger: str) -> None:
            cfg = controls[trigger]
            start = int(round(cfg['start'].get()))
            end = max(start, int(round(cfg['end'].get())))
            success = self.trigger_engine.test_trigger_vibration(
                target=trigger,
                intensity=int(round(cfg['intensity'].get())),
                frequency=int(round(cfg['frequency'].get())),
                start_position=start,
                end_position=end,
                duration=2.5,
            )
            if success:
                self._set_status(
                    f"Probando vibracion en {'L2' if trigger == 'left' else 'R2'}; presiona el gatillo"
                )
            else:
                messagebox.showwarning(
                    "Vibracion de gatillos",
                    "Conecta el DualSense fisico antes de probar."
                )

        for column, (trigger, title) in enumerate((('left', 'L2'), ('right', 'R2'))):
            cfg = settings[trigger]
            panel = CTkFrame(
                columns, fg_color=self.COLORS['bg_card'],
                corner_radius=12, border_width=1,
                border_color=self.COLORS['border']
            )
            panel.grid(row=0, column=column, padx=6, pady=2, sticky="nsew")

            CTkLabel(
                panel, text=f"{title} · Vibracion del gatillo",
                font=self.FONTS['title_sm'],
                text_color=self.COLORS['trigger_accent']
            ).pack(anchor="w", padx=12, pady=(12, 5))

            enabled_var = tk.BooleanVar(value=bool(cfg.get('enabled', False)))
            CTkSwitch(
                panel, text="Activar en este perfil",
                variable=enabled_var,
                onvalue=True, offvalue=False,
                font=self.FONTS['small_bold'],
                text_color=self.COLORS['text_primary'],
                progress_color=self.COLORS['trigger_accent'],
                button_color=self.COLORS['text_primary'],
            ).pack(anchor="w", padx=12, pady=(2, 5))

            controls[trigger] = {
                'enabled': enabled_var,
                'intensity': self._create_vibration_slider(
                    panel, "Intensidad (0-255)", 0, 255,
                    int(cfg.get('intensity', 180)), 255
                ),
                'frequency': self._create_vibration_slider(
                    panel, "Frecuencia (Hz)", 1, 255,
                    int(cfg.get('frequency', 25)), 254
                ),
                'start': self._create_vibration_slider(
                    panel, "Zona de inicio (0-9)", 0, 9,
                    int(cfg.get('start_position', 2)), 9
                ),
                'end': self._create_vibration_slider(
                    panel, "Zona final (0-9)", 0, 9,
                    int(cfg.get('end_position', 9)), 9
                ),
            }

            CTkButton(
                panel, text=f"Probar {title}",
                font=self.FONTS['small_bold'],
                fg_color=self.COLORS['trigger_accent'],
                hover_color=self.COLORS['trigger_accent_hover'],
                corner_radius=8, height=34,
                command=lambda t=trigger: run_test(t)
            ).pack(fill=tk.X, padx=12, pady=(12, 12))

        actions = CTkFrame(win, fg_color="transparent")
        actions.pack(fill=tk.X, padx=18, pady=(10, 16))

        def close_editor() -> None:
            self.trigger_engine.stop_trigger_vibration_test(restore=True)
            try:
                win.grab_release()
            except tk.TclError:
                pass
            win.destroy()

        def save_editor() -> None:
            for trigger in ('left', 'right'):
                cfg = controls[trigger]
                start = int(round(cfg['start'].get()))
                end = max(start, int(round(cfg['end'].get())))
                self.trigger_engine.update_profile_vibration(
                    profile_id, trigger,
                    enabled=bool(cfg['enabled'].get()),
                    intensity=int(round(cfg['intensity'].get())),
                    frequency=int(round(cfg['frequency'].get())),
                    start_position=start,
                    end_position=end,
                    reapply=False,
                )
            if self.trigger_engine.get_current_profile() == profile_id:
                self.trigger_engine.apply_profile(profile_id)
            self._persist_profile_trigger_vibration()
            self._populate_profiles_grid()
            self._set_status(f"Vibracion guardada en el perfil: {profile.name}")
            close_editor()

        CTkButton(
            actions, text="Detener prueba",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['bg_secondary'],
            hover_color=self.COLORS['border'],
            corner_radius=8,
            command=lambda: self.trigger_engine.stop_trigger_vibration_test(restore=True)
        ).pack(side=tk.LEFT)

        CTkButton(
            actions, text="Cancelar",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['bg_secondary'],
            hover_color=self.COLORS['border'],
            corner_radius=8,
            command=close_editor
        ).pack(side=tk.RIGHT, padx=(6, 0))

        CTkButton(
            actions, text="Guardar",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['accent_hover'],
            corner_radius=8,
            command=save_editor
        ).pack(side=tk.RIGHT)

        win.protocol("WM_DELETE_WINDOW", close_editor)

    def _open_trigger_vibration_test(self) -> None:
        """Abre una prueba libre del modo oficial de vibracion de gatillos."""
        if not self.trigger_engine:
            messagebox.showerror("Prueba de vibracion", "El motor de gatillos no esta disponible.")
            return

        if CUSTOMTK_AVAILABLE:
            win = ctk.CTkToplevel(self.root, fg_color=self.COLORS['bg_primary'])
        else:
            win = tk.Toplevel(self.root, bg=self.COLORS['bg_primary'])

        win.title("Prueba de vibracion de gatillos")
        win.geometry("500x590")
        win.minsize(450, 540)
        win.transient(self.root)
        win.grab_set()

        CTkLabel(
            win, text="Prueba de vibracion de gatillos",
            font=self.FONTS['display'],
            text_color=self.COLORS['text_primary']
        ).pack(anchor="w", padx=18, pady=(16, 2))
        CTkLabel(
            win,
            text=(
                "Inicia la prueba y presiona el gatillo dentro del rango elegido. "
                "Al terminar se restaura automaticamente el efecto anterior."
            ),
            font=self.FONTS['caption'],
            text_color=self.COLORS['text_secondary'],
            wraplength=460,
            justify="left"
        ).pack(anchor="w", padx=18, pady=(0, 12))

        panel = CTkFrame(win, fg_color=self.COLORS['bg_card'], corner_radius=12)
        panel.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 10))

        CTkLabel(
            panel, text="Gatillo a probar",
            font=self.FONTS['small'],
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=12, pady=(12, 4))

        target_var = tk.StringVar(value="Ambos")
        CTkSegmentedButton(
            panel, values=["L2", "R2", "Ambos"],
            variable=target_var,
            fg_color=self.COLORS['bg_secondary'],
            selected_color=self.COLORS['trigger_accent'],
            selected_hover_color=self.COLORS['trigger_accent_hover'],
            font=self.FONTS['small_bold']
        ).pack(fill=tk.X, padx=12, pady=(0, 5))

        intensity = self._create_vibration_slider(panel, "Intensidad (0-255)", 0, 255, 220, 255)
        frequency = self._create_vibration_slider(panel, "Frecuencia (Hz)", 1, 255, 30, 254)
        start = self._create_vibration_slider(panel, "Zona de inicio (0-9)", 0, 9, 1, 9)
        end = self._create_vibration_slider(panel, "Zona final (0-9)", 0, 9, 9, 9)
        duration = self._create_vibration_slider(panel, "Duracion (segundos)", 1, 8, 3, 7)

        actions = CTkFrame(win, fg_color="transparent")
        actions.pack(fill=tk.X, padx=18, pady=(0, 16))

        def start_test() -> None:
            target = {'L2': 'left', 'R2': 'right', 'Ambos': 'both'}[target_var.get()]
            start_zone = int(round(start.get()))
            end_zone = max(start_zone, int(round(end.get())))
            success = self.trigger_engine.test_trigger_vibration(
                target=target,
                intensity=int(round(intensity.get())),
                frequency=int(round(frequency.get())),
                start_position=start_zone,
                end_position=end_zone,
                duration=float(duration.get()),
            )
            if success:
                self._set_status("Prueba de vibracion activa; presiona el gatillo")
            else:
                messagebox.showwarning(
                    "Prueba de vibracion",
                    "Conecta el DualSense fisico antes de probar."
                )

        def close_test() -> None:
            self.trigger_engine.stop_trigger_vibration_test(restore=True)
            try:
                win.grab_release()
            except tk.TclError:
                pass
            win.destroy()

        CTkButton(
            actions, text="Detener",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['bg_secondary'],
            hover_color=self.COLORS['border'],
            corner_radius=8,
            command=lambda: self.trigger_engine.stop_trigger_vibration_test(restore=True)
        ).pack(side=tk.LEFT)

        CTkButton(
            actions, text="Cerrar",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['bg_secondary'],
            hover_color=self.COLORS['border'],
            corner_radius=8,
            command=close_test
        ).pack(side=tk.RIGHT, padx=(6, 0))

        CTkButton(
            actions, text="Probar ahora",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['trigger_accent'],
            hover_color=self.COLORS['trigger_accent_hover'],
            corner_radius=8,
            command=start_test
        ).pack(side=tk.RIGHT)

        win.protocol("WM_DELETE_WINDOW", close_test)

    def _build_triggers_tab(self) -> None:
        """Construye la pestaña de control manual de gatillos."""
        if CUSTOMTK_AVAILABLE:
            triggers_tab = self.tabs.add("Gatillos")
        else:
            triggers_tab = CTkFrame(self.tabs, fg_color=self.COLORS['bg_secondary'])

        # Layout: dos columnas (L2 y R2)
        triggers_tab.grid_columnconfigure(0, weight=1)
        triggers_tab.grid_columnconfigure(1, weight=1)

        # ===== Panel L2 =====
        l2_frame = CTkFrame(triggers_tab, fg_color=self.COLORS['bg_card'], corner_radius=12)
        l2_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        CTkLabel(
            l2_frame,
            text="L2 (Gatillo Izquierdo)",
            font=self.FONTS['title'],
            text_color=self.COLORS['text_primary']
        ).pack(pady=(15, 10))

        # Visualizador de posicion
        self.l2_position_bar = CTkProgressBar(
            l2_frame, width=200, height=20,
            progress_color=self.COLORS['trigger_accent'],
            fg_color=self.COLORS['bg_secondary'],
            corner_radius=10
        )
        self.l2_position_bar.pack(pady=5)
        self.l2_position_bar.set(0)

        self.l2_position_label = CTkLabel(
            l2_frame, text="Posicion:   0",
            font=self.FONTS['mono'],
            text_color=self.COLORS['text_primary']
        )
        self.l2_position_label.pack(pady=(0, 10))

        # Selector de efecto
        CTkLabel(
            l2_frame, text="Efecto:",
            font=self.FONTS['body'],
            text_color=self.COLORS['text_primary']
        ).pack(anchor="w", padx=15, pady=(10, 5))

        self.l2_effect_var = tk.StringVar(value="off")
        self.l2_effect_menu = CTkOptionMenu(
            l2_frame,
            values=["off", "rigid", "pulse", "continuous_vibration", "sections"],
            variable=self.l2_effect_var,
            command=lambda v: self._on_effect_change('left', v),
            font=self.FONTS['small'],
            dropdown_font=self.FONTS['small'],
            fg_color=self.COLORS['bg_secondary'],
            button_color=self.COLORS['trigger_accent'],
            button_hover_color=self.COLORS['trigger_accent_hover'],
        )
        self.l2_effect_menu.pack(fill=tk.X, padx=15, pady=5)

        # Sliders de configuracion
        self._build_trigger_sliders(l2_frame, 'left')

        # ===== Panel R2 =====
        r2_frame = CTkFrame(triggers_tab, fg_color=self.COLORS['bg_card'], corner_radius=12)
        r2_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        CTkLabel(
            r2_frame,
            text="R2 (Gatillo Derecho)",
            font=self.FONTS['title'],
            text_color=self.COLORS['text_primary']
        ).pack(pady=(15, 10))

        # Visualizador de posicion
        self.r2_position_bar = CTkProgressBar(
            r2_frame, width=200, height=20,
            progress_color=self.COLORS['trigger_accent'],
            fg_color=self.COLORS['bg_secondary'],
            corner_radius=10
        )
        self.r2_position_bar.pack(pady=5)
        self.r2_position_bar.set(0)

        self.r2_position_label = CTkLabel(
            r2_frame, text="Posicion:   0",
            font=self.FONTS['mono'],
            text_color=self.COLORS['text_primary']
        )
        self.r2_position_label.pack(pady=(0, 10))

        # Selector de efecto
        CTkLabel(
            r2_frame, text="Efecto:",
            font=self.FONTS['body'],
            text_color=self.COLORS['text_primary']
        ).pack(anchor="w", padx=15, pady=(10, 5))

        self.r2_effect_var = tk.StringVar(value="off")
        self.r2_effect_menu = CTkOptionMenu(
            r2_frame,
            values=["off", "rigid", "pulse", "continuous_vibration", "sections"],
            variable=self.r2_effect_var,
            command=lambda v: self._on_effect_change('right', v),
            font=self.FONTS['small'],
            dropdown_font=self.FONTS['small'],
            fg_color=self.COLORS['bg_secondary'],
            button_color=self.COLORS['trigger_accent'],
            button_hover_color=self.COLORS['trigger_accent_hover'],
        )
        self.r2_effect_menu.pack(fill=tk.X, padx=15, pady=5)

        # Sliders de configuracion
        self._build_trigger_sliders(r2_frame, 'right')

        # ===== Editor Visual de Curva (arrastrar puntos con el mouse) =====
        curve_frame = CTkFrame(triggers_tab, fg_color=self.COLORS['bg_card'], corner_radius=12)
        curve_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="nsew")

        curve_header = CTkFrame(curve_frame, fg_color="transparent")
        curve_header.pack(fill=tk.X, padx=15, pady=(15, 5))

        CTkLabel(
            curve_header, text="Editor Visual de Curva",
            font=self.FONTS['title_sm'],
            text_color=self.COLORS['text_primary']
        ).pack(side=tk.LEFT)

        self.curve_trigger_var = tk.StringVar(value="R2")
        curve_trigger_toggle = CTkSegmentedButton(
            curve_header, values=["L2", "R2"],
            variable=self.curve_trigger_var,
            command=lambda v: self._on_curve_trigger_switch(v),
            fg_color=self.COLORS['bg_secondary'],
            selected_color=self.COLORS['trigger_accent'],
            selected_hover_color=self.COLORS['trigger_accent_hover'],
            font=self.FONTS['small'],
        )
        curve_trigger_toggle.pack(side=tk.RIGHT)

        CTkLabel(
            curve_frame,
            text="Arrastra los 4 puntos para crear 4 tramos reales de resistencia. Cada tramo se envía al hardware por separado.",
            font=self.FONTS['micro'],
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=15, pady=(0, 8))

        self.curve_canvas = tk.Canvas(
            curve_frame, width=self.CURVE_CANVAS_W, height=self.CURVE_CANVAS_H,
            bg=self.COLORS['bg_secondary'], highlightthickness=0
        )
        self.curve_canvas.pack(padx=15, pady=(0, 10))

        self.curve_zones_label = CTkLabel(
            curve_frame,
            text="",
            font=self.FONTS['micro'],
            text_color=self.COLORS['text_secondary']
        )
        self.curve_zones_label.pack(anchor="w", padx=15, pady=(0, 8))

        curve_actions = CTkFrame(curve_frame, fg_color="transparent")
        curve_actions.pack(fill=tk.X, padx=15, pady=(0, 15))

        CTkButton(
            curve_actions, text="Resetear curva",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['bg_secondary'],
            hover_color=self.COLORS['border'],
            corner_radius=8, height=30,
            command=self._reset_curve
        ).pack(side=tk.LEFT)

        CTkButton(
            curve_actions, text="Probar vibracion",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['bg_secondary'],
            hover_color=self.COLORS['border'],
            corner_radius=8, height=30,
            command=self._open_trigger_vibration_test
        ).pack(side=tk.LEFT, padx=(8, 0))

        CTkButton(
            curve_actions, text="Guardar curva",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['trigger_accent'],
            hover_color=self.COLORS['trigger_accent_hover'],
            corner_radius=8, height=30,
            command=self._save_curve
        ).pack(side=tk.RIGHT)

        # Estado interno: 4 puntos (posicion 0-9, fuerza 0-255) por gatillo.
        # Se cargan de lo guardado si existe, si no arrancan con una curva
        # pareja de ejemplo.
        default_points = [(0, 40), (3, 120), (6, 180), (9, 220)]
        self._curve_points = {
            'left': self._load_saved_curve('left') or list(default_points),
            'right': self._load_saved_curve('right') or list(default_points),
        }
        self._curve_dragging = None
        self._curve_last_apply = 0.0

        self.curve_canvas.bind("<Button-1>", self._on_curve_press)
        self.curve_canvas.bind("<B1-Motion>", self._on_curve_drag)
        self.curve_canvas.bind("<ButtonRelease-1>", self._on_curve_release)

        self._redraw_curve()

        # Boton de reset
        reset_btn = CTkButton(
            triggers_tab,
            text="Resetear Ambos Gatillos",
            font=self.FONTS['body_bold'],
            fg_color=self.COLORS['danger'],
            hover_color=self.COLORS['danger_hover'],
            corner_radius=10,
            height=40,
            command=self._reset_triggers
        )
        reset_btn.grid(row=2, column=0, columnspan=2, pady=15)

        # Agregar tab (solo para tkinter estandar)
        if not CUSTOMTK_AVAILABLE:
            self.tabs.add(triggers_tab, text="Gatillos")

    def _build_trigger_sliders(self, parent, trigger: str) -> None:
        """Construye los sliders de configuracion para un gatillo."""
        # Intensidad
        CTkLabel(
            parent, text="Intensidad:",
            font=self.FONTS['small'],
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=15, pady=(10, 0))

        intensity_frame = CTkFrame(parent, fg_color="transparent")
        intensity_frame.pack(fill=tk.X, padx=15, pady=5)

        intensity_slider = CTkSlider(
            intensity_frame,
            from_=0, to=255,
            number_of_steps=255,
            command=lambda v, t=trigger: self._on_intensity_change(t, v),
            fg_color=self.COLORS['bg_secondary'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['accent'],
            button_hover_color=self.COLORS['accent_hover'],
        )
        intensity_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        intensity_slider.set(128)

        intensity_value = CTkLabel(
            intensity_frame, text="128",
            font=self.FONTS['small'],
            text_color=self.COLORS['text_primary'],
            width=35
        )
        intensity_value.pack(side=tk.RIGHT, padx=(5, 0))

        setattr(self, f'{trigger}_intensity_slider', intensity_slider)
        setattr(self, f'{trigger}_intensity_value', intensity_value)

        # Posicion de inicio
        CTkLabel(
            parent, text="Posicion Inicio:",
            font=self.FONTS['small'],
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=15, pady=(10, 0))

        start_frame = CTkFrame(parent, fg_color="transparent")
        start_frame.pack(fill=tk.X, padx=15, pady=5)

        start_slider = CTkSlider(
            start_frame,
            from_=0, to=9,
            number_of_steps=9,
            command=lambda v, t=trigger: self._on_position_change(t, 'start', v),
            fg_color=self.COLORS['bg_secondary'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['accent'],
        )
        start_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        start_slider.set(0)

        start_value = CTkLabel(
            start_frame, text="0",
            font=self.FONTS['small'],
            text_color=self.COLORS['text_primary'],
            width=35
        )
        start_value.pack(side=tk.RIGHT, padx=(5, 0))

        setattr(self, f'{trigger}_start_slider', start_slider)
        setattr(self, f'{trigger}_start_value', start_value)

        # Posicion de fin
        CTkLabel(
            parent, text="Posicion Fin:",
            font=self.FONTS['small'],
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=15, pady=(10, 0))

        end_frame = CTkFrame(parent, fg_color="transparent")
        end_frame.pack(fill=tk.X, padx=15, pady=5)

        end_slider = CTkSlider(
            end_frame,
            from_=0, to=9,
            number_of_steps=9,
            command=lambda v, t=trigger: self._on_position_change(t, 'end', v),
            fg_color=self.COLORS['bg_secondary'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['accent'],
        )
        end_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        end_slider.set(9)

        end_value = CTkLabel(
            end_frame, text="9",
            font=self.FONTS['small'],
            text_color=self.COLORS['text_primary'],
            width=35
        )
        end_value.pack(side=tk.RIGHT, padx=(5, 0))

        setattr(self, f'{trigger}_end_slider', end_slider)
        setattr(self, f'{trigger}_end_value', end_value)

        # Frecuencia (para efectos pulsados)
        CTkLabel(
            parent, text="Frecuencia (Hz):",
            font=self.FONTS['small'],
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=15, pady=(10, 0))

        freq_frame = CTkFrame(parent, fg_color="transparent")
        freq_frame.pack(fill=tk.X, padx=15, pady=5)

        freq_slider = CTkSlider(
            freq_frame,
            from_=1, to=255,
            number_of_steps=254,
            command=lambda v, t=trigger: self._on_frequency_change(t, v),
            fg_color=self.COLORS['bg_secondary'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['accent'],
        )
        freq_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        freq_slider.set(25)

        freq_value = CTkLabel(
            freq_frame, text="25",
            font=self.FONTS['small'],
            text_color=self.COLORS['text_primary'],
            width=35
        )
        freq_value.pack(side=tk.RIGHT, padx=(5, 0))

        setattr(self, f'{trigger}_freq_slider', freq_slider)
        setattr(self, f'{trigger}_freq_value', freq_value)

    # ===== Pestaña: Macros =====

    def _build_macros_tab(self) -> None:
        """Construye la pestaña de macros."""
        if CUSTOMTK_AVAILABLE:
            macros_tab = self.tabs.add("Macros")
        else:
            macros_tab = CTkFrame(self.tabs, fg_color=self.COLORS['bg_secondary'])

        header_frame = CTkFrame(macros_tab, fg_color="transparent")
        header_frame.pack(fill=tk.X, padx=15, pady=15)

        CTkLabel(
            header_frame,
            text="Macros",
            font=self.FONTS['display'],
            text_color=self.COLORS['text_primary']
        ).pack(side=tk.LEFT)

        CTkLabel(
            header_frame,
            text="Graba secuencias de botones y asignales un gatillo",
            font=self.FONTS['small'],
            text_color=self.COLORS['text_secondary']
        ).pack(side=tk.LEFT, padx=(15, 0))

        new_macro_btn = CTkButton(
            header_frame,
            text="+ Nueva Macro",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['trigger_accent'],
            hover_color=self.COLORS['trigger_accent_hover'],
            corner_radius=8,
            height=32,
            command=lambda: self._open_macro_editor()
        )
        new_macro_btn.pack(side=tk.RIGHT, padx=(10, 0))

        macros_enabled_default = self.profile_manager.get_setting('macros_enabled', True) if self.profile_manager else True
        self.macros_enabled_var = tk.BooleanVar(value=macros_enabled_default)
        macros_switch = CTkSwitch(
            header_frame,
            text="Activas",
            variable=self.macros_enabled_var,
            command=self._on_macros_enabled_toggle,
            fg_color=self.COLORS['border'],
            progress_color=self.COLORS['trigger_accent'],
            button_color=self.COLORS['text_primary'],
            font=self.FONTS['small'],
        )
        macros_switch.pack(side=tk.RIGHT, padx=10)

        self.macros_emu_status_label = CTkLabel(
            macros_tab, text="",
            font=self.FONTS['caption'],
            anchor="w", justify="left", wraplength=700
        )
        self.macros_emu_status_label.pack(anchor="w", padx=15, pady=(0, 8))

        # Lista de macros
        self.macros_list_frame = CTkScrollableFrame(
            macros_tab,
            fg_color=self.COLORS['bg_secondary'],
            scrollbar_button_color=self.COLORS['border'],
            scrollbar_button_hover_color=self.COLORS['trigger_accent']
        )
        self.macros_list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        if not CUSTOMTK_AVAILABLE:
            self.tabs.add(macros_tab, text="Macros")

        self._populate_macros_list()
        self._refresh_emulation_status_labels()

    def _populate_macros_list(self) -> None:
        """Refresca la lista de macros guardadas."""
        if not hasattr(self, 'macros_list_frame'):
            return

        for widget in self.macros_list_frame.winfo_children():
            widget.destroy()

        if not self.macro_engine:
            CTkLabel(
                self.macros_list_frame,
                text="Motor de macros no disponible.",
                font=self.FONTS['body'],
                text_color=self.COLORS['text_secondary']
            ).pack(pady=30)
            return

        macros = self.macro_engine.get_macros()

        if not macros:
            CTkLabel(
                self.macros_list_frame,
                text='Todavia no creaste ninguna macro.\nToca "+ Nueva Macro" para grabar la primera.',
                font=self.FONTS['body'],
                text_color=self.COLORS['text_secondary'],
                justify="center"
            ).pack(pady=40)
            return

        for macro in macros:
            card = self._create_macro_card(self.macros_list_frame, macro)
            card.pack(fill=tk.X, padx=5, pady=5)

    def _create_macro_card(self, parent, macro) -> CTkFrame:
        """Crea una tarjeta visual para una macro guardada."""
        from src.macro_engine import BUTTON_LABELS

        card = CTkFrame(
            parent,
            fg_color=self.COLORS['bg_card'],
            corner_radius=12,
            border_width=2,
            border_color=self.COLORS['border']
        )

        top = CTkFrame(card, fg_color="transparent")
        top.pack(fill=tk.X, padx=12, pady=(12, 2))

        CTkLabel(
            top, text=macro.name,
            font=self.FONTS['title_sm'],
            text_color=self.COLORS['text_primary']
        ).pack(side=tk.LEFT)

        trigger_text = BUTTON_LABELS.get(macro.trigger_button) if macro.trigger_button else None
        CTkLabel(
            top,
            text=trigger_text if trigger_text else "Sin gatillo (solo manual)",
            font=self.FONTS['caption'],
            text_color=self.COLORS['trigger_accent'] if trigger_text else self.COLORS['text_secondary']
        ).pack(side=tk.RIGHT)

        CTkLabel(
            card,
            text=f"{len(macro.steps)} pasos  ·  repetir x{macro.repeat}",
            font=self.FONTS['mono'],
            text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=12, pady=(0, 10))

        btns = CTkFrame(card, fg_color="transparent")
        btns.pack(fill=tk.X, padx=12, pady=(0, 12))

        CTkButton(
            btns, text="▶ Probar", width=90,
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['trigger_accent'],
            hover_color=self.COLORS['trigger_accent_hover'],
            corner_radius=8, height=30,
            command=lambda mid=macro.id: self._test_macro(mid)
        ).pack(side=tk.LEFT, padx=(0, 5))

        CTkButton(
            btns, text="Editar", width=90,
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['bg_secondary'],
            hover_color=self.COLORS['border'],
            corner_radius=8, height=30,
            command=lambda mid=macro.id: self._open_macro_editor(mid)
        ).pack(side=tk.LEFT, padx=5)

        CTkButton(
            btns, text="Eliminar", width=90,
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['danger'],
            hover_color=self.COLORS['danger_hover'],
            corner_radius=8, height=30,
            command=lambda mid=macro.id, name=macro.name: self._delete_macro(mid, name)
        ).pack(side=tk.LEFT, padx=5)

        return card

    def _on_macros_enabled_toggle(self) -> None:
        """Activa/desactiva la escucha de gatillos de macros."""
        enabled = self.macros_enabled_var.get()
        if self.macro_engine:
            self.macro_engine.set_enabled(enabled)
        if self.profile_manager:
            self.profile_manager.set_setting('macros_enabled', enabled)

    def _test_macro(self, macro_id: str) -> None:
        """Reproduce una macro guardada de forma manual."""
        if not self.macro_engine:
            return
        if self.macro_engine.play_macro(macro_id):
            self._set_status("Reproduciendo macro...")
        else:
            self._set_status("No se pudo reproducir la macro (¿ya se esta reproduciendo?)")

    def _delete_macro(self, macro_id: str, name: str) -> None:
        """Elimina una macro guardada, con confirmacion."""
        if not messagebox.askyesno("Eliminar macro", f'¿Eliminar la macro "{name}"?'):
            return
        if self.macro_engine:
            self.macro_engine.delete_macro(macro_id)
            if self.profile_manager:
                self.profile_manager.set_macros(self.macro_engine.export_macros())
            self._populate_macros_list()
            self._set_status(f'Macro "{name}" eliminada')

    def _open_macro_editor(self, macro_id: Optional[str] = None) -> None:
        """Abre la ventana para crear o editar una macro."""
        if not self.macro_engine:
            messagebox.showerror("Macros", "El motor de macros no esta disponible.")
            return

        from src.macro_engine import Macro, MacroTrigger, TriggerKind, MACRO_BUTTONS, BUTTON_LABELS

        editing = None
        if macro_id:
            editing = next((m for m in self.macro_engine.get_macros() if m.id == macro_id), None)

        if CUSTOMTK_AVAILABLE:
            win = ctk.CTkToplevel(self.root, fg_color=self.COLORS['bg_primary'])
        else:
            win = tk.Toplevel(self.root, bg=self.COLORS['bg_primary'])

        win.title("Editar Macro" if editing else "Nueva Macro")
        win.geometry("440x600")
        win.minsize(400, 500)
        win.transient(self.root)
        win.grab_set()

        # Copia de trabajo de los pasos: no se toca la macro guardada hasta "Guardar"
        editor_steps: List = list(editing.steps) if editing else []
        recording_state = {"active": False}

        # --- Nombre ---
        CTkLabel(
            win, text="Nombre",
            font=self.FONTS['small'], text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=15, pady=(15, 2))

        name_entry = CTkEntry(win, font=self.FONTS['body'])
        name_entry.pack(fill=tk.X, padx=15)
        name_entry.insert(0, editing.name if editing else "Macro nueva")

        # --- Boton que la activa ---
        CTkLabel(
            win, text="Boton que la activa en el control fisico",
            font=self.FONTS['small'], text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=15, pady=(12, 2))

        NONE_LABEL = "Ninguno (solo manual, boton Probar)"
        trigger_values = [NONE_LABEL] + [BUTTON_LABELS[b] for b in MACRO_BUTTONS]
        trigger_var = tk.StringVar(
            value=BUTTON_LABELS.get(editing.trigger_button, NONE_LABEL)
            if (editing and editing.trigger_button) else NONE_LABEL
        )
        CTkOptionMenu(
            win, values=trigger_values, variable=trigger_var,
            font=self.FONTS['small'],
            fg_color=self.COLORS['bg_secondary'],
            button_color=self.COLORS['trigger_accent'],
            button_hover_color=self.COLORS['trigger_accent_hover'],
        ).pack(fill=tk.X, padx=15)

        # --- Repeticiones ---
        CTkLabel(
            win, text="Repeticiones (1-50)",
            font=self.FONTS['small'], text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=15, pady=(12, 2))

        repeat_entry = CTkEntry(win, font=self.FONTS['body'])
        repeat_entry.pack(fill=tk.X, padx=15)
        repeat_entry.insert(0, str(editing.repeat if editing else 1))

        # --- Grabacion ---
        rec_frame = CTkFrame(win, fg_color=self.COLORS['bg_card'], corner_radius=10)
        rec_frame.pack(fill=tk.X, padx=15, pady=(15, 5))

        rec_status_label = CTkLabel(
            rec_frame, text=f"{len(editor_steps)} pasos grabados",
            font=self.FONTS['mono'], text_color=self.COLORS['text_primary']
        )
        rec_status_label.pack(side=tk.LEFT, padx=12, pady=10)

        rec_btn = CTkButton(
            rec_frame, text="● Grabar",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['danger'],
            hover_color=self.COLORS['danger_hover'],
            corner_radius=8, width=120,
            command=lambda: toggle_recording()
        )
        rec_btn.pack(side=tk.RIGHT, padx=12, pady=10)

        CTkLabel(
            win,
            text=f"Toca \"Grabar\" y despues presiona los botones en tu DualSense fisico "
                 f"(maximo {self.macro_engine.MAX_RECORD_SECONDS}s).",
            font=self.FONTS['micro'], text_color=self.COLORS['text_secondary'],
            wraplength=400, justify="left"
        ).pack(anchor="w", padx=15, pady=(0, 10))

        # --- Preview de pasos ---
        CTkLabel(
            win, text="Pasos grabados",
            font=self.FONTS['small'], text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=15)

        steps_frame = CTkScrollableFrame(
            win, fg_color=self.COLORS['bg_secondary'],
            scrollbar_button_color=self.COLORS['border']
        )
        steps_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(2, 10))

        def refresh_steps_preview():
            for w in steps_frame.winfo_children():
                w.destroy()
            if not editor_steps:
                CTkLabel(
                    steps_frame, text="Sin pasos todavia.",
                    font=self.FONTS['caption'], text_color=self.COLORS['text_secondary']
                ).pack(pady=10)
                return
            for i, step in enumerate(editor_steps, 1):
                CTkLabel(
                    steps_frame, text=f"{i:>2}. {step.describe()}",
                    font=self.FONTS['mono'], text_color=self.COLORS['text_primary'],
                    anchor="w"
                ).pack(fill=tk.X, padx=8, pady=1)

        refresh_steps_preview()

        def safe_ui(fn):
            """Ejecuta fn solo si la ventana del editor sigue viva (evita errores
            si el callback de grabacion llega despues de cerrar la ventana)."""
            try:
                if win.winfo_exists():
                    fn()
            except tk.TclError:
                pass

        def poll_recording():
            if not recording_state["active"]:
                return
            if not self.macro_engine.is_recording:
                finish_recording()
                return
            try:
                win.after(150, poll_recording)
            except tk.TclError:
                pass

        def start_recording_ui():
            recording_state["active"] = True
            editor_steps.clear()
            refresh_steps_preview()
            self.macro_engine.start_recording()
            rec_btn.configure(
                text="■ Detener",
                fg_color=self.COLORS['trigger_accent'],
                hover_color=self.COLORS['trigger_accent_hover']
            )
            rec_status_label.configure(text="Grabando... movete!")
            win.after(150, poll_recording)

        def finish_recording():
            recording_state["active"] = False
            steps = self.macro_engine.stop_recording()
            editor_steps.clear()
            editor_steps.extend(steps)
            rec_btn.configure(
                text="● Grabar",
                fg_color=self.COLORS['danger'],
                hover_color=self.COLORS['danger_hover']
            )
            rec_status_label.configure(text=f"{len(editor_steps)} pasos grabados")
            refresh_steps_preview()

        def toggle_recording():
            if recording_state["active"]:
                finish_recording()
                return
            if not (self.connection_manager and self.connection_manager.is_connected):
                messagebox.showwarning("Macros", "Conecta el DualSense fisico para grabar una macro.")
                return
            start_recording_ui()

        def on_recording_tick(step_count, elapsed):
            if recording_state["active"]:
                safe_ui(lambda: rec_status_label.configure(
                    text=f"Grabando... {step_count} pasos · {elapsed:.1f}s"
                ))

        self.macro_engine.on_recording_tick(on_recording_tick)

        # --- Botones de accion ---
        actions = CTkFrame(win, fg_color="transparent")
        actions.pack(fill=tk.X, padx=15, pady=(0, 15))

        def do_test():
            if recording_state["active"]:
                messagebox.showinfo("Macros", "Termina de grabar antes de probar.")
                return
            if not editor_steps:
                messagebox.showinfo("Macros", "No hay pasos para probar todavia.")
                return
            self.macro_engine.play_steps(list(editor_steps))

        CTkButton(
            actions, text="Probar", font=self.FONTS['small_bold'],
            fg_color=self.COLORS['bg_secondary'], hover_color=self.COLORS['border'],
            corner_radius=8, command=do_test
        ).pack(side=tk.LEFT)

        def do_cancel():
            if recording_state["active"]:
                recording_state["active"] = False
                self.macro_engine.stop_recording()
            win.destroy()

        CTkButton(
            actions, text="Cancelar", font=self.FONTS['small_bold'],
            fg_color=self.COLORS['bg_secondary'], hover_color=self.COLORS['border'],
            corner_radius=8, command=do_cancel
        ).pack(side=tk.RIGHT, padx=(5, 0))

        def do_save():
            if recording_state["active"]:
                finish_recording()

            name = name_entry.get().strip() or "Macro sin nombre"

            try:
                repeat = max(1, min(50, int(repeat_entry.get().strip() or "1")))
            except ValueError:
                repeat = 1

            trig_display = trigger_var.get()
            trigger_button = None
            for b in MACRO_BUTTONS:
                if BUTTON_LABELS[b] == trig_display:
                    trigger_button = b
                    break

            if not editor_steps:
                messagebox.showwarning("Macros", "Graba al menos un paso antes de guardar.")
                return

            otras_macros = [m for m in self.macro_engine.get_macros() if not editing or m.id != editing.id]

            # Aviso: nombre repetido (no bloquea, pero confunde en la lista)
            if any(m.name.strip().lower() == name.lower() for m in otras_macros):
                if not messagebox.askyesno(
                    "Nombre repetido",
                    f'Ya existe otra macro llamada "{name}". ¿Guardar igual?'
                ):
                    return

            # Aviso: mismo boton disparador que otra macro (las dos se van a
            # disparar juntas al presionarlo)
            if trigger_button:
                conflicto = next((m for m in otras_macros if m.trigger_button == trigger_button), None)
                if conflicto:
                    if not messagebox.askyesno(
                        "Boton ya usado",
                        f'"{BUTTON_LABELS[trigger_button]}" ya activa la macro "{conflicto.name}".\n'
                        f'Si guardas, las dos se van a disparar juntas al presionarlo. ¿Continuar?'
                    ):
                        return

            macro = Macro(
                id=editing.id if editing else self.macro_engine.new_macro_id(),
                name=name,
                trigger=MacroTrigger(
                    kind=TriggerKind.BUTTON if trigger_button else TriggerKind.MANUAL,
                    buttons=[trigger_button] if trigger_button else [],
                ),
                steps=list(editor_steps),
                repeat=repeat,
            )
            self.macro_engine.save_macro(macro)
            if self.profile_manager:
                self.profile_manager.set_macros(self.macro_engine.export_macros())

            win.destroy()
            self._populate_macros_list()
            self._set_status(f'Macro "{name}" guardada')

        CTkButton(
            actions, text="Guardar", font=self.FONTS['small_bold'],
            fg_color=self.COLORS['trigger_accent'], hover_color=self.COLORS['trigger_accent_hover'],
            corner_radius=8, command=do_save
        ).pack(side=tk.RIGHT)

        win.protocol("WM_DELETE_WINDOW", do_cancel)

    # ===== Pestaña: Botones (remapeo) =====

    def _build_buttons_tab(self) -> None:
        """Construye el editor de remapeo avanzado por capas."""
        from src.advanced_mapping import DEFAULT_CONFIG, sanitize_config

        if CUSTOMTK_AVAILABLE:
            buttons_tab = self.tabs.add("Botones")
        else:
            buttons_tab = CTkFrame(self.tabs, fg_color=self.COLORS['bg_secondary'])

        header_frame = CTkFrame(buttons_tab, fg_color="transparent")
        header_frame.pack(fill=tk.X, padx=15, pady=15)

        CTkLabel(
            header_frame, text="Remapeo avanzado",
            font=self.FONTS['display'],
            text_color=self.COLORS['text_primary']
        ).pack(side=tk.LEFT)

        CTkLabel(
            header_frame,
            text="Acciones, atajos, capas, gestos y turbo por cada entrada",
            font=self.FONTS['small'],
            text_color=self.COLORS['text_secondary']
        ).pack(side=tk.LEFT, padx=(15, 0))

        CTkButton(
            header_frame, text="Restablecer",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['bg_secondary'],
            hover_color=self.COLORS['border'],
            corner_radius=8, height=32,
            command=self._reset_button_map
        ).pack(side=tk.RIGHT)

        self._advanced_mapping_config = sanitize_config(
            self.advanced_mapper.get_config() if self.advanced_mapper else DEFAULT_CONFIG
        )
        self._button_edit_layer_var = tk.StringVar(
            value=self._advanced_mapping_config['default_layer']
        )
        self.advanced_enabled_var = tk.BooleanVar(
            value=bool(self._advanced_mapping_config['enabled'])
        )

        control_bar = CTkFrame(
            buttons_tab, fg_color=self.COLORS['bg_card'], corner_radius=12,
            border_width=1, border_color=self.COLORS['border'],
        )
        control_bar.pack(fill=tk.X, padx=15, pady=(0, 8))

        CTkSwitch(
            control_bar, text="Remapeo avanzado activo", variable=self.advanced_enabled_var,
            command=self._toggle_advanced_mapping, font=self.FONTS['small_bold'],
            progress_color=self.COLORS['accent'], button_color=self.COLORS['accent'],
        ).pack(side=tk.LEFT, padx=12, pady=10)

        CTkLabel(control_bar, text="Capa de edición", font=self.FONTS['small'],
                 text_color=self.COLORS['text_secondary']).pack(side=tk.LEFT, padx=(18, 6))
        self.button_layer_menu = CTkOptionMenu(
            control_bar, values=list(self._advanced_mapping_config['layers']),
            variable=self._button_edit_layer_var, width=145,
            command=self._on_button_layer_changed,
            fg_color=self.COLORS['bg_secondary'], button_color=self.COLORS['accent'],
            button_hover_color=self.COLORS['accent_hover'],
        )
        self.button_layer_menu.pack(side=tk.LEFT, pady=10)
        CTkButton(
            control_bar, text="+ Capa", width=66, height=30,
            font=self.FONTS['small_bold'], fg_color=self.COLORS['bg_secondary'],
            hover_color=self.COLORS['border'], corner_radius=7,
            command=self._add_mapping_layer,
        ).pack(side=tk.LEFT, padx=(8, 4))
        CTkButton(
            control_bar, text="−", width=30, height=30,
            font=self.FONTS['small_bold'], fg_color="transparent",
            text_color=self.COLORS['danger'], hover_color=self.COLORS['bg_secondary'],
            corner_radius=7, command=self._delete_mapping_layer,
        ).pack(side=tk.LEFT, padx=(0, 12))

        note = CTkLabel(
            buttons_tab,
            text=("Una entrada puede tener varias acciones: mantener, alternar, corta, larga o doble toque. "
                  "Los requisitos crean atajos (por ejemplo L1 + Cruz); Passthrough deja pasar el botón original."),
            font=self.FONTS['micro'],
            text_color=self.COLORS['text_secondary'],
            justify="left", wraplength=800,
        )
        note.pack(anchor="w", padx=15, pady=(0, 4))

        self.buttons_emu_status_label = CTkLabel(
            buttons_tab, text="",
            font=self.FONTS['caption'],
            anchor="w", justify="left", wraplength=700
        )
        self.buttons_emu_status_label.pack(anchor="w", padx=15, pady=(0, 10))

        self.buttons_list_frame = CTkScrollableFrame(
            buttons_tab,
            fg_color=self.COLORS['bg_secondary'],
            scrollbar_button_color=self.COLORS['border'],
            scrollbar_button_hover_color=self.COLORS['accent']
        )
        self.buttons_list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        if not CUSTOMTK_AVAILABLE:
            self.tabs.add(buttons_tab, text="Botones")

        # El mapa basico antiguo sigue vivo como compatibilidad. Un binding
        # avanzado que bloquee el origen lo reemplaza solo para esa entrada.
        self._button_map_state = (
            self.connection_manager.emulator.get_button_map()
            if (self.connection_manager and self.connection_manager.emulator)
            else {}
        )

        self._populate_button_rows()
        self._refresh_emulation_status_labels()

    def _populate_button_rows(self) -> None:
        """Dibuja bindings de la capa elegida sin perder el mapa legado."""
        from src.emulator import REMAPPABLE_BUTTONS, BUTTON_FRIENDLY_NAMES

        for widget in self.buttons_list_frame.winfo_children():
            widget.destroy()

        for source in REMAPPABLE_BUTTONS:
            row = CTkFrame(
                self.buttons_list_frame,
                fg_color=self.COLORS['bg_card'],
                corner_radius=10, border_width=1, border_color=self.COLORS['border'],
            )
            row.pack(fill=tk.X, padx=5, pady=4)

            CTkLabel(
                row, text=BUTTON_FRIENDLY_NAMES[source],
                font=self.FONTS['body'],
                text_color=self.COLORS['text_primary'],
                width=180, anchor="w"
            ).pack(side=tk.LEFT, padx=(15, 8), pady=12)

            summary = CTkLabel(
                row, text=self._advanced_binding_summary(source),
                font=self.FONTS['caption'], text_color=self.COLORS['text_secondary'],
                anchor="w", justify="left", wraplength=460,
            )
            summary.pack(side=tk.LEFT, padx=6, pady=9, fill=tk.X, expand=True)

            count = len(self._current_layer_bindings(source))
            CTkButton(
                row, text=f"Editar{f' ({count})' if count else ''}", width=92, height=31,
                font=self.FONTS['small_bold'], fg_color=self.COLORS['accent'],
                hover_color=self.COLORS['accent_hover'], corner_radius=8,
                command=lambda src=source: self._open_advanced_mapping_editor(src),
            ).pack(side=tk.RIGHT, padx=12, pady=10)

    def _current_button_layer(self) -> str:
        layer = self._button_edit_layer_var.get()
        return layer if layer in self._advanced_mapping_config['layers'] else 'base'

    def _current_layer_bindings(self, source: str) -> List[Dict[str, Any]]:
        return list(self._advanced_mapping_config['layers'].get(self._current_button_layer(), {}).get(source, []))

    def _advanced_binding_summary(self, source: str) -> str:
        from src.emulator import BUTTON_FRIENDLY_NAMES
        action_names = {
            'controller': 'Control', 'keyboard': 'Tecla', 'mouse_button': 'Mouse',
            'mouse_move': 'Mover mouse', 'macro': 'Macro', 'profile': 'Perfil',
            'layer': 'Capa', 'disabled': 'Desactivado', 'passthrough': 'Passthrough',
        }
        activation_names = {
            'hold': 'Mantener', 'toggle': 'Alternar', 'press': 'Al pulsar',
            'short': 'Corta', 'long': 'Larga', 'double': 'Doble',
        }
        bindings = self._current_layer_bindings(source)
        if bindings:
            parts = []
            for binding in bindings:
                value = binding.get('value', '') or '—'
                if binding.get('action_type') == 'controller':
                    value = BUTTON_FRIENDLY_NAMES.get(value, value)
                turbo = ' · turbo' if binding.get('turbo') else ''
                parts.append(f"{activation_names.get(binding.get('activation'), 'Acción')}: "
                             f"{action_names.get(binding.get('action_type'), 'Acción')} {value}{turbo}")
            return "\n".join(parts)
        legacy = self._button_map_state.get(source)
        if legacy == 'none':
            return 'Legado: deshabilitado'
        if legacy and legacy != source:
            return f"Legado: → {BUTTON_FRIENDLY_NAMES.get(legacy, legacy)}"
        return 'Sin binding · passthrough normal'

    def _save_advanced_mapping_config(self) -> None:
        from src.advanced_mapping import sanitize_config
        self._advanced_mapping_config = sanitize_config(self._advanced_mapping_config)
        if self.advanced_mapper:
            self.advanced_mapper.set_config(self._advanced_mapping_config)
        if self.profile_manager:
            self.profile_manager.set_advanced_mapping(self._advanced_mapping_config)
            self.profile_manager.save_config()

    def _toggle_advanced_mapping(self) -> None:
        self._advanced_mapping_config['enabled'] = bool(self.advanced_enabled_var.get())
        self._save_advanced_mapping_config()
        self._set_status(
            'Remapeo avanzado activado' if self.advanced_enabled_var.get() else 'Remapeo avanzado desactivado'
        )

    def _on_button_layer_changed(self, _choice: str) -> None:
        self._populate_button_rows()

    def _refresh_button_layer_menu(self, selected: Optional[str] = None) -> None:
        layers = list(self._advanced_mapping_config['layers'])
        target = selected if selected in layers else 'base'
        self.button_layer_menu.configure(values=layers)
        self._button_edit_layer_var.set(target)

    def _add_mapping_layer(self) -> None:
        if CUSTOMTK_AVAILABLE:
            win = ctk.CTkToplevel(self.root, fg_color=self.COLORS['bg_primary'])
        else:
            win = tk.Toplevel(self.root, bg=self.COLORS['bg_primary'])
        win.title('Nueva capa')
        win.geometry('360x180')
        win.transient(self.root)
        CTkLabel(win, text='Nombre de la capa', font=self.FONTS['title_sm'],
                 text_color=self.COLORS['text_primary']).pack(anchor='w', padx=18, pady=(18, 5))
        entry = CTkEntry(win, placeholder_text='Ej.: combate', height=34)
        entry.pack(fill=tk.X, padx=18)

        def save() -> None:
            name = re.sub(r'[^a-z0-9_]+', '_', entry.get().strip().lower().replace(' ', '_')).strip('_')
            if not name:
                messagebox.showwarning('Capas', 'Escribe un nombre válido.', parent=win)
                return
            if name in self._advanced_mapping_config['layers']:
                messagebox.showwarning('Capas', 'Ya existe una capa con ese nombre.', parent=win)
                return
            self._advanced_mapping_config['layers'][name] = {}
            self._save_advanced_mapping_config()
            self._refresh_button_layer_menu(name)
            self._populate_button_rows()
            win.destroy()

        CTkButton(win, text='Cancelar', width=90, command=win.destroy,
                  fg_color=self.COLORS['bg_secondary'], hover_color=self.COLORS['border']).pack(side=tk.LEFT, padx=18, pady=18)
        CTkButton(win, text='Crear capa', width=100, command=save,
                  fg_color=self.COLORS['accent'], hover_color=self.COLORS['accent_hover']).pack(side=tk.RIGHT, padx=18, pady=18)
        entry.focus_set()

    def _delete_mapping_layer(self) -> None:
        layer = self._current_button_layer()
        if layer == 'base':
            messagebox.showinfo('Capas', 'La capa base no se puede eliminar.', parent=self.root)
            return
        if not messagebox.askyesno('Eliminar capa', f'¿Eliminar la capa "{layer}" y todos sus bindings?', parent=self.root):
            return
        self._advanced_mapping_config['layers'].pop(layer, None)
        if self._advanced_mapping_config['default_layer'] == layer:
            self._advanced_mapping_config['default_layer'] = 'base'
        self._save_advanced_mapping_config()
        self._refresh_button_layer_menu('base')
        self._populate_button_rows()

    def _open_advanced_mapping_editor(self, source: str) -> None:
        from src.emulator import BUTTON_FRIENDLY_NAMES
        if CUSTOMTK_AVAILABLE:
            win = ctk.CTkToplevel(self.root, fg_color=self.COLORS['bg_primary'])
        else:
            win = tk.Toplevel(self.root, bg=self.COLORS['bg_primary'])
        win.title(f'Bindings · {BUTTON_FRIENDLY_NAMES[source]}')
        win.geometry('680x510')
        win.transient(self.root)

        CTkLabel(win, text=BUTTON_FRIENDLY_NAMES[source], font=self.FONTS['display_sm'],
                 text_color=self.COLORS['text_primary']).pack(anchor='w', padx=18, pady=(16, 2))
        subtitle = CTkLabel(win, text=f'Capa: {self._current_button_layer()}', font=self.FONTS['caption'],
                            text_color=self.COLORS['trigger_accent'])
        subtitle.pack(anchor='w', padx=18, pady=(0, 10))
        list_frame = CTkScrollableFrame(win, fg_color=self.COLORS['bg_secondary'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 10))

        def refresh() -> None:
            for widget in list_frame.winfo_children():
                widget.destroy()
            bindings = self._current_layer_bindings(source)
            if not bindings:
                CTkLabel(list_frame, text='Sin acciones. Añade una para empezar.', font=self.FONTS['body'],
                         text_color=self.COLORS['text_secondary']).pack(pady=28)
                return
            for index, binding in enumerate(bindings):
                card = CTkFrame(list_frame, fg_color=self.COLORS['bg_card'], corner_radius=9)
                card.pack(fill=tk.X, padx=4, pady=4)
                CTkLabel(card, text=self._advanced_binding_summary_from(binding), font=self.FONTS['small'],
                         text_color=self.COLORS['text_primary'], justify='left', anchor='w').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=9)
                CTkButton(card, text='Editar', width=62, height=28, font=self.FONTS['small_bold'],
                          fg_color=self.COLORS['bg_secondary'], hover_color=self.COLORS['border'],
                          command=lambda i=index: self._open_mapping_binding_editor(source, i, refresh)).pack(side=tk.RIGHT, padx=(4, 8), pady=7)
                CTkButton(card, text='×', width=28, height=28, font=self.FONTS['body_bold'],
                          fg_color='transparent', text_color=self.COLORS['danger'], hover_color=self.COLORS['bg_secondary'],
                          command=lambda i=index: self._delete_mapping_binding(source, i, refresh)).pack(side=tk.RIGHT, pady=7)

        actions = CTkFrame(win, fg_color='transparent')
        actions.pack(fill=tk.X, padx=18, pady=(0, 16))
        CTkButton(actions, text='+ Añadir acción', command=lambda: self._open_mapping_binding_editor(source, None, refresh),
                  font=self.FONTS['small_bold'], fg_color=self.COLORS['accent'], hover_color=self.COLORS['accent_hover']).pack(side=tk.LEFT)
        CTkButton(actions, text='Cerrar', command=win.destroy, font=self.FONTS['small_bold'],
                  fg_color=self.COLORS['bg_secondary'], hover_color=self.COLORS['border']).pack(side=tk.RIGHT)
        refresh()

    def _advanced_binding_summary_from(self, binding: Dict[str, Any]) -> str:
        names = {'controller': 'Control virtual', 'keyboard': 'Tecla / atajo', 'mouse_button': 'Clic mouse',
                 'mouse_move': 'Mover mouse', 'macro': 'Macro', 'profile': 'Perfil', 'layer': 'Capa',
                 'disabled': 'Desactivar entrada', 'passthrough': 'Passthrough'}
        modes = {'hold': 'Mantener', 'toggle': 'Alternar', 'press': 'Al pulsar',
                 'short': 'Pulsación corta', 'long': 'Pulsación larga', 'double': 'Doble toque'}
        suffix = ' · turbo' if binding.get('turbo') else ''
        requirements = f" · con {' + '.join(binding.get('requires', []))}" if binding.get('requires') else ''
        return f"{modes.get(binding.get('activation'), 'Acción')} → {names.get(binding.get('action_type'), 'Acción')} {binding.get('value') or '—'}{suffix}{requirements}"

    def _delete_mapping_binding(self, source: str, index: int, refresh_callback) -> None:
        layer_map = self._advanced_mapping_config['layers'].setdefault(self._current_button_layer(), {})
        bindings = list(layer_map.get(source, []))
        if 0 <= index < len(bindings):
            bindings.pop(index)
        if bindings:
            layer_map[source] = bindings
        else:
            layer_map.pop(source, None)
        self._save_advanced_mapping_config()
        self._populate_button_rows()
        refresh_callback()

    def _open_mapping_binding_editor(self, source: str, index: Optional[int], on_saved) -> None:
        from src.advanced_mapping import sanitize_binding
        bindings = self._current_layer_bindings(source)
        binding = dict(bindings[index]) if index is not None and 0 <= index < len(bindings) else sanitize_binding({})
        if CUSTOMTK_AVAILABLE:
            win = ctk.CTkToplevel(self.root, fg_color=self.COLORS['bg_primary'])
        else:
            win = tk.Toplevel(self.root, bg=self.COLORS['bg_primary'])
        win.title('Editar acción' if index is not None else 'Nueva acción')
        win.geometry('650x610')
        win.transient(self.root)
        form = CTkScrollableFrame(win, fg_color=self.COLORS['bg_primary'])
        form.pack(fill=tk.BOTH, expand=True, padx=18, pady=16)

        type_labels = {'Control virtual': 'controller', 'Tecla / atajo': 'keyboard', 'Clic del mouse': 'mouse_button',
                       'Mover mouse': 'mouse_move', 'Macro': 'macro', 'Cambiar perfil': 'profile',
                       'Cambiar capa': 'layer', 'Desactivar entrada': 'disabled', 'Passthrough': 'passthrough'}
        mode_labels = {'Mantener': 'hold', 'Alternar': 'toggle', 'Al pulsar': 'press', 'Pulsación corta': 'short',
                       'Pulsación larga': 'long', 'Doble toque': 'double'}
        type_var = tk.StringVar(value=next((label for label, value in type_labels.items() if value == binding['action_type']), 'Control virtual'))
        mode_var = tk.StringVar(value=next((label for label, value in mode_labels.items() if value == binding['activation']), 'Mantener'))
        target_var = tk.StringVar(value=binding['value'])
        requires_var = tk.StringVar(value=', '.join(binding['requires']))
        block_var = tk.BooleanVar(value=bool(binding['block_original']))
        turbo_var = tk.BooleanVar(value=bool(binding['turbo']))

        def label(text: str) -> None:
            CTkLabel(form, text=text, font=self.FONTS['small_bold'], text_color=self.COLORS['text_secondary']).pack(anchor='w', pady=(8, 3))

        label('Tipo de acción')
        type_menu = CTkOptionMenu(form, values=list(type_labels), variable=type_var,
                                  fg_color=self.COLORS['bg_secondary'], button_color=self.COLORS['accent'], button_hover_color=self.COLORS['accent_hover'])
        type_menu.pack(fill=tk.X)
        label('Cuándo se activa')
        CTkOptionMenu(form, values=list(mode_labels), variable=mode_var,
                      fg_color=self.COLORS['bg_secondary'], button_color=self.COLORS['accent'], button_hover_color=self.COLORS['accent_hover']).pack(fill=tk.X)
        label('Destino / valor')
        target_entry = CTkEntry(form, textvariable=target_var, height=34)
        target_entry.pack(fill=tk.X)
        target_hint = CTkLabel(form, text='', font=self.FONTS['micro'], text_color=self.COLORS['text_secondary'], justify='left', wraplength=590)
        target_hint.pack(anchor='w', pady=(3, 5))
        quick_var = tk.StringVar(value='Elegir sugerencia…')
        quick_menu = CTkOptionMenu(form, values=['Elegir sugerencia…'], variable=quick_var,
                                   fg_color=self.COLORS['bg_secondary'], button_color=self.COLORS['accent'], button_hover_color=self.COLORS['accent_hover'])
        quick_menu.pack(fill=tk.X)

        def refresh_targets(_choice=None) -> None:
            from src.emulator import BUTTON_FRIENDLY_NAMES, REMAPPABLE_BUTTONS
            action_type = type_labels[type_var.get()]
            if action_type == 'controller':
                choices = list(REMAPPABLE_BUTTONS)
                hint = 'Control virtual: usa un ID de botón o selecciónalo arriba.'
            elif action_type == 'macro':
                choices = [macro.id for macro in self.macro_engine.get_macros()] if self.macro_engine else []
                hint = 'Macro: selecciona o escribe su ID.'
            elif action_type == 'profile':
                choices = [profile_id for profile_id, _name in self.trigger_engine.get_profile_names()] if self.trigger_engine else []
                hint = 'Perfil: al mantener vuelve al perfil anterior al soltar; Alternar lo deja activo.'
            elif action_type == 'layer':
                choices = list(self._advanced_mapping_config['layers'])
                hint = 'Capa: al mantener vuelve a la capa anterior al soltar.'
            elif action_type == 'mouse_button':
                choices, hint = ['left', 'right', 'middle', 'x1', 'x2'], 'Mouse: left, right, middle, x1 o x2.'
            elif action_type == 'mouse_move':
                choices, hint = [], 'Movimiento relativo: escribe dx,dy; por ejemplo 30,-15.'
            elif action_type == 'keyboard':
                choices, hint = [], 'Tecla o atajo: por ejemplo F, SPACE, CTRL+SHIFT+F o ALT+TAB.'
            elif action_type == 'disabled':
                choices, hint = [], 'Bloquea la entrada física sin enviar otra acción.'
            else:
                choices, hint = [], 'Deja pasar la entrada física al gamepad virtual.'
            values = ['Elegir sugerencia…'] + choices
            quick_menu.configure(values=values)
            quick_var.set('Elegir sugerencia…')
            target_hint.configure(text=hint)

        def select_target(choice: str) -> None:
            if choice != 'Elegir sugerencia…':
                target_var.set(choice)

        type_menu.configure(command=refresh_targets)
        quick_menu.configure(command=select_target)
        refresh_targets()
        label('Atajo / filtro (botones que deben mantenerse)')
        CTkEntry(form, textvariable=requires_var, placeholder_text='Ej.: L1, R1').pack(fill=tk.X)
        option_row = CTkFrame(form, fg_color='transparent')
        option_row.pack(fill=tk.X, pady=(10, 0))
        CTkSwitch(option_row, text='Bloquear acción original', variable=block_var,
                  font=self.FONTS['small'], progress_color=self.COLORS['accent']).pack(side=tk.LEFT)
        CTkSwitch(option_row, text='Turbo', variable=turbo_var,
                  font=self.FONTS['small'], progress_color=self.COLORS['trigger_accent']).pack(side=tk.RIGHT)
        timing_row = CTkFrame(form, fg_color='transparent')
        timing_row.pack(fill=tk.X, pady=(8, 0))
        CTkLabel(timing_row, text='Turbo Hz', font=self.FONTS['small'], text_color=self.COLORS['text_secondary']).pack(side=tk.LEFT)
        turbo_entry = CTkEntry(timing_row, width=55, justify='center')
        turbo_entry.insert(0, str(binding['turbo_hz']))
        turbo_entry.pack(side=tk.LEFT, padx=(5, 16))
        CTkLabel(timing_row, text='Larga ms', font=self.FONTS['small'], text_color=self.COLORS['text_secondary']).pack(side=tk.LEFT)
        long_entry = CTkEntry(timing_row, width=62, justify='center')
        long_entry.insert(0, str(binding['long_press_ms']))
        long_entry.pack(side=tk.LEFT, padx=(5, 16))
        CTkLabel(timing_row, text='Doble ms', font=self.FONTS['small'], text_color=self.COLORS['text_secondary']).pack(side=tk.LEFT)
        double_entry = CTkEntry(timing_row, width=62, justify='center')
        double_entry.insert(0, str(binding['double_tap_ms']))
        double_entry.pack(side=tk.LEFT, padx=(5, 0))

        footer = CTkFrame(form, fg_color='transparent')
        footer.pack(fill=tk.X, pady=(18, 4))
        def save() -> None:
            raw = {
                'action_type': type_labels[type_var.get()], 'value': target_var.get(),
                'activation': mode_labels[mode_var.get()], 'requires': requires_var.get(),
                'block_original': block_var.get(), 'turbo': turbo_var.get(),
                'turbo_hz': turbo_entry.get(), 'long_press_ms': long_entry.get(), 'double_tap_ms': double_entry.get(),
            }
            clean = sanitize_binding(raw)
            layer_map = self._advanced_mapping_config['layers'].setdefault(self._current_button_layer(), {})
            current = list(layer_map.get(source, []))
            if index is None:
                current.append(clean)
            else:
                current[index] = clean
            layer_map[source] = current
            # Un binding avanzado bloqueante reemplaza el remapeo simple para
            # evitar que una configuracion antigua reaparezca al borrarlo.
            if clean['block_original']:
                self._button_map_state.pop(source, None)
                if self.connection_manager and self.connection_manager.emulator:
                    self.connection_manager.emulator.set_button_map(self._button_map_state)
                if self.profile_manager:
                    self.profile_manager.set_button_map(self._button_map_state)
            self._save_advanced_mapping_config()
            self._populate_button_rows()
            on_saved()
            win.destroy()

        CTkButton(footer, text='Cancelar', command=win.destroy, width=94,
                  fg_color=self.COLORS['bg_secondary'], hover_color=self.COLORS['border']).pack(side=tk.LEFT)
        CTkButton(footer, text='Guardar acción', command=save, width=120,
                  fg_color=self.COLORS['accent'], hover_color=self.COLORS['accent_hover']).pack(side=tk.RIGHT)

    def _on_button_remap_change(self, source: str, choice: str) -> None:
        """Aplica y guarda un cambio de remapeo de un boton individual."""
        from src.emulator import BUTTON_FRIENDLY_NAMES

        friendly_to_key = {v: k for k, v in BUTTON_FRIENDLY_NAMES.items()}
        friendly_to_key["Deshabilitado"] = "none"
        target = friendly_to_key.get(choice, source)

        if target == source:
            # Es identidad (el boton hace lo suyo de siempre): no hace
            # falta guardar nada para el.
            self._button_map_state.pop(source, None)
        else:
            self._button_map_state[source] = target

        if self.connection_manager and self.connection_manager.emulator:
            self.connection_manager.emulator.set_button_map(self._button_map_state)
        if self.profile_manager:
            self.profile_manager.set_button_map(self._button_map_state)

        self._set_status(f"{BUTTON_FRIENDLY_NAMES[source]} ahora activa: {choice}")

    def _reset_button_map(self) -> None:
        """Vuelve mapas simples, capas y acciones a su estado original."""
        if not messagebox.askyesno('Restablecer remapeo', '¿Eliminar todos los bindings avanzados y remapeos simples?', parent=self.root):
            return
        from src.advanced_mapping import DEFAULT_CONFIG, sanitize_config
        self._button_map_state = {}
        self._advanced_mapping_config = sanitize_config(DEFAULT_CONFIG)
        self.advanced_enabled_var.set(True)
        if self.connection_manager and self.connection_manager.emulator:
            self.connection_manager.emulator.set_button_map({})
        if self.profile_manager:
            self.profile_manager.set_button_map({})
        self._save_advanced_mapping_config()
        self._refresh_button_layer_menu('base')
        self._populate_button_rows()
        self._set_status("Remapeo avanzado restablecido")

    def _build_gyro_tab(self) -> None:
        """Construye la seccion de giroscopio y Gyro Aim."""
        if CUSTOMTK_AVAILABLE:
            gyro_tab = self.tabs.add("Giroscopio")
        else:
            gyro_tab = CTkFrame(self.tabs, bg=self.COLORS['bg_secondary'])

        scroll = CTkScrollableFrame(
            gyro_tab,
            fg_color=self.COLORS['bg_secondary'],
            scrollbar_button_color=self.COLORS['border'],
        )
        scroll.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._gyro_ui_loading = True
        self._gyro_sliders = {}
        self._gyro_value_labels = {}

        header = CTkFrame(scroll, fg_color="transparent")
        header.pack(fill=tk.X, padx=5, pady=(2, 12))
        CTkLabel(header, text="Giroscopio / Gyro Aim", font=self.FONTS['display'],
                 text_color=self.COLORS['text_primary']).pack(side=tk.LEFT)
        self.gyro_active_label = CTkLabel(
            header, text="INACTIVO", font=self.FONTS['caption'],
            text_color=self.COLORS['text_secondary'])
        self.gyro_active_label.pack(side=tk.RIGHT)

        basic = self._create_settings_section(scroll, "Modo y activacion")
        basic.pack(fill=tk.X, pady=(0, 12))
        basic_inner = CTkFrame(basic, fg_color="transparent")
        basic_inner.pack(fill=tk.X, padx=10, pady=8)

        self.gyro_enabled_var = tk.BooleanVar(value=False)
        CTkLabel(basic_inner, text="Habilitar giroscopio", font=self.FONTS['body'],
                 text_color=self.COLORS['text_primary']).grid(row=0, column=0, sticky="w", pady=5)
        self.gyro_enabled_switch = CTkSwitch(
            basic_inner, text="", variable=self.gyro_enabled_var,
            command=self._gyro_push_from_ui, width=45,
            progress_color=self.COLORS['accent'])
        self.gyro_enabled_switch.grid(row=0, column=1, sticky="e", pady=5)

        mode_names = ["Desactivado", "Passthrough DS4", "Mouse", "Stick derecho"]
        self.gyro_mode_var = tk.StringVar(value="Desactivado")
        CTkLabel(basic_inner, text="Modo", font=self.FONTS['body'],
                 text_color=self.COLORS['text_primary']).grid(row=1, column=0, sticky="w", pady=5)
        self.gyro_mode_menu = CTkOptionMenu(
            basic_inner, values=mode_names, variable=self.gyro_mode_var,
            command=lambda _v: self._gyro_push_from_ui(), width=180,
            fg_color=self.COLORS['bg_card'], button_color=self.COLORS['accent'],
            button_hover_color=self.COLORS['accent_hover'])
        self.gyro_mode_menu.grid(row=1, column=1, sticky="e", pady=5)

        activation_names = ["Siempre activo", "Mantener L2", "Mantener boton",
                            "Tocar touchpad", "Alternar", "Activacion invertida"]
        self.gyro_activation_var = tk.StringVar(value="Siempre activo")
        CTkLabel(basic_inner, text="Activacion", font=self.FONTS['body'],
                 text_color=self.COLORS['text_primary']).grid(row=2, column=0, sticky="w", pady=5)
        CTkOptionMenu(
            basic_inner, values=activation_names, variable=self.gyro_activation_var,
            command=lambda _v: self._gyro_push_from_ui(), width=180,
            fg_color=self.COLORS['bg_card'], button_color=self.COLORS['accent'],
            button_hover_color=self.COLORS['accent_hover']).grid(row=2, column=1, sticky="e", pady=5)

        self.gyro_button_var = tk.StringVar(value="L2_btn")
        activation_buttons = ["L2_btn", "R2_btn", "L1", "R1", "L3", "R3",
                              "cross", "circle", "square", "triangle", "touchpad", "create", "options"]
        CTkLabel(basic_inner, text="Boton activador", font=self.FONTS['body'],
                 text_color=self.COLORS['text_primary']).grid(row=3, column=0, sticky="w", pady=5)
        CTkOptionMenu(
            basic_inner, values=activation_buttons, variable=self.gyro_button_var,
            command=lambda _v: self._gyro_push_from_ui(), width=180,
            fg_color=self.COLORS['bg_card'], button_color=self.COLORS['accent'],
            button_hover_color=self.COLORS['accent_hover']).grid(row=3, column=1, sticky="e", pady=5)
        basic_inner.grid_columnconfigure(0, weight=1)

        aim = self._create_settings_section(scroll, "Ajuste de movimiento")
        aim.pack(fill=tk.X, pady=(0, 12))
        for key, label, lo, hi, steps, fmt in (
            ('sensitivity_x', 'Sensibilidad horizontal', 0.01, 10.0, 999, '{:.2f}x'),
            ('sensitivity_y', 'Sensibilidad vertical', 0.01, 10.0, 999, '{:.2f}x'),
            ('deadzone', 'Zona muerta', 0.0, 20.0, 400, '{:.2f}°/s'),
            ('smoothing', 'Suavizado', 0.0, 0.95, 95, '{:.2f}'),
            ('min_threshold', 'Umbral minimo', 0.0, 10.0, 200, '{:.2f}'),
            ('max_speed', 'Limite de velocidad', 100.0, 5000.0, 490, '{:.0f} px/s'),
            ('acceleration', 'Aceleracion', 0.0, 3.0, 300, '{:.2f}'),
        ):
            self._gyro_add_slider(aim, key, label, lo, hi, steps, fmt)

        switch_row = CTkFrame(aim, fg_color="transparent")
        switch_row.pack(fill=tk.X, padx=10, pady=8)
        self.gyro_invert_x_var = tk.BooleanVar(value=False)
        self.gyro_invert_y_var = tk.BooleanVar(value=True)
        self.gyro_accel_var = tk.BooleanVar(value=False)
        self.gyro_drift_var = tk.BooleanVar(value=True)
        for text, variable in (("Invertir X", self.gyro_invert_x_var), ("Invertir Y", self.gyro_invert_y_var),
                               ("Aceleracion", self.gyro_accel_var), ("Filtro anti-drift", self.gyro_drift_var)):
            CTkSwitch(switch_row, text=text, variable=variable, command=self._gyro_push_from_ui,
                      font=self.FONTS['small'], progress_color=self.COLORS['accent']).pack(side=tk.LEFT, padx=(0, 16))

        stick = self._create_settings_section(scroll, "Salida de stick derecho")
        stick.pack(fill=tk.X, pady=(0, 12))
        for key, label, lo, hi, steps, fmt in (
            ('stick_sensitivity_x', 'Sensibilidad X', 0.0001, 0.10, 999, '{:.4f}'),
            ('stick_sensitivity_y', 'Sensibilidad Y', 0.0001, 0.10, 999, '{:.4f}'),
            ('stick_deadzone', 'Zona muerta de salida', 0.0, 0.50, 100, '{:.2f}'),
            ('stick_anti_deadzone', 'Anti-deadzone', 0.0, 0.50, 100, '{:.2f}'),
            ('stick_max_output', 'Limite maximo', 0.05, 1.0, 95, '{:.2f}'),
            ('stick_mix', 'Mezcla con stick fisico', 0.0, 1.0, 100, '{:.2f}'),
        ):
            self._gyro_add_slider(stick, key, label, lo, hi, steps, fmt)

        stick_options = CTkFrame(stick, fg_color="transparent")
        stick_options.pack(fill=tk.X, padx=10, pady=8)
        self.gyro_curve_var = tk.StringVar(value="Lineal")
        self.gyro_mix_var = tk.StringVar(value="Sumar")
        CTkLabel(stick_options, text="Curva", font=self.FONTS['small'],
                 text_color=self.COLORS['text_secondary']).pack(side=tk.LEFT)
        CTkOptionMenu(stick_options, values=["Lineal", "Exponencial", "Precision"],
                      variable=self.gyro_curve_var, command=lambda _v: self._gyro_push_from_ui(),
                      width=140, fg_color=self.COLORS['bg_card'], button_color=self.COLORS['accent']).pack(side=tk.LEFT, padx=(8, 25))
        CTkLabel(stick_options, text="Mezcla", font=self.FONTS['small'],
                 text_color=self.COLORS['text_secondary']).pack(side=tk.LEFT)
        CTkOptionMenu(stick_options, values=["Sumar", "Reemplazar", "Priorizar gyro"],
                      variable=self.gyro_mix_var, command=lambda _v: self._gyro_push_from_ui(),
                      width=150, fg_color=self.COLORS['bg_card'], button_color=self.COLORS['accent']).pack(side=tk.LEFT, padx=8)

        actions = self._create_settings_section(scroll, "Calibracion y prueba")
        actions.pack(fill=tk.X, pady=(0, 12))
        action_inner = CTkFrame(actions, fg_color="transparent")
        action_inner.pack(fill=tk.X, padx=10, pady=10)
        CTkButton(action_inner, text="Calibrar reposo", command=self._gyro_calibrate,
                  fg_color=self.COLORS['accent'], hover_color=self.COLORS['accent_hover']).pack(side=tk.LEFT, padx=(0, 8))
        CTkButton(action_inner, text="Recentrar", command=self._gyro_recenter,
                  fg_color=self.COLORS['bg_card'], hover_color=self.COLORS['border']).pack(side=tk.LEFT, padx=8)
        CTkButton(action_inner, text="Prueba 2 s", command=self._gyro_test,
                  fg_color=self.COLORS['warning'], hover_color=self.COLORS['warning_hover'],
                  text_color="#161616").pack(side=tk.LEFT, padx=8)
        self.gyro_calibration_label = CTkLabel(action_inner, text="Sin calibrar",
                                               font=self.FONTS['caption'], text_color=self.COLORS['text_secondary'])
        self.gyro_calibration_label.pack(side=tk.RIGHT)

        live = self._create_settings_section(scroll, "Lectura en tiempo real")
        live.pack(fill=tk.X, pady=(0, 10))
        live_inner = CTkFrame(live, fg_color="transparent")
        live_inner.pack(fill=tk.X, padx=10, pady=10)
        self.gyro_sensor_label = CTkLabel(live_inner, text="Pitch 0.00 | Yaw 0.00 | Roll 0.00",
                                          font=self.FONTS['mono'], text_color=self.COLORS['text_primary'])
        self.gyro_sensor_label.pack(anchor="w")
        self.gyro_accel_label = CTkLabel(live_inner, text="Accel X 0 | Y 0 | Z 0",
                                         font=self.FONTS['mono'], text_color=self.COLORS['text_secondary'])
        self.gyro_accel_label.pack(anchor="w", pady=(4, 0))
        self.gyro_output_label = CTkLabel(live_inner, text="Salida X 0.00 | Y 0.00 | 0 Hz",
                                          font=self.FONTS['mono'], text_color=self.COLORS['accent'])
        self.gyro_output_label.pack(anchor="w", pady=(4, 8))
        self.gyro_canvas = tk.Canvas(live_inner, width=300, height=150,
                                     bg=self.COLORS['bg_card'], highlightthickness=1,
                                     highlightbackground=self.COLORS['border'])
        self.gyro_canvas.pack(fill=tk.X)
        self.gyro_canvas.create_line(150, 10, 150, 140, fill=self.COLORS['border'])
        self.gyro_canvas.create_line(10, 75, 290, 75, fill=self.COLORS['border'])
        self._gyro_vector_line = self.gyro_canvas.create_line(
            150, 75, 150, 75, fill=self.COLORS['accent'], width=4, arrow=tk.LAST)

        config = self.gyro_engine.get_config() if self.gyro_engine else None
        if config:
            self._gyro_load_config(config)
        self._gyro_ui_loading = False

    def _gyro_add_slider(self, parent, key, label, minimum, maximum, steps, value_format) -> None:
        row = CTkFrame(parent, fg_color="transparent")
        row.pack(fill=tk.X, padx=10, pady=5)
        top = CTkFrame(row, fg_color="transparent")
        top.pack(fill=tk.X)
        CTkLabel(top, text=label, font=self.FONTS['small'],
                 text_color=self.COLORS['text_primary']).pack(side=tk.LEFT)
        value_label = CTkLabel(top, text=value_format.format(minimum), font=self.FONTS['mono'],
                               text_color=self.COLORS['text_secondary'], width=90)
        value_label.pack(side=tk.RIGHT)
        slider = CTkSlider(row, from_=minimum, to=maximum, number_of_steps=steps,
                           command=lambda value, k=key, f=value_format: self._gyro_slider_changed(k, value, f),
                           progress_color=self.COLORS['accent'], button_color=self.COLORS['accent'],
                           button_hover_color=self.COLORS['accent_hover'])
        slider.pack(fill=tk.X, pady=(4, 0))
        self._gyro_sliders[key] = slider
        self._gyro_value_labels[key] = (value_label, value_format)

    def _gyro_slider_changed(self, key: str, value: float, value_format: str) -> None:
        label, _ = self._gyro_value_labels[key]
        label.configure(text=value_format.format(float(value)))
        self._gyro_push_from_ui()

    def _gyro_push_from_ui(self) -> None:
        if getattr(self, '_gyro_ui_loading', True) or not self.gyro_engine:
            return
        modes = {"Desactivado": "disabled", "Passthrough DS4": "passthrough_ds4",
                 "Mouse": "mouse", "Stick derecho": "right_stick"}
        activations = {"Siempre activo": "always", "Mantener L2": "hold_l2",
                       "Mantener boton": "hold_button", "Tocar touchpad": "touchpad",
                       "Alternar": "toggle", "Activacion invertida": "inverted"}
        curves = {"Lineal": "linear", "Exponencial": "exponential", "Precision": "precision"}
        mixes = {"Sumar": "add", "Reemplazar": "replace", "Priorizar gyro": "prioritize"}
        changes = {key: slider.get() for key, slider in self._gyro_sliders.items()}
        changes.update({
            'enabled': bool(self.gyro_enabled_var.get()),
            'mode': modes.get(self.gyro_mode_var.get(), 'disabled'),
            'activation': activations.get(self.gyro_activation_var.get(), 'always'),
            'activation_button': self.gyro_button_var.get(),
            'invert_x': bool(self.gyro_invert_x_var.get()),
            'invert_y': bool(self.gyro_invert_y_var.get()),
            'acceleration_enabled': bool(self.gyro_accel_var.get()),
            'drift_filter': bool(self.gyro_drift_var.get()),
            'response_curve': curves.get(self.gyro_curve_var.get(), 'linear'),
            'stick_mix_mode': mixes.get(self.gyro_mix_var.get(), 'add'),
        })
        self.gyro_engine.update_config(**changes)
        if changes['mode'] == 'passthrough_ds4':
            emulator = getattr(self.connection_manager, 'emulator', None)
            mode = getattr(getattr(emulator, 'mode', None), 'value', 'none')
            if mode != 'ps4':
                self._set_status("Gyro passthrough listo; selecciona emulacion PlayStation 4")

    def _gyro_load_config(self, config) -> None:
        if not hasattr(self, '_gyro_sliders'):
            return
        self._gyro_ui_loading = True
        modes = {'disabled': 'Desactivado', 'passthrough_ds4': 'Passthrough DS4',
                 'mouse': 'Mouse', 'right_stick': 'Stick derecho'}
        activations = {'always': 'Siempre activo', 'hold_l2': 'Mantener L2',
                       'hold_button': 'Mantener boton', 'touchpad': 'Tocar touchpad',
                       'toggle': 'Alternar', 'inverted': 'Activacion invertida'}
        curves = {'linear': 'Lineal', 'exponential': 'Exponencial', 'precision': 'Precision'}
        mixes = {'add': 'Sumar', 'replace': 'Reemplazar', 'prioritize': 'Priorizar gyro'}
        self.gyro_enabled_var.set(bool(config.enabled))
        self.gyro_mode_var.set(modes.get(config.mode, 'Desactivado'))
        self.gyro_activation_var.set(activations.get(config.activation, 'Siempre activo'))
        self.gyro_button_var.set(config.activation_button)
        self.gyro_invert_x_var.set(bool(config.invert_x))
        self.gyro_invert_y_var.set(bool(config.invert_y))
        self.gyro_accel_var.set(bool(config.acceleration_enabled))
        self.gyro_drift_var.set(bool(config.drift_filter))
        self.gyro_curve_var.set(curves.get(config.response_curve, 'Lineal'))
        self.gyro_mix_var.set(mixes.get(config.stick_mix_mode, 'Sumar'))
        for key, slider in self._gyro_sliders.items():
            value = float(getattr(config, key))
            slider.set(value)
            label, fmt = self._gyro_value_labels[key]
            label.configure(text=fmt.format(value))
        self._gyro_ui_loading = False

    def _gyro_calibrate(self) -> None:
        if self.gyro_engine:
            self.gyro_engine.begin_calibration(120)
            self._set_status("Deja el control inmovil sobre una superficie mientras se calibra")

    def _gyro_recenter(self) -> None:
        if self.gyro_engine:
            self.gyro_engine.recenter()
            self._set_status("Orientacion del giroscopio recentrada")

    def _gyro_test(self) -> None:
        if self.gyro_engine:
            self.gyro_engine.test_output(2.0)
            self._set_status("Prueba de Gyro Aim activa durante 2 segundos")

    def _update_gyro_telemetry(self) -> None:
        if not self.gyro_engine or not hasattr(self, 'gyro_sensor_label'):
            return
        telemetry = self.gyro_engine.get_telemetry()
        self.gyro_sensor_label.configure(
            text=f"Pitch {telemetry.pitch:7.2f} | Yaw {telemetry.yaw:7.2f} | Roll {telemetry.roll:7.2f}")
        self.gyro_accel_label.configure(
            text=f"Accel X {telemetry.accel_x:6.0f} | Y {telemetry.accel_y:6.0f} | Z {telemetry.accel_z:6.0f}")
        self.gyro_output_label.configure(
            text=f"Salida X {telemetry.output_x:8.2f} | Y {telemetry.output_y:8.2f} | {telemetry.sample_hz:5.1f} Hz")
        self.gyro_active_label.configure(
            text="ACTIVO" if telemetry.active else "INACTIVO",
            text_color=self.COLORS['success'] if telemetry.active else self.COLORS['text_secondary'])
        if telemetry.calibrating:
            self.gyro_calibration_label.configure(text=f"Calibrando {telemetry.calibration_progress * 100:.0f}%")
        else:
            self.gyro_calibration_label.configure(text="Calibrado" if telemetry.calibrated else "Sin calibrar")
        width = max(50, self.gyro_canvas.winfo_width())
        height = max(50, self.gyro_canvas.winfo_height())
        cx, cy = width / 2, height / 2
        if telemetry.mode == 'passthrough_ds4':
            visual_x, visual_y, scale = telemetry.yaw, telemetry.pitch, 0.65
        else:
            visual_x, visual_y = telemetry.output_x, telemetry.output_y
            scale = 55.0 if telemetry.mode == 'right_stick' else 0.035
        ox = max(-width * .42, min(width * .42, visual_x * scale))
        oy = max(-height * .42, min(height * .42, visual_y * scale))
        self.gyro_canvas.coords(self._gyro_vector_line, cx, cy, cx + ox, cy + oy)

    # ===== Nikaido Input Studio =====

    def _build_input_studio_tab(self) -> None:
        """Construye el panel de palancas sin depender de un mando conectado."""
        if CUSTOMTK_AVAILABLE:
            input_tab = self.tabs.add("Input Studio")
        else:
            input_tab = CTkFrame(self.tabs, bg=self.COLORS['bg_secondary'])

        scroll = CTkScrollableFrame(
            input_tab, fg_color=self.COLORS['bg_secondary'],
            scrollbar_button_color=self.COLORS['border'],
        )
        scroll.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._input_ui_loading = True
        self._input_sliders = {}
        self._input_value_labels = {}
        self._input_drag_index = None
        self._input_scopes = {}
        self._input_calibration_revision = 0

        header = CTkFrame(scroll, fg_color="transparent")
        header.pack(fill=tk.X, padx=5, pady=(2, 12))
        CTkLabel(header, text="Nikaido Input Studio", font=self.FONTS['display'],
                 text_color=self.COLORS['text_primary']).pack(side=tk.LEFT)
        self.input_active_profile_label = CTkLabel(
            header, text="Perfil activo: --", font=self.FONTS['caption'],
            text_color=self.COLORS['accent'])
        self.input_active_profile_label.pack(side=tk.RIGHT)

        profile_section = self._create_settings_section(scroll, "Perfil y palanca")
        profile_section.pack(fill=tk.X, pady=(0, 12))
        profile_row = CTkFrame(profile_section, fg_color="transparent")
        profile_row.pack(fill=tk.X, padx=10, pady=8)
        CTkLabel(profile_row, text="Editar y activar perfil", font=self.FONTS['body'],
                 text_color=self.COLORS['text_primary']).pack(side=tk.LEFT)
        self._input_profile_labels = {}
        self._input_profile_ids = {}
        self.input_profile_var = tk.StringVar(value="")
        self.input_profile_menu = CTkOptionMenu(
            profile_row, values=["Sin perfiles"], variable=self.input_profile_var,
            command=self._input_profile_selected, width=220,
            fg_color=self.COLORS['bg_card'], button_color=self.COLORS['accent'],
            button_hover_color=self.COLORS['accent_hover'])
        self.input_profile_menu.pack(side=tk.RIGHT)

        stick_row = CTkFrame(profile_section, fg_color="transparent")
        stick_row.pack(fill=tk.X, padx=10, pady=(0, 10))
        CTkLabel(stick_row, text="Palanca a ajustar", font=self.FONTS['body'],
                 text_color=self.COLORS['text_primary']).pack(side=tk.LEFT)
        self.input_stick_var = tk.StringVar(value="Derecha")
        self.input_stick_toggle = CTkSegmentedButton(
            stick_row, values=["Izquierda", "Derecha"], variable=self.input_stick_var,
            command=lambda _value: self._input_load_config(), width=220,
            selected_color=self.COLORS['accent'], selected_hover_color=self.COLORS['accent_hover'])
        self.input_stick_toggle.pack(side=tk.RIGHT)

        processing = self._create_settings_section(scroll, "Respuesta de entrada")
        processing.pack(fill=tk.X, pady=(0, 12))
        for key, label, low, high, steps, fmt in (
            ('inner_deadzone', 'Deadzone interior', 0.00, 0.50, 100, '{:.0%}'),
            ('outer_deadzone', 'Deadzone exterior', 0.00, 0.30, 60, '{:.0%}'),
            ('anti_deadzone', 'Anti-deadzone', 0.00, 0.50, 100, '{:.0%}'),
            ('sensitivity_x', 'Sensibilidad X', 0.10, 3.00, 290, '{:.2f}x'),
            ('sensitivity_y', 'Sensibilidad Y', 0.10, 3.00, 290, '{:.2f}x'),
        ):
            self._input_add_slider(processing, key, label, low, high, steps, fmt)

        options = CTkFrame(processing, fg_color="transparent")
        options.pack(fill=tk.X, padx=10, pady=(6, 10))
        self.input_curve_var = tk.StringVar(value="Lineal")
        CTkLabel(options, text="Curva", font=self.FONTS['small'],
                 text_color=self.COLORS['text_secondary']).pack(side=tk.LEFT)
        self.input_curve_menu = CTkOptionMenu(
            options, values=["Lineal", "Exponencial", "Agresiva", "Personalizada"],
            variable=self.input_curve_var, command=self._input_curve_changed, width=160,
            fg_color=self.COLORS['bg_card'], button_color=self.COLORS['accent'],
            button_hover_color=self.COLORS['accent_hover'])
        self.input_curve_menu.pack(side=tk.LEFT, padx=(8, 24))
        self.input_invert_x_var = tk.BooleanVar(value=False)
        self.input_invert_y_var = tk.BooleanVar(value=False)
        self.input_drift_var = tk.BooleanVar(value=True)
        for text, variable in (("Invertir X", self.input_invert_x_var),
                               ("Invertir Y", self.input_invert_y_var),
                               ("Correccion de drift", self.input_drift_var)):
            CTkSwitch(options, text=text, variable=variable, command=self._input_switch_changed,
                      font=self.FONTS['small'], progress_color=self.COLORS['accent']).pack(side=tk.LEFT, padx=(0, 14))

        curve_section = self._create_settings_section(scroll, "Curva personalizada")
        curve_section.pack(fill=tk.X, pady=(0, 12))
        CTkLabel(curve_section,
                 text="Arrastra los puntos para crear la curva. Al editar, se activa Personalizada.",
                 font=self.FONTS['caption'], text_color=self.COLORS['text_secondary']).pack(anchor="w", padx=10, pady=(8, 4))
        self.input_curve_canvas = tk.Canvas(
            curve_section, height=180, bg=self.COLORS['bg_card'], highlightthickness=1,
            highlightbackground=self.COLORS['border'])
        self.input_curve_canvas.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.input_curve_canvas.bind("<ButtonPress-1>", self._input_curve_press)
        self.input_curve_canvas.bind("<B1-Motion>", self._input_curve_drag)
        self.input_curve_canvas.bind("<ButtonRelease-1>", self._input_curve_release)

        action_section = self._create_settings_section(scroll, "Correccion de drift")
        action_section.pack(fill=tk.X, pady=(0, 12))
        action_row = CTkFrame(action_section, fg_color="transparent")
        action_row.pack(fill=tk.X, padx=10, pady=10)
        CTkButton(action_row, text="Calibrar reposo", command=self._input_calibrate_drift,
                  fg_color=self.COLORS['accent'], hover_color=self.COLORS['accent_hover']).pack(side=tk.LEFT, padx=(0, 8))
        CTkButton(action_row, text="Restablecer palanca", command=self._input_reset_stick,
                  fg_color=self.COLORS['bg_card'], hover_color=self.COLORS['border']).pack(side=tk.LEFT)
        self.input_drift_status = CTkLabel(
            action_row, text="Deja la palanca sin tocar antes de calibrar.", font=self.FONTS['caption'],
            text_color=self.COLORS['text_secondary'])
        self.input_drift_status.pack(side=tk.RIGHT)

        live_section = self._create_settings_section(scroll, "Vista en vivo")
        live_section.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        live_grid = CTkFrame(live_section, fg_color="transparent")
        live_grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._create_input_scope(live_grid, "L fisica", "physical_left", 0, 0)
        self._create_input_scope(live_grid, "L virtual", "virtual_left", 0, 1)
        self._create_input_scope(live_grid, "R fisica", "physical_right", 1, 0)
        self._create_input_scope(live_grid, "R virtual", "virtual_right", 1, 1)
        for index in range(2):
            live_grid.grid_columnconfigure(index, weight=1, uniform="input_scope")
            live_grid.grid_rowconfigure(index, weight=1, uniform="input_scope")

        self._input_refresh_profiles()
        self._input_load_config()
        self._input_ui_loading = False
        self.root.after_idle(self._redraw_input_curve)

        if not CUSTOMTK_AVAILABLE:
            self.tabs.add(input_tab, text="Input Studio")

    @staticmethod
    def _input_stick_key(value: str) -> str:
        return 'left' if value == 'Izquierda' else 'right'

    def _input_current_profile(self) -> str:
        if self.input_studio:
            return self.input_studio.get_active_profile()
        if self.trigger_engine and self.trigger_engine.get_current_profile():
            return self.trigger_engine.get_current_profile()
        if self.profile_manager:
            return self.profile_manager.get_active_profile()
        return 'assault_rifle'

    def _input_refresh_profiles(self) -> None:
        profiles = self.trigger_engine.get_profile_names() if self.trigger_engine else []
        self._input_profile_labels = {}
        self._input_profile_ids = {}
        for profile_id, name in profiles:
            label = f"{name} ({profile_id})"
            self._input_profile_labels[profile_id] = label
            self._input_profile_ids[label] = profile_id
        values = list(self._input_profile_ids) or ["Sin perfiles"]
        self.input_profile_menu.configure(values=values)
        current = self._input_current_profile()
        self.input_profile_var.set(self._input_profile_labels.get(current, values[0]))
        self.input_active_profile_label.configure(
            text=f"Perfil activo: {self._input_profile_labels.get(current, current)}")

    def _input_profile_selected(self, label: str) -> None:
        profile_id = self._input_profile_ids.get(label)
        if profile_id:
            self._apply_profile(profile_id)

    def _input_add_slider(self, parent, key, label, minimum, maximum, steps, value_format) -> None:
        row = CTkFrame(parent, fg_color="transparent")
        row.pack(fill=tk.X, padx=10, pady=5)
        top = CTkFrame(row, fg_color="transparent")
        top.pack(fill=tk.X)
        CTkLabel(top, text=label, font=self.FONTS['small'],
                 text_color=self.COLORS['text_primary']).pack(side=tk.LEFT)
        value_label = CTkLabel(top, text="--", font=self.FONTS['mono'],
                               text_color=self.COLORS['text_secondary'], width=76)
        value_label.pack(side=tk.RIGHT)
        slider = CTkSlider(
            row, from_=minimum, to=maximum, number_of_steps=steps,
            command=lambda value, k=key, f=value_format: self._input_slider_changed(k, value, f),
            progress_color=self.COLORS['accent'], button_color=self.COLORS['accent'],
            button_hover_color=self.COLORS['accent_hover'])
        slider.pack(fill=tk.X, pady=(4, 0))
        self._input_sliders[key] = slider
        self._input_value_labels[key] = (value_label, value_format)

    def _input_load_config(self) -> None:
        if not self.input_studio or not hasattr(self, '_input_sliders'):
            return
        self._input_ui_loading = True
        profile_id = self._input_current_profile()
        stick = self._input_stick_key(self.input_stick_var.get())
        config = self.input_studio.get_config(profile_id, stick)
        for key, slider in self._input_sliders.items():
            value = float(config[key])
            slider.set(value)
            label, fmt = self._input_value_labels[key]
            label.configure(text=fmt.format(value))
        names = {'linear': 'Lineal', 'exponential': 'Exponencial',
                 'aggressive': 'Agresiva', 'custom': 'Personalizada'}
        self.input_curve_var.set(names.get(config['curve'], 'Lineal'))
        self.input_invert_x_var.set(bool(config['invert_x']))
        self.input_invert_y_var.set(bool(config['invert_y']))
        self.input_drift_var.set(bool(config['drift_correction']))
        self.input_drift_status.configure(
            text=f"Offset X {config['drift_offset_x']:+.3f} | Y {config['drift_offset_y']:+.3f}")
        self._input_ui_loading = False
        self._redraw_input_curve()

    def _input_persist_memory(self) -> None:
        if self.profile_manager and self.input_studio:
            self.profile_manager.set_setting('profile_input_studio', self.input_studio.export_profiles())

    def _input_update_config(self, **changes) -> None:
        if getattr(self, '_input_ui_loading', True) or not self.input_studio:
            return
        config = self.input_studio.update_config(
            self._input_current_profile(), self._input_stick_key(self.input_stick_var.get()), **changes)
        self._input_persist_memory()
        return config

    def _input_slider_changed(self, key: str, value: float, value_format: str) -> None:
        label, _ = self._input_value_labels[key]
        label.configure(text=value_format.format(float(value)))
        self._input_update_config(**{key: float(value)})
        if key in ('inner_deadzone', 'outer_deadzone'):
            self._update_input_studio_live()

    def _input_switch_changed(self) -> None:
        self._input_update_config(
            invert_x=bool(self.input_invert_x_var.get()),
            invert_y=bool(self.input_invert_y_var.get()),
            drift_correction=bool(self.input_drift_var.get()),
        )

    def _input_curve_changed(self, value: str) -> None:
        curves = {'Lineal': 'linear', 'Exponencial': 'exponential',
                  'Agresiva': 'aggressive', 'Personalizada': 'custom'}
        self._input_update_config(curve=curves.get(value, 'linear'))
        self._redraw_input_curve()

    def _input_curve_bounds(self) -> tuple:
        canvas = self.input_curve_canvas
        width = max(120, canvas.winfo_width())
        height = max(120, canvas.winfo_height())
        return width, height, 28, 18

    def _input_curve_to_canvas(self, x: float, y: float) -> tuple:
        width, height, mx, my = self._input_curve_bounds()
        return mx + x * (width - 2 * mx), height - my - y * (height - 2 * my)

    def _input_canvas_to_curve(self, x: float, y: float) -> tuple:
        width, height, mx, my = self._input_curve_bounds()
        return (max(0.0, min(1.0, (x - mx) / max(1, width - 2 * mx))),
                max(0.0, min(1.0, (height - my - y) / max(1, height - 2 * my))))

    @staticmethod
    def _input_curve_value(value: float, config: dict) -> float:
        curve = config.get('curve', 'linear')
        if curve == 'exponential':
            return value * value
        if curve == 'aggressive':
            return math.sqrt(value)
        if curve != 'custom':
            return value
        points = config.get('custom_curve', [])
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if value <= x1:
                return y1 if x1 <= x0 else y0 + (y1 - y0) * ((value - x0) / (x1 - x0))
        return 1.0

    def _redraw_input_curve(self) -> None:
        if not hasattr(self, 'input_curve_canvas') or not self.input_studio:
            return
        canvas = self.input_curve_canvas
        canvas.delete('all')
        width, height, mx, my = self._input_curve_bounds()
        for step in range(5):
            x = mx + step * (width - 2 * mx) / 4
            y = my + step * (height - 2 * my) / 4
            canvas.create_line(x, my, x, height - my, fill=self.COLORS['border'])
            canvas.create_line(mx, y, width - mx, y, fill=self.COLORS['border'])
        config = self.input_studio.get_config(
            self._input_current_profile(), self._input_stick_key(self.input_stick_var.get()))
        coords = []
        for index in range(81):
            x = index / 80
            coords.extend(self._input_curve_to_canvas(x, self._input_curve_value(x, config)))
        canvas.create_line(*coords, fill=self.COLORS['accent'], width=3, smooth=True)
        if config.get('curve') == 'custom':
            for index, (x, y) in enumerate(config['custom_curve']):
                cx, cy = self._input_curve_to_canvas(x, y)
                radius = 6 if index not in (0, len(config['custom_curve']) - 1) else 4
                canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                   fill=self.COLORS['accent'], outline=self.COLORS['text_primary'])

    def _input_curve_press(self, event) -> None:
        if not self.input_studio:
            return
        profile = self._input_current_profile()
        stick = self._input_stick_key(self.input_stick_var.get())
        config = self.input_studio.get_config(profile, stick)
        if config.get('curve') != 'custom':
            self.input_curve_var.set('Personalizada')
            config = self._input_update_config(curve='custom') or config
        points = config['custom_curve']
        nearest, distance = None, 18.0
        for index in range(1, len(points) - 1):
            px, py = self._input_curve_to_canvas(points[index][0], points[index][1])
            current = math.hypot(event.x - px, event.y - py)
            if current < distance:
                nearest, distance = index, current
        self._input_drag_index = nearest

    def _input_curve_drag(self, event) -> None:
        index = self._input_drag_index
        if index is None or not self.input_studio:
            return
        profile = self._input_current_profile()
        stick = self._input_stick_key(self.input_stick_var.get())
        config = self.input_studio.get_config(profile, stick)
        points = [list(point) for point in config['custom_curve']]
        x, y = self._input_canvas_to_curve(event.x, event.y)
        x = max(points[index - 1][0] + 0.02, min(points[index + 1][0] - 0.02, x))
        points[index] = [round(x, 4), round(y, 4)]
        self._input_update_config(custom_curve=points, curve='custom')
        self._redraw_input_curve()

    def _input_curve_release(self, _event) -> None:
        self._input_drag_index = None

    def _input_calibrate_drift(self) -> None:
        if not self.input_studio or not self.connection_manager:
            self._set_status("Conecta un DualSense antes de calibrar el drift")
            return
        state = self.connection_manager.state
        if not state.connected:
            self._set_status("Conecta un DualSense antes de calibrar el drift")
            return
        stick = self._input_stick_key(self.input_stick_var.get())
        self.input_studio.update_config(self._input_current_profile(), stick, drift_correction=True)
        self.input_drift_var.set(True)
        self.input_studio.begin_drift_calibration(self._input_current_profile(), stick, samples=120)
        self._input_persist_memory()
        self.input_drift_status.configure(text="Calibrando reposo: 0%")
        self._set_status("No muevas la palanca durante la calibracion de drift")

    def _input_reset_stick(self) -> None:
        if not self.input_studio:
            return
        self.input_studio.reset_stick(self._input_current_profile(), self._input_stick_key(self.input_stick_var.get()))
        self._input_persist_memory()
        self._input_load_config()
        self._set_status("Ajustes de la palanca restablecidos")

    def _create_input_scope(self, parent, title: str, key: str, row: int, column: int) -> None:
        frame = CTkFrame(parent, fg_color=self.COLORS['bg_card'], corner_radius=8)
        frame.grid(
            row=row, column=column, sticky="nsew",
            padx=(0, 6) if column == 0 else (6, 0),
            pady=(0, 6) if row == 0 else (6, 0),
        )
        header = CTkFrame(frame, fg_color="transparent")
        header.pack(fill=tk.X, padx=10, pady=(8, 2))
        CTkLabel(header, text=title, font=self.FONTS['body_bold'],
                 text_color=self.COLORS['text_primary']).pack(side=tk.LEFT)
        dot_color = self.COLORS['warning'] if key.startswith('physical') else self.COLORS['accent']
        CTkLabel(header, text="o", font=self.FONTS['small'], text_color=dot_color).pack(side=tk.RIGHT)
        canvas = tk.Canvas(frame, height=150, bg=self.COLORS['bg_card'], highlightthickness=0)
        canvas.pack(fill=tk.X, padx=8)
        label = CTkLabel(frame, text="X +0.000 | Y +0.000 | M 0.000", font=self.FONTS['mono'],
                         text_color=self.COLORS['text_secondary'])
        label.pack(anchor="w", padx=10, pady=(2, 8))
        self._input_scopes[key] = {'canvas': canvas, 'label': label}

    def _draw_input_scope(self, scope: dict, x: float, y: float, config: dict, color: str) -> None:
        canvas = scope['canvas']
        canvas.delete('all')
        width, height = max(80, canvas.winfo_width()), max(80, canvas.winfo_height())
        cx, cy = width / 2, height / 2
        radius = min(width, height) * .40
        canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                           outline=self.COLORS['border'], width=2)
        outer = radius * max(0.0, 1.0 - float(config.get('outer_deadzone', 0.0)))
        inner = radius * float(config.get('inner_deadzone', 0.0))
        canvas.create_oval(cx - outer, cy - outer, cx + outer, cy + outer,
                           outline=self.COLORS['text_secondary'], dash=(3, 3))
        canvas.create_oval(cx - inner, cy - inner, cx + inner, cy + inner,
                           outline=self.COLORS['warning'], dash=(2, 2))
        anti = radius * float(config.get('anti_deadzone', 0.0))
        if anti > 1:
            canvas.create_oval(cx - anti, cy - anti, cx + anti, cy + anti,
                               outline=self.COLORS['accent'], dash=(1, 4))
        canvas.create_line(cx - radius, cy, cx + radius, cy, fill=self.COLORS['border'])
        canvas.create_line(cx, cy - radius, cx, cy + radius, fill=self.COLORS['border'])
        px, py = cx + max(-1.0, min(1.0, x)) * radius, cy + max(-1.0, min(1.0, y)) * radius
        canvas.create_line(cx, cy, px, py, fill=color, width=2)
        canvas.create_oval(px - 7, py - 7, px + 7, py + 7, fill=color, outline=self.COLORS['text_primary'])
        magnitude = min(1.0, math.hypot(float(x), float(y)))
        scope['label'].configure(text=f"X {x:+.3f} | Y {y:+.3f} | M {magnitude:.3f}")

    def _update_input_studio_live(self) -> None:
        if not self.input_studio or not hasattr(self, '_input_scopes'):
            return
        profile = self._input_current_profile()
        selected_stick = self._input_stick_key(self.input_stick_var.get())
        calibrations = {}
        newest_revision = self._input_calibration_revision
        for stick in ('left', 'right'):
            calibration = self.input_studio.get_drift_calibration(stick)
            calibrations[stick] = calibration
            if calibration['completed']:
                newest_revision = max(newest_revision, int(calibration['revision']))
        if newest_revision > self._input_calibration_revision:
            self._input_calibration_revision = newest_revision
            self._input_persist_memory()
            self._input_load_config()

        selected_calibration = calibrations.get(selected_stick, {})
        if selected_calibration.get('active'):
            self.input_drift_status.configure(
                text=f"Calibrando reposo: {selected_calibration['progress'] * 100:.0f}%")
        elif selected_calibration.get('completed'):
            self.input_drift_status.configure(text="Drift calibrado | Offset aplicado")
        else:
            selected_config = self.input_studio.get_config(profile, selected_stick)
            self.input_drift_status.configure(
                text=f"Offset X {selected_config['drift_offset_x']:+.3f} | Y {selected_config['drift_offset_y']:+.3f}")

        emulator = getattr(self.connection_manager, 'emulator', None)
        for stick in ('left', 'right'):
            telemetry = self.input_studio.get_telemetry(stick)
            config = self.input_studio.get_config(profile, stick)
            virtual = (telemetry['output_x'], telemetry['output_y'])
            if emulator:
                try:
                    virtual = emulator.get_virtual_stick_output(stick)
                except Exception:
                    pass
            self._draw_input_scope(
                self._input_scopes[f'physical_{stick}'],
                telemetry['physical_x'], telemetry['physical_y'], config, self.COLORS['warning'])
            self._draw_input_scope(
                self._input_scopes[f'virtual_{stick}'],
                virtual[0], virtual[1], config, self.COLORS['accent'])

    def _build_settings_tab(self) -> None:
        """Construye la pestaña de configuracion."""
        if CUSTOMTK_AVAILABLE:
            settings_tab = self.tabs.add("Configuracion")
        else:
            settings_tab = CTkFrame(self.tabs, fg_color=self.COLORS['bg_secondary'])

        # Scrollable frame
        scroll_frame = CTkScrollableFrame(
            settings_tab,
            fg_color=self.COLORS['bg_secondary'],
            scrollbar_button_color=self.COLORS['border'],
        )
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ===== Seccion: General =====
        general_frame = self._create_settings_section(scroll_frame, "General")
        general_frame.pack(fill=tk.X, pady=(0, 15))

        # Auto-conectar
        self.auto_connect_switch = self._create_switch_setting(
            general_frame, "Conexion automatica al inicio",
            self.profile_manager.get_setting('auto_connect', True) if self.profile_manager else True
        )
        self.auto_connect_switch.pack(fill=tk.X, padx=10, pady=5)

        # Minimizar a bandeja
        self.minimize_tray_switch = self._create_switch_setting(
            general_frame, "Minimizar a bandeja al cerrar",
            self.profile_manager.get_setting('minimize_to_tray', True) if self.profile_manager else True
        )
        self.minimize_tray_switch.pack(fill=tk.X, padx=10, pady=5)

        # ===== Seccion: Emulacion =====
        emu_frame = self._create_settings_section(scroll_frame, "Emulación (Compatibilidad PC)")
        emu_frame.pack(fill=tk.X, pady=(0, 15))

        emu_inner = CTkFrame(emu_frame, fg_color="transparent")
        emu_inner.pack(fill=tk.X, padx=10, pady=5)

        CTkLabel(
            emu_inner, text="Control Virtual:",
            font=self.FONTS['body'],
            text_color=self.COLORS['text_primary']
        ).pack(side=tk.LEFT)

        self.emulation_var = tk.StringVar(value="Apagado")
        self.emulation_menu = CTkOptionMenu(
            emu_inner,
            values=["Apagado", "Xbox 360", "PlayStation 4"],
            variable=self.emulation_var,
            command=self._on_emulation_change,
            width=150,
            font=self.FONTS['small'],
            fg_color=self.COLORS['bg_secondary'],
            button_color=self.COLORS['accent'],
            button_hover_color=self.COLORS['accent_hover'],
        )
        self.emulation_menu.pack(side=tk.RIGHT)

        # Restaurar configuración de emulación guardada
        if self.profile_manager:
            saved_emu = self.profile_manager.get_setting('emulation_mode', "Apagado")
            self.emulation_var.set(saved_emu)
            # Retrasamos la conexión del emulador 1 segundo para no saturar el arranque
            self.root.after(1000, lambda: self._on_emulation_change(saved_emu))

        # ===== Seccion: Touchpad como mouse =====
        touchpad_frame = self._create_settings_section(scroll_frame, "Touchpad como mouse")
        touchpad_frame.pack(fill=tk.X, pady=(0, 15))

        touchpad_enabled = (
            self.touchpad_mouse.is_enabled() if self.touchpad_mouse else False
        )
        touchpad_switch_row = self._create_switch_setting(
            touchpad_frame, "Usar el touchpad para mover el cursor", touchpad_enabled
        )
        touchpad_switch_row.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.touchpad_mouse_switch = touchpad_switch_row.winfo_children()[1]
        self.touchpad_mouse_enabled_var = self.touchpad_mouse_switch.var
        self.touchpad_mouse_switch.configure(command=self._on_touchpad_mouse_toggle)

        sensitivity_row = CTkFrame(touchpad_frame, fg_color="transparent")
        sensitivity_row.pack(fill=tk.X, padx=10, pady=(0, 5))

        CTkLabel(
            sensitivity_row, text="Sensibilidad:",
            font=self.FONTS['body'],
            text_color=self.COLORS['text_primary']
        ).pack(side=tk.LEFT)

        self.touchpad_sensitivity_value = CTkLabel(
            sensitivity_row, text="2.5x",
            font=self.FONTS['mono'],
            text_color=self.COLORS['text_primary'],
            width=55
        )
        self.touchpad_sensitivity_value.pack(side=tk.RIGHT)

        sensitivity = (
            self.touchpad_mouse.get_sensitivity() if self.touchpad_mouse else
            (self.profile_manager.get_setting('touchpad_mouse.sensitivity', 2.5)
             if self.profile_manager else 2.5)
        )
        self.touchpad_sensitivity_slider = CTkSlider(
            touchpad_frame,
            from_=0.1, to=10.0,
            number_of_steps=99,
            command=self._on_touchpad_sensitivity_change,
            fg_color=self.COLORS['bg_secondary'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['accent'],
            button_hover_color=self.COLORS['accent_hover'],
        )
        self.touchpad_sensitivity_slider.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.touchpad_sensitivity_slider.set(sensitivity)
        self.touchpad_sensitivity_value.configure(text=f"{sensitivity:.1f}x")

        available = bool(self.touchpad_mouse and self.touchpad_mouse.is_available())
        touchpad_hint = (
            "El clic físico del touchpad funciona como clic izquierdo."
            if available else
            "No disponible: pywin32 no está instalado o la app no se está ejecutando en Windows."
        )
        CTkLabel(
            touchpad_frame,
            text=touchpad_hint,
            font=self.FONTS['micro'],
            text_color=self.COLORS['text_secondary'] if available else self.COLORS['warning'],
            wraplength=620, justify="left"
        ).pack(anchor="w", padx=10, pady=(0, 10))

        if not available:
            self.touchpad_mouse_enabled_var.set(False)
            try:
                self.touchpad_mouse_switch.configure(state="disabled")
                self.touchpad_sensitivity_slider.configure(state="disabled")
            except Exception:
                pass

        # ===== Seccion: LED =====
        led_frame = self._create_settings_section(scroll_frame, "LED y Apariencia")
        led_frame.pack(fill=tk.X, pady=(0, 15))

        # Color del LED
        color_frame = CTkFrame(led_frame, fg_color="transparent")
        color_frame.pack(fill=tk.X, padx=10, pady=5)

        CTkLabel(
            color_frame, text="Color LED Touchpad:",
            font=self.FONTS['body'],
            text_color=self.COLORS['text_primary']
        ).pack(side=tk.LEFT)

        self.led_color_btn = CTkButton(
            color_frame,
            text="Elegir Color",
            font=self.FONTS['small'],
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['accent_hover'],
            corner_radius=8,
            command=self._choose_led_color
        )
        self.led_color_btn.pack(side=tk.RIGHT)

        # Preview del color
        self.led_preview = CTkFrame(
            color_frame, width=30, height=30,
            fg_color=self.COLORS['accent'], corner_radius=15
        )
        self.led_preview.pack(side=tk.RIGHT, padx=10)

        # Numero de jugador
        player_frame = CTkFrame(led_frame, fg_color="transparent")
        player_frame.pack(fill=tk.X, padx=10, pady=5)

        CTkLabel(
            player_frame, text="Numero de jugador:",
            font=self.FONTS['body'],
            text_color=self.COLORS['text_primary']
        ).pack(side=tk.LEFT)

        self.player_var = tk.StringVar(value="1")
        player_menu = CTkOptionMenu(
            player_frame,
            values=["0 (Apagado)", "1", "2", "3", "4"],
            variable=self.player_var,
            command=self._on_player_change,
            width=120,
            font=self.FONTS['small'],
        )
        player_menu.pack(side=tk.RIGHT)

        # ===== Seccion: Bluetooth =====
        bt_frame = self._create_settings_section(scroll_frame, "Bluetooth")
        bt_frame.pack(fill=tk.X, pady=(0, 15))

        # Boton de reinicio Bluetooth
        self.reset_bt_btn = CTkButton(
            bt_frame,
            text="Reiniciar Bluetooth",
            font=self.FONTS['body_bold'],
            fg_color=self.COLORS['warning'],
            hover_color=self.COLORS['warning_hover'],
            corner_radius=10,
            command=self._reset_bluetooth
        )
        self.reset_bt_btn.pack(fill=tk.X, padx=10, pady=10)

        # Auto-reset Bluetooth
        self.auto_reset_bt_switch = self._create_switch_setting(
            bt_frame, "Auto-reset Bluetooth al conectar",
            self.profile_manager.get_setting('bluetooth_auto_reset', False) if self.profile_manager else False
        )
        self.auto_reset_bt_switch.pack(fill=tk.X, padx=10, pady=5)

        # ===== Seccion: Perfiles =====
        profiles_frame = self._create_settings_section(scroll_frame, "Gestion de Perfiles")
        profiles_frame.pack(fill=tk.X, pady=(0, 15))

        # Importar/Exportar botones
        btn_frame = CTkFrame(profiles_frame, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        CTkButton(
            btn_frame,
            text="Importar Perfil",
            font=self.FONTS['small'],
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['accent_hover'],
            corner_radius=8,
            command=self._import_profile
        ).pack(side=tk.LEFT, padx=(0, 5))

        CTkButton(
            btn_frame,
            text="Exportar Perfil",
            font=self.FONTS['small'],
            fg_color=self.COLORS['accent'],
            hover_color=self.COLORS['accent_hover'],
            corner_radius=8,
            command=self._export_profile
        ).pack(side=tk.LEFT, padx=5)

        CTkButton(
            btn_frame,
            text="Restaurar Defaults",
            font=self.FONTS['small'],
            fg_color=self.COLORS['danger'],
            hover_color=self.COLORS['danger_hover'],
            corner_radius=8,
            command=self._reset_defaults
        ).pack(side=tk.RIGHT)

        # ===== Seccion: Perfil por Juego =====
        game_frame = self._create_settings_section(scroll_frame, "Perfil por Juego")
        game_frame.pack(fill=tk.X, pady=(0, 15))

        from src.game_profile_watcher import PSUTIL_AVAILABLE

        if not PSUTIL_AVAILABLE:
            CTkLabel(
                game_frame,
                text="⚠ Falta instalar 'psutil' (pip install psutil) para que esto funcione.",
                font=self.FONTS['small'],
                text_color=self.COLORS['warning'],
                wraplength=500, justify="left"
            ).pack(anchor="w", padx=10, pady=(0, 10))

        game_enabled_default = (
            self.game_profile_watcher.is_enabled() if self.game_profile_watcher else True
        )
        game_switch_row = self._create_switch_setting(
            game_frame, "Detectar juego y cambiar perfil automaticamente", game_enabled_default
        )
        game_switch_row.pack(fill=tk.X, padx=10, pady=(0, 10))
        game_switch_row.winfo_children()[1].configure(command=self._on_game_profiles_toggle)
        self.game_profiles_switch = game_switch_row.winfo_children()[1]
        self.game_profiles_enabled_var = self.game_profiles_switch.var

        CTkLabel(
            game_frame,
            text="Agregá el nombre del .exe del juego (ej: valorant.exe) y el perfil de gatillos que querés que se aplique solo cuando ese juego este corriendo.",
            font=self.FONTS['micro'],
            text_color=self.COLORS['text_secondary'],
            wraplength=500, justify="left"
        ).pack(anchor="w", padx=10, pady=(0, 10))

        # Fila para agregar una nueva asociacion
        add_row = CTkFrame(game_frame, fg_color="transparent")
        add_row.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.game_exe_entry = CTkEntry(
            add_row, placeholder_text="nombre.exe",
            font=self.FONTS['small']
        )
        self.game_exe_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        profile_names = self.trigger_engine.get_profile_names() if self.trigger_engine else []
        self._game_profile_choices = {name: pid for pid, name in profile_names}
        self.game_profile_var = tk.StringVar(
            value=profile_names[0][1] if profile_names else "off"
        )
        CTkOptionMenu(
            add_row,
            values=[name for _, name in profile_names] or ["off"],
            variable=self.game_profile_var,
            font=self.FONTS['small'],
            fg_color=self.COLORS['bg_secondary'],
            button_color=self.COLORS['trigger_accent'],
            button_hover_color=self.COLORS['trigger_accent_hover'],
        ).pack(side=tk.LEFT, padx=5)

        CTkButton(
            add_row, text="Agregar", width=90,
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['trigger_accent'],
            hover_color=self.COLORS['trigger_accent_hover'],
            corner_radius=8,
            command=self._add_game_profile_mapping
        ).pack(side=tk.LEFT, padx=(5, 0))

        # Lista de asociaciones actuales
        self.game_profiles_list_frame = CTkFrame(game_frame, fg_color="transparent")
        self.game_profiles_list_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self._populate_game_profiles_list()

        # ===== Seccion: Interfaz personalizada =====
        ui_editor_frame = self._create_settings_section(scroll_frame, "Interfaz personalizada")
        ui_editor_frame.pack(fill=tk.X, pady=(0, 15))

        CTkLabel(
            ui_editor_frame,
            text=(
                "Diseña una pantalla con imágenes, GIFs, textos, zonas clicables y datos en vivo. "
                "Los paquetes .nikaido-theme incluyen sus recursos y pueden moverse entre equipos."
            ),
            font=self.FONTS['small'],
            text_color=self.COLORS['text_secondary'],
            wraplength=620, justify="left"
        ).pack(anchor="w", padx=10, pady=(5, 8))

        saved_ui_path = self.profile_manager.get_setting('ui_layout_path', '') if self.profile_manager else ''
        self.ui_theme_path_var = tk.StringVar(value=saved_ui_path or "Ningún tema instalado")
        CTkLabel(
            ui_editor_frame,
            textvariable=self.ui_theme_path_var,
            font=self.FONTS['caption'],
            text_color=self.COLORS['text_secondary'],
            wraplength=620, justify="left"
        ).pack(anchor="w", padx=10, pady=(0, 8))

        ui_buttons = CTkFrame(ui_editor_frame, fg_color="transparent")
        ui_buttons.pack(fill=tk.X, padx=10, pady=(0, 7))

        CTkButton(
            ui_buttons, text="Abrir UI Studio",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['accent'], hover_color=self.COLORS['accent_hover'],
            corner_radius=8, command=self._open_interface_editor
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        CTkButton(
            ui_buttons, text="Importar y aplicar",
            font=self.FONTS['small_bold'],
            fg_color=self.COLORS['trigger_accent'], hover_color=self.COLORS['trigger_accent_hover'],
            corner_radius=8, command=self._select_and_apply_ui_layout
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        ui_buttons_2 = CTkFrame(ui_editor_frame, fg_color="transparent")
        ui_buttons_2.pack(fill=tk.X, padx=10, pady=(0, 7))

        CTkButton(
            ui_buttons_2, text="Aplicar tema guardado",
            font=self.FONTS['small'],
            fg_color=self.COLORS['bg_secondary'], hover_color=self.COLORS['border'],
            corner_radius=8, command=self._apply_saved_ui_layout
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        CTkButton(
            ui_buttons_2, text="Volver a interfaz clásica",
            font=self.FONTS['small'],
            fg_color=self.COLORS['danger'], hover_color=self.COLORS['danger_hover'],
            corner_radius=8, command=self._disable_custom_ui
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        ui_start_row = self._create_switch_setting(
            ui_editor_frame, "Cargar interfaz personalizada al iniciar",
            self.profile_manager.get_setting('ui_custom_enabled', False) if self.profile_manager else False
        )
        ui_start_row.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.ui_custom_start_switch = ui_start_row.winfo_children()[1]
        self.ui_custom_start_var = self.ui_custom_start_switch.var
        self.ui_custom_start_switch.configure(command=self._on_custom_ui_startup_toggle)

        CTkLabel(
            ui_editor_frame,
            text="F12 alterna en cualquier momento entre la interfaz clásica y la personalizada.",
            font=self.FONTS['micro'], text_color=self.COLORS['text_secondary']
        ).pack(anchor="w", padx=10, pady=(0, 10))

        # ===== Seccion: Acerca de =====
        about_frame = self._create_settings_section(scroll_frame, "Acerca de")
        about_frame.pack(fill=tk.X)

        CTkLabel(
            about_frame,
            text="DualSense Controller v1.0\nPanel de control para PlayStation 5 DualSense en Windows",
            font=self.FONTS['small'],
            text_color=self.COLORS['text_secondary'],
            justify="left"
        ).pack(padx=10, pady=10, anchor="w")

        CTkLabel(
            about_frame,
            text="Desarrollado con Python, pydualsense y CustomTkinter\nRequiere control conectado via USB o Bluetooth",
            font=self.FONTS['caption'],
            text_color=self.COLORS['text_secondary'],
            justify="left"
        ).pack(padx=10, pady=(0, 10), anchor="w")

        # Agregar tab (solo para tkinter estandar)
        if not CUSTOMTK_AVAILABLE:
            self.tabs.add(settings_tab, text="Configuracion")

    def _open_interface_editor(self) -> None:
        """Abre Nikaido UI Studio y permite aplicar cambios en vivo."""
        try:
            from gui.interface_editor import InterfaceEditor

            if self._interface_editor_window and self._interface_editor_window.winfo_exists():
                self._interface_editor_window.deiconify()
                self._interface_editor_window.lift()
                self._interface_editor_window.focus_force()
                return

            project_root = Path(__file__).resolve().parent.parent
            initial = None
            saved = self.profile_manager.get_setting('ui_layout_path', '') if self.profile_manager else ''
            if saved and Path(saved).is_file():
                initial = Path(saved)

            editor_storage = (
                Path(self.profile_manager.get_config_dir()) / "ui_layouts"
                if self.profile_manager else project_root / "config" / "ui_layouts"
            )
            editor = InterfaceEditor(
                self.root,
                project_root=project_root,
                storage_dir=editor_storage,
                initial_path=initial,
                on_apply=self._apply_layout_from_editor,
            )
            editor.transient(self.root)
            self._interface_editor_window = editor
            editor.bind("<Destroy>", lambda event: self._clear_editor_reference(event, editor), add="+")
            self._set_status("Nikaido UI Studio abierto")
        except Exception as exc:
            logger.error("No se pudo abrir el editor visual: %s", exc, exc_info=True)
            messagebox.showerror("Editor visual", f"No se pudo abrir el editor:\n{exc}")

    def _clear_editor_reference(self, event, editor) -> None:
        if event.widget is editor and self._interface_editor_window is editor:
            self._interface_editor_window = None

    def _ui_themes_dir(self) -> Path:
        """Directorio persistente para temas instalados."""
        if self.profile_manager:
            base = Path(self.profile_manager.get_config_dir())
        else:
            base = Path.home() / "DualSenseController"
        path = base / "ui_themes"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _select_and_apply_ui_layout(self) -> None:
        """Importa un JSON o paquete portable, lo instala y lo activa."""
        chosen = filedialog.askopenfilename(
            title="Importar interfaz Nikaido",
            filetypes=[
                ("Temas Nikaido", "*.nikaido-theme *.nikaido-ui.json *.json"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not chosen:
            return
        try:
            from gui.ui_theme import install_theme

            layout = install_theme(chosen, self._ui_themes_dir())
            self._activate_custom_ui(layout, persist=True)
            self._set_status(f"Interfaz aplicada: {layout.name}")
        except Exception as exc:
            logger.error("No se pudo importar el tema: %s", exc, exc_info=True)
            messagebox.showerror("Interfaz personalizada", f"No se pudo importar el tema:\n{exc}")

    def _apply_saved_ui_layout(self) -> None:
        """Carga y aplica la ruta guardada en configuración."""
        saved = self.profile_manager.get_setting('ui_layout_path', '') if self.profile_manager else ''
        if not saved:
            messagebox.showwarning("Interfaz personalizada", "No hay un tema guardado.")
            return
        try:
            from gui.ui_theme import load_layout, validate_layout

            layout = load_layout(saved, extract_dir=self._ui_themes_dir())
            errors, _warnings = validate_layout(layout, check_assets=True)
            if errors:
                raise ValueError("\n".join(errors))
            self._activate_custom_ui(layout, persist=False)
        except Exception as exc:
            logger.error("No se pudo aplicar el tema guardado: %s", exc, exc_info=True)
            messagebox.showerror("Interfaz personalizada", f"No se pudo aplicar el tema guardado:\n{exc}")

    def _restore_custom_ui_preference(self) -> None:
        """Restaura el tema al iniciar, sin impedir que la UI clásica arranque."""
        if not self.profile_manager:
            return
        if not self.profile_manager.get_setting('ui_custom_enabled', False):
            return
        saved = self.profile_manager.get_setting('ui_layout_path', '')
        if not saved:
            return
        try:
            from gui.ui_theme import load_layout, validate_layout

            layout = load_layout(saved, extract_dir=self._ui_themes_dir())
            errors, warnings = validate_layout(layout, check_assets=True)
            if errors:
                raise ValueError("; ".join(errors))
            self._activate_custom_ui(layout, persist=False)
            if warnings:
                logger.warning("Tema cargado con advertencias: %s", warnings)
        except Exception as exc:
            logger.error("No se pudo restaurar la interfaz personalizada: %s", exc, exc_info=True)
            self._show_standard_ui()
            self._set_status("El tema personalizado falló; se restauró la interfaz clásica")

    def _apply_layout_from_editor(self, layout) -> None:
        """Recibe una instantánea estable del editor y la activa de inmediato."""
        from gui.ui_theme import UILayout

        source_path = getattr(layout, 'source_path', None)
        base_dir = getattr(layout, 'base_dir', None)
        # El editor continúa modificando su propio modelo. El renderer recibe una
        # copia para que un cambio posterior no deje la interfaz aplicada a medias.
        snapshot = UILayout.from_dict(
            layout.to_dict(),
            base_dir=base_dir,
            source_path=source_path,
        )
        persist = bool(source_path and Path(source_path).is_file())
        self._activate_custom_ui(snapshot, persist=persist)
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except tk.TclError:
            pass

    def _activate_custom_ui(self, layout, *, persist: bool) -> None:
        """Valida, crea el renderer y oculta temporalmente la UI clásica."""
        from gui.interface_renderer import InterfaceRenderer
        from gui.ui_theme import validate_layout

        errors, warnings = validate_layout(layout, check_assets=True)
        if errors:
            raise ValueError("Tema inválido:\n- " + "\n- ".join(errors))

        if self._custom_ui_renderer is not None:
            try:
                self._custom_ui_renderer.destroy()
            except Exception:
                pass
            self._custom_ui_renderer = None

        renderer = InterfaceRenderer(
            self.main_frame,
            layout,
            action_callback=self._dispatch_ui_action,
            context_provider=self._get_custom_ui_context,
            on_error=self._on_custom_ui_error,
        )
        self._custom_ui_renderer = renderer
        self._custom_ui_layout = layout
        self._show_custom_ui()

        if persist and self.profile_manager:
            source_path = getattr(layout, 'source_path', None)
            if source_path:
                self.profile_manager.set_setting('ui_layout_path', str(Path(source_path).resolve()))
                self.profile_manager.set_setting('ui_custom_enabled', True)
                self.profile_manager.save_config()
                if hasattr(self, 'ui_theme_path_var'):
                    self.ui_theme_path_var.set(str(Path(source_path).resolve()))
                if hasattr(self, 'ui_custom_start_var'):
                    self.ui_custom_start_var.set(True)

        warning_suffix = f" ({len(warnings)} advertencias)" if warnings else ""
        self._set_status(f"Interfaz personalizada activa: {layout.name}{warning_suffix}")

    def _show_custom_ui(self) -> None:
        """Muestra el renderer existente sin reconstruirlo."""
        if self._custom_ui_renderer is None or not self._custom_ui_renderer.winfo_exists():
            self._apply_saved_ui_layout()
            return
        for widget in (self.header, self.tabs, self.status_bar):
            try:
                widget.pack_forget()
            except Exception:
                pass
        self._custom_ui_renderer.pack(fill=tk.BOTH, expand=True)
        self._custom_ui_active = True

    def _show_standard_ui(self) -> None:
        """Vuelve a la interfaz clásica conservando el tema cargado para F12."""
        if self._custom_ui_renderer is not None:
            try:
                self._custom_ui_renderer.pack_forget()
            except Exception:
                pass
        self.header.pack(fill=tk.X, pady=(0, 10))
        self.tabs.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.status_bar.pack(fill=tk.X, pady=(0, 0))
        self._custom_ui_active = False

    def _disable_custom_ui(self) -> None:
        """Desactiva el tema de forma permanente y vuelve a la UI clásica."""
        self._show_standard_ui()
        if self._custom_ui_renderer is not None:
            try:
                self._custom_ui_renderer.destroy()
            except Exception:
                pass
        self._custom_ui_renderer = None
        self._custom_ui_layout = None
        if self.profile_manager:
            self.profile_manager.set_setting('ui_custom_enabled', False)
            self.profile_manager.save_config()
        if hasattr(self, 'ui_custom_start_var'):
            self.ui_custom_start_var.set(False)
        self._set_status("Interfaz clásica restaurada")

    def _toggle_custom_ui(self, _event=None):
        """F12: alterna sin cambiar la preferencia de inicio."""
        if self._custom_ui_active:
            self._show_standard_ui()
            self._set_status("Interfaz clásica temporal (F12 para volver)")
        elif self._custom_ui_renderer is not None and self._custom_ui_renderer.winfo_exists():
            self._show_custom_ui()
        else:
            saved = self.profile_manager.get_setting('ui_layout_path', '') if self.profile_manager else ''
            if saved:
                self._apply_saved_ui_layout()
        return "break"

    def _on_custom_ui_startup_toggle(self) -> None:
        enabled = bool(self.ui_custom_start_var.get())
        if self.profile_manager:
            self.profile_manager.set_setting('ui_custom_enabled', enabled)
            self.profile_manager.save_config()
        if enabled and self._custom_ui_renderer is None:
            self._apply_saved_ui_layout()
        elif not enabled and self._custom_ui_active:
            self._show_standard_ui()

    def _reload_custom_ui(self) -> None:
        saved = self.profile_manager.get_setting('ui_layout_path', '') if self.profile_manager else ''
        if saved:
            self._apply_saved_ui_layout()
        elif self._custom_ui_layout is not None and self._custom_ui_renderer is not None:
            self._custom_ui_renderer.set_layout(self._custom_ui_layout)

    def _dispatch_ui_action(self, action: str, args: Dict[str, Any], _element) -> None:
        """Despacha únicamente acciones conocidas; un tema jamás ejecuta Python."""
        if action.startswith("profile.apply:"):
            args = dict(args)
            args.setdefault("profile_id", action.split(":", 1)[1])
            action = "profile.apply"

        navigation = {
            "navigate.profiles": "Perfiles",
            "navigate.buttons": "Botones",
            "navigate.triggers": "Gatillos",
            "navigate.macros": "Macros",
            "navigate.input_studio": "Input Studio",
            "navigate.settings": "Configuracion",
        }
        if action in navigation:
            self._show_standard_ui()
            self._navigate_to_tab(navigation[action])
            return

        handlers = {
            "none": lambda: None,
            "controller.connect": self._request_controller_connect,
            "controller.disconnect": self._request_controller_disconnect,
            "profile.next": lambda: self._apply_relative_profile(1),
            "profile.previous": lambda: self._apply_relative_profile(-1),
            "profile.import": self._import_profile,
            "profile.export": self._export_profile,
            "trigger.reset": self._reset_triggers,
            "macro.new": self._open_macro_editor,
            "macro.toggle": self._toggle_macros_from_theme,
            "buttons.reset": self._reset_button_map,
            "emulation.xbox": lambda: self._on_emulation_change("Xbox 360"),
            "emulation.ps4": lambda: self._on_emulation_change("PlayStation 4"),
            "emulation.off": lambda: self._on_emulation_change("Apagado"),
            "led.choose": self._choose_led_color,
            "bluetooth.reset": self._reset_bluetooth,
            "ui.editor": self._open_interface_editor,
            "ui.reload": self._reload_custom_ui,
            "ui.standard": self._show_standard_ui,
            "ui.custom": self._show_custom_ui,
            "ui.disable": self._disable_custom_ui,
            "window.fullscreen.toggle": self._toggle_fullscreen,
            "app.minimize": self.hide_window,
            "app.close": self.exit_app,
        }
        if action == "profile.apply":
            profile_id = str(args.get("profile_id", "")).strip()
            if not profile_id:
                self._set_status("La acción profile.apply necesita profile_id")
                return
            self._apply_profile(profile_id)
            return
        if action == "macro.play":
            macro_id = str(args.get("macro_id", "")).strip()
            if not macro_id:
                self._set_status("La acción macro.play necesita macro_id")
                return
            self._test_macro(macro_id)
            return
        if action == "player.set":
            try:
                player = max(1, min(4, int(args.get("player", 1))))
            except (TypeError, ValueError):
                player = 1
            if hasattr(self, 'player_var'):
                self.player_var.set(str(player))
            self._on_player_change(str(player))
            self._set_status(f"Jugador configurado: {player}")
            return

        handler = handlers.get(action)
        if handler is None:
            logger.warning("Acción de tema ignorada: %s", action)
            self._set_status(f"Acción no compatible: {action}")
            return
        handler()

    def _navigate_to_tab(self, name: str) -> None:
        try:
            if CUSTOMTK_AVAILABLE:
                self.tabs.set(name)
            else:
                for tab_id in self.tabs.tabs():
                    if self.tabs.tab(tab_id, 'text') == name:
                        self.tabs.select(tab_id)
                        break
            self._set_status(f"Pestaña abierta: {name}")
        except Exception as exc:
            logger.warning("No se pudo abrir la pestaña %s: %s", name, exc)

    def _request_controller_connect(self) -> None:
        if not self.connection_manager:
            return
        if self.connection_manager.is_connected:
            self._set_status("El DualSense ya está conectado")
            return
        try:
            self.connection_manager.request_connect()
            self._set_status("Buscando DualSense...")
        except Exception as exc:
            self._set_status(f"No se pudo iniciar la conexión: {exc}")

    def _request_controller_disconnect(self) -> None:
        if self.connection_manager:
            self.connection_manager.disconnect()
            self._set_status("DualSense desconectado manualmente")

    def _apply_relative_profile(self, direction: int) -> None:
        if not self.trigger_engine:
            return
        profiles = self.trigger_engine.get_profile_names()
        if not profiles:
            self._set_status("No hay perfiles disponibles")
            return
        ids = [profile_id for profile_id, _name in profiles]
        current = self.trigger_engine.get_current_profile()
        try:
            index = ids.index(current)
        except ValueError:
            index = -1 if direction > 0 else 0
        target = ids[(index + direction) % len(ids)]
        self._apply_profile(target)

    def _toggle_macros_from_theme(self) -> None:
        if not self.macro_engine:
            return
        enabled = not self.macro_engine.is_enabled
        self.macro_engine.set_enabled(enabled)
        if hasattr(self, 'macros_enabled_var'):
            self.macros_enabled_var.set(enabled)
        if self.profile_manager:
            self.profile_manager.set_setting('macros_enabled', enabled)
        self._set_status("Macros activadas" if enabled else "Macros desactivadas")

    def _toggle_fullscreen(self) -> None:
        try:
            current = bool(self.root.attributes("-fullscreen"))
            self.root.attributes("-fullscreen", not current)
            self._set_status("Pantalla completa activada" if not current else "Pantalla completa desactivada")
        except Exception as exc:
            self._set_status(f"No se pudo cambiar pantalla completa: {exc}")

    def _get_custom_ui_context(self) -> Dict[str, Any]:
        connected = bool(self.connection_manager and self.connection_manager.is_connected)
        connection_type = ""
        if connected and self.connection_manager:
            try:
                connection_type = self.connection_manager.connection_type.value.upper()
            except Exception:
                connection_type = ""

        profile_id = self.trigger_engine.get_current_profile() if self.trigger_engine else ""
        profile_name = profile_id or "Ninguno"
        if self.trigger_engine and profile_id:
            profile = self.trigger_engine.get_profile(profile_id)
            if profile:
                profile_name = profile.name

        battery = self._last_battery_level if self._last_battery_level is not None else "--"
        profile_count = len(self.trigger_engine.get_profile_names()) if self.trigger_engine else 0
        emulation_mode = "Apagado"
        if self.connection_manager and self.connection_manager.emulator:
            try:
                emulation_mode = {"xbox": "Xbox 360", "ps4": "PlayStation 4", "none": "Apagado"}.get(
                    self.connection_manager.emulator.mode.value, self.connection_manager.emulator.mode.value
                )
            except Exception:
                pass
        macros_enabled = bool(self.macro_engine and self.macro_engine.is_enabled)
        return {
            "connected": connected,
            "connection": "Conectado" if connected else "Desconectado",
            "connection_type": connection_type,
            "battery": battery,
            "battery_percent": f"{battery}%" if isinstance(battery, int) else "--%",
            "is_charging": self._last_charging,
            "charging": "Sí" if self._last_charging else "No",
            "active_profile": profile_name,
            "active_profile_id": profile_id or "",
            "profile_count": profile_count,
            "emulation_mode": emulation_mode,
            "macros_enabled": "Sí" if macros_enabled else "No",
            "status": self._last_status_message,
            "l2": self._last_l2,
            "r2": self._last_r2,
            "app_version": "1.0",
        }

    def _on_custom_ui_error(self, message: str) -> None:
        self._set_status(f"Error en interfaz personalizada: {message}")

    def _create_settings_section(self, parent, title: str) -> CTkFrame:
        """Crea una seccion de configuracion con titulo."""
        section = CTkFrame(parent, fg_color=self.COLORS['bg_card'], corner_radius=12)

        CTkLabel(
            section,
            text=title,
            font=self.FONTS['title_sm'],
            text_color=self.COLORS['accent']
        ).pack(anchor="w", padx=15, pady=(12, 5))

        # Separador
        separator = CTkFrame(section, height=2, fg_color=self.COLORS['border'])
        separator.pack(fill=tk.X, padx=15, pady=(0, 8))

        return section

    def _create_switch_setting(self, parent, text: str, default: bool) -> CTkFrame:
        """Crea un frame con label y switch."""
        frame = CTkFrame(parent, fg_color="transparent")

        CTkLabel(
            frame, text=text,
            font=self.FONTS['body'],
            text_color=self.COLORS['text_primary']
        ).pack(side=tk.LEFT)

        switch_var = tk.BooleanVar(value=default)
        switch = CTkSwitch(
            frame,
            text="",
            variable=switch_var,
            fg_color=self.COLORS['border'],
            progress_color=self.COLORS['accent'],
            button_color=self.COLORS['text_primary'],
        )
        switch.pack(side=tk.RIGHT)
        switch.var = switch_var

        return frame

    def _build_status_bar(self) -> None:
        """Construye la barra de estado inferior."""
        self.status_bar = CTkFrame(
            self.main_frame,
            fg_color=self.COLORS['bg_secondary'],
            corner_radius=8,
            height=30
        )
        self.status_bar.pack(fill=tk.X, pady=(0, 0))
        self.status_bar.pack_propagate(False)

        self.status_label = CTkLabel(
            self.status_bar,
            text="Iniciando...",
            font=self.FONTS['caption'],
            text_color=self.COLORS['text_secondary']
        )
        self.status_label.pack(side=tk.LEFT, padx=10)

        self.fps_label = CTkLabel(
            self.status_bar,
            text="",
            font=self.FONTS['micro'],
            text_color=self.COLORS['text_secondary']
        )
        self.fps_label.pack(side=tk.RIGHT, padx=10)

    # ===== Callbacks y Eventos =====

    def _setup_callbacks(self) -> None:
        """Configura los callbacks del sistema."""
        if self.connection_manager:
            self.connection_manager.on_connect(self._on_controller_connected)
            self.connection_manager.on_disconnect(self._on_controller_disconnected)
            self.connection_manager.on_battery_change(self._on_battery_change)
            self.connection_manager.on_state_update(self._on_state_update)
            self.connection_manager.on_error(self._on_connection_error)

        if self.trigger_engine:
            self.trigger_engine.on_profile_change(self._on_profile_applied)

    def _on_window_close(self) -> None:
        """Maneja el evento de cierre de ventana."""
        minimize_to_tray = False

        if self.profile_manager:
            minimize_to_tray = self.profile_manager.get_setting('minimize_to_tray', True)

        if minimize_to_tray and not self._minimized_to_tray:
            self.hide_window()
        else:
            self.exit_app()

    def hide_window(self) -> None:
        """Oculta la ventana principal (modo bandeja)."""
        self._minimized_to_tray = True
        self.root.withdraw()

        if self.tray_manager:
            self.tray_manager.set_status("Ejecutando en segundo plano")

        self._set_status("Minimizado a bandeja. Haz clic en el icono para restaurar.")
        logger.info("Ventana minimizada a bandeja")

    def show_window(self) -> None:
        """Muestra la ventana principal."""
        self._minimized_to_tray = False
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def exit_app(self) -> None:
        """Cierra completamente la aplicacion."""
        self._running = False

        # Cancelar after pendientes
        if self._after_id:
            self.root.after_cancel(self._after_id)

        # Guardar configuracion
        if self.profile_manager:
            geo = self._get_window_geometry()
            self.profile_manager.save_window_geometry(**geo)
            if self.trigger_engine:
                self.profile_manager.set_setting(
                    'profile_trigger_vibration',
                    self.trigger_engine.export_vibration_overrides()
                )
                self.profile_manager.set_setting(
                    'profile_gyro',
                    self.trigger_engine.export_gyro_overrides()
                )
            if self.input_studio:
                self.profile_manager.set_setting(
                    'profile_input_studio', self.input_studio.export_profiles()
                )
            self.profile_manager.save_config()

        # Detener modulos
        if self.trigger_engine:
            self.trigger_engine.stop()

        if self.gyro_engine:
            self.gyro_engine.stop()

        if self.connection_manager:
            self.connection_manager.stop()

        if self.tray_manager:
            self.tray_manager.stop()

        # Destruir ventana
        self.root.destroy()

        # Notificar a main
        for callback in self._on_close:
            try:
                callback()
            except Exception:
                pass

        logger.info("Aplicacion cerrada")

    def on_close(self, callback: Callable[[], None]) -> None:
        """Registra callback para cierre de aplicacion."""
        self._on_close.append(callback)

    # ===== Acciones =====

    def _apply_profile(self, profile_id: str) -> None:
        """Aplica un perfil de arma."""
        if self.trigger_engine:
            success = self.trigger_engine.apply_profile(profile_id)
            if success:
                self._set_status(f"Perfil aplicado: {profile_id}")
                # Guardar como activo
                if self.profile_manager:
                    self.profile_manager.set_active_profile(profile_id)
            else:
                self._set_status("Error aplicando perfil")

    def _on_effect_change(self, trigger: str, effect_type: str) -> None:
        """Maneja cambio de efecto desde el dropdown."""
        self._apply_current_trigger_settings(trigger, effect_type_override=effect_type, throttled=False)
        self._set_status(f"Efecto {effect_type} aplicado a {trigger}")

    def _apply_current_trigger_settings(self, trigger: str, effect_type_override: str = None, throttled: bool = True) -> None:
        """Arma un TriggerEffect con el efecto y los sliders actuales de un
        gatillo y lo manda en vivo. Se usa tanto al elegir un efecto del
        dropdown como al mover cualquiera de los sliders (posicion,
        intensidad, frecuencia) -- antes los sliders solo actualizaban su
        numerito en pantalla y no mandaban nada al control real."""
        if not self.trigger_engine:
            return

        now = time.time()
        last_apply_attr = f'_{trigger}_slider_last_apply'
        if throttled and (now - getattr(self, last_apply_attr, 0)) < 0.05:
            return
        setattr(self, last_apply_attr, now)

        from src.trigger_engine import TriggerEffect, TriggerEffectType

        effect_var = self.l2_effect_var if trigger == 'left' else self.r2_effect_var
        effect_type = effect_type_override or effect_var.get()

        effect_map = {
            'off': TriggerEffectType.OFF,
            'rigid': TriggerEffectType.RIGID,
            'pulse': TriggerEffectType.PULSE,
            'continuous_vibration': TriggerEffectType.CONTINUOUS_VIBRATION,
            'sections': TriggerEffectType.SECTIONS,
        }

        effect = TriggerEffect(
            name=effect_type,
            effect_type=effect_map.get(effect_type, TriggerEffectType.OFF),
            intensity=int(getattr(self, f'{trigger}_intensity_slider').get()),
            start_position=int(getattr(self, f'{trigger}_start_slider').get()),
            end_position=int(getattr(self, f'{trigger}_end_slider').get()),
            frequency=int(getattr(self, f'{trigger}_freq_slider').get()),
        )

        self.trigger_engine.apply_effect(trigger, effect)

    def _on_intensity_change(self, trigger: str, value: float) -> None:
        """Actualiza el label de intensidad y aplica en vivo."""
        label = getattr(self, f'{trigger}_intensity_value')
        label.configure(text=f"{int(value)}")
        self._apply_current_trigger_settings(trigger)

    def _on_position_change(self, trigger: str, which: str, value: float) -> None:
        """Actualiza el label de posicion (inicio/fin) y aplica en vivo."""
        label = getattr(self, f'{trigger}_{which}_value')
        label.configure(text=f"{int(value)}")
        self._apply_current_trigger_settings(trigger)

    def _on_frequency_change(self, trigger: str, value: float) -> None:
        """Actualiza el label de frecuencia y aplica en vivo."""
        label = getattr(self, f'{trigger}_freq_value')
        label.configure(text=f"{int(value)}")
        self._apply_current_trigger_settings(trigger)

    # ===== Editor Visual de Curva de Gatillo =====

    def _curve_to_canvas(self, pos: float, force: float) -> tuple:
        """Convierte (posicion 0-9, fuerza 0-255) a coordenadas del canvas."""
        w, h = self.CURVE_CANVAS_W, self.CURVE_CANVAS_H
        mx, my = self.CURVE_MARGIN_X, self.CURVE_MARGIN_Y
        x = mx + (pos / 9.0) * (w - 2 * mx)
        y = (h - my) - (force / 255.0) * (h - 2 * my)
        return x, y

    def _canvas_to_curve(self, x: float, y: float) -> tuple:
        """Convierte coordenadas del canvas a (posicion 0-9, fuerza 0-255),
        recortado a los limites validos."""
        w, h = self.CURVE_CANVAS_W, self.CURVE_CANVAS_H
        mx, my = self.CURVE_MARGIN_X, self.CURVE_MARGIN_Y
        pos = (x - mx) / max(1, (w - 2 * mx)) * 9.0
        force = ((h - my) - y) / max(1, (h - 2 * my)) * 255.0
        pos = max(0, min(9, round(pos)))
        force = max(0, min(255, int(force)))
        return pos, force

    def _current_curve_trigger(self) -> str:
        return 'left' if self.curve_trigger_var.get() == "L2" else 'right'

    def _redraw_curve(self) -> None:
        """Redibuja la grilla, la curva y los puntos arrastrables."""
        if not hasattr(self, 'curve_canvas'):
            return

        c = self.curve_canvas
        c.delete("all")
        w, h = self.CURVE_CANVAS_W, self.CURVE_CANVAS_H
        mx, my = self.CURVE_MARGIN_X, self.CURVE_MARGIN_Y

        # Grilla vertical: una linea por cada posicion 0-9
        for pos in range(10):
            x, _ = self._curve_to_canvas(pos, 0)
            c.create_line(x, my, x, h - my, fill=self.COLORS['border'])

        # Grilla horizontal: lineas de referencia de fuerza
        for force in (0, 64, 128, 192, 255):
            _, y = self._curve_to_canvas(0, force)
            c.create_line(mx, y, w - mx, y, fill=self.COLORS['border'])
            c.create_text(
                mx - 18, y, text=str(force),
                fill=self.COLORS['text_secondary'], font=self.FONTS['micro']
            )

        c.create_text(
            mx, h - 6, text="Suelto", anchor="w",
            fill=self.COLORS['text_secondary'], font=self.FONTS['micro']
        )
        c.create_text(
            w - mx, h - 6, text="Fondo", anchor="e",
            fill=self.COLORS['text_secondary'], font=self.FONTS['micro']
        )

        trigger = self._current_curve_trigger()
        points = self._curve_points[trigger]

        # Curva escalonada: cada punto inicia un tramo independiente que se
        # mantiene hasta el siguiente. Es exactamente lo que recibe el mando.
        sorted_points = sorted(points, key=lambda p: p[0])
        coords = []
        if sorted_points:
            first_pos, first_force = sorted_points[0]
            if first_pos > 0:
                x0, y0 = self._curve_to_canvas(0, 0)
                x1, _ = self._curve_to_canvas(first_pos, 0)
                _, y1 = self._curve_to_canvas(first_pos, first_force)
                coords.extend([x0, y0, x1, y0, x1, y1])
            else:
                x1, y1 = self._curve_to_canvas(first_pos, first_force)
                coords.extend([x1, y1])

            for index, (pos, force) in enumerate(sorted_points):
                next_pos = sorted_points[index + 1][0] if index + 1 < len(sorted_points) else 9
                x_start, y_force = self._curve_to_canvas(pos, force)
                x_end, _ = self._curve_to_canvas(next_pos, force)
                if not coords:
                    coords.extend([x_start, y_force])
                coords.extend([x_end, y_force])
                if index + 1 < len(sorted_points):
                    _, next_y = self._curve_to_canvas(next_pos, sorted_points[index + 1][1])
                    coords.extend([x_end, next_y])
        if len(coords) >= 4:
            c.create_line(*coords, fill=self.COLORS['trigger_accent'], width=3)

        # Puntos arrastrables (el orden de la lista original define el
        # indice, que es lo que usa el drag para saber cual mover)
        for i, (pos, force) in enumerate(points):
            x, y = self._curve_to_canvas(pos, force)
            r = 8
            c.create_oval(
                x - r, y - r, x + r, y + r,
                fill=self.COLORS['trigger_accent'],
                outline=self.COLORS['text_primary'], width=2
            )

        if hasattr(self, 'curve_zones_label'):
            if self.trigger_engine and hasattr(self.trigger_engine, 'get_section_zone_strengths'):
                strengths = self.trigger_engine.get_section_zone_strengths(sorted_points)
                zone_text = " · ".join(str(value) for value in strengths)
                self.curve_zones_label.configure(
                    text=f"Fuerza real por zona 0-9 (escala del mando 0-8): {zone_text}"
                )
            else:
                self.curve_zones_label.configure(text="")

    def _on_curve_press(self, event) -> None:
        """Detecta que punto se va a arrastrar segun donde se hizo click."""
        trigger = self._current_curve_trigger()
        points = self._curve_points[trigger]

        closest_i, closest_dist = None, float('inf')
        for i, (pos, force) in enumerate(points):
            x, y = self._curve_to_canvas(pos, force)
            dist = ((x - event.x) ** 2 + (y - event.y) ** 2) ** 0.5
            if dist < closest_dist:
                closest_dist = dist
                closest_i = i

        # Radio de "agarre": si el click no cayo cerca de ningun punto, no
        # se arrastra nada (para no mover un punto sin querer).
        if closest_dist <= 16:
            self._curve_dragging = closest_i

    def _on_curve_drag(self, event) -> None:
        """Mueve el punto que se esta arrastrando y aplica en vivo (con
        throttle para no saturar el HID con updates a 60+ por segundo)."""
        if self._curve_dragging is None:
            return
        trigger = self._current_curve_trigger()
        pos, force = self._canvas_to_curve(event.x, event.y)
        points = self._curve_points[trigger]
        index = self._curve_dragging
        min_pos = points[index - 1][0] + 1 if index > 0 else 0
        max_pos = points[index + 1][0] - 1 if index < len(points) - 1 else 9
        pos = max(min_pos, min(max_pos, pos))
        points[index] = (pos, force)
        self._redraw_curve()
        self._apply_curve_live(trigger, throttled=True)

    def _on_curve_release(self, event) -> None:
        """Suelta el punto y manda el estado final de la curva, sin throttle."""
        if self._curve_dragging is None:
            return
        trigger = self._current_curve_trigger()
        self._curve_dragging = None
        self._apply_curve_live(trigger, throttled=False)

    def _on_curve_trigger_switch(self, value: str) -> None:
        """Cambia entre editar la curva de L2 o R2."""
        self._redraw_curve()

    def _apply_curve_live(self, trigger: str, throttled: bool) -> None:
        """Manda la curva actual al gatillo real como efecto SECTIONS."""
        now = time.time()
        if throttled and (now - self._curve_last_apply) < 0.05:
            return
        self._curve_last_apply = now

        if not self.trigger_engine:
            return

        from src.trigger_engine import TriggerEffect, TriggerEffectType

        points = sorted(self._curve_points[trigger], key=lambda p: p[0])
        effect = TriggerEffect(
            name="Curva personalizada",
            effect_type=TriggerEffectType.SECTIONS,
            custom_params={'sections': [(p, f) for p, f in points]},
        )
        self.trigger_engine.apply_effect(trigger, effect)

    def _reset_curve(self) -> None:
        """Vuelve la curva del gatillo actual a la forma pareja por defecto."""
        trigger = self._current_curve_trigger()
        self._curve_points[trigger] = [(0, 40), (3, 120), (6, 180), (9, 220)]
        self._redraw_curve()
        self._apply_curve_live(trigger, throttled=False)
        self._set_status("Curva reseteada")

    def _save_curve(self) -> None:
        """Guarda la curva actual para que persista entre sesiones."""
        trigger = self._current_curve_trigger()
        if self.profile_manager:
            self.profile_manager.set_setting(f'trigger_curve_{trigger}', self._curve_points[trigger])
        self._set_status(f"Curva de {self.curve_trigger_var.get()} guardada")

    def _load_saved_curve(self, trigger: str):
        """Carga una curva guardada previamente, si existe."""
        if not self.profile_manager:
            return None
        saved = self.profile_manager.get_setting(f'trigger_curve_{trigger}', None)
        if saved and isinstance(saved, list) and len(saved) == 4:
            try:
                points = []
                for point in saved:
                    pos, force = point
                    points.append((
                        max(0, min(9, int(pos))),
                        max(0, min(255, int(force))),
                    ))
                points.sort(key=lambda p: p[0])
                if len({p[0] for p in points}) != 4:
                    return None
                return points
            except Exception:
                return None
        return None

    def _refresh_emulation_status_labels(self) -> None:
        """Actualiza los avisos de estado de emulacion en Macros y Botones,
        para que quede claro cuando esos dos no van a tener efecto todavia
        en ningun juego (necesitan el control virtual Xbox/PS4 prendido)."""
        active = bool(
            self.connection_manager and self.connection_manager.emulator
            and self.connection_manager.emulator.is_active
        )
        if active:
            mode_names = {'xbox': 'Xbox 360', 'ps4': 'PlayStation 4'}
            mode_name = mode_names.get(self.connection_manager.emulator.mode.value, "control virtual")
            text = f"● Emulación activa ({mode_name}): esto ya se aplica en los juegos."
            color = self.COLORS['success']
        else:
            text = ("⚠ Emulación apagada: esto no se va a notar en ningún juego todavía. "
                    "Prendela en Configuración → Emulación (Compatibilidad PC).")
            color = self.COLORS['warning']

        for attr in ('macros_emu_status_label', 'buttons_emu_status_label'):
            label = getattr(self, attr, None)
            if label:
                try:
                    label.configure(text=text, text_color=color)
                except Exception:
                    pass

    def _on_emulation_change(self, value: str) -> None:
        """Maneja el cambio de emulacion de control."""
        if not hasattr(self, 'connection_manager') or not self.connection_manager:
            return

        if value == "Xbox 360":
            mode = EmulationMode.XBOX
        elif value == "PlayStation 4":
            mode = EmulationMode.PS4
        else:
            mode = EmulationMode.NONE

        success = self.connection_manager.set_emulation_mode(mode)
        
        if success:
            self._set_status(f"Emulación cambiada a: {value}")
            if self.profile_manager:
                self.profile_manager.set_setting('emulation_mode', value)
        else:
            self._set_status("Error al emular. Asegúrate de tener ViGEmBus instalado.")
            self.emulation_var.set("Apagado")
            if self.profile_manager:
                self.profile_manager.set_setting('emulation_mode', "Apagado")

        self._refresh_emulation_status_labels()

    def _reset_triggers(self) -> None:
        """Resetea ambos gatillos."""
        if self.trigger_engine:
            self.trigger_engine.reset_triggers()
            self._set_status("Gatillos reseteados")

    def _choose_led_color(self) -> None:
        """Abre selector de color para el LED."""
        color = colorchooser.askcolor(title="Elegir color LED")
        if color[0]:
            r, g, b = int(color[0][0]), int(color[0][1]), int(color[0][2])
            self.led_preview.configure(fg_color=color[1])

            if self.connection_manager:
                self.connection_manager.set_led_color(r, g, b)

            if self.profile_manager:
                self.profile_manager.set_setting('led_color', [r, g, b])

    def _on_player_change(self, value: str) -> None:
        """Maneja cambio de numero de jugador."""
        try:
            player = int(value.split()[0])
        except (ValueError, IndexError):
            player = 1

        if self.connection_manager:
            self.connection_manager.set_player_led(player)

        if self.profile_manager:
            self.profile_manager.set_setting('player_number', player)

    def _on_touchpad_mouse_toggle(self) -> None:
        """Activa o desactiva el touchpad como mouse y guarda la preferencia."""
        enabled = bool(self.touchpad_mouse_enabled_var.get())

        if not self.touchpad_mouse or not self.touchpad_mouse.is_available():
            self.touchpad_mouse_enabled_var.set(False)
            enabled = False
            self._set_status("Touchpad como mouse no disponible en este sistema")
        else:
            self.touchpad_mouse.set_enabled(enabled)
            self._set_status(
                "Touchpad como mouse activado" if enabled
                else "Touchpad como mouse desactivado"
            )

        if self.profile_manager:
            self.profile_manager.set_setting('touchpad_mouse.enabled', enabled)

    def _on_touchpad_sensitivity_change(self, value: float) -> None:
        """Actualiza la sensibilidad del cursor en vivo."""
        sensitivity = max(0.1, min(10.0, float(value)))
        self.touchpad_sensitivity_value.configure(text=f"{sensitivity:.1f}x")

        if self.touchpad_mouse:
            self.touchpad_mouse.set_sensitivity(sensitivity)
        if self.profile_manager:
            self.profile_manager.set_setting('touchpad_mouse.sensitivity', sensitivity)

    def _reset_bluetooth(self) -> None:
        """Reinicia el Bluetooth."""
        self._set_status("Reiniciando Bluetooth...")
        self.reset_bt_btn.configure(state="disabled")

        def do_reset():
            if self.connection_manager:
                success = self.connection_manager.perform_bluetooth_reset()
                self.root.after(0, lambda: self._on_bluetooth_reset_done(success))

        import threading
        thread = threading.Thread(target=do_reset, daemon=True)
        thread.start()

    def _on_bluetooth_reset_done(self, success: bool) -> None:
        """Callback cuando termina el reinicio de Bluetooth."""
        self.reset_bt_btn.configure(state="normal")
        if success:
            self._set_status("Bluetooth reiniciado exitosamente")
        else:
            self._set_status("Error reiniciando Bluetooth. Revisa permisos de administrador.")

    # ===== Perfil por Juego =====

    def _on_game_profiles_toggle(self) -> None:
        """Activa/desactiva la deteccion automatica de juego."""
        enabled = self.game_profiles_enabled_var.get()
        if self.game_profile_watcher:
            self.game_profile_watcher.set_enabled(enabled)
        if self.profile_manager:
            self.profile_manager.set_setting('game_profiles_enabled', enabled)

    def _add_game_profile_mapping(self) -> None:
        """Agrega una asociacion exe -> perfil y la guarda."""
        exe_name = self.game_exe_entry.get().strip()
        if not exe_name:
            messagebox.showwarning("Perfil por Juego", "Escribí el nombre del ejecutable (ej: valorant.exe).")
            return
        if not exe_name.lower().endswith('.exe'):
            exe_name += '.exe'

        profile_name = self.game_profile_var.get()
        profile_id = self._game_profile_choices.get(profile_name)
        if not profile_id:
            messagebox.showwarning("Perfil por Juego", "Elegí un perfil válido.")
            return

        if not self.game_profile_watcher:
            messagebox.showerror("Perfil por Juego", "El detector de juegos no está disponible.")
            return

        self.game_profile_watcher.add_mapping(exe_name, profile_id)
        if self.profile_manager:
            self.profile_manager.set_game_profiles(self.game_profile_watcher.get_mapping())

        self.game_exe_entry.delete(0, tk.END)
        self._populate_game_profiles_list()
        self._set_status(f"{exe_name} -> {profile_name}")

    def _remove_game_profile_mapping(self, exe_name: str) -> None:
        """Elimina una asociacion exe -> perfil."""
        if self.game_profile_watcher:
            self.game_profile_watcher.remove_mapping(exe_name)
            if self.profile_manager:
                self.profile_manager.set_game_profiles(self.game_profile_watcher.get_mapping())
        self._populate_game_profiles_list()

    def _populate_game_profiles_list(self) -> None:
        """Redibuja la lista de asociaciones exe -> perfil guardadas."""
        if not hasattr(self, 'game_profiles_list_frame'):
            return

        for widget in self.game_profiles_list_frame.winfo_children():
            widget.destroy()

        mapping = self.game_profile_watcher.get_mapping() if self.game_profile_watcher else {}

        if not mapping:
            CTkLabel(
                self.game_profiles_list_frame,
                text="Todavía no agregaste ningún juego.",
                font=self.FONTS['caption'],
                text_color=self.COLORS['text_secondary']
            ).pack(anchor="w", pady=5)
            return

        profile_names = dict(self.trigger_engine.get_profile_names()) if self.trigger_engine else {}

        for exe_name, profile_id in mapping.items():
            row = CTkFrame(self.game_profiles_list_frame, fg_color=self.COLORS['bg_card'], corner_radius=8)
            row.pack(fill=tk.X, pady=3)

            CTkLabel(
                row, text=exe_name,
                font=self.FONTS['mono'],
                text_color=self.COLORS['text_primary']
            ).pack(side=tk.LEFT, padx=10, pady=8)

            CTkLabel(
                row, text=f"→ {profile_names.get(profile_id, profile_id)}",
                font=self.FONTS['small'],
                text_color=self.COLORS['trigger_accent']
            ).pack(side=tk.LEFT, padx=5)

            CTkButton(
                row, text="✕", width=28, height=24,
                font=self.FONTS['small_bold'],
                fg_color=self.COLORS['danger'],
                hover_color=self.COLORS['danger_hover'],
                corner_radius=6,
                command=lambda e=exe_name: self._remove_game_profile_mapping(e)
            ).pack(side=tk.RIGHT, padx=10, pady=6)

    def _import_profile(self) -> None:
        """Importa un perfil desde archivo JSON."""
        file_path = filedialog.askopenfilename(
            title="Importar Perfil",
            filetypes=[("Perfil Nikaido", "*.Nika"), ("Perfil antiguo", "*.json"), ("Todos", "*.*")]
        )
        if file_path and self.profile_manager:
            profile_id = self.profile_manager.import_profile(file_path)
            if profile_id:
                imported = self.profile_manager.get_custom_profiles().get(profile_id)
                if self.trigger_engine and isinstance(imported, dict):
                    self.trigger_engine.load_profiles_from_dict({profile_id: imported})
                    self._persist_custom_weapon_profiles()
                self._refresh_weapon_profile_views()
                self._set_status(f"Perfil importado: {profile_id}")
            else:
                messagebox.showerror("Error", "No se pudo importar el perfil")

    def _export_profile(self) -> None:
        """Exporta el perfil activo a archivo JSON."""
        if not self.profile_manager or not self.trigger_engine:
            return

        profile_id = self.trigger_engine.get_current_profile()
        if not profile_id:
            messagebox.showwarning("Advertencia", "No hay perfil activo para exportar")
            return

        file_path = filedialog.asksaveasfilename(
            title="Exportar Perfil",
            defaultextension=".json",
            filetypes=[("Perfil Nikaido", "*.Nika"), ("Perfil antiguo", "*.json"), ("Todos", "*.*")]
        )
        if file_path:
            profile = self.trigger_engine.get_profile(profile_id)
            success = self.profile_manager.export_profile(
                profile_id, file_path, profile.to_dict() if profile else None
            )
            if success:
                self._set_status(f"Perfil exportado a: {file_path}")
            else:
                messagebox.showerror("Error", "No se pudo exportar el perfil")

    def _reset_defaults(self) -> None:
        """Restaura configuracion por defecto."""
        result = messagebox.askyesno(
            "Confirmar",
            "Esto eliminara todos tus perfiles personalizados y restaurara la configuracion original. ¿Continuar?"
        )
        if result and self.profile_manager:
            self.profile_manager.reset_to_defaults()
            self._set_status("Configuracion restaurada a valores por defecto")
            self._populate_profiles_grid()

    # ===== Actualizaciones de UI =====

    def _on_controller_connected(self, connection_type) -> None:
        """Callback cuando se conecta el control."""
        conn_type_str = "USB" if connection_type.value == "usb" else "BLUETOOTH"
        color = self.COLORS['success'] if connection_type.value == "usb" else self.COLORS['accent']

        self.connection_indicator.dot.configure(text_color=color)
        self.connection_indicator.label.configure(text="Conectado")

        self.type_indicator.dot.configure(text_color=color)
        self.type_indicator.label.configure(text=f"{conn_type_str}")

        self._set_status(f"DualSense conectado via {conn_type_str}")

        # Aplicar perfil guardado
        if self.trigger_engine and self.profile_manager:
            active = self.profile_manager.get_active_profile()
            self.trigger_engine.apply_profile(active)

    def _on_controller_disconnected(self) -> None:
        """Callback cuando se desconecta el control."""
        self._last_battery_level = None
        self._last_charging = False
        self._last_l2 = 0
        self._last_r2 = 0
        self.connection_indicator.dot.configure(text_color=self.COLORS['danger'])
        self.connection_indicator.label.configure(text="Desconectado")

        self.type_indicator.dot.configure(text_color=self.COLORS['text_secondary'])
        self.type_indicator.label.configure(text="")

        self.battery_icon.configure(text_color=self.COLORS['text_secondary'])
        self.battery_label.configure(text="--%", text_color=self.COLORS['text_secondary'])
        self.battery_bar.set(0)

        self._set_status("DualSense desconectado")

    def _on_battery_change(self, level: int, status) -> None:
        """Callback cuando cambia el estado de bateria."""
        self._last_battery_level = int(level)
        self._last_charging = status.value in ['cargando', 'cargado completo']
        # Color segun nivel
        if level >= 60:
            color = self.COLORS['battery_high']
        elif level >= 20:
            color = self.COLORS['battery_medium']
        else:
            color = self.COLORS['battery_low']

        # Icono
        charging = status.value in ['cargando', 'cargado completo']
        icon = "🔌" if charging else "🔋"

        self.battery_icon.configure(text_color=color)
        self.battery_label.configure(text=f"{level}%", text_color=color)
        self.battery_bar.configure(progress_color=color)
        self.battery_bar.set(level / 100)

        # Actualizar tray
        if self.tray_manager:
            self.tray_manager.set_battery(level, charging)

    def _on_state_update(self, state) -> None:
        """Callback para actualizacion de estado del control."""
        # Actualizar posicion de gatillos
        self._last_l2 = int(state.left_trigger)
        self._last_r2 = int(state.right_trigger)
        l2_pos = state.left_trigger / 255
        r2_pos = state.right_trigger / 255

        self.l2_position_bar.set(l2_pos)
        self.l2_position_label.configure(text=f"Posicion: {state.left_trigger:>3}")

        self.r2_position_bar.set(r2_pos)
        self.r2_position_label.configure(text=f"Posicion: {state.right_trigger:>3}")

    def _on_connection_error(self, message: str) -> None:
        """Callback para errores de conexion."""
        self._set_status(f"Error: {message}")

    def _on_profile_applied(self, profile_id: str) -> None:
        """Callback cuando se aplica un perfil."""
        if self.trigger_engine:
            profile = self.trigger_engine.get_profile(profile_id)
            if profile:
                self.active_profile_label.configure(text=f"EN USO  ·  {profile.name}")
                self.profile_desc_label.configure(text=profile.description)

        # El callback del motor principal ya aplico la configuracion del
        # perfil. Solo reflejamos sus valores en la UI desde el hilo Tk.
        if self.gyro_engine and hasattr(self, '_gyro_sliders'):
            try:
                self.root.after(0, lambda: self._gyro_load_config(self.gyro_engine.get_config()))
            except Exception:
                pass

        if self.input_studio and hasattr(self, 'input_profile_var'):
            def refresh_input_studio():
                self._input_refresh_profiles()
                self._input_load_config()
            try:
                self.root.after(0, refresh_input_studio)
            except Exception:
                pass

        # Actualizar tray
        if self.tray_manager:
            self.tray_manager.set_current_profile(profile_id)

    def _set_status(self, message: str) -> None:
        """Actualiza el texto de la barra de estado y el contexto de temas."""
        self._last_status_message = str(message)
        self.status_label.configure(text=message)
        logger.info(f"Status: {message}")

    def _get_window_geometry(self) -> dict:
        """Obtiene la geometria actual de la ventana."""
        self.root.update_idletasks()
        return {
            'width': self.root.winfo_width(),
            'height': self.root.winfo_height(),
            'x': self.root.winfo_x(),
            'y': self.root.winfo_y(),
        }

        # ===== Ciclo de Vida =====

    def start(self) -> None:
        """Inicia la interfaz grafica."""
        self._running = True
        self._set_status("Listo - Conecta tu DualSense")
        
        # Sincronizar la UI si el control se conectó más rápido que la interfaz
        if self.connection_manager and self.connection_manager.is_connected:
            self._on_controller_connected(self.connection_manager.connection_type)
            # Forzar la lectura inicial de la batería
            bat_level, bat_status = self.connection_manager.get_battery_info()
            self._on_battery_change(bat_level, bat_status)

        self._schedule_update()

    def _schedule_update(self) -> None:
        """Programa la proxima actualizacion de UI."""
        if not self._running:
            return

        self._update_ui()
        self._after_id = self.root.after(self._update_interval, self._schedule_update)

    def _update_ui(self) -> None:
        """Actualizacion periodica de la interfaz."""
        self._update_gyro_telemetry()
        self._update_input_studio_live()

    def run(self) -> None:
        """Ejecuta el loop principal de la interfaz."""
        self.start()

        # Restaurar geometria guardada
        if self.profile_manager:
            geo = self.profile_manager.get_window_geometry()
            if geo['x'] is not None and geo['y'] is not None:
                self.root.geometry(f"{geo['width']}x{geo['height']}+{geo['x']}+{geo['y']}")

            # Minimizar al inicio si esta configurado
            if self.profile_manager.get_setting('start_minimized', False):
                self.hide_window()

        self.root.mainloop()

    def stop(self) -> None:
        """Detiene la interfaz grafica."""
        self._running = False
        if self._after_id:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
