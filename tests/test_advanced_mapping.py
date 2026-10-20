import unittest
from types import SimpleNamespace

from src.advanced_mapping import AdvancedMapper, sanitize_config
from src.emulator import EmulatorManager


class FakeEmulator:
    def __init__(self):
        self.states = []

    def set_advanced_button_state(self, buttons, blocked_sources):
        self.states.append((set(buttons), set(blocked_sources)))


class FakeOutput:
    def __init__(self):
        self.events = []

    def press_keyboard(self, value):
        self.events.append(('key_down', value))

    def release_keyboard(self, value):
        self.events.append(('key_up', value))

    def press_mouse(self, value):
        self.events.append(('mouse_down', value))

    def release_mouse(self, value):
        self.events.append(('mouse_up', value))

    def move_mouse(self, value):
        self.events.append(('move', value))

    def release_all(self):
        self.events.append(('release_all',))


class FakeMacroEngine:
    def __init__(self):
        self.played = []

    def play_macro(self, macro_id):
        self.played.append(macro_id)
        return True


def state(**buttons):
    return SimpleNamespace(buttons=buttons)


class AdvancedMappingTests(unittest.TestCase):
    def setUp(self):
        self.emulator = FakeEmulator()
        self.output = FakeOutput()
        self.macro = FakeMacroEngine()
        self.active_profile = 'assault_rifle'
        self.applied_profiles = []
        self.mapper = AdvancedMapper(
            emulator=self.emulator,
            macro_engine=self.macro,
            profile_getter=lambda: self.active_profile,
            profile_applier=self._apply_profile,
            output=self.output,
        )

    def _apply_profile(self, profile_id):
        self.active_profile = profile_id
        self.applied_profiles.append(profile_id)
        return True

    def _set_config(self, layers):
        self.mapper.set_config({'enabled': True, 'default_layer': 'base', 'layers': layers})

    def test_hold_controller_action_replaces_physical_button(self):
        self._set_config({'base': {
            'cross': [{'action_type': 'controller', 'value': 'circle', 'activation': 'hold'}],
        }})
        snapshot = self.mapper.process_state(state(cross=True), now=0.0)
        self.assertEqual(snapshot['buttons'], ['circle'])
        self.assertEqual(snapshot['blocked'], ['cross'])

        snapshot = self.mapper.process_state(state(cross=False), now=0.1)
        self.assertEqual(snapshot['buttons'], [])

    def test_short_long_and_double_gestures_are_independent_bindings(self):
        self._set_config({'base': {
            'cross': [
                {'action_type': 'keyboard', 'value': 'F', 'activation': 'short', 'pulse_ms': 40},
                {'action_type': 'controller', 'value': 'triangle', 'activation': 'long', 'long_press_ms': 300},
                {'action_type': 'controller', 'value': 'circle', 'activation': 'double', 'double_tap_ms': 260},
            ],
        }})
        self.mapper.process_state(state(cross=True), now=0.0)
        self.mapper.process_state(state(cross=False), now=0.1)
        self.assertIn(('key_down', 'F'), self.output.events)
        self.mapper.process_state(state(cross=False), now=0.2)
        self.assertIn(('key_up', 'F'), self.output.events)

        self.mapper.process_state(state(cross=True), now=1.0)
        snapshot = self.mapper.process_state(state(cross=True), now=1.35)
        self.assertIn('triangle', snapshot['buttons'])
        self.mapper.process_state(state(cross=False), now=1.4)

        self.mapper.process_state(state(cross=True), now=2.0)
        self.mapper.process_state(state(cross=False), now=2.05)
        snapshot = self.mapper.process_state(state(cross=True), now=2.18)
        self.assertIn('circle', snapshot['buttons'])

    def test_turbo_toggles_output_and_layer_hold_restores_base(self):
        self._set_config({'base': {
            'R1': [{'action_type': 'controller', 'value': 'cross', 'activation': 'hold', 'turbo': True, 'turbo_hz': 10}],
            'L1': [{'action_type': 'layer', 'value': 'alt', 'activation': 'hold'}],
        }, 'alt': {
            'cross': [{'action_type': 'controller', 'value': 'triangle', 'activation': 'hold'}],
        }})
        self.assertIn('cross', self.mapper.process_state(state(R1=True), now=0.0)['buttons'])
        self.assertNotIn('cross', self.mapper.process_state(state(R1=True), now=0.05)['buttons'])
        self.assertIn('cross', self.mapper.process_state(state(R1=True), now=0.10)['buttons'])
        self.mapper.process_state(state(R1=False), now=0.12)

        self.mapper.process_state(state(L1=True), now=1.0)
        self.assertEqual(self.mapper.get_active_layer(), 'alt')
        snapshot = self.mapper.process_state(state(L1=True, cross=True), now=1.1)
        self.assertIn('triangle', snapshot['buttons'])
        self.mapper.process_state(state(L1=False, cross=False), now=1.2)
        self.assertEqual(self.mapper.get_active_layer(), 'base')

    def test_macro_profile_passthrough_and_disabled_actions(self):
        self._set_config({'base': {
            'square': [{'action_type': 'macro', 'value': 'macro_test', 'activation': 'press'}],
            'triangle': [{'action_type': 'profile', 'value': 'sniper', 'activation': 'hold'}],
            'circle': [{'action_type': 'passthrough', 'activation': 'hold'}],
            'options': [{'action_type': 'disabled', 'activation': 'hold'}],
        }})
        self.mapper.process_state(state(square=True), now=0.0)
        self.assertEqual(self.macro.played, ['macro_test'])

        self.mapper.process_state(state(triangle=True), now=0.1)
        self.assertEqual(self.active_profile, 'sniper')
        self.mapper.process_state(state(triangle=False), now=0.2)
        self.assertEqual(self.active_profile, 'assault_rifle')

        pass_snapshot = self.mapper.process_state(state(circle=True), now=0.3)
        self.assertNotIn('circle', pass_snapshot['blocked'])
        disabled_snapshot = self.mapper.process_state(state(options=True), now=0.4)
        self.assertIn('options', disabled_snapshot['blocked'])
        self.assertEqual(disabled_snapshot['buttons'], [])

    def test_sanitization_accepts_multiple_bindings_and_filters_unknown_buttons(self):
        config = sanitize_config({'layers': {
            ' Combate ': {
                'cross': {'action_type': 'keyboard', 'value': 'ctrl+f', 'requires': ['L1', 'bad']},
                'bad': [{'action_type': 'controller', 'value': 'cross'}],
            },
        }, 'default_layer': 'combate'})
        self.assertEqual(config['default_layer'], 'combate')
        binding = config['layers']['combate']['cross'][0]
        self.assertEqual(binding['requires'], ['L1'])
        self.assertEqual(binding['value'], 'ctrl+f')

    def test_emulator_combines_advanced_output_and_honors_source_blocking(self):
        emulator = EmulatorManager()
        emulator.set_button_map({'cross': 'circle'})
        emulator.set_advanced_button_state({'triangle'}, {'cross'})
        self.assertEqual(emulator._remap_buttons({'cross': True}), {'triangle': True})

        emulator.set_advanced_button_state({'triangle'}, set())
        self.assertEqual(
            emulator._remap_buttons({'cross': True}),
            {'circle': True, 'triangle': True},
        )


if __name__ == '__main__':
    unittest.main()

class FakeGyroEngine:
    def __init__(self):
        self.enabled = False
        self.recentered = 0

    def recenter(self): self.recentered += 1
    def get_config(self): return SimpleNamespace(enabled=self.enabled)
    def update_config(self, **changes):
        if 'enabled' in changes:
            self.enabled = bool(changes['enabled'])


def test_release_activation_and_gyro_actions():
    emulator = FakeEmulator()
    gyro = FakeGyroEngine()
    mapper = AdvancedMapper(emulator=emulator, output=FakeOutput(), gyro_engine=gyro)
    mapper.set_config({'layers': {'base': {
        'cross': [{'action_type': 'controller', 'value': 'circle', 'activation': 'release'}],
        'square': [{'action_type': 'gyro', 'value': 'recenter', 'activation': 'press'}],
        'triangle': [{'action_type': 'gyro', 'value': 'toggle', 'activation': 'press'}],
    }}})
    assert 'circle' not in mapper.process_state(state(cross=True), now=0.0)['buttons']
    assert 'circle' in mapper.process_state(state(cross=False), now=0.1)['buttons']
    mapper.process_state(state(cross=False), now=0.2)
    assert 'circle' not in mapper.get_snapshot()['buttons']
    mapper.process_state(state(square=True), now=1.0)
    assert gyro.recentered == 1
    mapper.process_state(state(square=False), now=1.1)
    mapper.process_state(state(triangle=True), now=1.2)
    assert gyro.enabled is True


def test_exclusive_double_delays_and_cancels_single_press():
    emulator = FakeEmulator()
    mapper = AdvancedMapper(emulator=emulator, output=FakeOutput())
    mapper.set_config({'layers': {'base': {
        'cross': [
            {'action_type': 'controller', 'value': 'square', 'activation': 'press', 'pulse_ms': 60},
            {'action_type': 'controller', 'value': 'circle', 'activation': 'double', 'double_tap_ms': 250, 'exclusive_double': True},
        ],
    }}})
    first = mapper.process_state(state(cross=True), now=0.0)
    assert 'square' not in first['buttons']
    mapper.process_state(state(cross=False), now=0.05)
    second = mapper.process_state(state(cross=True), now=0.15)
    assert 'circle' in second['buttons']
    assert 'square' not in second['buttons']

    mapper.reset()
    mapper.process_state(state(cross=True), now=1.0)
    mapper.process_state(state(cross=False), now=1.05)
    delayed = mapper.process_state(state(cross=False), now=1.26)
    assert 'square' in delayed['buttons']


def test_layer_chord_applies_in_same_input_frame():
    mapper = AdvancedMapper(emulator=FakeEmulator(), output=FakeOutput())
    mapper.set_config({'layers': {
        'base': {'L1': [{'action_type': 'layer', 'value': 'alt', 'activation': 'hold'}]},
        'alt': {'cross': [{'action_type': 'controller', 'value': 'triangle', 'activation': 'hold'}]},
    }})
    snapshot = mapper.process_state(state(L1=True, cross=True), now=0.0)
    assert snapshot['layer'] == 'alt'
    assert 'triangle' in snapshot['buttons']


def test_profile_mapping_change_waits_for_release_and_uses_latest_request():
    emulator = FakeEmulator()
    mapper = AdvancedMapper(emulator=emulator, output=FakeOutput())
    source_config = {'layers': {'base': {
        'triangle': [{'action_type': 'profile', 'value': 'sniper', 'activation': 'hold'}],
    }}}
    target_config = {'layers': {'base': {
        'cross': [{'action_type': 'controller', 'value': 'circle', 'activation': 'hold'}],
    }}}
    restored_config = {'layers': {'base': {
        'square': [{'action_type': 'controller', 'value': 'cross', 'activation': 'hold'}],
    }}}
    active = {'id': 'base'}

    def apply(profile):
        active['id'] = profile
        mapper.queue_profile_config(target_config if profile == 'sniper' else restored_config)
        return True

    mapper.profile_getter = lambda: active['id']
    mapper.profile_applier = apply
    mapper.set_config(source_config)
    mapper.process_state(state(triangle=True), now=0.0)
    assert active['id'] == 'sniper'
    assert mapper.get_diagnostics_snapshot()['profile_config_pending']
    # La regla original sigue viva hasta recibir la liberación.
    mapper.process_state(state(triangle=False), now=0.1)
    assert active['id'] == 'base'
    assert not mapper.get_diagnostics_snapshot()['profile_config_pending']
    assert 'square' in mapper.get_config()['layers']['base']


def test_toggle_actions_with_same_source_do_not_collide_between_layers():
    emulator = FakeEmulator()
    mapper = AdvancedMapper(emulator=emulator, output=FakeOutput())
    mapper.set_config({'enabled': True, 'default_layer': 'base', 'layers': {
        'base': {
            'cross': [{'action_type': 'controller', 'value': 'circle', 'activation': 'toggle'}],
            'L1': [{'action_type': 'layer', 'value': 'alt', 'activation': 'hold'}],
        },
        'alt': {
            'cross': [{'action_type': 'controller', 'value': 'triangle', 'activation': 'toggle'}],
        },
    }})

    mapper.process_state(state(cross=True), now=0.00)
    mapper.process_state(state(cross=False), now=0.05)
    assert 'circle' in mapper.get_snapshot()['buttons']

    mapper.process_state(state(L1=True), now=0.10)
    mapper.process_state(state(L1=True, cross=True), now=0.15)
    snapshot = mapper.process_state(state(L1=True, cross=False), now=0.20)
    assert {'circle', 'triangle'} <= set(snapshot['buttons'])

    mapper.process_state(state(L1=False, cross=False), now=0.25)
    assert mapper.get_active_layer() == 'base'


def test_nested_layer_holds_can_be_released_out_of_order():
    mapper = AdvancedMapper(emulator=FakeEmulator(), output=FakeOutput())
    mapper.set_config({'enabled': True, 'default_layer': 'base', 'layers': {
        'base': {
            'L1': [{'action_type': 'layer', 'value': 'alt', 'activation': 'hold'}],
        },
        'alt': {
            'R1': [{'action_type': 'layer', 'value': 'sniper', 'activation': 'hold'}],
        },
        'sniper': {
            'cross': [{'action_type': 'controller', 'value': 'triangle', 'activation': 'hold'}],
        },
    }})

    mapper.process_state(state(L1=True), now=0.00)
    assert mapper.get_active_layer() == 'alt'
    mapper.process_state(state(L1=True, R1=True), now=0.05)
    assert mapper.get_active_layer() == 'sniper'

    # Soltar el modificador más viejo no debe cancelar el más reciente.
    mapper.process_state(state(L1=False, R1=True), now=0.10)
    assert mapper.get_active_layer() == 'sniper'
    snapshot = mapper.process_state(state(L1=False, R1=True, cross=True), now=0.15)
    assert 'triangle' in snapshot['buttons']

    mapper.process_state(state(L1=False, R1=False, cross=False), now=0.20)
    assert mapper.get_active_layer() == 'base'


def test_sanitize_config_bounds_untrusted_mapping_size_and_values():
    from src.advanced_mapping import (
        MAX_ACTION_VALUE_LENGTH,
        MAX_BINDINGS_PER_SOURCE,
        MAX_LAYERS,
        MAX_REQUIRED_BUTTONS,
        sanitize_config,
    )

    raw = {
        "layers": {
            f"Layer {index}": {
                "cross": [
                    {
                        "action_type": "keyboard",
                        "value": "A" * (MAX_ACTION_VALUE_LENGTH + 50),
                        "requires": ["L1", "L1", "R1", "square", "circle", "triangle", "cross", "up", "down", "left"],
                    }
                    for _ in range(MAX_BINDINGS_PER_SOURCE + 10)
                ]
            }
            for index in range(MAX_LAYERS + 10)
        }
    }
    clean = sanitize_config(raw)
    assert len(clean["layers"]) <= MAX_LAYERS + 1  # base is added when it was not among the capped layers
    first = next(layer for name, layer in clean["layers"].items() if name != "base")
    assert len(first["cross"]) == MAX_BINDINGS_PER_SOURCE
    binding = first["cross"][0]
    assert len(binding["value"]) == MAX_ACTION_VALUE_LENGTH
    assert len(binding["requires"]) <= MAX_REQUIRED_BUTTONS
    assert len(binding["requires"]) == len(set(binding["requires"]))


def test_sanitization_never_exceeds_layer_limit_and_keeps_base():
    from src.advanced_mapping import MAX_LAYERS

    layers = {
        f"layer_{index}": {"cross": [{"action_type": "controller", "value": "circle"}]}
        for index in range(MAX_LAYERS + 20)
    }
    config = sanitize_config({"layers": layers, "default_layer": "layer_0"})
    assert len(config["layers"]) == MAX_LAYERS
    assert "base" in config["layers"]
