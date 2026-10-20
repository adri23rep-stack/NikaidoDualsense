from src.advanced_mapping import sanitize_config
from src.trigger_engine import TriggerEffect, TriggerEffectType, WeaponProfile


def effect():
    return TriggerEffect(name='x', effect_type=TriggerEffectType.OFF)


def test_weapon_profile_roundtrips_advanced_mapping():
    mapping = sanitize_config({'layers': {'base': {
        'cross': [{'action_type': 'controller', 'value': 'circle', 'activation': 'hold'}]
    }}})
    profile = WeaponProfile(
        name='Test', description='', left_trigger=effect(), right_trigger=effect(),
        advanced_mapping_config=mapping,
    )
    restored = WeaponProfile.from_dict(profile.to_dict())
    assert restored.advanced_mapping_config['layers']['base']['cross'][0]['value'] == 'circle'


def test_advanced_mapping_serialization_does_not_share_nested_references():
    mapping = sanitize_config({'layers': {'base': {
        'cross': [{'action_type': 'controller', 'value': 'circle', 'activation': 'hold'}]
    }}})
    profile = WeaponProfile(
        name='Test', description='', left_trigger=effect(), right_trigger=effect(),
        advanced_mapping_config=mapping,
    )
    payload = profile.to_dict()
    payload['advanced_mapping']['layers']['base']['cross'][0]['value'] = 'triangle'
    assert profile.advanced_mapping_config['layers']['base']['cross'][0]['value'] == 'circle'

    restored = WeaponProfile.from_dict(profile.to_dict())
    restored.advanced_mapping_config['layers']['base']['cross'][0]['value'] = 'square'
    assert profile.advanced_mapping_config['layers']['base']['cross'][0]['value'] == 'circle'


def test_shutdown_does_not_overwrite_legacy_global_mapping_with_active_profile():
    from pathlib import Path

    main_source = (Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8')
    shutdown = main_source.split('    def shutdown(self):', 1)[1].split('\ndef main():', 1)[0]
    assert 'set_advanced_mapping(' not in shutdown
    assert "export_profile_overrides()" in shutdown
