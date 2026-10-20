"""Galería moderna de perfiles y biblioteca comunitaria de juegos."""

from __future__ import annotations

import copy
import json
import logging
import re
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from src.profile_catalog import (
    DEFAULT_PROFILE_ID,
    ordered_builtin_ids,
    profile_presentation,
)

from ..components import ScrollPage
from ..profile_editor import ProfileEditorDialog, profile_image_widget
from ..profile_gallery import ProfileDetailPanel, ProfileGalleryCard
from ..i18n import translate_widget_tree
from ..ui_common import (
    C,
    QFileDialog,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
    button,
    card,
    clear_layout,
    label,
    resource_path,
)

if TYPE_CHECKING:
    from ..main_window import NikaidoWindow

logger = logging.getLogger(__name__)


def profile_action(label: str):
    """Evita que una excepción de un slot Qt parezca un botón sin respuesta."""

    def decorate(callback):
        @wraps(callback)
        def guarded(self, *args, **kwargs):
            try:
                return callback(self, *args, **kwargs)
            except Exception:
                logger.exception("Error en Profile Studio al %s", label)
                try:
                    self.window.alert(
                        f"No se pudo {label}. Revisa el diagnóstico para ver el detalle."
                    )
                except Exception:
                    logger.exception("No se pudo mostrar el error de Profile Studio")
                return None

        return guarded

    return decorate


class ProfilesPage(ScrollPage):
    """Opción D: galería visual con detalle lateral y trabajo bajo demanda."""

    def __init__(self, window: "NikaidoWindow") -> None:
        super().__init__()
        self.window = window
        self.selected_profile_id: Optional[str] = None
        self._card_widgets: dict[str, ProfileGalleryCard] = {}
        self._last_signature: Optional[str] = None
        self._last_columns = 0
        self._compact_layout: Optional[bool] = None
        self._display_mode = str(
            self.window.profile_manager.get_setting("profile_library.view", "grid")
            if self.window.profile_manager
            else "grid"
        )
        if self._display_mode not in {"grid", "list"}:
            self._display_mode = "grid"

        self._responsive_timer = QTimer(self)
        self._responsive_timer.setSingleShot(True)
        self._responsive_timer.setInterval(120)
        self._responsive_timer.timeout.connect(self._refresh_if_layout_changed)
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(180)
        self._filter_timer.timeout.connect(lambda: self.refresh(force=True))

        self._build_header()
        self._build_filters()
        self._build_content()
        self.refresh(force=True)

    # ===== Construcción visual =====

    def _build_header(self) -> None:
        header = QHBoxLayout()
        header.setSpacing(10)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title_box.addWidget(label("Perfiles", "title"))
        subtitle = QLabel("Crea, organiza y personaliza tu experiencia en el DualSense.")
        subtitle.setStyleSheet(f"color:{C['muted']};font-size:10px")
        subtitle.setWordWrap(True)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        header.addWidget(button("Importar", self.import_profile))
        header.addWidget(button("＋ Nuevo perfil", self.create_from_active, primary=True))
        self.search_edit = QLineEdit()
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setPlaceholderText("Buscar perfiles")
        self.search_edit.setMinimumWidth(190)
        self.search_edit.setMaximumWidth(280)
        self.search_edit.textChanged.connect(lambda _text: self._filter_timer.start())
        header.addWidget(self.search_edit)
        self.layout.addLayout(header)

    def _build_filters(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)

        self.category_filter = self._make_combo()
        self.category_filter.currentIndexChanged.connect(lambda _index: self.refresh(force=True))
        row.addWidget(self.category_filter)

        self.sort_filter = self._make_combo()
        self.sort_filter.addItem("Recomendados", "recommended")
        self.sort_filter.addItem("Nombre A–Z", "name")
        self.sort_filter.addItem("Categoría", "category")
        self.sort_filter.addItem("Favoritos primero", "favorites")
        stored_sort = (
            self.window.profile_manager.get_setting("profile_library.sort", "recommended")
            if self.window.profile_manager
            else "recommended"
        )
        self.sort_filter.setCurrentIndex(max(0, self.sort_filter.findData(stored_sort)))
        self.sort_filter.currentIndexChanged.connect(self._sort_changed)
        row.addWidget(self.sort_filter)

        self.favorite_filter = self._make_combo()
        self.favorite_filter.addItem("Todos", "all")
        self.favorite_filter.addItem("Solo favoritos", "favorites")
        self.favorite_filter.addItem("Incluidos", "builtin")
        self.favorite_filter.addItem("Mis perfiles", "custom")
        self.favorite_filter.currentIndexChanged.connect(lambda _index: self.refresh(force=True))
        row.addWidget(self.favorite_filter)
        row.addStretch()

        self.grid_button = QPushButton("▦")
        self.grid_button.setProperty("iconButton", True)
        self.grid_button.setFixedSize(36, 36)
        self.grid_button.setToolTip("Vista de galería")
        self.grid_button.clicked.connect(lambda: self.set_display_mode("grid"))
        row.addWidget(self.grid_button)
        self.list_button = QPushButton("☷")
        self.list_button.setProperty("iconButton", True)
        self.list_button.setFixedSize(36, 36)
        self.list_button.setToolTip("Vista compacta")
        self.list_button.clicked.connect(lambda: self.set_display_mode("list"))
        row.addWidget(self.list_button)
        self.layout.addLayout(row)
        self._sync_view_buttons()

    @staticmethod
    def _make_combo() -> Any:
        from ..ui_common import QComboBox

        combo = QComboBox()
        combo.setMinimumWidth(150)
        return combo

    def _build_content(self) -> None:
        self.content_grid = QGridLayout()
        self.content_grid.setContentsMargins(0, 0, 0, 0)
        self.content_grid.setSpacing(12)
        self.layout.addLayout(self.content_grid)

        self.gallery_panel = QWidget()
        self.gallery_layout = QVBoxLayout(self.gallery_panel)
        self.gallery_layout.setContentsMargins(0, 0, 0, 0)
        self.gallery_layout.setSpacing(10)
        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.gallery_layout.addLayout(self.grid)

        self.create_strip = QPushButton("＋    Crear nuevo perfil    ·    parte del perfil activo o duplica uno existente")
        self.create_strip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.create_strip.setAutoDefault(False)
        self.create_strip.setMinimumHeight(54)
        self.create_strip.setStyleSheet(
            f"QPushButton {{ text-align:left;padding:12px 16px;background:transparent;"
            f"border:1px dashed {C['border']};border-radius:12px;color:{C['muted']}; }}"
            f"QPushButton:hover {{ border-color:{C['accent']};color:{C['text']}; }}"
        )
        self.create_strip.clicked.connect(self.create_from_active)
        self.gallery_layout.addWidget(self.create_strip)

        disclaimer = QLabel(
            "Los ocho perfiles de juegos son configuraciones comunitarias no oficiales de Team Nikaido. "
            "No incluyen arte, logotipos ni archivos de los publishers."
        )
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet(f"color:{C['muted']};font-size:8px")
        self.gallery_layout.addWidget(disclaimer)
        self.gallery_layout.addStretch()

        self.detail_panel = ProfileDetailPanel(self.window)
        self.detail_panel.apply_requested.connect(self.apply_profile)
        self.detail_panel.edit_requested.connect(self.edit_profile)
        self.detail_panel.duplicate_requested.connect(self.duplicate_profile)
        self.detail_panel.export_requested.connect(self.export_profile)
        self.detail_panel.favorite_requested.connect(self.toggle_favorite)
        self.detail_panel.delete_requested.connect(self.delete_profile)
        self.detail_panel.reset_requested.connect(self.reset_builtin_profile)
        self.detail_panel.navigate_requested.connect(self._navigate_selected_profile)

        self.content_grid.addWidget(self.gallery_panel, 0, 0)
        self.content_grid.addWidget(self.detail_panel, 0, 1)
        self.content_grid.setColumnStretch(0, 1)
        self.content_grid.setColumnStretch(1, 0)
        self.layout.addStretch()

    # ===== Responsive y persistencia visual =====

    def resizeEvent(self, event: Any) -> None:  # pragma: no cover - interacción Qt
        super().resizeEvent(event)
        self._responsive_timer.start()

    def _apply_layout_mode(self) -> None:
        compact = self.viewport().width() < 1080
        if compact == self._compact_layout:
            return
        self._compact_layout = compact
        self.content_grid.removeWidget(self.gallery_panel)
        self.content_grid.removeWidget(self.detail_panel)
        if compact:
            self.content_grid.addWidget(self.gallery_panel, 0, 0)
            self.content_grid.addWidget(self.detail_panel, 1, 0)
            self.detail_panel.setMaximumWidth(10_000)
        else:
            self.content_grid.addWidget(self.gallery_panel, 0, 0)
            self.content_grid.addWidget(self.detail_panel, 0, 1)
            self.detail_panel.setMaximumWidth(430)
        self.content_grid.setColumnStretch(0, 1)
        self.content_grid.setColumnStretch(1, 0)

    def _column_count(self) -> int:
        if self._display_mode == "list":
            return 1
        width = self.gallery_panel.width() or self.viewport().width()
        return max(1, min(3, max(300, width - 6) // 270))

    def _refresh_if_layout_changed(self) -> None:
        compact = self.viewport().width() < 1080
        columns = self._column_count()
        if compact != self._compact_layout or columns != self._last_columns:
            self.refresh(force=True)

    def set_display_mode(self, mode: str) -> None:
        parsed = "list" if str(mode) == "list" else "grid"
        if parsed == self._display_mode:
            return
        self._display_mode = parsed
        self._sync_view_buttons()
        manager = self.window.profile_manager
        if manager:
            manager.set_setting("profile_library.view", parsed)
            self.window.request_config_save()
        self.refresh(force=True)

    def _sync_view_buttons(self) -> None:
        self.grid_button.setProperty("primary", self._display_mode == "grid")
        self.list_button.setProperty("primary", self._display_mode == "list")
        self.grid_button.style().unpolish(self.grid_button)
        self.grid_button.style().polish(self.grid_button)
        self.list_button.style().unpolish(self.list_button)
        self.list_button.style().polish(self.list_button)

    def _sort_changed(self, _index: int) -> None:
        manager = self.window.profile_manager
        if manager:
            manager.set_setting("profile_library.sort", self.sort_filter.currentData())
            self.window.request_config_save()
        self.refresh(force=True)

    # ===== Datos y filtros =====

    def _favorite_ids(self) -> set[str]:
        manager = self.window.profile_manager
        return set(manager.get_favorites()) if manager else set()

    def _all_profiles(self) -> list[tuple[str, Any]]:
        engine = self.window.trigger_engine
        return list(engine.get_all_profiles().items()) if engine else []

    def _update_categories(self, profiles: list[tuple[str, Any]]) -> None:
        selected = self.category_filter.currentData()
        categories = sorted({str(profile.category or "General") for _pid, profile in profiles})
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("Todos los perfiles", "all")
        for category in categories:
            self.category_filter.addItem(category, category)
        index = self.category_filter.findData(selected)
        self.category_filter.setCurrentIndex(max(0, index))
        self.category_filter.blockSignals(False)

    def _filtered_profiles(self) -> list[tuple[str, Any]]:
        engine = self.window.trigger_engine
        profiles = self._all_profiles()
        search = self.search_edit.text().strip().lower()
        category = str(self.category_filter.currentData() or "all")
        scope = str(self.favorite_filter.currentData() or "all")
        favorites = self._favorite_ids()
        result: list[tuple[str, Any]] = []
        for profile_id, profile in profiles:
            custom = engine.is_custom_profile(profile_id)
            terms = " ".join(
                [
                    profile_id,
                    str(profile.name),
                    str(profile.category),
                    str(profile.description),
                    " ".join(getattr(profile, "tags", []) or []),
                    str((getattr(profile, "light_config", {}) or {}).get("effect", "")),
                ]
            ).lower()
            if search and search not in terms:
                continue
            if category != "all" and str(profile.category or "General") != category:
                continue
            if scope == "favorites" and profile_id not in favorites:
                continue
            if scope == "builtin" and custom:
                continue
            if scope == "custom" and not custom:
                continue
            result.append((profile_id, profile))

        sort_mode = str(self.sort_filter.currentData() or "recommended")
        active = engine.get_current_profile()
        order = {profile_id: index for index, profile_id in enumerate(ordered_builtin_ids())}
        if sort_mode == "name":
            result.sort(key=lambda item: str(item[1].name).lower())
        elif sort_mode == "category":
            result.sort(key=lambda item: (str(item[1].category).lower(), str(item[1].name).lower()))
        elif sort_mode == "favorites":
            result.sort(key=lambda item: (item[0] not in favorites, item[0] != active, str(item[1].name).lower()))
        else:
            result.sort(
                key=lambda item: (
                    item[0] != active,
                    engine.is_custom_profile(item[0]),
                    order.get(item[0], 10_000),
                    str(item[1].name).lower(),
                )
            )
        return result

    # ===== Actualización de la galería =====

    def refresh(self, force: bool = False) -> None:
        engine = self.window.trigger_engine
        if not engine:
            return
        self._apply_layout_mode()
        all_profiles = self._all_profiles()
        self._update_categories(all_profiles)
        profiles = self._filtered_profiles()
        active = engine.get_current_profile()
        visible_ids = {profile_id for profile_id, _profile in profiles}
        if not self.selected_profile_id or not engine.get_profile(self.selected_profile_id):
            self.selected_profile_id = active or (profiles[0][0] if profiles else None)
        elif self.selected_profile_id not in visible_ids:
            self.selected_profile_id = active if active in visible_ids else (profiles[0][0] if profiles else None)

        columns = self._column_count()
        signature = json.dumps(
            {
                "active": active,
                "columns": columns,
                "mode": self._display_mode,
                "search": self.search_edit.text(),
                "category": self.category_filter.currentData(),
                "scope": self.favorite_filter.currentData(),
                "sort": self.sort_filter.currentData(),
                "favorites": sorted(self._favorite_ids()),
                "profiles": [(profile_id, profile.to_dict()) for profile_id, profile in profiles],
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        if not force and signature == self._last_signature:
            self._sync_card_states(active)
            self._refresh_detail()
            return
        self._last_signature = signature
        self._last_columns = columns
        self._card_widgets = {}
        clear_layout(self.grid)
        for column in range(3):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)

        favorites = self._favorite_ids()
        for index, (profile_id, profile) in enumerate(profiles):
            card_widget = ProfileGalleryCard(
                self,
                profile_id,
                profile,
                active=profile_id == active,
                favorite=profile_id in favorites,
                selected=profile_id == self.selected_profile_id,
                custom=engine.is_custom_profile(profile_id),
                display_mode=self._display_mode,
            )
            card_widget.selected.connect(self.select_profile)
            self._card_widgets[profile_id] = card_widget
            self.grid.addWidget(card_widget, index // columns, index % columns)

        if not profiles:
            empty = card()
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(18, 18, 18, 18)
            empty_layout.addWidget(label("No encontramos perfiles", "heading"))
            helper = QLabel("Cambia los filtros o crea un perfil nuevo a partir del activo.")
            helper.setWordWrap(True)
            helper.setProperty("muted", True)
            empty_layout.addWidget(helper)
            empty_layout.addWidget(button("Crear perfil", self.create_from_active, primary=True))
            self.grid.addWidget(empty, 0, 0)
        self._refresh_detail()
        translate_widget_tree(self.gallery_panel, getattr(self.window, "language", "es"))

    def _sync_card_states(self, active: Optional[str]) -> None:
        for profile_id, widget in self._card_widgets.items():
            widget.set_active_state(profile_id == active)
            widget.set_selected_state(profile_id == self.selected_profile_id)

    @profile_action("seleccionar el perfil")
    def select_profile(self, profile_id: str) -> None:
        old = self.selected_profile_id
        self.selected_profile_id = str(profile_id)
        if old in self._card_widgets:
            self._card_widgets[old].set_selected_state(False)
        if self.selected_profile_id in self._card_widgets:
            self._card_widgets[self.selected_profile_id].set_selected_state(True)
        self._refresh_detail()

    def _macro_count(self, profile_id: str) -> int:
        manager = self.window.profile_manager
        macros = manager.get_macros() if manager else {}
        count = 0
        for macro in macros.values():
            if not isinstance(macro, dict):
                continue
            profile_ids = macro.get("profile_ids", [])
            if isinstance(profile_ids, list) and profile_id in profile_ids:
                count += 1
        return count

    def _refresh_detail(self) -> None:
        engine = self.window.trigger_engine
        profile_id = self.selected_profile_id
        profile = engine.get_profile(profile_id) if engine and profile_id else None
        if not profile or not profile_id:
            self.detail_panel.show_empty()
            translate_widget_tree(self.detail_panel, getattr(self.window, "language", "es"))
            return
        self.detail_panel.set_profile(
            profile_id,
            profile,
            active=engine.get_current_profile() == profile_id,
            custom=engine.is_custom_profile(profile_id),
            favorite=profile_id in self._favorite_ids(),
            macro_count=self._macro_count(profile_id),
        )
        translate_widget_tree(self.detail_panel, getattr(self.window, "language", "es"))

    # ===== Navegación y acciones =====

    def _call_later(self, ms: int, callback) -> None:
        """Usa el scheduler cancelable de la ventana y conserva hosts antiguos."""
        scheduler = getattr(self.window, "call_later", None)
        if callable(scheduler):
            scheduler(ms, callback)
        else:  # Compatibilidad con plugins y pruebas que alojan la página sola.
            QTimer.singleShot(ms, callback)

    def _navigate_selected_profile(self, destination: str) -> None:
        profile_id = self.selected_profile_id
        if not profile_id:
            return
        self.window.navigate(destination)
        page_names = {
            "lights": "lights_page",
            "triggers": "triggers_page",
            "vibration": "vibration_page",
            "input": "input_page",
            "macros": "macros_page",
        }

        def select() -> None:
            page = getattr(self.window, page_names.get(destination, ""), None)
            selector = getattr(page, "select_profile", None)
            if callable(selector):
                selector(profile_id)

        self._call_later(0, select)

    @profile_action("aplicar el perfil")
    def apply_profile(self, profile_id: str) -> None:
        resolved = self.window.trigger_engine.canonical_profile_id(profile_id)
        self.selected_profile_id = resolved
        self.window.apply_profile(resolved)
        self._call_later(0, lambda: self.refresh(force=True))

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _profile_with_current_input(self, profile_id: str) -> Any:
        profile = self.window.trigger_engine.get_profile(profile_id)
        if not profile:
            return None
        result = copy.deepcopy(profile)
        if self.window.input_studio:
            result.input_studio_config = self.window.input_studio.get_profile_config(profile_id)
        return result

    def _unique_profile_id(self, name: str) -> str:
        engine = self.window.trigger_engine
        base = re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_") or "perfil"
        profile_id = base
        suffix = 2
        while engine.get_profile(profile_id):
            profile_id = f"{base}_{suffix}"
            suffix += 1
        return profile_id

    @profile_action("crear el perfil")
    def create_from_active(self) -> None:
        engine = self.window.trigger_engine
        if not engine:
            self.window.alert("El motor de perfiles todavía no está disponible")
            return

        # Crear debe funcionar incluso antes de conectar el DualSense o aplicar
        # un perfil. En ese estado el motor aún puede no tener ``current_profile``.
        source_id = (
            engine.get_current_profile()
            or self.selected_profile_id
            or DEFAULT_PROFILE_ID
        )
        source_id = engine.canonical_profile_id(source_id)
        source = self._profile_with_current_input(source_id)
        if not source:
            available = self._all_profiles()
            if available:
                source_id = available[0][0]
                source = self._profile_with_current_input(source_id)
        if not source:
            self.window.alert("No hay un perfil base disponible para crear uno nuevo")
            return
        source.name = f"{source.name} personalizado"
        source.category = "Personal"
        source.origin = "user"
        source.created_at = self._now()
        source.updated_at = source.created_at
        source.tags = ["Personalizado"]
        # Usar el ID de origen permite previsualizar su banner incluido mientras
        # el perfil nuevo todavía no tiene un ID propio.
        dialog = ProfileEditorDialog(self.window, source_id, source, creating=True)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            profile = copy.deepcopy(dialog.profile)
            profile_id = self._unique_profile_id(profile.name)
            profile.origin = "user"
            profile.created_at = profile.created_at or self._now()
            profile.updated_at = self._now()
            stored_assets = self._commit_new_media(
                dialog,
                profile_id,
                profile,
                source_profile_id=source_id,
            )
        finally:
            dialog.deleteLater()
        if self.window.input_studio:
            self.window.input_studio.copy_profile(source_id, profile_id)
            profile.input_studio_config = self.window.input_studio.get_profile_config(profile_id)
        if engine.add_custom_profile(profile_id, profile):
            self._persist()
            self.selected_profile_id = profile_id
            self.window.refresh_profiles()
            self.apply_profile(profile_id)
            self.window.toast("Perfil creado")
            return
        if any(stored_assets) and self.window.profile_manager:
            self.window.profile_manager.remove_profile_icon(profile_id)
            self.window.profile_manager.remove_profile_banner(profile_id)
        if self.window.input_studio:
            self.window.input_studio.remove_profile(profile_id)
        self.window.alert("No se pudo crear el perfil")

    @profile_action("editar el perfil")
    def edit_profile(self, profile_id: str) -> None:
        profile = self._profile_with_current_input(profile_id)
        if not profile:
            return
        dialog = ProfileEditorDialog(self.window, profile_id, profile)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            updated = copy.deepcopy(dialog.profile)
            updated.updated_at = self._now()
            if not updated.created_at and self.window.trigger_engine.is_custom_profile(profile_id):
                updated.created_at = updated.updated_at
            self._commit_media(dialog, profile_id, updated)
        finally:
            dialog.deleteLater()
        if self.window.input_studio:
            updated.input_studio_config = self.window.input_studio.get_profile_config(profile_id)
        if self.window.trigger_engine.update_profile(profile_id, updated):
            self._persist()
            if self.window.trigger_engine.get_current_profile() == profile_id:
                self.window.apply_profile(profile_id, force=True)
            self.selected_profile_id = profile_id
            self.window.refresh_profiles()
            self._call_later(0, lambda: self.refresh(force=True))
            self.window.toast("Perfil guardado")

    @profile_action("duplicar el perfil")
    def duplicate_profile(self, profile_id: str) -> None:
        engine = self.window.trigger_engine
        source = self._profile_with_current_input(profile_id)
        if not source or not engine:
            return
        duplicate = copy.deepcopy(source)
        duplicate.name = f"{source.name} copia"
        duplicate.category = "Personal"
        duplicate.origin = "user"
        duplicate.created_at = self._now()
        duplicate.updated_at = duplicate.created_at
        new_id = self._unique_profile_id(duplicate.name)
        manager = self.window.profile_manager
        copied_icon = ""
        copied_banner = ""
        if manager:
            icon_source = self._profile_icon_source(source)
            banner_source = self._profile_banner_source(profile_id, source)
            if icon_source:
                copied_icon = manager.store_profile_icon(icon_source, new_id)
            if banner_source:
                copied_banner = manager.store_profile_banner(banner_source, new_id)
        duplicate.icon_path = copied_icon
        duplicate.image_path = copied_icon
        duplicate.banner_path = copied_banner
        if self.window.input_studio:
            self.window.input_studio.copy_profile(profile_id, new_id)
            duplicate.input_studio_config = self.window.input_studio.get_profile_config(new_id)
        if engine.add_custom_profile(new_id, duplicate):
            self._persist()
            self.selected_profile_id = new_id
            self.window.refresh_profiles()
            self._call_later(0, lambda: self.refresh(force=True))
            self.window.toast("Perfil duplicado")
            return
        if manager:
            manager.remove_profile_icon(new_id)
            manager.remove_profile_banner(new_id)
        if self.window.input_studio:
            self.window.input_studio.remove_profile(new_id)
        self.window.alert("No se pudo duplicar el perfil")

    @profile_action("restaurar el perfil incluido")
    def reset_builtin_profile(self, profile_id: str) -> None:
        engine = self.window.trigger_engine
        profile = engine.get_profile(profile_id) if engine else None
        if not profile or engine.is_custom_profile(profile_id):
            return
        if (
            QMessageBox.question(
                self,
                "Restaurar perfil incluido",
                f"¿Restaurar ‘{profile.name}’ a su configuración original de Nikaido?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        manager = self.window.profile_manager
        if manager:
            manager.remove_profile_icon(profile_id)
            manager.remove_profile_banner(profile_id)
        if not engine.reset_builtin_profile(profile_id):
            self.window.alert("No se pudo restaurar el perfil")
            return
        restored = engine.get_profile(profile_id)
        if restored and self.window.input_studio:
            self.window.input_studio.set_profile_config(profile_id, restored.input_studio_config)
        self._persist()
        if engine.get_current_profile() == profile_id:
            self.window.apply_profile(profile_id, force=True)
        self.window.refresh_profiles()
        self.refresh(force=True)
        self.window.toast("Perfil restaurado")

    @profile_action("cambiar el favorito")
    def toggle_favorite(self, profile_id: str) -> None:
        manager = self.window.profile_manager
        if not manager:
            return
        if profile_id in self._favorite_ids():
            manager.remove_favorite(profile_id)
            self.window.toast("Quitado de favoritos")
        else:
            manager.add_favorite(profile_id)
            self.window.toast("Agregado a favoritos")
        self.window.request_config_save()
        self.refresh(force=True)

    @staticmethod
    def _profile_icon_source(profile: Any) -> str:
        candidate = str(
            getattr(profile, "icon_path", "")
            or getattr(profile, "image_path", "")
            or ""
        )
        return candidate if candidate and Path(candidate).is_file() else ""

    @staticmethod
    def _profile_banner_source(profile_id: str, profile: Any) -> str:
        banner_value = getattr(profile, "banner_path", None)
        custom = str(
            (getattr(profile, "image_path", "") if banner_value is None else banner_value)
            or ""
        )
        if custom and Path(custom).is_file():
            return custom
        presentation = profile_presentation(profile_id)
        if presentation:
            bundled = resource_path(presentation.cover_asset)
            if bundled.is_file():
                return str(bundled)
        return ""

    @staticmethod
    def _profile_cover_source(profile_id: str, profile: Any) -> str:
        """Alias histórico para la portada del perfil."""
        return ProfilesPage._profile_banner_source(profile_id, profile)

    def _commit_new_media(
        self,
        dialog: ProfileEditorDialog,
        profile_id: str,
        profile: Any,
        *,
        source_profile_id: str,
    ) -> tuple[str, str]:
        """Copia icono y banner a archivos independientes del perfil nuevo."""
        manager = self.window.profile_manager
        if not manager:
            profile.image_path = ""
            profile.icon_path = ""
            profile.banner_path = ""
            return "", ""

        icon_source = (
            dialog.icon_source
            if dialog.icon_changed
            else self._profile_icon_source(profile)
        )
        banner_source = (
            dialog.banner_source
            if dialog.banner_changed
            else self._profile_banner_source(source_profile_id, profile)
        )
        stored_icon = (
            manager.store_profile_icon(icon_source, profile_id) if icon_source else ""
        )
        stored_banner = (
            manager.store_profile_banner(banner_source, profile_id) if banner_source else ""
        )
        profile.icon_path = stored_icon or ""
        profile.image_path = profile.icon_path
        profile.banner_path = stored_banner or ""
        return stored_icon, stored_banner

    def _commit_new_image(
        self,
        dialog: ProfileEditorDialog,
        profile_id: str,
        profile: Any,
        *,
        source_profile_id: str,
    ) -> str:
        """Alias compatible; devuelve el primer recurso visual guardado."""
        icon, banner = self._commit_new_media(
            dialog, profile_id, profile, source_profile_id=source_profile_id
        )
        return icon or banner

    def _commit_media(
        self, dialog: ProfileEditorDialog, profile_id: str, profile: Any
    ) -> None:
        manager = self.window.profile_manager
        if not manager:
            return

        # Los perfiles antiguos podían usar el mismo archivo para icono y
        # portada. Antes de cambiar o quitar el icono, independizamos el
        # banner para no modificarlo accidentalmente.
        current_icon = str(
            getattr(profile, "icon_path", "")
            or getattr(profile, "image_path", "")
            or ""
        )
        current_banner = str(getattr(profile, "banner_path", "") or "")
        if (
            dialog.icon_changed
            and not dialog.banner_changed
            and current_icon
            and current_icon == current_banner
            and Path(current_icon).is_file()
        ):
            preserved_banner = manager.store_profile_banner(current_icon, profile_id)
            if preserved_banner:
                profile.banner_path = preserved_banner

        if dialog.icon_changed:
            if not dialog.icon_source:
                manager.remove_profile_icon(profile_id)
                profile.icon_path = ""
                profile.image_path = ""
            else:
                stored = manager.store_profile_icon(dialog.icon_source, profile_id)
                if stored:
                    profile.icon_path = stored
                    profile.image_path = stored
        else:
            profile.icon_path = str(
                getattr(profile, "icon_path", "")
                or getattr(profile, "image_path", "")
                or ""
            )
            profile.image_path = profile.icon_path

        if dialog.banner_changed:
            if not dialog.banner_source:
                manager.remove_profile_banner(profile_id)
                profile.banner_path = ""
            else:
                stored = manager.store_profile_banner(dialog.banner_source, profile_id)
                if stored:
                    profile.banner_path = stored

    def _commit_image(
        self, dialog: ProfileEditorDialog, profile_id: str, profile: Any
    ) -> None:
        """Alias de compatibilidad con extensiones de la interfaz anterior."""
        self._commit_media(dialog, profile_id, profile)

    @profile_action("eliminar el perfil")
    def delete_profile(self, profile_id: str) -> None:
        engine = self.window.trigger_engine
        profile = engine.get_profile(profile_id) if engine else None
        if not profile or not engine.is_custom_profile(profile_id):
            return
        if (
            QMessageBox.question(
                self,
                "Eliminar perfil",
                f"¿Eliminar ‘{profile.name}’? Esta acción no se puede deshacer.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        was_active = engine.get_current_profile() == profile_id
        if engine.remove_profile(profile_id):
            if self.window.input_studio:
                self.window.input_studio.remove_profile(profile_id)
            manager = self.window.profile_manager
            if manager:
                manager.remove_profile_icon(profile_id)
                manager.remove_profile_banner(profile_id)
                manager.remove_favorite(profile_id)
            self._persist()
            self.selected_profile_id = DEFAULT_PROFILE_ID
            if was_active:
                self.window.apply_profile(DEFAULT_PROFILE_ID, force=True)
            self.window.refresh_profiles()
            self.refresh(force=True)
            self.window.toast("Perfil eliminado")

    def _persist(self) -> None:
        manager = self.window.profile_manager
        engine = self.window.trigger_engine
        if not manager or not engine:
            return
        manager.set_custom_profiles(engine.export_custom_profiles_to_dict())
        manager.set_setting("profile_overrides", engine.export_profile_overrides())
        manager.set_setting("profile_trigger_vibration", engine.export_vibration_overrides())
        if self.window.input_studio:
            manager.set_setting("profile_input_studio", self.window.input_studio.export_profiles())
        self.window.request_config_save()

    @profile_action("importar el perfil")
    def import_profile(self) -> None:
        from src.trigger_engine import MAX_CUSTOM_TRIGGER_PROFILES

        engine = self.window.trigger_engine
        if engine and len(engine.export_custom_profiles_to_dict()) >= MAX_CUSTOM_TRIGGER_PROFILES:
            self.window.alert(
                f"Alcanzaste el límite de {MAX_CUSTOM_TRIGGER_PROFILES} perfiles personalizados."
            )
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar perfil",
            "",
            "Perfil Nikaido (*.Nika *.nika);;Perfiles antiguos (*.json)",
        )
        if not path or not self.window.profile_manager:
            return
        profile_id = self.window.profile_manager.import_profile(path)
        if not profile_id:
            self.window.alert("No se pudo importar el perfil")
            return
        from src.trigger_engine import WeaponProfile

        payload = self.window.profile_manager.get_custom_profiles().get(profile_id)
        try:
            profile = WeaponProfile.from_dict(payload)
        except Exception as exc:
            self.window.alert(f"Perfil inválido: {exc}")
            return
        profile.origin = "imported"
        profile.created_at = profile.created_at or self._now()
        profile.updated_at = self._now()
        if profile.input_studio_config and self.window.input_studio:
            self.window.input_studio.set_profile_config(profile_id, profile.input_studio_config)
        if not self.window.trigger_engine.add_custom_profile(profile_id, profile):
            self.window.alert("El perfil importado usa un ID reservado o duplicado")
            return
        if self.window.macro_engine:
            self.window.macro_engine.load_macros(self.window.profile_manager.get_macros())
        self._persist()
        self.selected_profile_id = profile_id
        self.window.refresh_profiles()
        self.refresh(force=True)
        self.window.toast("Perfil importado")

    @profile_action("exportar el perfil")
    def export_profile(self, profile_id: Optional[str] = None) -> None:
        engine = self.window.trigger_engine
        profile_id = profile_id or self.selected_profile_id or (
            engine.get_current_profile() if engine else None
        )
        profile = self._profile_with_current_input(profile_id) if profile_id else None
        if not profile:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar perfil",
            f"{profile_id}.Nika",
            "Perfil Nikaido (*.Nika)",
        )
        if (
            path
            and self.window.profile_manager
            and self.window.profile_manager.export_profile(profile_id, path, profile.to_dict())
        ):
            self.window.toast("Perfil exportado")

    def export_active(self) -> None:
        """Compatibilidad con acciones anteriores que exportaban el perfil activo."""
        self.export_profile()


# Compatibilidad pública para plugins y módulos de versiones anteriores.
__all__ = ["ProfileEditorDialog", "ProfilesPage", "profile_image_widget"]
