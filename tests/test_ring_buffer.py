import numpy as np

from hearing_assist.audio import RingBuffer


def test_ring_buffer_returns_latest_without_wrap() -> None:
    buf = RingBuffer(max_samples=8)
    buf.append(np.array([1, 2, 3], dtype=np.int16))
    np.testing.assert_array_equal(buf.latest(), np.array([1, 2, 3], dtype=np.int16))


def test_ring_buffer_wraps_and_keeps_recent() -> None:
    buf = RingBuffer(max_samples=5)
    buf.append(np.array([1, 2, 3], dtype=np.int16))
    buf.append(np.array([4, 5, 6], dtype=np.int16))
    np.testing.assert_array_equal(buf.latest(), np.array([2, 3, 4, 5, 6], dtype=np.int16))


def test_ring_buffer_handles_large_single_append() -> None:
    buf = RingBuffer(max_samples=4)
    buf.append(np.array([1, 2, 3, 4, 5, 6], dtype=np.int16))
    np.testing.assert_array_equal(buf.latest(), np.array([3, 4, 5, 6], dtype=np.int16))
