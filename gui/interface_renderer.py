"""Renderer seguro y responsivo para interfaces creadas con Nikaido UI Studio."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageSequence, ImageTk

from gui.ui_theme import UIElement, UILayout, condition_matches, substitute_variables

logger = logging.getLogger(__name__)

ActionCallback = Callable[[str, Dict[str, Any], UIElement], None]
ContextProvider = Callable[[], Dict[str, Any]]


class InterfaceRenderer(tk.Frame):
    """Dibuja un :class:`UILayout` sobre un Canvas y despacha acciones permitidas."""

    UPDATE_INTERVAL_MS = 250
    DEFAULT_GIF_DELAY_MS = 100
    MAX_SOURCE_IMAGE_PIXELS = 20_000_000
    MAX_ANIMATION_FRAMES = 240
    MAX_CACHED_ANIMATION_PIXELS = 80_000_000

    def __init__(
        self,
        parent: tk.Misc,
        layout: UILayout,
        *,
        action_callback: ActionCallback,
        context_provider: ContextProvider,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(parent, bg=str(layout.canvas.get("background", "#17171C")), highlightthickness=0)
        self.layout = layout
        self.action_callback = action_callback
        self.context_provider = context_provider
        self.on_error = on_error

        self.canvas = tk.Canvas(
            self,
            bg=str(layout.canvas.get("background", "#17171C")),
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self._items: Dict[str, int] = {}
        self._photos: Dict[str, ImageTk.PhotoImage] = {}
        self._frame_cache: Dict[Tuple[str, str, int, int, int], List[Tuple[Image.Image, int]]] = {}
        self._gif_index: Dict[str, int] = {}
        self._gif_jobs: Dict[str, str] = {}
        self._render_state: Dict[str, str] = {}
        self._last_text: Dict[str, str] = {}
        self._last_visibility: Dict[str, bool] = {}
        self._hovered_id: Optional[str] = None
        self._pressed_id: Optional[str] = None
        self.current_page = layout.default_page
        self._page_history: List[str] = []
        self._tooltip_items: List[int] = []
        self._update_job: Optional[str] = None
        self._resize_job: Optional[str] = None
        self._destroyed = False
        self._scale = (1.0, 1.0)
        self._offset = (0.0, 0.0)

        self.canvas.bind("<Configure>", self._on_configure)
        self.canvas.bind("<Leave>", lambda _e: self._hide_tooltip())
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.after_idle(self.render_all)
        self._schedule_dynamic_update()

    # ------------------------------------------------------------------
    # Ciclo de vida y geometría
    # ------------------------------------------------------------------

    def set_layout(self, layout: UILayout) -> None:
        self._cancel_all_jobs()
        self.layout = layout
        self.current_page = layout.default_page
        self._page_history.clear()
        self.configure(bg=str(layout.canvas.get("background", "#17171C")))
        self.canvas.configure(bg=str(layout.canvas.get("background", "#17171C")))
        self._frame_cache.clear()
        self._gif_index.clear()
        self._last_text.clear()
        self._last_visibility.clear()
        self.render_all()
        self._schedule_dynamic_update()

    def _on_configure(self, _event: tk.Event) -> None:
        if self._resize_job:
            try:
                self.after_cancel(self._resize_job)
            except tk.TclError:
                pass
        self._resize_job = self.after(80, self.render_all)

    def _compute_transform(self) -> Tuple[float, float, float, float]:
        logical_w = max(1.0, float(self.layout.canvas.get("width", 900)))
        logical_h = max(1.0, float(self.layout.canvas.get("height", 560)))
        actual_w = max(1.0, float(self.canvas.winfo_width()))
        actual_h = max(1.0, float(self.canvas.winfo_height()))
        mode = str(self.layout.canvas.get("scale_mode", "contain"))

        if mode == "stretch":
            sx, sy = actual_w / logical_w, actual_h / logical_h
            ox = oy = 0.0
        else:
            scale = max(actual_w / logical_w, actual_h / logical_h) if mode == "cover" else min(
                actual_w / logical_w, actual_h / logical_h
            )
            sx = sy = scale
            ox = (actual_w - logical_w * scale) / 2
            oy = (actual_h - logical_h * scale) / 2
        self._scale = (sx, sy)
        self._offset = (ox, oy)
        return sx, sy, ox, oy

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render_all(self) -> None:
        if self._destroyed or not self.winfo_exists():
            return
        self._resize_job = None
        self._cancel_gif_jobs()
        self.canvas.delete("all")
        self._items.clear()
        self._photos.clear()
        self._render_state.clear()
        self._hide_tooltip()

        context = self._context()
        self._compute_transform()
        for element in sorted(self.layout.elements, key=lambda item: item.z_index):
            if self._element_on_current_page(element):
                self._render_element(element, context=context, state="normal")

    def _element_on_current_page(self, element: UIElement) -> bool:
        return element.page in {"*", self.current_page}

    def open_page(self, page_id: str, *, remember: bool = True) -> bool:
        """Abre una pantalla interna del tema y conserva historial para page.back."""
        valid_pages = {str(page.get("id", "")) for page in self.layout.pages}
        if page_id not in valid_pages:
            logger.warning("Pantalla de tema inexistente: %s", page_id)
            return False
        if page_id == self.current_page:
            return True
        if remember:
            self._page_history.append(self.current_page)
            self._page_history = self._page_history[-50:]
        self.current_page = page_id
        self.render_all()
        return True

    def go_back_page(self) -> bool:
        if not self._page_history:
            if self.current_page != self.layout.default_page:
                return self.open_page(self.layout.default_page, remember=False)
            return False
        previous = self._page_history.pop()
        return self.open_page(previous, remember=False)

    def _render_element(self, element: UIElement, *, context: Optional[Dict[str, Any]] = None,
                        state: str = "normal") -> None:
        context = context or self._context()
        visible = bool(element.visible and condition_matches(element.visible_when, context))
        self._last_visibility[element.id] = visible
        if not visible:
            self._delete_element(element.id)
            return

        sx, sy = self._scale
        ox, oy = self._offset
        width = max(1, int(round(element.width * sx)))
        height = max(1, int(round(element.height * sy)))
        x = ox + element.x * sx
        y = oy + element.y * sy

        image, delay = self._build_element_image(element, width, height, context, state, frame_index=0)
        if image is None:
            self._delete_element(element.id)
            return

        photo = ImageTk.PhotoImage(image)
        old = self._items.get(element.id)
        tags = ("ui-element", f"element:{element.id}")
        if old and self.canvas.type(old):
            self.canvas.coords(old, x, y)
            self.canvas.itemconfigure(old, image=photo, state="normal")
            item = old
        else:
            item = self.canvas.create_image(x, y, anchor="nw", image=photo, tags=tags)
            self._items[element.id] = item
            self._bind_item(element, item)
        self._photos[element.id] = photo
        self._render_state[element.id] = state

        self._last_text[element.id] = self._dynamic_content_key(element, context)

        frames = self._load_frames(element, state, width, height, context)
        if len(frames) > 1:
            self._gif_index[element.id] = 0
            first_delay = frames[0][1] or delay or self.DEFAULT_GIF_DELAY_MS
            self._schedule_gif(element, state, width, height, max(20, first_delay))

    def _delete_element(self, element_id: str) -> None:
        item = self._items.pop(element_id, None)
        if item:
            self.canvas.delete(item)
        self._photos.pop(element_id, None)
        job = self._gif_jobs.pop(element_id, None)
        if job:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass

    def _build_element_image(
        self,
        element: UIElement,
        width: int,
        height: int,
        context: Dict[str, Any],
        state: str,
        *,
        frame_index: int,
    ) -> Tuple[Optional[Image.Image], int]:
        frames = self._load_frames(element, state, width, height, context)
        if not frames:
            return None, self.DEFAULT_GIF_DELAY_MS
        image, delay = frames[frame_index % len(frames)]
        return image.copy(), delay

    def _dynamic_content_key(self, element: UIElement, context: Dict[str, Any]) -> str:
        text = substitute_variables(element.text, context)
        if element.type in {"text", "speech_bubble", "button"}:
            return text
        if element.type == "progress":
            variable = str(element.metadata.get("value_variable", "battery"))
            return f"{variable}={context.get(variable, 0)}|{text}"
        return ""

    def _load_frames(
        self, element: UIElement, state: str, width: int, height: int, context: Dict[str, Any]
    ) -> List[Tuple[Image.Image, int]]:
        dynamic_key = self._dynamic_content_key(element, context)
        cache_state = f"{state}:{dynamic_key}" if dynamic_key else state
        cache_key = (element.id, cache_state, width, height, int(round(element.rotation)))
        cached = self._frame_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            if element.type == "image":
                frames = self._image_frames(element, state, width, height)
            elif element.type == "text":
                frames = [(self._text_image(element, width, height, dynamic_key, state), 0)]
            elif element.type == "button":
                frames = [(self._button_image(element, width, height, dynamic_key, state), 0)]
            elif element.type == "speech_bubble":
                frames = [(self._speech_bubble_image(element, width, height, substitute_variables(element.text, context), state), 0)]
            elif element.type == "progress":
                frames = [(self._progress_image(element, width, height, context, state), 0)]
            elif element.type in {"rectangle", "ellipse", "hotspot"}:
                frames = [(self._shape_image(element, width, height, state), 0)]
            else:
                frames = []
        except Exception as exc:
            logger.warning("No se pudo renderizar %s: %s", element.id, exc)
            frames = [(self._error_placeholder(width, height), 0)]

        result: List[Tuple[Image.Image, int]] = []
        for image, delay in frames:
            if element.rotation:
                image = image.rotate(-float(element.rotation), expand=True, resample=Image.Resampling.BICUBIC)
            if element.opacity < 1:
                alpha = image.getchannel("A").point(lambda p: int(p * max(0.0, min(1.0, element.opacity))))
                image.putalpha(alpha)
            result.append((image, delay))
        self._frame_cache[cache_key] = result
        return result

    def _shape_image(self, element: UIElement, width: int, height: int, state: str) -> Image.Image:
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        if element.type == "hotspot":
            return image
        draw = ImageDraw.Draw(image)
        fill = self._state_fill(element, state)
        outline = element.outline or None
        outline_width = max(0, int(round(element.outline_width * min(self._scale))))
        box = [0, 0, max(0, width - 1), max(0, height - 1)]
        if element.type == "ellipse":
            draw.ellipse(box, fill=fill or None, outline=outline, width=max(1, outline_width) if outline else 1)
        else:
            radius = max(0, int(round(element.radius * min(self._scale))))
            draw.rounded_rectangle(
                box,
                radius=min(radius, width // 2, height // 2),
                fill=fill or None,
                outline=outline,
                width=max(1, outline_width) if outline else 1,
            )
        return image

    def _button_image(self, element: UIElement, width: int, height: int, text: str, state: str) -> Image.Image:
        image = self._shape_image(element, width, height, state)
        draw = ImageDraw.Draw(image)
        font_size = max(6, int(round(element.font_size * min(self._scale))))
        font = self._font(element.font_family, font_size, element.font_weight)
        color = element.text_color
        wrapped = self._wrap_text(draw, text, font, max(1, width - 16))
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=max(2, int(font_size * 0.2)), align="center")
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        draw.multiline_text(
            ((width - text_w) / 2, (height - text_h) / 2 - bbox[1]),
            wrapped, fill=color, font=font, spacing=max(2, int(font_size * 0.2)), align="center"
        )
        return image

    def _progress_image(
        self, element: UIElement, width: int, height: int, context: Dict[str, Any], state: str
    ) -> Image.Image:
        """Dibuja una barra dinámica enlazada a una variable del contexto."""
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        scale = min(self._scale)
        radius = max(0, int(round(element.radius * scale)))
        track = str(element.metadata.get("track_fill", "#242733"))
        foreground = self._state_fill(element, state) or "#7C6FF0"
        outline = element.outline or None
        outline_width = max(1, int(round(element.outline_width * scale))) if outline else 1
        box = [0, 0, max(0, width - 1), max(0, height - 1)]
        draw.rounded_rectangle(
            box, radius=min(radius, width // 2, height // 2), fill=track,
            outline=outline, width=outline_width,
        )

        variable = str(element.metadata.get("value_variable", "battery"))
        try:
            value = float(context.get(variable, 0))
            minimum = float(element.metadata.get("minimum", 0))
            maximum = float(element.metadata.get("maximum", 100))
        except (TypeError, ValueError, OverflowError):
            value, minimum, maximum = 0.0, 0.0, 100.0
        span = max(1e-9, maximum - minimum)
        ratio = max(0.0, min(1.0, (value - minimum) / span))
        direction = str(element.metadata.get("direction", "horizontal"))
        if direction == "vertical":
            filled_height = int(round(height * ratio))
            fill_box = [0, height - filled_height, width - 1, height - 1]
        else:
            filled_width = int(round(width * ratio))
            fill_box = [0, 0, max(0, filled_width - 1), height - 1]
        if ratio > 0:
            draw.rounded_rectangle(
                fill_box, radius=min(radius, max(1, (fill_box[2] - fill_box[0] + 1) // 2), max(1, (fill_box[3] - fill_box[1] + 1) // 2)),
                fill=foreground,
            )

        label = substitute_variables(element.text, context)
        if label:
            font_size = max(6, int(round(element.font_size * scale)))
            font = self._font(element.font_family, font_size, element.font_weight)
            bbox = draw.textbbox((0, 0), label, font=font)
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(
                ((width - text_w) / 2, (height - text_h) / 2 - bbox[1]),
                label, fill=element.text_color, font=font,
            )
        return image

    def _speech_bubble_image(
        self, element: UIElement, width: int, height: int, text: str, state: str
    ) -> Image.Image:
        """Dibuja un globo redondeado con cola configurable y texto centrado."""
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        scale = min(self._scale)
        tail_height = max(8, min(height // 3, int(round(float(element.metadata.get("tail_height", 18)) * scale))))
        body_height = max(1, height - tail_height)
        radius = max(0, int(round(element.radius * scale)))
        fill = self._state_fill(element, state) or None
        outline = element.outline or None
        outline_width = max(1, int(round(element.outline_width * scale))) if outline else 1
        body_box = [0, 0, max(0, width - 1), max(0, body_height - 1)]
        draw.rounded_rectangle(
            body_box, radius=min(radius, width // 2, body_height // 2),
            fill=fill, outline=outline, width=outline_width,
        )

        tail_position = str(element.metadata.get("tail_position", "left")).lower()
        tail_width = max(12, min(width // 2, int(round(float(element.metadata.get("tail_width", 30)) * scale))))
        if tail_position == "right":
            center = max(tail_width // 2 + 4, width - max(18, int(width * 0.18)))
        elif tail_position == "center":
            center = width // 2
        else:
            center = min(width - tail_width // 2 - 4, max(tail_width // 2 + 4, int(width * 0.18)))
        points = [
            (center - tail_width // 2, body_height - 2),
            (center + tail_width // 2, body_height - 2),
            (center, height - 1),
        ]
        draw.polygon(points, fill=fill, outline=outline)
        if outline and outline_width > 1:
            draw.line([points[0], points[2], points[1]], fill=outline, width=outline_width, joint="curve")

        font_size = max(6, int(round(element.font_size * scale)))
        font = self._font(element.font_family, font_size, element.font_weight)
        padding = max(6, int(round(float(element.metadata.get("padding", 14)) * scale)))
        available_width = max(1, width - padding * 2)
        wrapped = self._wrap_text(draw, text, font, available_width)
        spacing = max(2, int(font_size * 0.2))
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing, align="center")
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        draw.multiline_text(
            ((width - text_w) / 2, (body_height - text_h) / 2 - bbox[1]),
            wrapped, fill=element.text_color, font=font, spacing=spacing, align="center",
        )
        return image

    def _text_image(self, element: UIElement, width: int, height: int, text: str, state: str) -> Image.Image:
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        font_size = max(6, int(round(element.font_size * min(self._scale))))
        font = self._font(element.font_family, font_size, element.font_weight)
        color = self._state_fill(element, state) if state != "normal" and element.hover_fill else element.text_color
        spacing = max(2, int(font_size * 0.22))
        wrapped = self._wrap_text(draw, text, font, width)
        align = element.text_align if element.text_align in {"left", "center", "right"} else "left"
        anchor_x = 0 if align == "left" else width / 2 if align == "center" else width
        draw.multiline_text(
            (anchor_x, 0),
            wrapped,
            fill=color,
            font=font,
            spacing=spacing,
            align=align,
            anchor="ma" if align == "center" else "ra" if align == "right" else "la",
        )
        return image

    def _image_frames(self, element: UIElement, state: str, width: int, height: int) -> List[Tuple[Image.Image, int]]:
        source = element.source
        if state == "hover" and element.metadata.get("hover_source"):
            source = str(element.metadata["hover_source"])
        elif state == "pressed" and element.metadata.get("pressed_source"):
            source = str(element.metadata["pressed_source"])
        path = self.layout.resolve_asset(source)
        if not path or not path.is_file():
            return [(self._error_placeholder(width, height), 0)]

        fit = str(element.metadata.get("fit", "stretch"))
        frames: List[Tuple[Image.Image, int]] = []
        with Image.open(path) as source_image:
            source_width, source_height = source_image.size
            if (
                source_width <= 0
                or source_height <= 0
                or source_width * source_height > self.MAX_SOURCE_IMAGE_PIXELS
            ):
                return [(self._error_placeholder(width, height), 0)]
            output_pixels = max(1, int(width) * int(height))
            max_frames = min(
                self.MAX_ANIMATION_FRAMES,
                max(1, self.MAX_CACHED_ANIMATION_PIXELS // output_pixels),
            )
            for raw in ImageSequence.Iterator(source_image):
                frame = raw.convert("RGBA")
                frame = self._fit_image(frame, width, height, fit)
                duration = int(raw.info.get("duration", source_image.info.get("duration", self.DEFAULT_GIF_DELAY_MS)))
                frames.append((frame, max(20, duration)))
                # Evita que un GIF monstruoso devore memoria sin pedir permiso.
                if len(frames) >= max_frames:
                    break
        return frames or [(self._error_placeholder(width, height), 0)]

    @staticmethod
    def _fit_image(image: Image.Image, width: int, height: int, mode: str) -> Image.Image:
        if mode == "contain":
            copy = image.copy()
            copy.thumbnail((width, height), Image.Resampling.LANCZOS)
            output = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            output.alpha_composite(copy, ((width - copy.width) // 2, (height - copy.height) // 2))
            return output
        if mode == "cover":
            scale = max(width / max(1, image.width), height / max(1, image.height))
            resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
            left = max(0, (resized.width - width) // 2)
            top = max(0, (resized.height - height) // 2)
            return resized.crop((left, top, left + width, top + height))
        return image.resize((width, height), Image.Resampling.LANCZOS)

    @staticmethod
    def _error_placeholder(width: int, height: int) -> Image.Image:
        image = Image.new("RGBA", (width, height), (74, 38, 48, 230))
        draw = ImageDraw.Draw(image)
        draw.rectangle([0, 0, width - 1, height - 1], outline=(229, 72, 77, 255), width=2)
        draw.line([0, 0, width - 1, height - 1], fill=(229, 72, 77, 255), width=2)
        draw.line([width - 1, 0, 0, height - 1], fill=(229, 72, 77, 255), width=2)
        return image

    @staticmethod
    def _font(family: str, size: int, weight: str) -> ImageFont.ImageFont:
        candidates: List[str] = []
        family = (family or "Segoe UI").strip()
        compact = family.replace(" ", "")
        bold = str(weight).lower() in {"bold", "semibold", "600", "700"}
        if os.name == "nt":
            windir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
            if family.lower().startswith("segoe"):
                candidates.extend([str(windir / ("seguisb.ttf" if bold else "segoeui.ttf"))])
            candidates.extend([str(windir / f"{compact}{'bd' if bold else ''}.ttf")])
        candidates.extend([
            family,
            f"{family} Bold" if bold else family,
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ])
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size=size)
            except (OSError, ValueError):
                continue
        return ImageFont.load_default()

    @staticmethod
    def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> str:
        if width <= 1:
            return text
        lines: List[str] = []
        for paragraph in str(text).splitlines() or [""]:
            words = paragraph.split(" ")
            current = ""
            for word in words:
                candidate = word if not current else f"{current} {word}"
                if draw.textlength(candidate, font=font) <= width or not current:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return "\n".join(lines)

    def _state_fill(self, element: UIElement, state: str) -> str:
        if state == "pressed" and element.pressed_fill:
            return element.pressed_fill
        if state == "hover" and element.hover_fill:
            return element.hover_fill
        return element.fill

    # ------------------------------------------------------------------
    # Eventos, estados y acciones
    # ------------------------------------------------------------------

    def _bind_item(self, element: UIElement, item: int) -> None:
        if element.action == "none" and not element.tooltip and not element.hover_fill and not element.metadata.get("hover_source"):
            return
        self.canvas.tag_bind(item, "<Enter>", lambda event, eid=element.id: self._on_enter(event, eid))
        self.canvas.tag_bind(item, "<Leave>", lambda event, eid=element.id: self._on_leave(event, eid))
        self.canvas.tag_bind(item, "<ButtonPress-1>", lambda event, eid=element.id: self._on_press(event, eid))
        self.canvas.tag_bind(item, "<ButtonRelease-1>", lambda event, eid=element.id: self._on_release(event, eid))
        self.canvas.tag_bind(item, "<Motion>", lambda event, eid=element.id: self._on_motion(event, eid))

    def _element(self, element_id: str) -> Optional[UIElement]:
        return next((element for element in self.layout.elements if element.id == element_id), None)

    def _on_enter(self, event: tk.Event, element_id: str) -> None:
        element = self._element(element_id)
        if not element:
            return
        self._hovered_id = element_id
        try:
            self.canvas.configure(cursor=element.cursor or "hand2")
        except tk.TclError:
            self.canvas.configure(cursor="hand2")
        self._rerender_state(element, "hover")
        if element.tooltip:
            self._show_tooltip(event.x, event.y, substitute_variables(element.tooltip, self._context()))

    def _on_leave(self, _event: tk.Event, element_id: str) -> None:
        element = self._element(element_id)
        if not element:
            return
        self._hovered_id = None
        self._pressed_id = None
        self.canvas.configure(cursor="")
        self._hide_tooltip()
        self._rerender_state(element, "normal")

    def _on_press(self, _event: tk.Event, element_id: str) -> None:
        element = self._element(element_id)
        if not element:
            return
        self._pressed_id = element_id
        self._rerender_state(element, "pressed")

    def _on_release(self, event: tk.Event, element_id: str) -> None:
        element = self._element(element_id)
        if not element:
            return
        was_pressed = self._pressed_id == element_id
        self._pressed_id = None
        self._rerender_state(element, "hover" if self._hovered_id == element_id else "normal")
        if was_pressed and element.action != "none":
            try:
                if element.action == "page.open":
                    self.open_page(str(element.action_args.get("page", "")))
                elif element.action == "page.back":
                    self.go_back_page()
                else:
                    self.action_callback(element.action, dict(element.action_args), element)
            except Exception as exc:
                logger.exception("Error ejecutando acción de tema: %s", element.action)
                if self.on_error:
                    self.on_error(str(exc))
        if self._destroyed or not self.winfo_exists():
            return
        if element.tooltip:
            self._show_tooltip(event.x, event.y, substitute_variables(element.tooltip, self._context()))

    def _on_motion(self, event: tk.Event, element_id: str) -> None:
        element = self._element(element_id)
        if element and element.tooltip:
            self._show_tooltip(event.x, event.y, substitute_variables(element.tooltip, self._context()))

    def _rerender_state(self, element: UIElement, state: str) -> None:
        if self._render_state.get(element.id) == state:
            return
        self._frame_cache = {key: value for key, value in self._frame_cache.items() if key[0] != element.id}
        job = self._gif_jobs.pop(element.id, None)
        if job:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._render_element(element, context=self._context(), state=state)

    # ------------------------------------------------------------------
    # GIF y actualización dinámica
    # ------------------------------------------------------------------

    def _schedule_gif(self, element: UIElement, state: str, width: int, height: int, delay: int) -> None:
        def advance() -> None:
            if self._destroyed or element.id not in self._items:
                return
            current_state = self._render_state.get(element.id, state)
            frames = self._load_frames(element, current_state, width, height, self._context())
            if len(frames) <= 1:
                return
            index = (self._gif_index.get(element.id, 0) + 1) % len(frames)
            self._gif_index[element.id] = index
            image, next_delay = frames[index]
            photo = ImageTk.PhotoImage(image)
            item = self._items.get(element.id)
            if item:
                try:
                    self.canvas.itemconfigure(item, image=photo)
                    self._photos[element.id] = photo
                except tk.TclError:
                    return
            self._gif_jobs[element.id] = self.after(max(20, next_delay), advance)

        self._gif_jobs[element.id] = self.after(max(20, delay), advance)

    def _schedule_dynamic_update(self) -> None:
        if self._destroyed:
            return
        if self._update_job:
            try:
                self.after_cancel(self._update_job)
            except tk.TclError:
                pass
        self._update_job = self.after(self.UPDATE_INTERVAL_MS, self._dynamic_update)

    def _dynamic_update(self) -> None:
        self._update_job = None
        if self._destroyed:
            return
        context = self._context()
        for element in self.layout.elements:
            if not self._element_on_current_page(element):
                self._delete_element(element.id)
                self._last_visibility[element.id] = False
                continue
            should_show = bool(element.visible and condition_matches(element.visible_when, context))
            was_visible = self._last_visibility.get(element.id)
            if should_show != was_visible:
                self._frame_cache = {key: value for key, value in self._frame_cache.items() if key[0] != element.id}
                self._render_element(element, context=context, state=self._render_state.get(element.id, "normal"))
                continue
            if should_show and element.type in {"text", "speech_bubble", "button", "progress"}:
                current = self._dynamic_content_key(element, context)
                if current != self._last_text.get(element.id):
                    self._frame_cache = {key: value for key, value in self._frame_cache.items() if key[0] != element.id}
                    self._render_element(element, context=context, state=self._render_state.get(element.id, "normal"))
        self._schedule_dynamic_update()

    def _context(self) -> Dict[str, Any]:
        try:
            context = dict(self.context_provider() or {})
        except Exception:
            logger.exception("No se pudo obtener el contexto dinámico del tema")
            context = {}
        now = datetime.now()
        context.setdefault("time", now.strftime("%H:%M"))
        context.setdefault("date", now.strftime("%d/%m/%Y"))
        context.setdefault("current_page", self.current_page)
        return context

    # ------------------------------------------------------------------
    # Tooltip y limpieza
    # ------------------------------------------------------------------

    def _show_tooltip(self, x: int, y: int, text: str) -> None:
        self._hide_tooltip()
        if not text:
            return
        font = ("Segoe UI", 10)
        temp = self.canvas.create_text(x + 14, y + 18, text=text, anchor="nw", font=font)
        bbox = self.canvas.bbox(temp)
        if not bbox:
            return
        self.canvas.delete(temp)
        x1, y1, x2, y2 = bbox
        pad = 6
        rect = self.canvas.create_rectangle(
            x1 - pad, y1 - pad, x2 + pad, y2 + pad,
            fill="#111116", outline="#7C6FF0", width=1, tags="tooltip"
        )
        label = self.canvas.create_text(
            x + 14, y + 18, text=text, anchor="nw", fill="#F2F1F5", font=font, tags="tooltip"
        )
        self._tooltip_items = [rect, label]
        self.canvas.tag_raise("tooltip")

    def _hide_tooltip(self) -> None:
        for item in self._tooltip_items:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self._tooltip_items.clear()

    def _cancel_gif_jobs(self) -> None:
        for job in list(self._gif_jobs.values()):
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._gif_jobs.clear()

    def _cancel_all_jobs(self) -> None:
        self._cancel_gif_jobs()
        for job in (self._update_job, self._resize_job):
            if job:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        self._update_job = None
        self._resize_job = None

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        self._destroyed = True
        self._cancel_all_jobs()
