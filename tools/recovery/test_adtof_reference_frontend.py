"""Primary-source differential checks, plus a strict PCM boundary contract."""
import os
from pathlib import Path
import shutil

import numpy as np
import pytest

from audit_adtof_frontend import oracle, synthetic_signals
from frontend_adtof_reference import features, filterbank, frame_audio, magnitude


def test_primary_source_conformance():
    location = os.environ.get('BEATSIGHT_MADMOM_AUDIT_PRIMARY')
    if not location:
        pytest.skip('Set BEATSIGHT_MADMOM_AUDIT_PRIMARY to the saved hash-recorded source directory')
    reference = oracle(Path(location))
    assert np.array_equal(filterbank(), reference.bank)
    for _, audio in synthetic_signals():
        frames, mag, feat = reference.stages(audio)
        assert np.array_equal(frame_audio(audio), frames)
        np.testing.assert_allclose(magnitude(audio), mag, atol=1e-5, rtol=1e-5)
        np.testing.assert_allclose(features(audio)[:, :, 0], feat, atol=1e-5, rtol=1e-5)


def test_endpoint_and_silence():
    for n, count in [(1,1),(440,1),(441,1),(442,2),(4410,10)]:
        result = features(np.zeros(n,dtype=np.float32))
        assert result.shape == (count,84,1)
        assert result.dtype == np.float32
        assert not result.any()


def test_rejects_out_of_contract_pcm():
    for audio in [np.array([],dtype=np.float32), np.zeros(100,dtype=np.int16),
                  np.zeros(100,dtype=np.float64), np.zeros((20,2),dtype=np.float32),
                  np.array([np.nan],dtype=np.float32),np.array([np.inf],dtype=np.float32)]:
        with pytest.raises(ValueError):features(audio)


def test_primary_receipts_verify_relocated_content(tmp_path):
    location = os.environ.get('BEATSIGHT_MADMOM_AUDIT_PRIMARY')
    if not location:
        pytest.skip('Requires hash-recorded primary files')
    source = Path(location)
    for path in source.iterdir():
        if path.is_file():shutil.copy2(path,tmp_path/path.name)
    assert np.array_equal(oracle(tmp_path).bank,filterbank())
    with (tmp_path/'madmom-filters.py').open('a') as f:f.write('\n# Altered copy\n')
    with pytest.raises(ValueError,match='Primary source hash changed'):oracle(tmp_path)
