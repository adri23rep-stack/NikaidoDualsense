from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "gui" / "pages" / "profiles.py").read_text(encoding="utf-8")
GALLERY = (ROOT / "gui" / "profile_gallery.py").read_text(encoding="utf-8")
EDITOR = (ROOT / "gui" / "profile_editor.py").read_text(encoding="utf-8")
VISUALS = (ROOT / "gui" / "profile_visuals.py").read_text(encoding="utf-8")


def test_profile_gallery_has_no_continuous_animation_clock():
    assert "_animation_timer" not in PAGE
    assert "QTimer(" not in GALLERY


def test_cards_use_cached_static_covers_instead_of_rgb_widgets():
    assert "ProfileCoverWidget" in GALLERY
    assert "_pixmap_cache" in GALLERY
    card = GALLERY.split("class ProfileGalleryCard", 1)[1].split("class ProfileFeatureRow", 1)[0]
    assert "NeonEffectIcon" not in card


def test_selection_updates_only_card_states_and_detail_panel():
    method = PAGE.split("    def select_profile", 1)[1].split("    def _macro_count", 1)[0]
    assert "_refresh_detail()" in method
    assert "refresh(force=True)" not in method
    assert "set_selected_state" in method


def test_search_and_resize_are_debounced():
    assert "self._filter_timer.setInterval(180)" in PAGE
    assert "self.search_edit.textChanged.connect(lambda _text: self._filter_timer.start())" in PAGE
    assert "self._responsive_timer.setInterval(120)" in PAGE


def test_profile_avatar_uses_flat_render_without_animated_halo_or_arc():
    paint = VISUALS.split("def paintEvent", 1)[1]
    assert "QRadialGradient" not in paint
    assert "drawArc" not in paint
    assert "Render plano y barato" in paint


def test_editor_preview_is_limited_and_respects_reduce_motion():
    assert "self._preview_timer.setInterval(250)" in EDITOR
    assert "if not reduce_motion:" in EDITOR
