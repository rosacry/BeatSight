"""Mapping and boundary controls for the recovery-only alternative model."""
from collections import Counter
import os
from pathlib import Path
import sys

import numpy as np
import pytest

from compare_adt_str import COMPONENTS, notes_to_chart, token_audit
from evaluate_mdb import drum_family


def test_custom_mapping_is_not_gm_and_keeps_other_targets():
    counts = Counter(drum_family(c) for c in COMPONENTS.values())
    assert counts == {'KD': 2, 'SD': 2, 'HH': 3, 'TT': 3, 'CY': 4, 'OT': 12}
    assert COMPONENTS[44] == 'hihat_open' and COMPONENTS[46] == 'crash'
    assert drum_family(COMPONENTS[37]) == 'OT'
    assert drum_family(COMPONENTS[50]) == 'OT'


def test_simultaneous_hits_and_same_family_duplicates_survive():
    notes = np.array([[.1, .2, p, 100] for p in [35, 36, 38, 41, 44, 46, 49]])
    chart = notes_to_chart(notes)
    assert len(chart['hitObjects']) == 7
    assert all(e['time'] == 100 for e in chart['hitObjects'])
    assert sum(e['component'] == 'kick' for e in chart['hitObjects']) == 2
    with pytest.raises(ValueError, match='Unmapped'):
        notes_to_chart([[0, .1, 81, 100]])


def test_grammar_detects_native_decoder_misalignment_risk():
    assert not token_audit([2, 14, 338, 500, 14, 346, 480, 3, 3])['issues']
    assert not token_audit([2, 0, 3])['issues']
    assert token_audit([2, 14, 338, 14, 346, 480, 3])['issues']
    assert not token_audit([2, 14, 338, 500])['has_EOS']


@pytest.mark.skipif(not os.environ.get('ADT_STR_SOURCE'), reason='Requires pinned native source')
def test_native_tokenizer_and_tail_chunk_contract():
    sys.path.insert(0, str(Path(os.environ['ADT_STR_SOURCE'])))
    import torch
    from adt_transcriber import _chunk_audio
    from modules.midi_tokenizer import MidiTokenizer, MidiTokenizerConfig
    tokenizer = MidiTokenizer(MidiTokenizerConfig(False, 2, 3, 1, 0, True))
    # All custom classes and coincident timestamps, with changing velocities.
    notes = torch.tensor([[.5, .6, p, p + 50] for p in COMPONENTS])
    decoded = tokenizer.decode(tokenizer.notes_to_adt_tokens(notes).numpy())
    torch.testing.assert_close(decoded, notes)
    signal = torch.arange(17).reshape(1, -1).float()
    chunks = _chunk_audio(signal, 8)
    assert [start for start, _ in chunks] == [0, 8, 16]
    torch.testing.assert_close(chunks[2][1], torch.tensor([[16., 0, 0, 0, 0, 0, 0, 0]]))
    torch.testing.assert_close(torch.cat([c for _, c in chunks], 1)[:, :17], signal)
