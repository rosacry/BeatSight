import numpy as np
import pytest
from probe_adt_str_runtime import batch_audio, trim_eos


def test_original_batch_membership_and_tail():
    signal = np.arange(19, dtype=np.float32)[None, :]
    np.testing.assert_array_equal(batch_audio(signal, 1, chunk_samples=4, batch_size=2),
                                  [[8, 9, 10, 11], [12, 13, 14, 15]])
    np.testing.assert_array_equal(batch_audio(signal, 2, chunk_samples=4, batch_size=2), [[16, 17, 18, 0]])
    with pytest.raises(ValueError): batch_audio(signal, 3, chunk_samples=4, batch_size=2)


def test_eos_trimming_keeps_unfinished_sequences():
    np.testing.assert_array_equal(trim_eos([2, 4, 338, 500, 3, 3]), [2, 4, 338, 500, 3])
    np.testing.assert_array_equal(trim_eos([2, 4, 338, 500]), [2, 4, 338, 500])
