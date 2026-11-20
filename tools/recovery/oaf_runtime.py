"""Load pinned Magenta inference modules without unrelated generation packages."""
from pathlib import Path
import importlib
import sys
import types


def load(root):
    root = Path(root)
    # librosa 0.7.2 imports this old location. Restore the module alias to the
    # installed jit decorator, without replacing any numerical implementation.
    import numba
    decorators = types.ModuleType('numba.decorators')
    decorators.jit = numba.jit
    sys.modules['numba.decorators'] = decorators
    # Avoid magenta/__init__.py's unrelated generation/pipeline imports. The
    # actual transcription modules and required common function are unmodified.
    for name in ['magenta', 'magenta.common']:
        module = types.ModuleType(name)
        module.__path__ = [str(root / 'source' / name.replace('.', '/'))]
        sys.modules[name] = module
    from magenta.common.sequence_example_lib import flatten_maybe_padded_sequences
    sys.modules['magenta.common'].flatten_maybe_padded_sequences = flatten_maybe_padded_sequences
    import tensorflow.compat.v1 as tf
    tf.disable_v2_behavior()
    # TF 2.13's tf.layers lazy loader still requests the old Keras package path.
    # Alias its installed legacy implementation; no layer/math replacement.
    for suffix in ['', '.normalization']:
        sys.modules['keras.legacy_tf_layers' + suffix] = importlib.import_module(
            'keras.src.legacy_tf_layers' + suffix)
    from magenta.models.onsets_frames_transcription import configs, data, model_tpu, infer_util
    return tf, configs, data, model_tpu, infer_util
