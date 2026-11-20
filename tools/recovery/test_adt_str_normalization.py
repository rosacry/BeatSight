import torch
import pytest
from probe_adt_str_normalization import normalized_rows


def test_normalizes_individual_segments_preserving_shape_and_silence():
    calls = []
    def primary(x):
        calls.append(x.clone())
        return x / x.abs().max()
    values = torch.tensor([[.01, -.02, 0], [2., -1., 0], [0, 0, 0]])
    original = values.clone()
    output, peaks = normalized_rows(values, primary)
    torch.testing.assert_close(output, torch.tensor([[.5, -1., 0], [1., -.5, 0], [0, 0, 0]]))
    assert len(calls) == 2 and peaks[-1] == 0
    torch.testing.assert_close(values, original)


def test_nonfinite_chunks_fail_closed():
    with pytest.raises(ValueError): normalized_rows(torch.tensor([[float('nan')]]), lambda x: x)
