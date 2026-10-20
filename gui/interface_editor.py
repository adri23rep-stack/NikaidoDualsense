"""Nikaido UI Studio: editor visual de interfaces personalizadas.

El editor produce diseños JSON para trabajo local y paquetes ``.nikaido-theme``
portables. No permite ejecutar código arbitrario: cada elemento solo puede invocar
acciones registradas por la aplicación principal.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import tkinter as tk
import uuid
from dataclasses import asdict
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageSequence, ImageTk

from src.security_utils import read_json_file_limited, safe_json_loads

from gui.ui_theme import (
    ACTION_DEFINITIONS,
    DEFAULT_ACTIONS,
    UIElement,
    UILayout,
    ThemeError,
    export_theme_package,
    load_layout,
    save_layout,
    substitute_variables,
    validate_layout,
)

ApplyCallback = Callable[[UILayout], None]


class InterfaceEditor(tk.Toplevel):
    """Editor visual basado en Canvas, con capas, propiedades y exportación."""

    DEFAULT_CANVAS_WIDTH = 900
    DEFAULT_CANVAS_HEIGHT = 560
    MIN_ELEMENT_SIZE = 8
    HANDLE_SIZE = 9
    GRID_SIZE = 10
    MAX_HISTORY = 60
    AUTOSAVE_MS = 30_000
    MAX_IMAGE_BYTES = 25 * 1024 * 1024
    MAX_SOURCE_IMAGE_PIXELS = 20_000_000
    MAX_ANIMATION_FRAMES = 200
    MAX_CACHED_ANIMATION_PIXELS = 80_000_000
    SAFE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

    def __init__(
        self,
        parent: tk.Misc,
        project_root: Optional[Path] = None,
        *,
        storage_dir: Optional[Path] = None,
        initial_path: Optional[Path] = None,
        on_apply: Optional[ApplyCallback] = None,
    ) -> None:
        super().__init__(parent)
        self.title("Nikaido UI Studio")
        self.geometry("1420x840")
        self.minsize(1120, 680)

        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.layouts_dir = Path(storage_dir).expanduser().resolve() if storage_dir else self.project_root / "config" / "ui_layouts"
        self.assets_dir = self.layouts_dir / "assets"
        self.autosave_file = self.layouts_dir / ".nikaido-ui-autosave.json"
        self.layouts_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

        self.on_apply = on_apply
        self.layout = UILayout(
            canvas={
                "width": self.DEFAULT_CANVAS_WIDTH,
                "height": self.DEFAULT_CANVAS_HEIGHT,
                "background": "#17171C",
                "scale_mode": "contain",
            },
            base_dir=self.layouts_dir,
            allow_external_assets=True,
        )
        self.current_page = self.layout.default_page
        self.elements: Dict[str, UIElement] = {}
        self.current_file: Optional[Path] = None
        self.selected_id: Optional[str] = None
        self.clipboard_element: Optional[Dict[str, Any]] = None
        self._dirty = False
        self._loading_properties = False
        self._history: List[Dict[str, Any]] = []
        self._history_index = -1
        self._drag_origin: Optional[Tuple[float, float]] = None
        self._element_origin: Optional[Tuple[float, float]] = None
        self._resize_origin: Optional[Tuple[float, float, float, float]] = None
        self._interaction_snapshot: Optional[Dict[str, Any]] = None
        self._canvas_items: Dict[str, int] = {}
        self._photo_refs: Dict[str, ImageTk.PhotoImage] = {}
        self._gif_frames: Dict[str, List[Tuple[ImageTk.PhotoImage, int]]] = {}
        self._gif_jobs: Dict[str, str] = {}
        self._zoom = 1.0
        self._grid_enabled = tk.BooleanVar(value=True)
        self._snap_enabled = tk.BooleanVar(value=True)
        self._autosave_job: Optional[str] = None
        self._property_preview_job: Optional[str] = None
        self._property_commit_job: Optional[str] = None
        self._property_trace_tokens: List[Tuple[tk.Variable, str]] = []

        self._build_ui()
        self._bind_live_property_updates()
        self._build_menu()
        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if initial_path:
            self.open_path(Path(initial_path), prompt_dirty=False)
        elif not self._offer_autosave_recovery():
            self._load_canvas_vars()
            self._reset_history()
            self._render_all()
        self._schedule_autosave()

    # ------------------------------------------------------------------
    # Construcción de interfaz
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Nuevo", accelerator="Ctrl+N", command=self.new_layout)
        file_menu.add_command(label="Crear plantilla inicial", command=self.create_starter_template)
        file_menu.add_command(label="Abrir…", accelerator="Ctrl+O", command=self.open_layout)
        file_menu.add_separator()
        file_menu.add_command(label="Guardar", accelerator="Ctrl+S", command=self.save_layout)
        file_menu.add_command(label="Guardar como…", accelerator="Ctrl+Shift+S", command=lambda: self.save_layout(save_as=True))
        file_menu.add_command(label="Exportar paquete…", accelerator="Ctrl+E", command=self.export_layout)
        file_menu.add_separator()
        file_menu.add_command(label="Validar diseño", command=self.validate_current_layout)
        file_menu.add_command(label="Cerrar", command=self._on_close)
        menu.add_cascade(label="Archivo", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=False)
        edit_menu.add_command(label="Deshacer", accelerator="Ctrl+Z", command=self.undo)
        edit_menu.add_command(label="Rehacer", accelerator="Ctrl+Y", command=self.redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Copiar", accelerator="Ctrl+C", command=self.copy_selected)
        edit_menu.add_command(label="Pegar", accelerator="Ctrl+V", command=self.paste_element)
        edit_menu.add_command(label="Duplicar", accelerator="Ctrl+D", command=self.duplicate_selected)
        edit_menu.add_command(label="Eliminar", accelerator="Supr", command=self.delete_selected)
        menu.add_cascade(label="Editar", menu=edit_menu)

        add_menu = tk.Menu(menu, tearoff=False)
        add_menu.add_command(label="Imagen o GIF", command=self.add_image)
        add_menu.add_command(label="Texto", command=self.add_text)
        add_menu.add_command(label="Globo de texto", command=self.add_speech_bubble)
        add_menu.add_command(label="Botón", command=self.add_button)
        add_menu.add_command(label="Barra dinámica", command=self.add_progress)
        add_menu.add_command(label="Rectángulo", command=self.add_rectangle)
        add_menu.add_command(label="Elipse", command=self.add_ellipse)
        add_menu.add_command(label="Zona invisible", command=self.add_hotspot)
        menu.add_cascade(label="Añadir", menu=add_menu)

        view_menu = tk.Menu(menu, tearoff=False)
        view_menu.add_checkbutton(label="Mostrar rejilla", variable=self._grid_enabled, command=self._render_all)
        view_menu.add_checkbutton(label="Ajustar a rejilla", variable=self._snap_enabled)
        view_menu.add_separator()
        view_menu.add_command(label="Zoom 50%", command=lambda: self.set_zoom(0.5))
        view_menu.add_command(label="Zoom 75%", command=lambda: self.set_zoom(0.75))
        view_menu.add_command(label="Zoom 100%", command=lambda: self.set_zoom(1.0))
        view_menu.add_command(label="Zoom 125%", command=lambda: self.set_zoom(1.25))
        view_menu.add_command(label="Zoom 150%", command=lambda: self.set_zoom(1.5))
        menu.add_cascade(label="Vista", menu=view_menu)

        self.config(menu=menu)

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self, padding=(7, 6))
        toolbar.pack(fill=tk.X)

        buttons = [
            ("Nuevo", self.new_layout),
            ("Abrir", self.open_layout),
            ("Guardar", self.save_layout),
            ("Exportar tema", self.export_layout),
            ("Imagen/GIF", self.add_image),
            ("Texto", self.add_text),
            ("Globo", self.add_speech_bubble),
            ("Botón", self.add_button),
            ("Barra", self.add_progress),
            ("Rectángulo", self.add_rectangle),
            ("Elipse", self.add_ellipse),
            ("Zona clic", self.add_hotspot),
        ]
        for text, command in buttons:
            ttk.Button(toolbar, text=text, command=command).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=7)
        ttk.Button(toolbar, text="Deshacer", command=self.undo).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Rehacer", command=self.redo).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Validar", command=self.validate_current_layout).pack(side=tk.LEFT, padx=2)

        if self.on_apply:
            ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=7)
            ttk.Button(
                toolbar, text="Aplicar y ver en Nikaido", command=self.apply_to_app
            ).pack(side=tk.LEFT, padx=2)

        zoom_frame = ttk.Frame(toolbar)
        zoom_frame.pack(side=tk.RIGHT)
        ttk.Label(zoom_frame, text="Zoom").pack(side=tk.LEFT, padx=(0, 4))
        self.zoom_var = tk.StringVar(value="100%")
        zoom_combo = ttk.Combobox(
            zoom_frame,
            textvariable=self.zoom_var,
            values=("50%", "75%", "100%", "125%", "150%", "200%"),
            width=7,
            state="readonly",
        )
        zoom_combo.pack(side=tk.LEFT)
        zoom_combo.bind("<<ComboboxSelected>>", lambda _e: self.set_zoom(float(self.zoom_var.get().rstrip("%")) / 100))

        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned, padding=7, width=220)
        center = ttk.Frame(paned, padding=7)
        right = ttk.Frame(paned, padding=7, width=340)
        paned.add(left, weight=1)
        paned.add(center, weight=5)
        paned.add(right, weight=2)

        self._build_layers_panel(left)
        self._build_canvas(center)
        self._build_properties_panel(right)

        self.status_var = tk.StringVar(value="Lienzo listo")
        status = ttk.Frame(self)
        status.pack(fill=tk.X)
        ttk.Label(status, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.coords_var = tk.StringVar(value="")
        ttk.Label(status, textvariable=self.coords_var, relief=tk.SUNKEN, anchor="e", width=28).pack(side=tk.RIGHT)

    def _build_layers_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Pantallas", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.page_var = tk.StringVar(value="main")
        self.page_combo = ttk.Combobox(parent, textvariable=self.page_var, state="readonly")
        self.page_combo.pack(fill=tk.X, pady=(5, 4))
        self.page_combo.bind("<<ComboboxSelected>>", self._on_page_select)

        page_buttons = ttk.Frame(parent)
        page_buttons.pack(fill=tk.X)
        ttk.Button(page_buttons, text="Nueva", command=self.add_page).grid(row=0, column=0, sticky="ew", padx=1, pady=1)
        ttk.Button(page_buttons, text="Renombrar", command=self.rename_page).grid(row=0, column=1, sticky="ew", padx=1, pady=1)
        ttk.Button(page_buttons, text="Eliminar", command=self.delete_page).grid(row=1, column=0, sticky="ew", padx=1, pady=1)
        ttk.Button(page_buttons, text="Inicial", command=self.set_default_page).grid(row=1, column=1, sticky="ew", padx=1, pady=1)
        page_buttons.columnconfigure((0, 1), weight=1)

        self.page_info_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.page_info_var, foreground="#666666", wraplength=200).pack(anchor="w", pady=(3, 6))
        ttk.Separator(parent).pack(fill=tk.X, pady=(0, 7))

        ttk.Label(parent, text="Capas", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.layers = tk.Listbox(parent, exportselection=False, activestyle="dotbox")
        self.layers.pack(fill=tk.BOTH, expand=True, pady=(6, 5))
        self.layers.bind("<<ListboxSelect>>", self._on_layer_select)
        self.layers.bind("<Double-Button-1>", lambda _e: self.rename_selected())

        layer_buttons = ttk.Frame(parent)
        layer_buttons.pack(fill=tk.X)
        ttk.Button(layer_buttons, text="Arriba", command=lambda: self.change_layer(1)).grid(row=0, column=0, sticky="ew", padx=1, pady=1)
        ttk.Button(layer_buttons, text="Abajo", command=lambda: self.change_layer(-1)).grid(row=0, column=1, sticky="ew", padx=1, pady=1)
        ttk.Button(layer_buttons, text="Duplicar", command=self.duplicate_selected).grid(row=1, column=0, sticky="ew", padx=1, pady=1)
        ttk.Button(layer_buttons, text="Eliminar", command=self.delete_selected).grid(row=1, column=1, sticky="ew", padx=1, pady=1)
        layer_buttons.columnconfigure((0, 1), weight=1)

        ttk.Separator(parent).pack(fill=tk.X, pady=8)
        ttk.Label(parent, text="Lienzo", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        canvas_form = ttk.Frame(parent)
        canvas_form.pack(fill=tk.X, pady=(4, 0))
        self.canvas_vars = {
            "width": tk.IntVar(value=self.DEFAULT_CANVAS_WIDTH),
            "height": tk.IntVar(value=self.DEFAULT_CANVAS_HEIGHT),
            "background": tk.StringVar(value="#17171C"),
            "scale_mode": tk.StringVar(value="contain"),
            "name": tk.StringVar(value="custom_layout"),
        }
        for row, (key, label) in enumerate((("name", "Nombre"), ("width", "Ancho"), ("height", "Alto"))):
            ttk.Label(canvas_form, text=label).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Entry(canvas_form, textvariable=self.canvas_vars[key], width=14).grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Label(canvas_form, text="Escalado").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Combobox(
            canvas_form, textvariable=self.canvas_vars["scale_mode"],
            values=("contain", "cover", "stretch"), state="readonly", width=11
        ).grid(row=3, column=1, sticky="ew", pady=2)
        ttk.Button(canvas_form, text="Color de fondo", command=self.choose_canvas_color).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(5, 2))
        ttk.Button(canvas_form, text="Aplicar lienzo", command=self.apply_canvas_properties).grid(row=5, column=0, columnspan=2, sticky="ew", pady=2)
        canvas_form.columnconfigure(1, weight=1)

    def _build_canvas(self, parent: ttk.Frame) -> None:
        wrap = ttk.Frame(parent)
        wrap.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(wrap, bg="#0C0C0F", highlightthickness=1, highlightbackground="#454552")
        x_scroll = ttk.Scrollbar(wrap, orient=tk.HORIZONTAL, command=self.canvas.xview)
        y_scroll = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        self.canvas.bind("<Button-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Motion>", self._on_canvas_motion)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_zoom_wheel)

    def _build_properties_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Propiedades", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        general = self._add_scrollable_tab(notebook, "General")
        appearance = self._add_scrollable_tab(notebook, "Apariencia")
        behavior = self._add_scrollable_tab(notebook, "Acción")

        self.vars: Dict[str, tk.Variable] = {
            "x": tk.DoubleVar(value=0),
            "y": tk.DoubleVar(value=0),
            "width": tk.DoubleVar(value=100),
            "height": tk.DoubleVar(value=60),
            "opacity": tk.DoubleVar(value=1.0),
            "rotation": tk.DoubleVar(value=0),
            "page": tk.StringVar(value="main"),
            "text": tk.StringVar(value=""),
            "font_family": tk.StringVar(value="Segoe UI"),
            "font_size": tk.IntVar(value=18),
            "font_weight": tk.StringVar(value="normal"),
            "text_align": tk.StringVar(value="left"),
            "text_color": tk.StringVar(value="#FFFFFF"),
            "fill": tk.StringVar(value="#7C6FF0"),
            "outline": tk.StringVar(value=""),
            "outline_width": tk.IntVar(value=0),
            "radius": tk.IntVar(value=16),
            "source": tk.StringVar(value=""),
            "hover_source": tk.StringVar(value=""),
            "pressed_source": tk.StringVar(value=""),
            "action": tk.StringVar(value="none"),
            "action_args": tk.StringVar(value="{}"),
            "page_target": tk.StringVar(value="main"),
            "tooltip": tk.StringVar(value=""),
            "visible_when": tk.StringVar(value="always"),
            "hover_fill": tk.StringVar(value=""),
            "pressed_fill": tk.StringVar(value=""),
            "fit": tk.StringVar(value="stretch"),
            "tail_position": tk.StringVar(value="left"),
            "tail_width": tk.IntVar(value=30),
            "tail_height": tk.IntVar(value=18),
            "padding": tk.IntVar(value=14),
            "progress_variable": tk.StringVar(value="battery"),
            "progress_minimum": tk.DoubleVar(value=0),
            "progress_maximum": tk.DoubleVar(value=100),
            "progress_track": tk.StringVar(value="#242733"),
            "progress_direction": tk.StringVar(value="horizontal"),
            "locked": tk.BooleanVar(value=False),
            "visible": tk.BooleanVar(value=True),
        }

        row = 0
        for key, label in (("x", "X"), ("y", "Y"), ("width", "Ancho"), ("height", "Alto"), ("rotation", "Rotación")):
            self._labeled_entry(general, row, label, self.vars[key]); row += 1
        ttk.Label(general, text="Pantalla").grid(row=row, column=0, sticky="w", pady=3)
        self.element_page_combo = ttk.Combobox(general, textvariable=self.vars["page"], state="readonly")
        self.element_page_combo.grid(row=row, column=1, sticky="ew", pady=3)
        row += 1
        ttk.Label(general, text="Usa * para mostrar el elemento en todas las pantallas.", wraplength=240, foreground="#666666").grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 4))
        row += 1
        ttk.Label(general, text="Opacidad").grid(row=row, column=0, sticky="w", pady=3)
        ttk.Scale(general, from_=0.0, to=1.0, variable=self.vars["opacity"], orient=tk.HORIZONTAL).grid(row=row, column=1, sticky="ew", pady=3)
        row += 1
        ttk.Checkbutton(general, text="Visible", variable=self.vars["visible"]).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Checkbutton(general, text="Bloqueado", variable=self.vars["locked"]).grid(row=row, column=1, sticky="w", pady=3)
        row += 1
        ttk.Label(general, text="Recurso").grid(row=row, column=0, sticky="w", pady=3)
        source_row = ttk.Frame(general)
        source_row.grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Entry(source_row, textvariable=self.vars["source"]).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(source_row, text="…", width=3, command=self.replace_image).pack(side=tk.LEFT, padx=(3, 0))
        row += 1
        for key, label in (("hover_source", "Imagen hover"), ("pressed_source", "Imagen presionada")):
            ttk.Label(general, text=label).grid(row=row, column=0, sticky="w", pady=3)
            state_row = ttk.Frame(general)
            state_row.grid(row=row, column=1, sticky="ew", pady=3)
            ttk.Entry(state_row, textvariable=self.vars[key]).pack(side=tk.LEFT, fill=tk.X, expand=True)
            ttk.Button(state_row, text="…", width=3, command=lambda k=key: self.choose_state_image(k)).pack(side=tk.LEFT, padx=(3, 0))
            ttk.Button(state_row, text="×", width=3, command=lambda k=key: self.vars[k].set("")).pack(side=tk.LEFT, padx=(2, 0))
            row += 1
        ttk.Label(general, text="Ajuste imagen").grid(row=row, column=0, sticky="w", pady=3)
        ttk.Combobox(general, textvariable=self.vars["fit"], values=("stretch", "contain", "cover"), state="readonly").grid(row=row, column=1, sticky="ew", pady=3)
        row += 1
        ttk.Button(general, text="Ajustar al tamaño original", command=self.fit_selected_image).grid(row=row, column=0, columnspan=2, sticky="ew", pady=6)
        general.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(appearance, text="Texto").grid(row=row, column=0, sticky="nw", pady=3)
        self.text_box = tk.Text(appearance, height=5, wrap="word")
        self.text_box.grid(row=row, column=1, sticky="nsew", pady=3)
        row += 1
        self._labeled_entry(appearance, row, "Fuente", self.vars["font_family"]); row += 1
        self._labeled_entry(appearance, row, "Tamaño", self.vars["font_size"]); row += 1
        ttk.Label(appearance, text="Peso").grid(row=row, column=0, sticky="w", pady=3)
        ttk.Combobox(appearance, textvariable=self.vars["font_weight"], values=("normal", "semibold", "bold"), state="readonly").grid(row=row, column=1, sticky="ew", pady=3); row += 1
        ttk.Label(appearance, text="Alineación").grid(row=row, column=0, sticky="w", pady=3)
        ttk.Combobox(appearance, textvariable=self.vars["text_align"], values=("left", "center", "right"), state="readonly").grid(row=row, column=1, sticky="ew", pady=3); row += 1
        self._color_row(appearance, row, "Color texto", "text_color"); row += 1
        self._color_row(appearance, row, "Relleno", "fill"); row += 1
        self._color_row(appearance, row, "Borde", "outline"); row += 1
        self._labeled_entry(appearance, row, "Grosor borde", self.vars["outline_width"]); row += 1
        self._labeled_entry(appearance, row, "Radio", self.vars["radius"]); row += 1
        self._color_row(appearance, row, "Hover", "hover_fill"); row += 1
        self._color_row(appearance, row, "Presionado", "pressed_fill"); row += 1
        ttk.Label(appearance, text="Cola del globo").grid(row=row, column=0, sticky="w", pady=3)
        ttk.Combobox(appearance, textvariable=self.vars["tail_position"], values=("left", "center", "right"), state="readonly").grid(row=row, column=1, sticky="ew", pady=3); row += 1
        self._labeled_entry(appearance, row, "Ancho cola", self.vars["tail_width"]); row += 1
        self._labeled_entry(appearance, row, "Alto cola", self.vars["tail_height"]); row += 1
        self._labeled_entry(appearance, row, "Margen interno", self.vars["padding"]); row += 1
        ttk.Label(appearance, text="Las opciones de cola se usan en elementos Globo.", wraplength=250, foreground="#666666").grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 4)); row += 1
        ttk.Separator(appearance).grid(row=row, column=0, columnspan=2, sticky="ew", pady=5); row += 1
        self._labeled_entry(appearance, row, "Variable barra", self.vars["progress_variable"]); row += 1
        self._labeled_entry(appearance, row, "Mínimo barra", self.vars["progress_minimum"]); row += 1
        self._labeled_entry(appearance, row, "Máximo barra", self.vars["progress_maximum"]); row += 1
        self._color_row(appearance, row, "Pista barra", "progress_track"); row += 1
        ttk.Label(appearance, text="Dirección barra").grid(row=row, column=0, sticky="w", pady=3)
        ttk.Combobox(appearance, textvariable=self.vars["progress_direction"], values=("horizontal", "vertical"), state="readonly").grid(row=row, column=1, sticky="ew", pady=3); row += 1
        ttk.Label(appearance, text="Variables útiles: battery, l2, r2. El relleno usa el color Relleno.", wraplength=250, foreground="#666666").grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 4)); row += 1
        ttk.Label(appearance, text="Variables: {battery}, {connection}, {active_profile}, {status}, {time}", wraplength=250, foreground="#666666").grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 2))
        appearance.columnconfigure(1, weight=1)
        appearance.rowconfigure(0, weight=1)

        row = 0
        ttk.Label(behavior, text="Acción").grid(row=row, column=0, sticky="w", pady=3)
        self.action_combo = ttk.Combobox(behavior, textvariable=self.vars["action"], values=DEFAULT_ACTIONS, state="readonly")
        self.action_combo.grid(row=row, column=1, sticky="ew", pady=3); row += 1
        ttk.Label(behavior, text="Pantalla destino").grid(row=row, column=0, sticky="w", pady=3)
        self.action_page_combo = ttk.Combobox(behavior, textvariable=self.vars["page_target"], state="readonly")
        self.action_page_combo.grid(row=row, column=1, sticky="ew", pady=3); row += 1
        ttk.Label(behavior, text="Se usa cuando la acción es page.open.", wraplength=250, foreground="#666666").grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 4)); row += 1
        ttk.Label(behavior, text="Argumentos JSON").grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(behavior, textvariable=self.vars["action_args"]).grid(row=row, column=1, sticky="ew", pady=3); row += 1
        ttk.Label(behavior, text="Ejemplo para profile.apply: {\"profile_id\": \"sniper\"}", wraplength=250, foreground="#666666").grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 6)); row += 1
        self._labeled_entry(behavior, row, "Tooltip", self.vars["tooltip"]); row += 1
        ttk.Label(behavior, text="Visible cuando").grid(row=row, column=0, sticky="w", pady=3)
        ttk.Combobox(
            behavior,
            textvariable=self.vars["visible_when"],
            values=("always", "controller.connected", "controller.disconnected", "battery.charging", "battery.low", "connection:usb", "connection:bluetooth", "not:controller.connected"),
        ).grid(row=row, column=1, sticky="ew", pady=3); row += 1
        ttk.Label(behavior, text="También admite profile:ID y not:condición.", wraplength=250, foreground="#666666").grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 6)); row += 1
        self.action_help_var = tk.StringVar(value=ACTION_DEFINITIONS["none"]["label"])
        ttk.Label(behavior, textvariable=self.action_help_var, wraplength=260).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        behavior.columnconfigure(1, weight=1)
        self.action_combo.bind("<<ComboboxSelected>>", self._update_action_help)

        footer = ttk.Frame(parent)
        footer.pack(fill=tk.X, pady=(7, 0))
        self.property_status_var = tk.StringVar(value="Los cambios se previsualizan automáticamente.")
        ttk.Label(
            footer, textvariable=self.property_status_var, wraplength=300, foreground="#666666"
        ).pack(fill=tk.X, pady=(0, 4))
        ttk.Button(footer, text="Aplicar cambios ahora", command=self.apply_properties).pack(fill=tk.X)

    def _bind_live_property_updates(self) -> None:
        """Actualiza la vista previa al editar, sin depender de un botón escondido."""
        for variable in self.vars.values():
            token = variable.trace_add("write", self._on_property_variable_changed)
            self._property_trace_tokens.append((variable, token))
        self.text_box.bind("<<Modified>>", self._on_property_text_modified, add="+")
        self.text_box.edit_modified(False)

    def _on_property_variable_changed(self, *_args) -> None:
        if self._loading_properties or not self.selected_id:
            return
        self._schedule_live_property_apply()

    def _on_property_text_modified(self, _event=None) -> None:
        if not self.text_box.edit_modified():
            return
        self.text_box.edit_modified(False)
        if self._loading_properties or not self.selected_id:
            return
        self._schedule_live_property_apply()

    def _schedule_live_property_apply(self) -> None:
        if self._property_preview_job:
            try:
                self.after_cancel(self._property_preview_job)
            except tk.TclError:
                pass
        self._property_preview_job = self.after(140, self._apply_properties_live)

    def _apply_properties_live(self) -> None:
        self._property_preview_job = None
        if not self._apply_properties_internal(show_errors=False, commit=False):
            return
        if self._property_commit_job:
            try:
                self.after_cancel(self._property_commit_job)
            except tk.TclError:
                pass
        self._property_commit_job = self.after(650, self._commit_live_properties)

    def _commit_live_properties(self) -> None:
        self._property_commit_job = None
        if self.selected_id:
            self._commit("Propiedades actualizadas")
            self.property_status_var.set("Cambios aplicados.")

    def _cancel_property_jobs(self) -> None:
        for attr in ("_property_preview_job", "_property_commit_job"):
            job = getattr(self, attr, None)
            if job:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
                setattr(self, attr, None)

    def _add_scrollable_tab(self, notebook: ttk.Notebook, title: str) -> ttk.Frame:
        """Crea una pestaña desplazable para que las propiedades no queden cortadas."""
        outer = ttk.Frame(notebook)
        notebook.add(outer, text=title)
        canvas = tk.Canvas(outer, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        inner = ttk.Frame(canvas, padding=8)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def update_region(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_width(event: tk.Event) -> None:
            canvas.itemconfigure(window, width=max(1, event.width))

        def wheel(event: tk.Event) -> str:
            canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return "break"

        inner.bind("<Configure>", update_region)
        canvas.bind("<Configure>", fit_width)
        canvas.bind("<MouseWheel>", wheel)
        inner.bind("<MouseWheel>", wheel)
        return inner

    @staticmethod
    def _labeled_entry(parent: ttk.Frame, row: int, label: str, variable: tk.Variable) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=3)

    def _color_row(self, parent: ttk.Frame, row: int, label: str, key: str) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Entry(frame, textvariable=self.vars[key]).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(frame, text="…", width=3, command=lambda k=key: self.choose_element_color(k)).pack(side=tk.LEFT, padx=(3, 0))

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-n>", lambda _e: self.new_layout())
        self.bind("<Control-o>", lambda _e: self.open_layout())
        self.bind("<Control-s>", lambda _e: self.save_layout())
        self.bind("<Control-Shift-S>", lambda _e: self.save_layout(save_as=True))
        self.bind("<Control-e>", lambda _e: self.export_layout())
        self.bind("<Control-z>", lambda _e: self.undo())
        self.bind("<Control-y>", lambda _e: self.redo())
        self.bind("<Control-c>", lambda _e: self.copy_selected())
        self.bind("<Control-v>", lambda _e: self.paste_element())
        self.bind("<Control-d>", lambda _e: self.duplicate_selected())
        self.bind("<Delete>", lambda _e: self.delete_selected())
        self.bind("<Up>", lambda e: self.nudge_selected(0, -10 if e.state & 0x1 else -1))
        self.bind("<Down>", lambda e: self.nudge_selected(0, 10 if e.state & 0x1 else 1))
        self.bind("<Left>", lambda e: self.nudge_selected(-10 if e.state & 0x1 else -1, 0))
        self.bind("<Right>", lambda e: self.nudge_selected(10 if e.state & 0x1 else 1, 0))
        self.bind("<Escape>", lambda _e: self.clear_selection())

    # ------------------------------------------------------------------
    # Modelo, historial y estado
    # ------------------------------------------------------------------

    def _new_id(self) -> str:
        return uuid.uuid4().hex[:10]

    def _sync_layout(self) -> UILayout:
        self.layout.elements = sorted(self.elements.values(), key=lambda e: e.z_index)
        self.layout.name = str(self.canvas_vars["name"].get()).strip() or "custom_layout"
        self.layout.canvas = {
            "width": int(self.canvas_vars["width"].get()),
            "height": int(self.canvas_vars["height"].get()),
            "background": str(self.canvas_vars["background"].get()),
            "scale_mode": str(self.canvas_vars["scale_mode"].get()),
        }
        self.layout.base_dir = self.current_file.parent if self.current_file else self.layouts_dir
        self.layout.source_path = self.current_file
        return self.layout

    def _snapshot(self) -> Dict[str, Any]:
        try:
            layout = self._sync_layout().to_dict()
        except (ValueError, tk.TclError):
            layout = self.layout.to_dict()
        return {"layout": layout, "selected_id": self.selected_id, "current_page": self.current_page}

    def _restore_snapshot(self, snapshot: Dict[str, Any]) -> None:
        self._cancel_gifs()
        self.layout = UILayout.from_dict(snapshot["layout"], base_dir=self.current_file.parent if self.current_file else self.layouts_dir)
        self.elements = {element.id: element for element in self.layout.elements}
        page_ids = self._page_ids()
        self.current_page = snapshot.get("current_page") if snapshot.get("current_page") in page_ids else self.layout.default_page
        self._load_canvas_vars()
        self.selected_id = snapshot.get("selected_id") if snapshot.get("selected_id") in self.elements else None
        self._render_all()
        self._refresh_layers()

    def _reset_history(self) -> None:
        self._history = [self._snapshot()]
        self._history_index = 0

    def _push_history(self) -> None:
        snapshot = self._snapshot()
        if self._history and self._history[self._history_index]["layout"] == snapshot["layout"]:
            return
        self._history = self._history[: self._history_index + 1]
        self._history.append(snapshot)
        if len(self._history) > self.MAX_HISTORY:
            self._history.pop(0)
        self._history_index = len(self._history) - 1

    def undo(self) -> None:
        if self._history_index <= 0:
            return
        self._history_index -= 1
        self._restore_snapshot(self._history[self._history_index])
        self._mark_dirty("Deshacer")

    def redo(self) -> None:
        if self._history_index >= len(self._history) - 1:
            return
        self._history_index += 1
        self._restore_snapshot(self._history[self._history_index])
        self._mark_dirty("Rehacer")

    def _commit(self, message: str) -> None:
        self._push_history()
        self._mark_dirty(message)

    def _mark_dirty(self, message: Optional[str] = None) -> None:
        self._dirty = True
        self._update_title()
        if message:
            self.status_var.set(message)

    def _mark_clean(self) -> None:
        self._dirty = False
        self._update_title()

    def _update_title(self) -> None:
        name = self.current_file.name if self.current_file else self.layout.name
        star = " *" if self._dirty else ""
        self.title(f"Nikaido UI Studio - {name}{star}")

    # ------------------------------------------------------------------
    # Elementos y capas
    # ------------------------------------------------------------------

    def add_text(self) -> None:
        text = simpledialog.askstring("Añadir texto", "Escribe el texto:", parent=self, initialvalue="Texto nuevo")
        if text is None:
            return
        self._add_element(UIElement(
            id=self._new_id(), type="text", x=80, y=80, width=280, height=60,
            text=text, fill="", page=self.current_page, z_index=len(self.elements)
        ))

    def add_speech_bubble(self) -> None:
        text = simpledialog.askstring(
            "Añadir globo", "Texto del globo:", parent=self, initialvalue="Mensaje"
        )
        if text is None:
            return
        self._add_element(UIElement(
            id=self._new_id(), type="speech_bubble", x=100, y=100, width=300, height=130,
            text=text, font_size=16, font_weight="semibold", text_align="center",
            text_color="#17171C", fill="#F4F5F8", outline="#D8DBE5", outline_width=1,
            hover_fill="#FFFFFF", pressed_fill="#E6E8EF", radius=22,
            page=self.current_page, z_index=len(self.elements),
            metadata={"tail_position": "left", "tail_width": 30, "tail_height": 18, "padding": 14},
        ))

    def add_button(self) -> None:
        text = simpledialog.askstring("Añadir botón", "Texto del botón:", parent=self, initialvalue="Botón")
        if text is None:
            return
        self._add_element(UIElement(
            id=self._new_id(), type="button", x=100, y=100, width=220, height=58,
            text=text, font_size=16, font_weight="semibold", text_align="center",
            fill="#7C6FF0", hover_fill="#8F84F5", pressed_fill="#6254D8",
            radius=14, page=self.current_page, z_index=len(self.elements)
        ))

    def add_progress(self) -> None:
        self._add_element(UIElement(
            id=self._new_id(), type="progress", x=100, y=100, width=280, height=28,
            text="{battery_percent}", font_size=12, font_weight="bold", text_align="center",
            text_color="#FFFFFF", fill="#2B9A78", outline="#303442", outline_width=1,
            radius=14, page=self.current_page, z_index=len(self.elements),
            metadata={
                "value_variable": "battery", "minimum": 0, "maximum": 100,
                "track_fill": "#242733", "direction": "horizontal",
                "name": "Barra dinámica",
            },
        ))

    def add_rectangle(self) -> None:
        self._add_element(UIElement(
            id=self._new_id(), type="rectangle", x=100, y=100, width=220, height=90,
            fill="#7C6FF0", hover_fill="#8F84F5", pressed_fill="#6254D8",
            page=self.current_page, z_index=len(self.elements)
        ))

    def add_ellipse(self) -> None:
        self._add_element(UIElement(
            id=self._new_id(), type="ellipse", x=100, y=100, width=130, height=130,
            fill="#7C6FF0", hover_fill="#8F84F5", pressed_fill="#6254D8",
            page=self.current_page, z_index=len(self.elements)
        ))

    def add_hotspot(self) -> None:
        self._add_element(UIElement(
            id=self._new_id(), type="hotspot", x=100, y=100, width=180, height=70,
            fill="", outline="#E8A33D", outline_width=1, opacity=0.25,
            action="none", page=self.current_page, z_index=len(self.elements),
            tooltip="Zona invisible: asigna una acción"
        ))

    def add_image(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Selecciona una imagen o GIF",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.webp *.gif *.bmp"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            source = self._import_asset(Path(path))
            w, h = self._validated_image_dimensions(source)
        except Exception as exc:
            messagebox.showerror("Imagen inválida", str(exc), parent=self)
            return
        scale = min(1.0, 380 / max(w, 1), 260 / max(h, 1))
        self._add_element(UIElement(
            id=self._new_id(), type="image", x=80, y=80,
            width=max(20, round(w * scale)), height=max(20, round(h * scale)),
            source=str(source), page=self.current_page, z_index=len(self.elements), metadata={"fit": "stretch"}
        ))

    @classmethod
    def _validated_image_dimensions(cls, source: Path) -> Tuple[int, int]:
        source = source.expanduser().resolve()
        if not source.is_file() or source.suffix.lower() not in cls.SAFE_IMAGE_EXTENSIONS:
            raise ValueError("Selecciona una imagen PNG, JPG, WEBP, GIF o BMP válida.")
        if source.stat().st_size > cls.MAX_IMAGE_BYTES:
            raise ValueError("La imagen supera el límite de 25 MB.")
        with Image.open(source) as image:
            width, height = image.size
            frames = max(1, int(getattr(image, "n_frames", 1) or 1))
            pixels = int(width) * int(height)
            if width <= 0 or height <= 0 or pixels > cls.MAX_SOURCE_IMAGE_PIXELS:
                raise ValueError("La imagen tiene dimensiones demasiado grandes.")
            if frames > cls.MAX_ANIMATION_FRAMES or pixels * frames > cls.MAX_CACHED_ANIMATION_PIXELS:
                raise ValueError("La animación es demasiado pesada para el editor.")
            image.verify()
        return int(width), int(height)

    def _import_asset(self, source: Path) -> Path:
        source = source.expanduser().resolve()
        self._validated_image_dimensions(source)
        digest = hashlib.sha256(str(source).encode("utf-8", errors="surrogatepass")).hexdigest()[:10]
        safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in source.stem).strip("._") or "asset"
        target = self.assets_dir / f"{safe_name}_{digest}{source.suffix.lower()}"
        if source != target:
            temp = target.with_suffix(target.suffix + ".tmp")
            try:
                shutil.copy2(source, temp)
                os.replace(temp, target)
            finally:
                temp.unlink(missing_ok=True)
        return target

    def _add_element(self, element: UIElement) -> None:
        self.elements[element.id] = element
        self.select_element(element.id)
        self._render_all()
        self._refresh_layers()
        self._commit(f"Añadido: {element.type}")

    def delete_selected(self) -> None:
        if not self.selected_id or self.selected_id not in self.elements:
            return
        element = self.elements.pop(self.selected_id)
        self._cancel_gif(element.id)
        self.selected_id = None
        self._render_all()
        self._refresh_layers()
        self._commit(f"Eliminado: {element.type}")

    def copy_selected(self) -> None:
        if self.selected_id and self.selected_id in self.elements:
            self.clipboard_element = copy.deepcopy(asdict(self.elements[self.selected_id]))
            self.status_var.set("Elemento copiado")

    def paste_element(self) -> None:
        if not self.clipboard_element:
            return
        data = copy.deepcopy(self.clipboard_element)
        data["id"] = self._new_id()
        data["x"] = float(data.get("x", 0)) + 20
        data["y"] = float(data.get("y", 0)) + 20
        data["z_index"] = len(self.elements)
        self._add_element(UIElement.from_dict(data))

    def duplicate_selected(self) -> None:
        self.copy_selected()
        self.paste_element()

    def rename_selected(self) -> None:
        if not self.selected_id:
            return
        element = self.elements[self.selected_id]
        current = str(element.metadata.get("name") or "")
        name = simpledialog.askstring("Nombre de capa", "Nombre:", initialvalue=current, parent=self)
        if name is None:
            return
        element.metadata["name"] = name.strip()
        self._refresh_layers()
        self._commit("Capa renombrada")

    def change_layer(self, direction: int) -> None:
        if not self.selected_id:
            return
        ordered = self._ordered_ids()
        index = ordered.index(self.selected_id)
        new_index = max(0, min(len(ordered) - 1, index + direction))
        if index == new_index:
            return
        ordered[index], ordered[new_index] = ordered[new_index], ordered[index]
        for z, element_id in enumerate(ordered):
            self.elements[element_id].z_index = z
        self._render_all()
        self._refresh_layers()
        self._commit("Orden de capas actualizado")

    def nudge_selected(self, dx: int, dy: int) -> None:
        if not self.selected_id:
            return
        element = self.elements[self.selected_id]
        if element.locked:
            return
        element.x = self._clamp_x(element, element.x + dx)
        element.y = self._clamp_y(element, element.y + dy)
        self._render_all()
        self._load_properties(element)
        self._commit(f"Movido a {element.x:.0f}, {element.y:.0f}")

    def _ordered_ids(self) -> List[str]:
        return [element.id for element in sorted(self.elements.values(), key=lambda item: item.z_index)]

    def _page_ids(self) -> List[str]:
        return [str(page.get("id", "")) for page in self.layout.pages if str(page.get("id", ""))]

    def _refresh_page_controls(self) -> None:
        page_ids = self._page_ids()
        if not page_ids:
            self.layout.pages = [{"id": "main", "name": "Inicio"}]
            self.layout.default_page = "main"
            page_ids = ["main"]
        if self.layout.default_page not in page_ids:
            self.layout.default_page = page_ids[0]
        if self.current_page not in page_ids:
            self.current_page = self.layout.default_page
        self.page_combo.configure(values=page_ids)
        self.page_var.set(self.current_page)
        self.element_page_combo.configure(values=page_ids + ["*"])
        self.action_page_combo.configure(values=page_ids)
        if self.vars["page"].get() not in page_ids + ["*"]:
            self.vars["page"].set(self.current_page)
        if self.vars["page_target"].get() not in page_ids:
            self.vars["page_target"].set(self.layout.default_page)
        page = next((page for page in self.layout.pages if page.get("id") == self.current_page), {})
        suffix = " · inicial" if self.current_page == self.layout.default_page else ""
        self.page_info_var.set(f"{page.get('name', self.current_page)}{suffix}")

    def _on_page_select(self, _event: Optional[tk.Event] = None) -> None:
        selected = str(self.page_var.get())
        if selected not in self._page_ids():
            return
        self.current_page = selected
        if self.selected_id and self.elements[self.selected_id].page not in {selected, "*"}:
            self.selected_id = None
        self._refresh_page_controls()
        self._render_all()
        self._refresh_layers()
        self.status_var.set(f"Pantalla activa: {selected}")

    def add_page(self) -> None:
        page_id = simpledialog.askstring(
            "Nueva pantalla", "ID corto (ejemplo: perfiles):", parent=self
        )
        if page_id is None:
            return
        page_id = page_id.strip().lower().replace(" ", "_")
        if not re.match(r"^[a-z0-9_.-]+$", page_id):
            messagebox.showerror("ID inválido", "Usa letras, números, punto, guion o guion bajo.", parent=self)
            return
        if page_id in self._page_ids():
            messagebox.showerror("ID duplicado", "Ya existe una pantalla con ese ID.", parent=self)
            return
        name = simpledialog.askstring("Nueva pantalla", "Nombre visible:", initialvalue=page_id.title(), parent=self)
        if name is None:
            return
        self.layout.pages.append({"id": page_id, "name": name.strip() or page_id})
        self.current_page = page_id
        self._refresh_page_controls()
        self._render_all()
        self._refresh_layers()
        self._commit(f"Pantalla añadida: {page_id}")

    def rename_page(self) -> None:
        page = next((page for page in self.layout.pages if page.get("id") == self.current_page), None)
        if not page:
            return
        name = simpledialog.askstring(
            "Renombrar pantalla", "Nombre visible:", initialvalue=str(page.get("name", self.current_page)), parent=self
        )
        if name is None:
            return
        page["name"] = name.strip() or self.current_page
        self._refresh_page_controls()
        self._commit("Pantalla renombrada")

    def delete_page(self) -> None:
        page_ids = self._page_ids()
        if len(page_ids) <= 1:
            messagebox.showwarning("Pantallas", "El diseño necesita al menos una pantalla.", parent=self)
            return
        page_id = self.current_page
        if not messagebox.askyesno(
            "Eliminar pantalla",
            f"¿Eliminar '{page_id}'? Sus elementos se moverán a otra pantalla.",
            parent=self,
        ):
            return
        remaining = [item for item in page_ids if item != page_id]
        destination = self.layout.default_page if self.layout.default_page != page_id else remaining[0]
        self.layout.pages = [page for page in self.layout.pages if page.get("id") != page_id]
        if self.layout.default_page == page_id:
            self.layout.default_page = destination
        for element in self.elements.values():
            if element.page == page_id:
                element.page = destination
            if element.action == "page.open" and str(element.action_args.get("page", "")) == page_id:
                element.action_args["page"] = destination
        self.current_page = destination
        self.selected_id = None
        self._refresh_page_controls()
        self._render_all()
        self._refresh_layers()
        self._commit(f"Pantalla eliminada: {page_id}")

    def set_default_page(self) -> None:
        if self.current_page not in self._page_ids():
            return
        self.layout.default_page = self.current_page
        self._refresh_page_controls()
        self._commit(f"Pantalla inicial: {self.current_page}")

    def _refresh_layers(self) -> None:
        current = self.selected_id
        self.layers.delete(0, tk.END)
        ordered_top_first = [
            element_id for element_id in reversed(self._ordered_ids())
            if self.elements[element_id].page in {self.current_page, "*"}
        ]
        for element_id in ordered_top_first:
            element = self.elements[element_id]
            custom_name = str(element.metadata.get("name") or "").strip()
            if custom_name:
                label = custom_name
            elif element.type in {"text", "speech_bubble", "button", "progress"}:
                label = element.text.replace("\n", " ")[:24] or ({"button": "Botón", "speech_bubble": "Globo", "progress": "Barra"}.get(element.type, "Texto"))
            elif element.type == "image":
                label = Path(element.source).name[:24]
            else:
                label = element.type
            flags = ("🔒 " if element.locked else "") + ("" if element.visible else "◌ ")
            self.layers.insert(tk.END, f"{flags}{element.type}: {label}")
        if current in ordered_top_first:
            index = ordered_top_first.index(current)
            self.layers.selection_set(index)
            self.layers.see(index)

    def _on_layer_select(self, _event: tk.Event) -> None:
        selection = self.layers.curselection()
        if not selection:
            return
        ordered_top_first = [
            element_id for element_id in reversed(self._ordered_ids())
            if self.elements[element_id].page in {self.current_page, "*"}
        ]
        if selection[0] < len(ordered_top_first):
            self.select_element(ordered_top_first[selection[0]])

    # ------------------------------------------------------------------
    # Render del editor
    # ------------------------------------------------------------------

    def set_zoom(self, zoom: float) -> None:
        self._zoom = max(0.25, min(3.0, zoom))
        self.zoom_var.set(f"{round(self._zoom * 100)}%")
        self._render_all()

    def _render_all(self) -> None:
        self._cancel_gifs()
        self.canvas.delete("all")
        self._canvas_items.clear()
        self._photo_refs.clear()
        self._gif_frames.clear()

        width = int(self.canvas_vars["width"].get())
        height = int(self.canvas_vars["height"].get())
        display_w = max(1, int(width * self._zoom))
        display_h = max(1, int(height * self._zoom))
        margin = 40
        self.canvas.configure(scrollregion=(0, 0, display_w + margin * 2, display_h + margin * 2))
        self._canvas_offset = (margin, margin)

        self.canvas.create_rectangle(
            margin, margin, margin + display_w, margin + display_h,
            fill=self.canvas_vars["background"].get(), outline="#5A5A66", width=1, tags="canvas-bg"
        )
        if self._grid_enabled.get():
            step = max(2, int(self.GRID_SIZE * self._zoom))
            for x in range(margin, margin + display_w + 1, step):
                self.canvas.create_line(x, margin, x, margin + display_h, fill="#2A2A31", tags="grid")
            for y in range(margin, margin + display_h + 1, step):
                self.canvas.create_line(margin, y, margin + display_w, y, fill="#2A2A31", tags="grid")

        for element in sorted(self.elements.values(), key=lambda item: item.z_index):
            if element.page in {self.current_page, "*"}:
                self._render_element(element)
        self._draw_selection()

    def _render_element(self, element: UIElement) -> None:
        if not element.visible:
            return
        ox, oy = self._canvas_offset
        x = ox + element.x * self._zoom
        y = oy + element.y * self._zoom
        w = max(1, element.width * self._zoom)
        h = max(1, element.height * self._zoom)
        tags = ("element", f"element:{element.id}")

        if element.type in {"rectangle", "hotspot"}:
            fill = element.fill if element.type != "hotspot" else "#E8A33D"
            outline = element.outline or ("#E8A33D" if element.type == "hotspot" else element.fill)
            item = self.canvas.create_rectangle(
                x, y, x + w, y + h, fill=fill, outline=outline,
                width=max(1, int(element.outline_width * self._zoom)),
                stipple="gray25" if element.type == "hotspot" else "", tags=tags
            )
        elif element.type == "ellipse":
            item = self.canvas.create_oval(x, y, x + w, y + h, fill=element.fill, outline=element.outline or element.fill, width=max(1, int(element.outline_width * self._zoom)), tags=tags)
        elif element.type == "speech_bubble":
            item = self._render_speech_bubble_preview(element, int(w), int(h), x, y, tags)
        elif element.type == "button":
            item = self._render_button_preview(element, int(w), int(h), x, y, tags)
        elif element.type == "progress":
            item = self._render_progress_preview(element, int(w), int(h), x, y, tags)
        elif element.type == "text":
            preview_context = {
                "battery": 87, "battery_percent": "87%", "connection": "Conectado",
                "connection_type": "USB", "active_profile": "Rifle de asalto", "status": "Listo",
                "l2": 0, "r2": 0, "time": "22:41", "date": "09/07/2026",
            }
            item = self.canvas.create_text(
                x, y, anchor="nw", width=w, text=substitute_variables(element.text, preview_context),
                fill=element.text_color, font=(element.font_family, max(6, int(element.font_size * self._zoom)), "bold" if element.font_weight in {"bold", "semibold"} else "normal"),
                justify=element.text_align, angle=-element.rotation, tags=tags
            )
        elif element.type == "image":
            item = self._render_image(element, int(w), int(h), x, y, tags)
        else:
            return

        self._canvas_items[element.id] = item
        self.canvas.tag_bind(item, "<Button-1>", self._on_item_press)
        self.canvas.tag_bind(item, "<B1-Motion>", self._on_canvas_drag)
        self.canvas.tag_bind(item, "<ButtonRelease-1>", self._on_canvas_release)

    def _render_progress_preview(
        self, element: UIElement, width: int, height: int, x: float, y: float, tags: Tuple[str, str]
    ) -> int:
        width, height = max(1, width), max(1, height)
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        radius = min(max(0, int(element.radius * self._zoom)), width // 2, height // 2)
        track = str(element.metadata.get("track_fill", "#242733"))
        draw.rounded_rectangle(
            [0, 0, width - 1, height - 1], radius=radius, fill=track,
            outline=element.outline or None,
            width=max(1, int(element.outline_width * self._zoom)) if element.outline else 1,
        )
        preview_values = {"battery": 87, "l2": 42, "r2": 68}
        variable = str(element.metadata.get("value_variable", "battery"))
        try:
            value = float(preview_values.get(variable, 65))
            minimum = float(element.metadata.get("minimum", 0))
            maximum = float(element.metadata.get("maximum", 100))
        except (TypeError, ValueError, OverflowError):
            value, minimum, maximum = 0.0, 0.0, 100.0
        ratio = max(0.0, min(1.0, (value - minimum) / max(1e-9, maximum - minimum)))
        if str(element.metadata.get("direction", "horizontal")) == "vertical":
            filled = int(height * ratio)
            fill_box = [0, height - filled, width - 1, height - 1]
        else:
            filled = int(width * ratio)
            fill_box = [0, 0, max(0, filled - 1), height - 1]
        if ratio > 0:
            draw.rounded_rectangle(
                fill_box, radius=min(radius, max(1, (fill_box[2] - fill_box[0] + 1) // 2), max(1, (fill_box[3] - fill_box[1] + 1) // 2)),
                fill=element.fill or "#7C6FF0",
            )
        preview_context = {
            "battery": 87, "battery_percent": "87%", "l2": 42, "r2": 68,
            "connection": "Conectado", "active_profile": "Rifle de asalto",
        }
        label = substitute_variables(element.text, preview_context)
        if label:
            font_size = max(6, int(element.font_size * self._zoom))
            font = self._preview_font(element.font_family, font_size, element.font_weight)
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((width - tw) / 2, (height - th) / 2 - bbox[1]), label, font=font, fill=element.text_color)
        if element.opacity < 1:
            alpha = image.getchannel("A").point(lambda alpha_value: int(alpha_value * element.opacity))
            image.putalpha(alpha)
        if element.rotation:
            image = image.rotate(-element.rotation, expand=True, resample=Image.Resampling.BICUBIC)
        photo = ImageTk.PhotoImage(image)
        self._photo_refs[element.id] = photo
        return self.canvas.create_image(x, y, anchor="nw", image=photo, tags=tags)

    def _render_speech_bubble_preview(
        self, element: UIElement, width: int, height: int, x: float, y: float, tags: Tuple[str, str]
    ) -> int:
        width, height = max(1, width), max(1, height)
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        tail_h = max(8, min(height // 3, int(element.metadata.get("tail_height", 18) * self._zoom)))
        body_h = max(1, height - tail_h)
        radius = min(max(0, int(element.radius * self._zoom)), width // 2, body_h // 2)
        outline_width = max(1, int(element.outline_width * self._zoom)) if element.outline else 1
        draw.rounded_rectangle(
            [0, 0, width - 1, body_h - 1], radius=radius, fill=element.fill or None,
            outline=element.outline or None, width=outline_width,
        )
        tail_w = max(12, min(width // 2, int(element.metadata.get("tail_width", 30) * self._zoom)))
        tail_pos = str(element.metadata.get("tail_position", "left"))
        center = width // 2 if tail_pos == "center" else (width - max(18, int(width * .18)) if tail_pos == "right" else max(18, int(width * .18)))
        points = [(center - tail_w // 2, body_h - 2), (center + tail_w // 2, body_h - 2), (center, height - 1)]
        draw.polygon(points, fill=element.fill or None, outline=element.outline or None)
        font_size = max(6, int(element.font_size * self._zoom))
        font = self._preview_font(element.font_family, font_size, element.font_weight)
        preview_context = {
            "battery": 87, "battery_percent": "87%", "connection": "Conectado",
            "active_profile": "Rifle de asalto", "status": "Listo", "time": "22:41"
        }
        content = substitute_variables(element.text, preview_context)
        padding = max(4, int(element.metadata.get("padding", 14) * self._zoom))
        wrapped = self._wrap_preview_text(draw, content, font, max(1, width - padding * 2))
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.multiline_text(((width - tw) / 2, (body_h - th) / 2 - bbox[1]), wrapped, font=font, fill=element.text_color, align="center")
        if element.opacity < 1:
            alpha = image.getchannel("A").point(lambda value: int(value * element.opacity))
            image.putalpha(alpha)
        if element.rotation:
            image = image.rotate(-element.rotation, expand=True, resample=Image.Resampling.BICUBIC)
        photo = ImageTk.PhotoImage(image)
        self._photo_refs[element.id] = photo
        return self.canvas.create_image(x, y, anchor="nw", image=photo, tags=tags)

    @staticmethod
    def _wrap_preview_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> str:
        lines: List[str] = []
        for paragraph in str(text).splitlines() or [""]:
            current = ""
            for word in paragraph.split(" "):
                candidate = word if not current else f"{current} {word}"
                if not current or draw.textlength(candidate, font=font) <= width:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return "\n".join(lines)

    def _render_button_preview(self, element: UIElement, width: int, height: int, x: float, y: float, tags: Tuple[str, str]) -> int:
        width, height = max(1, width), max(1, height)
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        radius = min(max(0, int(element.radius * self._zoom)), width // 2, height // 2)
        draw.rounded_rectangle(
            [0, 0, width - 1, height - 1], radius=radius, fill=element.fill or None,
            outline=element.outline or None, width=max(1, int(element.outline_width * self._zoom))
        )
        font_size = max(6, int(element.font_size * self._zoom))
        font = self._preview_font(element.font_family, font_size, element.font_weight)
        preview_context = {
            "battery": 87, "battery_percent": "87%", "connection": "Conectado",
            "active_profile": "Rifle de asalto", "status": "Listo", "time": "22:41"
        }
        text = substitute_variables(element.text, preview_context)
        bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center")
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.multiline_text(((width - tw) / 2, (height - th) / 2 - bbox[1]), text, font=font, fill=element.text_color, align="center")
        if element.opacity < 1:
            alpha = image.getchannel("A").point(lambda value: int(value * element.opacity))
            image.putalpha(alpha)
        if element.rotation:
            image = image.rotate(-element.rotation, expand=True, resample=Image.Resampling.BICUBIC)
        photo = ImageTk.PhotoImage(image)
        self._photo_refs[element.id] = photo
        return self.canvas.create_image(x, y, anchor="nw", image=photo, tags=tags)

    @staticmethod
    def _preview_font(family: str, size: int, weight: str):
        bold = str(weight).lower() in {"bold", "semibold", "600", "700"}
        candidates = []
        if os.name == "nt":
            fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
            if str(family).lower().startswith("segoe"):
                candidates.append(fonts / ("seguisb.ttf" if bold else "segoeui.ttf"))
        candidates.extend([
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            family,
        ])
        for candidate in candidates:
            try:
                return ImageFont.truetype(str(candidate), size=size)
            except (OSError, ValueError):
                continue
        return ImageFont.load_default()

    def _render_image(self, element: UIElement, width: int, height: int, x: float, y: float, tags: Tuple[str, str]) -> int:
        try:
            path = self.layout.resolve_asset(element.source) or Path(element.source)
            source_width, source_height = self._validated_image_dimensions(path)
            with Image.open(path) as source:
                frames: List[Tuple[ImageTk.PhotoImage, int]] = []
                output_pixels = max(1, int(width) * int(height))
                max_frames = min(
                    self.MAX_ANIMATION_FRAMES,
                    max(1, self.MAX_CACHED_ANIMATION_PIXELS // output_pixels),
                )
                for raw in ImageSequence.Iterator(source):
                    frame = raw.convert("RGBA")
                    fit = str(element.metadata.get("fit", "stretch"))
                    frame = self._fit_image(frame, width, height, fit)
                    if element.rotation:
                        frame = frame.rotate(-element.rotation, expand=True, resample=Image.Resampling.BICUBIC)
                    if element.opacity < 1:
                        alpha = frame.getchannel("A").point(lambda p: int(p * element.opacity))
                        frame.putalpha(alpha)
                    frames.append((ImageTk.PhotoImage(frame), max(20, int(raw.info.get("duration", source.info.get("duration", 100))))))
                    if len(frames) >= max_frames:
                        break
            if not frames:
                raise ValueError("Imagen sin cuadros")
            self._photo_refs[element.id] = frames[0][0]
            item = self.canvas.create_image(x, y, anchor="nw", image=frames[0][0], tags=tags)
            if len(frames) > 1:
                self._gif_frames[element.id] = frames
                self._animate_gif(element.id, item, 0)
            return item
        except Exception:
            return self.canvas.create_rectangle(x, y, x + width, y + height, fill="#4A2630", outline="#E5484D", width=2, tags=tags)

    @staticmethod
    def _fit_image(image: Image.Image, width: int, height: int, mode: str) -> Image.Image:
        width, height = max(1, width), max(1, height)
        if mode == "contain":
            copy_image = image.copy()
            copy_image.thumbnail((width, height), Image.Resampling.LANCZOS)
            result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            result.alpha_composite(copy_image, ((width - copy_image.width) // 2, (height - copy_image.height) // 2))
            return result
        if mode == "cover":
            scale = max(width / max(1, image.width), height / max(1, image.height))
            resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
            left = (resized.width - width) // 2
            top = (resized.height - height) // 2
            return resized.crop((left, top, left + width, top + height))
        return image.resize((width, height), Image.Resampling.LANCZOS)

    def _animate_gif(self, element_id: str, item: int, index: int) -> None:
        frames = self._gif_frames.get(element_id)
        if not frames or element_id not in self.elements:
            return
        photo, delay = frames[index % len(frames)]
        self._photo_refs[element_id] = photo
        try:
            self.canvas.itemconfigure(item, image=photo)
        except tk.TclError:
            return
        self._gif_jobs[element_id] = self.after(delay, lambda: self._animate_gif(element_id, item, index + 1))

    def _cancel_gif(self, element_id: str) -> None:
        job = self._gif_jobs.pop(element_id, None)
        if job:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._gif_frames.pop(element_id, None)

    def _cancel_gifs(self) -> None:
        for element_id in list(self._gif_jobs):
            self._cancel_gif(element_id)

    def _draw_selection(self) -> None:
        self.canvas.delete("selection")
        if not self.selected_id or self.selected_id not in self.elements:
            return
        element = self.elements[self.selected_id]
        ox, oy = self._canvas_offset
        x = ox + element.x * self._zoom
        y = oy + element.y * self._zoom
        w = element.width * self._zoom
        h = element.height * self._zoom
        self.canvas.create_rectangle(x - 3, y - 3, x + w + 3, y + h + 3, outline="#F0B65C", width=2, dash=(5, 3), tags="selection")
        size = self.HANDLE_SIZE
        self.canvas.create_rectangle(x + w - size / 2, y + h - size / 2, x + w + size / 2, y + h + size / 2, fill="#F0B65C", outline="#131316", tags=("selection", "resize-handle"))
        self.canvas.tag_raise("selection")

    # ------------------------------------------------------------------
    # Interacción con lienzo
    # ------------------------------------------------------------------

    def _event_canvas_xy(self, event: tk.Event) -> Tuple[float, float]:
        return self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def _logical_xy(self, canvas_x: float, canvas_y: float) -> Tuple[float, float]:
        ox, oy = self._canvas_offset
        return (canvas_x - ox) / self._zoom, (canvas_y - oy) / self._zoom

    def _element_from_event(self) -> Optional[str]:
        current = self.canvas.find_withtag("current")
        if not current:
            return None
        for tag in self.canvas.gettags(current[0]):
            if tag.startswith("element:"):
                return tag.split(":", 1)[1]
        return None

    def _on_item_press(self, event: tk.Event) -> None:
        element_id = self._element_from_event()
        if not element_id:
            return
        self.select_element(element_id)
        element = self.elements[element_id]
        if element.locked:
            return
        cx, cy = self._event_canvas_xy(event)
        lx, ly = self._logical_xy(cx, cy)
        self._interaction_snapshot = self._snapshot()
        self._drag_origin = (lx, ly)
        self._element_origin = (element.x, element.y)

    def _on_canvas_press(self, event: tk.Event) -> None:
        current = self.canvas.find_withtag("current")
        tags = self.canvas.gettags(current[0]) if current else ()
        if "resize-handle" in tags and self.selected_id:
            element = self.elements[self.selected_id]
            if not element.locked:
                cx, cy = self._event_canvas_xy(event)
                lx, ly = self._logical_xy(cx, cy)
                self._interaction_snapshot = self._snapshot()
                self._resize_origin = (lx, ly, element.width, element.height)
            return
        element_id = self._element_from_event()
        if element_id:
            self._on_item_press(event)
        else:
            self.clear_selection()

    def _on_canvas_drag(self, event: tk.Event) -> None:
        if not self.selected_id:
            return
        element = self.elements[self.selected_id]
        if element.locked:
            return
        cx, cy = self._event_canvas_xy(event)
        lx, ly = self._logical_xy(cx, cy)
        if self._resize_origin:
            start_x, start_y, start_w, start_h = self._resize_origin
            width = max(self.MIN_ELEMENT_SIZE, start_w + (lx - start_x))
            height = max(self.MIN_ELEMENT_SIZE, start_h + (ly - start_y))
            if self._snap_enabled.get():
                width = self._snap(width)
                height = self._snap(height)
            element.width = min(width, self._canvas_width() - element.x)
            element.height = min(height, self._canvas_height() - element.y)
        elif self._drag_origin and self._element_origin:
            dx = lx - self._drag_origin[0]
            dy = ly - self._drag_origin[1]
            x = self._element_origin[0] + dx
            y = self._element_origin[1] + dy
            if self._snap_enabled.get():
                x = self._snap(x)
                y = self._snap(y)
            element.x = self._clamp_x(element, x)
            element.y = self._clamp_y(element, y)
        else:
            return
        self._render_all()
        self._load_properties(element)

    def _on_canvas_release(self, _event: tk.Event) -> None:
        changed = self._interaction_snapshot is not None and self._interaction_snapshot["layout"] != self._snapshot()["layout"]
        self._drag_origin = None
        self._element_origin = None
        self._resize_origin = None
        self._interaction_snapshot = None
        if changed:
            self._commit("Elemento transformado")

    def _on_canvas_motion(self, event: tk.Event) -> None:
        cx, cy = self._event_canvas_xy(event)
        lx, ly = self._logical_xy(cx, cy)
        self.coords_var.set(f"X {lx:.0f}  Y {ly:.0f}  |  {round(self._zoom * 100)}%")

    def _on_mousewheel(self, event: tk.Event) -> None:
        if event.state & 0x4:
            return
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _on_zoom_wheel(self, event: tk.Event) -> str:
        factor = 1.1 if event.delta > 0 else 1 / 1.1
        self.set_zoom(self._zoom * factor)
        return "break"

    def _snap(self, value: float) -> float:
        return round(value / self.GRID_SIZE) * self.GRID_SIZE

    def _canvas_width(self) -> float:
        return float(self.canvas_vars["width"].get())

    def _canvas_height(self) -> float:
        return float(self.canvas_vars["height"].get())

    def _clamp_x(self, element: UIElement, x: float) -> float:
        return max(0, min(self._canvas_width() - element.width, x))

    def _clamp_y(self, element: UIElement, y: float) -> float:
        return max(0, min(self._canvas_height() - element.height, y))

    # ------------------------------------------------------------------
    # Selección y propiedades
    # ------------------------------------------------------------------

    def _flush_pending_property_changes(self) -> None:
        """Conserva el último cambio antes de seleccionar otra capa."""
        had_pending = bool(self._property_preview_job or self._property_commit_job)
        self._cancel_property_jobs()
        if had_pending and self.selected_id in self.elements:
            self._apply_properties_internal(show_errors=False, commit=True)

    def select_element(self, element_id: str) -> None:
        if element_id not in self.elements:
            return
        if self.selected_id and self.selected_id != element_id:
            self._flush_pending_property_changes()
        self.selected_id = element_id
        self._draw_selection()
        self._load_properties(self.elements[element_id])
        self._refresh_layers()

    def clear_selection(self) -> None:
        self._flush_pending_property_changes()
        self.selected_id = None
        self.canvas.delete("selection")
        self.layers.selection_clear(0, tk.END)

    def _load_properties(self, element: UIElement) -> None:
        self._loading_properties = True
        try:
            for key in (
                "x", "y", "width", "height", "opacity", "rotation", "page", "font_family", "font_size",
                "font_weight", "text_align", "text_color", "fill", "outline", "outline_width", "radius",
                "source", "action", "tooltip", "visible_when", "hover_fill", "pressed_fill", "locked", "visible"
            ):
                self.vars[key].set(getattr(element, key))
            self.vars["action_args"].set(json.dumps(element.action_args, ensure_ascii=False))
            self.vars["page_target"].set(str(element.action_args.get("page", self.layout.default_page)))
            self.vars["fit"].set(str(element.metadata.get("fit", "stretch")))
            self.vars["hover_source"].set(str(element.metadata.get("hover_source", "")))
            self.vars["pressed_source"].set(str(element.metadata.get("pressed_source", "")))
            self.vars["tail_position"].set(str(element.metadata.get("tail_position", "left")))
            self.vars["tail_width"].set(int(element.metadata.get("tail_width", 30)))
            self.vars["tail_height"].set(int(element.metadata.get("tail_height", 18)))
            self.vars["padding"].set(int(element.metadata.get("padding", 14)))
            self.vars["progress_variable"].set(str(element.metadata.get("value_variable", "battery")))
            self.vars["progress_minimum"].set(float(element.metadata.get("minimum", 0)))
            self.vars["progress_maximum"].set(float(element.metadata.get("maximum", 100)))
            self.vars["progress_track"].set(str(element.metadata.get("track_fill", "#242733")))
            self.vars["progress_direction"].set(str(element.metadata.get("direction", "horizontal")))
            self.text_box.delete("1.0", tk.END)
            self.text_box.insert("1.0", element.text)
            self.text_box.edit_modified(False)
            self._update_action_help()
        finally:
            self._loading_properties = False

    def _candidate_from_properties(self, element: UIElement) -> UIElement:
        """Lee el panel de propiedades de forma atómica.

        Antes el elemento se modificaba campo por campo; un valor inválido al final
        podía dejar cambios parciales sin dibujar. Ahora se construye una copia y
        solo se sustituye el original cuando todos los campos son válidos.
        """
        candidate = copy.deepcopy(element)
        action_args = safe_json_loads(
            str(self.vars["action_args"].get()).strip() or "{}",
            label="Los argumentos de la acción",
            max_bytes=64 * 1024,
            max_depth=12,
            max_nodes=2_000,
            max_collection_items=500,
        )
        if not isinstance(action_args, dict):
            raise ValueError("Los argumentos de acción deben ser un objeto JSON.")

        candidate.x = float(self.vars["x"].get())
        candidate.y = float(self.vars["y"].get())
        candidate.width = max(self.MIN_ELEMENT_SIZE, float(self.vars["width"].get()))
        candidate.height = max(self.MIN_ELEMENT_SIZE, float(self.vars["height"].get()))
        candidate.opacity = max(0.0, min(1.0, float(self.vars["opacity"].get())))
        candidate.rotation = float(self.vars["rotation"].get()) % 360
        candidate.page = str(self.vars["page"].get())
        if candidate.page not in set(self._page_ids()) | {"*"}:
            raise ValueError("La pantalla seleccionada no existe.")

        candidate.text = self.text_box.get("1.0", "end-1c")
        candidate.font_family = str(self.vars["font_family"].get()).strip() or "Segoe UI"
        candidate.font_size = max(6, int(self.vars["font_size"].get()))
        candidate.font_weight = str(self.vars["font_weight"].get())
        candidate.text_align = str(self.vars["text_align"].get())
        candidate.text_color = str(self.vars["text_color"].get()).strip()
        candidate.fill = str(self.vars["fill"].get()).strip()
        candidate.outline = str(self.vars["outline"].get()).strip()
        candidate.outline_width = max(0, int(self.vars["outline_width"].get()))
        candidate.radius = max(0, int(self.vars["radius"].get()))
        candidate.source = str(self.vars["source"].get()).strip()
        candidate.action = str(self.vars["action"].get()).strip() or "none"
        if candidate.action == "page.open":
            target_page = str(self.vars["page_target"].get()).strip()
            if target_page not in self._page_ids():
                raise ValueError("La pantalla destino no existe.")
            action_args["page"] = target_page
        candidate.action_args = action_args
        candidate.tooltip = str(self.vars["tooltip"].get())
        candidate.visible_when = str(self.vars["visible_when"].get()).strip() or "always"
        candidate.hover_fill = str(self.vars["hover_fill"].get()).strip()
        candidate.pressed_fill = str(self.vars["pressed_fill"].get()).strip()
        candidate.locked = bool(self.vars["locked"].get())
        candidate.visible = bool(self.vars["visible"].get())

        if candidate.type == "image":
            candidate.metadata["fit"] = str(self.vars["fit"].get())
            for state_key in ("hover_source", "pressed_source"):
                state_source = str(self.vars[state_key].get()).strip()
                if state_source:
                    candidate.metadata[state_key] = state_source
                else:
                    candidate.metadata.pop(state_key, None)
        if candidate.type == "speech_bubble":
            candidate.metadata["tail_position"] = str(self.vars["tail_position"].get())
            candidate.metadata["tail_width"] = max(12, int(self.vars["tail_width"].get()))
            candidate.metadata["tail_height"] = max(8, int(self.vars["tail_height"].get()))
            candidate.metadata["padding"] = max(0, int(self.vars["padding"].get()))
        if candidate.type == "progress":
            progress_minimum = float(self.vars["progress_minimum"].get())
            progress_maximum = float(self.vars["progress_maximum"].get())
            if progress_maximum <= progress_minimum:
                raise ValueError("El máximo de la barra debe superar al mínimo.")
            candidate.metadata["value_variable"] = str(self.vars["progress_variable"].get()).strip() or "battery"
            candidate.metadata["minimum"] = progress_minimum
            candidate.metadata["maximum"] = progress_maximum
            candidate.metadata["track_fill"] = str(self.vars["progress_track"].get()).strip() or "#242733"
            candidate.metadata["direction"] = str(self.vars["progress_direction"].get())

        candidate.x = self._clamp_x(candidate, candidate.x)
        candidate.y = self._clamp_y(candidate, candidate.y)
        return candidate

    def _apply_properties_internal(self, *, show_errors: bool, commit: bool) -> bool:
        if not self.selected_id or self.selected_id not in self.elements:
            return False
        try:
            candidate = self._candidate_from_properties(self.elements[self.selected_id])
        except (ValueError, TypeError, tk.TclError, json.JSONDecodeError) as exc:
            if hasattr(self, "property_status_var"):
                self.property_status_var.set(f"Valor pendiente o inválido: {exc}")
            if show_errors:
                messagebox.showerror("Valor inválido", str(exc), parent=self)
            return False

        current = self.elements[self.selected_id]
        if asdict(candidate) == asdict(current):
            if commit:
                self.property_status_var.set("No había cambios pendientes.")
            return True

        self.elements[self.selected_id] = candidate
        self._render_all()
        self._refresh_layers()
        if commit:
            self._commit("Propiedades actualizadas")
            self.property_status_var.set("Cambios aplicados.")
        else:
            self.property_status_var.set("Vista previa actualizada automáticamente.")
        return True

    def apply_properties(self) -> None:
        self._cancel_property_jobs()
        self._apply_properties_internal(show_errors=True, commit=True)

    def choose_element_color(self, key: str) -> None:
        current = str(self.vars[key].get()) or "#FFFFFF"
        chosen = colorchooser.askcolor(initialcolor=current, parent=self)[1]
        if chosen:
            self.vars[key].set(chosen)

    def choose_canvas_color(self) -> None:
        chosen = colorchooser.askcolor(initialcolor=self.canvas_vars["background"].get(), parent=self)[1]
        if chosen:
            self.canvas_vars["background"].set(chosen)
            self.apply_canvas_properties()

    def replace_image(self) -> None:
        if not self.selected_id or self.elements[self.selected_id].type != "image":
            return
        path = filedialog.askopenfilename(parent=self, filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.webp *.gif *.bmp")])
        if not path:
            return
        try:
            imported = self._import_asset(Path(path))
        except Exception as exc:
            messagebox.showerror("No se pudo importar", str(exc), parent=self)
            return
        self.vars["source"].set(str(imported))
        self.apply_properties()

    def choose_state_image(self, key: str) -> None:
        """Asigna una imagen alternativa para hover o presionado."""
        if key not in {"hover_source", "pressed_source"}:
            return
        if not self.selected_id or self.elements[self.selected_id].type != "image":
            messagebox.showinfo("Estado de imagen", "Selecciona primero un elemento de imagen.", parent=self)
            return
        path = filedialog.askopenfilename(
            parent=self,
            title="Selecciona una imagen de estado",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.webp *.gif *.bmp")],
        )
        if not path:
            return
        try:
            imported = self._import_asset(Path(path))
        except Exception as exc:
            messagebox.showerror("No se pudo importar", str(exc), parent=self)
            return
        self.vars[key].set(str(imported))

    def fit_selected_image(self) -> None:
        if not self.selected_id:
            return
        element = self.elements[self.selected_id]
        if element.type != "image":
            return
        try:
            path = self.layout.resolve_asset(element.source) or Path(element.source)
            element.width, element.height = self._validated_image_dimensions(path)
            element.x = self._clamp_x(element, element.x)
            element.y = self._clamp_y(element, element.y)
            self._load_properties(element)
            self._render_all()
            self._commit("Imagen ajustada al tamaño original")
        except Exception as exc:
            messagebox.showerror("No se pudo leer la imagen", str(exc), parent=self)

    def apply_canvas_properties(self) -> None:
        try:
            width = int(self.canvas_vars["width"].get())
            height = int(self.canvas_vars["height"].get())
            if width < 320 or height < 240:
                raise ValueError("El lienzo debe medir al menos 320 × 240.")
            if width > 7680 or height > 4320:
                raise ValueError("El lienzo no puede superar 7680 × 4320.")
            self._sync_layout()
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("Lienzo inválido", str(exc), parent=self)
            return
        for element in self.elements.values():
            element.x = self._clamp_x(element, element.x)
            element.y = self._clamp_y(element, element.y)
        self._render_all()
        self._commit("Lienzo actualizado")

    def _load_canvas_vars(self) -> None:
        self.canvas_vars["name"].set(self.layout.name)
        self.canvas_vars["width"].set(int(self.layout.canvas.get("width", self.DEFAULT_CANVAS_WIDTH)))
        self.canvas_vars["height"].set(int(self.layout.canvas.get("height", self.DEFAULT_CANVAS_HEIGHT)))
        self.canvas_vars["background"].set(str(self.layout.canvas.get("background", "#17171C")))
        self.canvas_vars["scale_mode"].set(str(self.layout.canvas.get("scale_mode", "contain")))
        self._refresh_page_controls()

    def _update_action_help(self, _event: Optional[tk.Event] = None) -> None:
        action = str(self.vars["action"].get())
        definition = ACTION_DEFINITIONS.get(action, {"label": "Acción no reconocida"})
        self.action_help_var.set(str(definition.get("label", action)))

    # ------------------------------------------------------------------
    # Archivo, validación y aplicación
    # ------------------------------------------------------------------

    def create_starter_template(self) -> None:
        """Carga una interfaz completa de ejemplo lista para editar y aplicar.

        La plantilla evita recursos externos para que siempre pueda abrirse. También
        sirve como referencia de páginas, variables, condiciones y acciones.
        """
        if not self._confirm_discard():
            return

        self._cancel_gifs()
        self.layout = UILayout(
            name="nikaido_modern",
            description="Plantilla moderna editable incluida con Nikaido UI Studio.",
            author="Nikaido UI Studio",
            canvas={
                "width": self.DEFAULT_CANVAS_WIDTH,
                "height": self.DEFAULT_CANVAS_HEIGHT,
                "background": "#101116",
                "scale_mode": "contain",
            },
            pages=[
                {"id": "main", "name": "Inicio"},
                {"id": "profiles", "name": "Perfiles"},
                {"id": "tools", "name": "Herramientas"},
            ],
            default_page="main",
            metadata={"template": True, "template_version": 1},
            allow_external_assets=True,
            base_dir=self.layouts_dir,
        )

        elements: List[UIElement] = []

        def add(element_type: str, *, page: str = "main", **kwargs: Any) -> UIElement:
            element = UIElement(
                id=self._new_id(),
                type=element_type,
                x=float(kwargs.pop("x", 0)),
                y=float(kwargs.pop("y", 0)),
                width=float(kwargs.pop("width", 100)),
                height=float(kwargs.pop("height", 60)),
                page=page,
                z_index=len(elements),
                **kwargs,
            )
            elements.append(element)
            return element

        # Base global: aparece en todas las pantallas.
        add(
            "rectangle", page="*", x=0, y=0, width=900, height=560,
            fill="#101116", locked=True, metadata={"name": "Fondo global"},
        )
        add(
            "rectangle", page="*", x=0, y=0, width=900, height=72,
            fill="#191B24", locked=True, metadata={"name": "Barra superior"},
        )
        add(
            "text", page="*", x=28, y=18, width=360, height=38,
            text="NIKAIDO  //  DUALSENSE", font_size=22, font_weight="bold",
            text_color="#F4F5F8", metadata={"name": "Título global"},
        )
        add(
            "text", page="*", x=610, y=18, width=150, height=24,
            text="{connection}", font_size=14, font_weight="semibold",
            text_color="#9EA3B5", text_align="right", metadata={"name": "Conexión"},
        )
        add(
            "text", page="*", x=770, y=18, width=100, height=24,
            text="{battery_percent}", font_size=14, font_weight="bold",
            text_color="#8AE6B4", text_align="right", metadata={"name": "Batería"},
        )
        add(
            "progress", page="*", x=770, y=48, width=100, height=7,
            text="", fill="#2B9A78", radius=4, locked=True,
            metadata={
                "name": "Nivel de batería", "value_variable": "battery",
                "minimum": 0, "maximum": 100, "track_fill": "#303442",
                "direction": "horizontal",
            },
        )
        add(
            "button", page="*", x=746, y=512, width=126, height=32,
            text="Interfaz clásica", font_size=11, font_weight="semibold",
            fill="#242733", hover_fill="#303442", pressed_fill="#181A22",
            text_color="#D8DBE5", radius=10, action="ui.standard",
            tooltip="Mostrar temporalmente la interfaz clásica",
            metadata={"name": "Salir a interfaz clásica"},
        )
        add(
            "text", page="*", x=28, y=520, width=620, height=22,
            text="{status}", font_size=11, text_color="#73798C",
            metadata={"name": "Estado de aplicación"},
        )

        # Inicio.
        add(
            "text", x=46, y=108, width=515, height=58,
            text="Tu DualSense, sin menús aburridos.", font_size=30, font_weight="bold",
            text_color="#FFFFFF", metadata={"name": "Encabezado de inicio"},
        )
        add(
            "text", x=48, y=166, width=520, height=46,
            text="Perfil activo: {active_profile}  ·  Emulación: {emulation_mode}",
            font_size=14, text_color="#A6AABC", metadata={"name": "Resumen dinámico"},
        )
        add(
            "button", x=48, y=232, width=250, height=70,
            text="PERFILES", font_size=18, font_weight="bold",
            fill="#6D5DF6", hover_fill="#8174FA", pressed_fill="#5443D9",
            radius=18, action="page.open", action_args={"page": "profiles"},
            tooltip="Abrir la pantalla personalizada de perfiles",
            metadata={"name": "Abrir perfiles personalizados"},
        )
        add(
            "button", x=318, y=232, width=250, height=70,
            text="HERRAMIENTAS", font_size=18, font_weight="bold",
            fill="#2B9A78", hover_fill="#36B28D", pressed_fill="#20765C",
            radius=18, action="page.open", action_args={"page": "tools"},
            tooltip="Emulación, macros y utilidades",
            metadata={"name": "Abrir herramientas"},
        )
        add(
            "button", x=48, y=322, width=250, height=58,
            text="Gatillos adaptativos", font_size=15, font_weight="semibold",
            fill="#242733", hover_fill="#303442", pressed_fill="#181A22",
            radius=15, action="navigate.triggers",
            metadata={"name": "Gatillos clásicos"},
        )
        add(
            "button", x=318, y=322, width=250, height=58,
            text="Configuración", font_size=15, font_weight="semibold",
            fill="#242733", hover_fill="#303442", pressed_fill="#181A22",
            radius=15, action="navigate.settings",
            metadata={"name": "Configuración clásica"},
        )
        add(
            "button", x=600, y=232, width=250, height=70,
            text="Conectar control", font_size=16, font_weight="bold",
            fill="#E79248", hover_fill="#F0A45E", pressed_fill="#C87531",
            text_color="#151515", radius=18, action="controller.connect",
            visible_when="controller.disconnected", tooltip="Iniciar búsqueda del DualSense",
            metadata={"name": "Conectar (solo desconectado)"},
        )
        add(
            "button", x=600, y=232, width=250, height=70,
            text="Desconectar control", font_size=16, font_weight="bold",
            fill="#D65261", hover_fill="#E26976", pressed_fill="#B83E4B",
            radius=18, action="controller.disconnect", visible_when="controller.connected",
            tooltip="Desconectar y detener la reconexión automática",
            metadata={"name": "Desconectar (solo conectado)"},
        )
        add(
            "rectangle", x=600, y=322, width=250, height=116,
            fill="#191B24", outline="#2D3040", outline_width=1, radius=18,
            locked=True, metadata={"name": "Tarjeta de telemetría"},
        )
        add(
            "text", x=622, y=342, width=205, height=28,
            text="L2  {l2}     R2  {r2}", font_size=17, font_weight="bold",
            text_color="#F4F5F8", text_align="center", metadata={"name": "Lectura de gatillos"},
        )
        add(
            "text", x=622, y=386, width=205, height=24,
            text="Macros: {macros_enabled}", font_size=13, text_color="#9EA3B5",
            text_align="center", metadata={"name": "Estado de macros"},
        )

        # Perfiles: acciones útiles sin depender de IDs predefinidos.
        add(
            "text", page="profiles", x=48, y=108, width=470, height=50,
            text="Perfiles", font_size=30, font_weight="bold", text_color="#FFFFFF",
            metadata={"name": "Título perfiles"},
        )
        add(
            "text", page="profiles", x=48, y=166, width=620, height=38,
            text="Activo: {active_profile}  ·  {profile_count} perfiles disponibles",
            font_size=14, text_color="#A6AABC", metadata={"name": "Perfil activo"},
        )
        add(
            "button", page="profiles", x=48, y=236, width=250, height=72,
            text="Perfil anterior", font_size=17, font_weight="bold",
            fill="#242733", hover_fill="#303442", pressed_fill="#181A22",
            radius=18, action="profile.previous", metadata={"name": "Perfil anterior"},
        )
        add(
            "button", page="profiles", x=318, y=236, width=250, height=72,
            text="Perfil siguiente", font_size=17, font_weight="bold",
            fill="#6D5DF6", hover_fill="#8174FA", pressed_fill="#5443D9",
            radius=18, action="profile.next", metadata={"name": "Perfil siguiente"},
        )
        add(
            "button", page="profiles", x=588, y=236, width=250, height=72,
            text="Administrar perfiles", font_size=16, font_weight="bold",
            fill="#2B9A78", hover_fill="#36B28D", pressed_fill="#20765C",
            radius=18, action="navigate.profiles", metadata={"name": "Administrador clásico"},
        )
        add(
            "button", page="profiles", x=48, y=332, width=250, height=58,
            text="Importar", font_size=15, font_weight="semibold",
            fill="#242733", hover_fill="#303442", pressed_fill="#181A22",
            radius=15, action="profile.import", metadata={"name": "Importar perfil"},
        )
        add(
            "button", page="profiles", x=318, y=332, width=250, height=58,
            text="Exportar activo", font_size=15, font_weight="semibold",
            fill="#242733", hover_fill="#303442", pressed_fill="#181A22",
            radius=15, action="profile.export", metadata={"name": "Exportar perfil"},
        )
        add(
            "button", page="profiles", x=48, y=430, width=160, height=46,
            text="← Volver", font_size=14, font_weight="semibold",
            fill="#191B24", hover_fill="#292C38", pressed_fill="#111218",
            radius=13, action="page.back", metadata={"name": "Volver"},
        )

        # Herramientas.
        add(
            "text", page="tools", x=48, y=108, width=470, height=50,
            text="Herramientas", font_size=30, font_weight="bold", text_color="#FFFFFF",
            metadata={"name": "Título herramientas"},
        )
        add(
            "text", page="tools", x=48, y=166, width=620, height=38,
            text="Emulación: {emulation_mode}  ·  Macros: {macros_enabled}",
            font_size=14, text_color="#A6AABC", metadata={"name": "Estado herramientas"},
        )
        tool_buttons = [
            (48, 226, "Xbox 360", "emulation.xbox", "#2B9A78", "#36B28D", "#20765C"),
            (318, 226, "PlayStation 4", "emulation.ps4", "#4169A8", "#527DC0", "#315184"),
            (588, 226, "Apagar emulación", "emulation.off", "#D65261", "#E26976", "#B83E4B"),
            (48, 316, "Activar / desactivar macros", "macro.toggle", "#6D5DF6", "#8174FA", "#5443D9"),
            (318, 316, "Restablecer gatillos", "trigger.reset", "#242733", "#303442", "#181A22"),
            (588, 316, "Restablecer botones", "buttons.reset", "#242733", "#303442", "#181A22"),
        ]
        for x, y, label, action, fill, hover, pressed in tool_buttons:
            add(
                "button", page="tools", x=x, y=y, width=250, height=68,
                text=label, font_size=15, font_weight="bold", fill=fill,
                hover_fill=hover, pressed_fill=pressed, radius=17, action=action,
                metadata={"name": label},
            )
        add(
            "button", page="tools", x=48, y=430, width=160, height=46,
            text="← Volver", font_size=14, font_weight="semibold",
            fill="#191B24", hover_fill="#292C38", pressed_fill="#111218",
            radius=13, action="page.back", metadata={"name": "Volver"},
        )

        self.elements = {element.id: element for element in elements}
        self.layout.elements = list(elements)
        self.current_file = None
        self.current_page = self.layout.default_page
        self.selected_id = None
        self._load_canvas_vars()
        self._render_all()
        self._refresh_layers()
        self._reset_history()
        self._dirty = True
        self.status_var.set("Plantilla inicial creada · edítala y pulsa Aplicar ahora")

    def new_layout(self) -> None:
        if not self._confirm_discard():
            return
        self._cancel_gifs()
        self.layout = UILayout(
            canvas={"width": self.DEFAULT_CANVAS_WIDTH, "height": self.DEFAULT_CANVAS_HEIGHT, "background": "#17171C", "scale_mode": "contain"},
            base_dir=self.layouts_dir,
            allow_external_assets=True,
        )
        self.elements.clear()
        self.current_file = None
        self.current_page = self.layout.default_page
        self.selected_id = None
        self._load_canvas_vars()
        self._render_all()
        self._refresh_layers()
        self._mark_clean()
        self._reset_history()
        self.status_var.set("Diseño nuevo")

    def open_layout(self) -> None:
        chosen = filedialog.askopenfilename(
            parent=self,
            initialdir=self.layouts_dir,
            filetypes=[("Temas Nikaido", "*.json *.nikaido-ui.json *.nikaido-theme"), ("Todos", "*.*")],
        )
        if chosen:
            self.open_path(Path(chosen))

    def open_path(self, path: Path, *, prompt_dirty: bool = True) -> None:
        if prompt_dirty and not self._confirm_discard():
            return
        try:
            layout = load_layout(
                path,
                extract_dir=self.layouts_dir / "installed",
                allow_external_assets=path.suffix.lower() == ".json",
            )
            errors, warnings = validate_layout(layout, check_assets=True)
            if errors:
                raise ThemeError("\n".join(errors))
        except Exception as exc:
            messagebox.showerror("No se pudo abrir", str(exc), parent=self)
            return
        self._cancel_gifs()
        self.layout = layout
        self.elements = {element.id: element for element in layout.elements}
        self.current_file = path.resolve() if path.suffix.lower() == ".json" else None
        self.current_page = layout.default_page
        self.selected_id = None
        self._load_canvas_vars()
        self._render_all()
        self._refresh_layers()
        self._mark_clean()
        self._reset_history()
        self.status_var.set(f"Abierto: {path.name}" + (f" | {len(warnings)} advertencias" if warnings else ""))

    def _localize_assets_for_json(self, layout: UILayout, path: Path) -> None:
        """Copia recursos junto al JSON para que el diseño siga funcionando al mover la carpeta."""
        asset_dir = path.parent / f"{path.stem}_assets"
        copied: Dict[Path, Path] = {}

        def localize(source_value: str) -> str:
            if not source_value:
                return source_value
            source = layout.resolve_asset(source_value)
            if not source or not source.is_file():
                return source_value
            if source in copied:
                destination = copied[source]
            else:
                asset_dir.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256(source.read_bytes()).hexdigest()[:10]
                safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", source.stem).strip("._") or "asset"
                destination = asset_dir / f"{safe_stem}_{digest}{source.suffix.lower()}"
                if source.resolve() != destination.resolve():
                    shutil.copy2(source, destination)
                copied[source] = destination
            try:
                return str(destination.relative_to(path.parent))
            except ValueError:
                return str(destination)

        for element in layout.elements:
            if element.type == "image":
                element.source = localize(element.source)
            for key in ("hover_source", "pressed_source"):
                if element.metadata.get(key):
                    element.metadata[key] = localize(str(element.metadata[key]))
        layout.base_dir = path.parent

    def save_layout(self, save_as: bool = False) -> bool:
        path = None if save_as else self.current_file
        if path is None:
            chosen = filedialog.asksaveasfilename(
                parent=self,
                initialdir=self.layouts_dir,
                defaultextension=".nikaido-ui.json",
                filetypes=[("Diseño Nikaido", "*.nikaido-ui.json"), ("JSON", "*.json")],
            )
            if not chosen:
                return False
            path = Path(chosen)
        try:
            layout = self._sync_layout()
            self._localize_assets_for_json(layout, path.resolve())
            errors, warnings = validate_layout(layout, check_assets=True)
            if errors:
                raise ThemeError("No se puede guardar:\n- " + "\n- ".join(errors))
            save_layout(layout, path)
            self.current_file = path.resolve()
            self.layout.base_dir = self.current_file.parent
            self.layout.source_path = self.current_file
            self._mark_clean()
            self._clear_autosave()
            self.status_var.set(f"Guardado: {self.current_file.name}" + (f" | {len(warnings)} advertencias" if warnings else ""))
            return True
        except Exception as exc:
            messagebox.showerror("No se pudo guardar", str(exc), parent=self)
            return False

    def export_layout(self) -> None:
        chosen = filedialog.asksaveasfilename(
            parent=self,
            initialdir=self.layouts_dir,
            defaultextension=".nikaido-theme",
            filetypes=[("Paquete de tema Nikaido", "*.nikaido-theme")],
        )
        if not chosen:
            return
        try:
            destination = export_theme_package(self._sync_layout(), chosen)
            self.status_var.set(f"Paquete exportado: {destination.name}")
            messagebox.showinfo(
                "Tema exportado",
                "El paquete incluye el diseño y todas sus imágenes. Ya se puede mover a otra PC sin romper rutas.",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror("No se pudo exportar", str(exc), parent=self)

    def validate_current_layout(self) -> bool:
        try:
            layout = self._sync_layout()
            errors, warnings = validate_layout(layout, check_assets=True)
        except Exception as exc:
            messagebox.showerror("Validación", str(exc), parent=self)
            return False
        if errors:
            text = "Errores:\n• " + "\n• ".join(errors)
            if warnings:
                text += "\n\nAdvertencias:\n• " + "\n• ".join(warnings)
            messagebox.showerror("Diseño inválido", text, parent=self)
            return False
        if warnings:
            messagebox.showwarning("Diseño válido con advertencias", "• " + "\n• ".join(warnings), parent=self)
        else:
            messagebox.showinfo("Diseño válido", "No se encontraron errores.", parent=self)
        return True

    def apply_to_app(self) -> None:
        """Guarda una copia de trabajo y la muestra realmente en la ventana principal."""
        if not self.on_apply:
            messagebox.showwarning("Vista previa", "Este editor no está conectado a Nikaido.", parent=self)
            return

        self._cancel_property_jobs()
        if self.selected_id and not self._apply_properties_internal(show_errors=True, commit=True):
            return

        try:
            layout = self._sync_layout()
            errors, warnings = validate_layout(layout, check_assets=True)
            if errors:
                messagebox.showerror("No se puede aplicar", "• " + "\n• ".join(errors), parent=self)
                return

            # Siempre se guarda una copia de vista previa. Esto hace que el botón
            # de aplicar funcione incluso si el usuario todavía no eligió Guardar como.
            preview_path = self.layouts_dir / "_active_editor_preview.nikaido-ui.json"
            preview = UILayout.from_dict(
                layout.to_dict(), base_dir=layout.base_dir or self.layouts_dir, source_path=preview_path
            )
            self._localize_assets_for_json(preview, preview_path)
            save_layout(preview, preview_path)
            preview.source_path = preview_path
            preview.base_dir = preview_path.parent

            self.on_apply(preview)
            self.status_var.set("Interfaz aplicada en Nikaido" + (f" | {len(warnings)} advertencias" if warnings else ""))
            self.property_status_var.set("Interfaz aplicada. F12 vuelve a la interfaz clásica.")

            # Un Toplevel transient suele quedarse encima de la app y hace parecer
            # que nada ocurrió. Se oculta para enseñar el resultado de inmediato.
            self.withdraw()
            parent = self.master
            try:
                parent.deiconify()
                parent.lift()
                parent.focus_force()
            except tk.TclError:
                pass
        except Exception as exc:
            messagebox.showerror("No se pudo aplicar", str(exc), parent=self)

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        answer = messagebox.askyesnocancel("Cambios sin guardar", "¿Quieres guardar los cambios antes de continuar?", parent=self)
        if answer is None:
            return False
        if answer:
            return self.save_layout()
        return True

    # ------------------------------------------------------------------
    # Autosave y cierre
    # ------------------------------------------------------------------

    def _offer_autosave_recovery(self) -> bool:
        """Ofrece restaurar el último autoguardado tras un cierre inesperado."""
        if not self.autosave_file.is_file():
            return False
        try:
            data = read_json_file_limited(
                self.autosave_file,
                label="El autoguardado de UI Studio",
                max_bytes=2 * 1024 * 1024,
                max_nodes=80_000,
                max_collection_items=10_000,
            )
            recovered = UILayout.from_dict(data, base_dir=self.layouts_dir, source_path=None)
            errors, _warnings = validate_layout(recovered, check_assets=False)
            if errors:
                raise ThemeError("; ".join(errors))
        except Exception:
            self.autosave_file.unlink(missing_ok=True)
            return False

        restore = messagebox.askyesno(
            "Recuperar diseño",
            "Nikaido UI Studio encontró cambios autoguardados de una sesión anterior. "
            "¿Quieres recuperarlos?",
            parent=self,
        )
        if not restore:
            self.autosave_file.unlink(missing_ok=True)
            return False

        self.layout = recovered
        self.elements = {element.id: element for element in recovered.elements}
        self.current_file = None
        self.current_page = recovered.default_page
        self.selected_id = None
        self._load_canvas_vars()
        self._render_all()
        self._refresh_layers()
        self._reset_history()
        self._mark_dirty("Diseño recuperado del autoguardado")
        return True

    def _clear_autosave(self) -> None:
        try:
            self.autosave_file.unlink(missing_ok=True)
        except OSError:
            pass

    def _schedule_autosave(self) -> None:
        if self._autosave_job:
            try:
                self.after_cancel(self._autosave_job)
            except tk.TclError:
                pass
        self._autosave_job = self.after(self.AUTOSAVE_MS, self._autosave)

    def _autosave(self) -> None:
        self._autosave_job = None
        if self._dirty:
            try:
                payload = json.dumps(self._sync_layout().to_dict(), ensure_ascii=False, indent=2)
                temp = self.autosave_file.with_suffix(self.autosave_file.suffix + ".tmp")
                temp.write_text(payload, encoding="utf-8")
                os.replace(temp, self.autosave_file)
                self.status_var.set("Autoguardado de recuperación actualizado")
            except Exception:
                pass
        self._schedule_autosave()

    def _on_close(self) -> None:
        self._cancel_property_jobs()
        if not self._confirm_discard():
            return
        self._clear_autosave()
        self._cancel_gifs()
        if self._autosave_job:
            try:
                self.after_cancel(self._autosave_job)
            except tk.TclError:
                pass
        self.destroy()
