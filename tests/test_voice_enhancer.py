import numpy as np

from hearing_assist.audio import VoiceEnhancer


def _tone(sample_rate: int, hz: float, seconds: float, amplitude: float) -> np.ndarray:
    t = np.arange(int(sample_rate * seconds), dtype=np.float32) / sample_rate
    return amplitude * np.sin(2.0 * np.pi * hz * t)


def _magnitude_at(samples: np.ndarray, sample_rate: int, hz: float) -> float:
    spectrum = np.fft.rfft(samples.astype(np.float32))
    freqs = np.fft.rfftfreq(samples.size, d=1.0 / sample_rate)
    index = int(np.argmin(np.abs(freqs - hz)))
    return float(np.abs(spectrum[index]))


def test_voice_enhancer_prioritizes_speech_band_over_low_rumble() -> None:
    sample_rate = 16_000
    mixed = _tone(sample_rate, 100.0, 0.5, 8_000.0) + _tone(
        sample_rate, 1_000.0, 0.5, 8_000.0
    )
    samples = mixed.astype(np.int16)

    enhanced = VoiceEnhancer(sample_rate).process(samples)

    before_ratio = _magnitude_at(samples, sample_rate, 1_000.0) / _magnitude_at(
        samples, sample_rate, 100.0
    )
    after_ratio = _magnitude_at(enhanced, sample_rate, 1_000.0) / _magnitude_at(
        enhanced, sample_rate, 100.0
    )

    assert after_ratio > before_ratio * 5.0
    assert enhanced.dtype == np.int16


def test_voice_enhancer_handles_empty_audio() -> None:
    samples = np.array([], dtype=np.int16)

    enhanced = VoiceEnhancer(16_000).process(samples)

    np.testing.assert_array_equal(enhanced, samples)
