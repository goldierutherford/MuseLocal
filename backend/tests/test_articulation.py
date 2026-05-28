import pytest
from backend.articulation import ArticulationEngine

@pytest.fixture
def sample_notes():
    return [
        {"note": 60, "start": 0.0, "end": 0.5, "velocity": 100},  # Downbeat 1 (Beat 0)
        {"note": 62, "start": 0.25, "end": 0.5, "velocity": 90}, # Offbeat
        {"note": 64, "start": 1.0, "end": 2.2, "velocity": 100},  # Downbeat 3 (Beat 2 at 120bpm, long note)
    ]

def test_humanization_offset_limits(sample_notes):
    """
    Verify humanization shifts start times within requested ms boundaries
    and does not shift them below 0.0s.
    """
    humanize_ms = 50.0
    adjusted = ArticulationEngine.apply_humanization(sample_notes, humanize_ms)
    
    assert len(adjusted) == len(sample_notes)
    for orig, adj in zip(sample_notes, adjusted):
        diff_start = abs(adj["start"] - orig["start"])
        # Should be within 50ms (0.05s)
        assert diff_start <= 0.051 # account for tiny floating point precision limits
        assert adj["start"] >= 0.0
        assert adj["end"] > adj["start"]

def test_humanization_zero_value(sample_notes):
    """
    A humanization setting of 0.0 should not alter note properties.
    """
    adjusted = ArticulationEngine.apply_humanization(sample_notes, 0.0)
    assert adjusted == sample_notes

def test_velocity_scaling_downbeat_accents(sample_notes):
    """
    Assert that strong downbeats (beats 0 and 2 at 120bpm) are boosted, 
    while off-beats are scaled down, and bounds stay within [1, 127].
    """
    # Base scale multiplier 1.0
    adjusted = ArticulationEngine.scale_velocities(sample_notes, accent_scale=1.0)
    
    # Note 0 (start=0.0): Strong downbeat (Beat 0) -> boosted * 1.15
    assert adjusted[0]["velocity"] == int(100 * 1.15)
    # Note 1 (start=0.25): Off-beat -> reduced * 0.85
    assert adjusted[1]["velocity"] == int(90 * 0.85)
    # Note 2 (start=1.0): Strong downbeat (Beat 2) -> boosted * 1.15
    assert adjusted[2]["velocity"] == int(100 * 1.15)


def test_velocity_scaling_hard_limits(sample_notes):
    """
    Ensure scaling never overflows past 127 or underflows below 1.
    """
    adjusted_max = ArticulationEngine.scale_velocities(sample_notes, accent_scale=3.0)
    for note in adjusted_max:
        assert note["velocity"] <= 127
        
    adjusted_min = ArticulationEngine.scale_velocities(sample_notes, accent_scale=0.0)
    for note in adjusted_min:
        assert note["velocity"] >= 1

def test_adjust_note_lengths(sample_notes):
    """
    Verify legato duration stretching and staccato shrinkage.
    """
    # Legato adjustment (duration * 1.2)
    legato = ArticulationEngine.adjust_note_lengths(sample_notes, length_ratio=1.2)
    orig_dur = sample_notes[0]["end"] - sample_notes[0]["start"]
    new_dur = legato[0]["end"] - legato[0]["start"]
    assert new_dur == pytest.approx(orig_dur * 1.2)

    # Staccato adjustment (duration * 0.5)
    staccato = ArticulationEngine.adjust_note_lengths(sample_notes, length_ratio=0.5)
    orig_dur_st = sample_notes[0]["end"] - sample_notes[0]["start"]
    new_dur_st = staccato[0]["end"] - staccato[0]["start"]
    assert new_dur_st == pytest.approx(orig_dur_st * 0.5)

def test_continuous_controller_swell_generation(sample_notes):
    """
    Assert that CC curves are generated ONLY for notes exceeding duration thresholds
    (e.g., > 0.8s) and verify linear vs exponential shapes.
    """
    # Note 0 (dur=0.5): too short, no CC
    # Note 1 (dur=0.25): too short, no CC
    # Note 2 (dur=1.2): duration >= 0.8 -> should trigger CC curve generation
    
    # Linear CC curves
    cc_events_lin = ArticulationEngine.generate_cc_curves(sample_notes, cc_number=11, curve_type="linear")
    # Should only match Note 2
    assert len(cc_events_lin) > 0
    assert all(ev["cc_number"] == 11 for ev in cc_events_lin)
    assert all(ev["linked_note_index"] == 2 for ev in cc_events_lin)
    
    # Verify linear curve shape (swell up to mid-point, then fade down)
    mid_index = len(cc_events_lin) // 2
    assert cc_events_lin[0]["value"] == 0
    assert cc_events_lin[mid_index]["value"] == 127
    assert cc_events_lin[-1]["value"] == 0

    # Exponential CC curves
    cc_events_exp = ArticulationEngine.generate_cc_curves(sample_notes, cc_number=1, curve_type="exponential")
    # Exponential swell up (starts slow, spikes at the end)
    assert cc_events_exp[0]["value"] == 0
    assert cc_events_exp[-1]["value"] == 127
    # Third of the way should be very low (0.33^2 * 127 = ~14)
    third_idx = len(cc_events_exp) // 3
    assert cc_events_exp[third_idx]["value"] < 25
