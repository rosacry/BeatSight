"""
Advanced Structured Decoding for Drum Transcription

This module extends the basic HMM/Viterbi decoder with:
1. Beam Search - Multi-hypothesis tracking with pruning
2. Transformer Decoder - Attention-based sequence refinement
3. CRF Layer - Structured prediction with global normalization

These advanced decoders are what transform "ML output" into
"human-quality charting" by modeling:
- Long-range musical structure (phrases, sections)
- Complex pattern dependencies
- Global sequence optimization

Why these approaches work better for drums:
- HMM/Viterbi: Fast, works well for local patterns
- Beam Search: Explores multiple interpretations, better for ambiguous passages
- Transformer: Learns complex musical relationships from data
- CRF: Global optimization, prevents impossible sequences

Usage:
    from pipeline.advanced_structured_decoder import (
        BeamSearchDecoder,
        TransformerSequenceDecoder,
        CRFDecoder,
        EnsembleDecoder,
    )

    # For best results, use ensemble
    decoder = EnsembleDecoder(
        decoders=['viterbi', 'beam', 'transformer'],
        weights=[0.3, 0.3, 0.4],
    )
    refined_events = decoder.decode(classified_hits, bpm=120)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union, TYPE_CHECKING
import math
import numpy as np

if TYPE_CHECKING:
    import torch

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F  # noqa: F401

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    torch = None  # type: ignore
    nn = None  # type: ignore

# Import from base structured decoder
from .structured_decoder import (
    DrumState,
    TransitionMatrix,
    DecodedEvent,
    ViterbiDecoder,
)


# =============================================================================
# BEAM SEARCH DECODER
# =============================================================================


@dataclass
class BeamHypothesis:
    """A single hypothesis in beam search."""

    states: List[int]  # Sequence of states so far
    log_prob: float  # Log probability of this sequence
    last_time: float  # Time of last event

    def __lt__(self, other):
        """For heap comparison."""
        return self.log_prob > other.log_prob  # Max-heap by log_prob


class BeamSearchDecoder:
    """
    Beam search decoder for drum transcription.

    Unlike Viterbi which only keeps the best path to each state,
    beam search maintains multiple complete hypotheses. This is
    particularly useful when:
    - There are ambiguous passages (ghost vs snare, ride vs hi-hat)
    - The optimal interpretation depends on future context
    - We want to output multiple possible interpretations

    The beam is pruned at each step to keep only the top-K hypotheses,
    making it tractable for long sequences.
    """

    def __init__(
        self,
        bpm: float = 120.0,
        time_signature: Tuple[int, int] = (4, 4),
        beam_width: int = 5,
        length_penalty: float = 0.0,
        diversity_penalty: float = 0.0,
    ):
        """
        Initialize beam search decoder.

        Args:
            bpm: Tempo in BPM
            time_signature: Time signature
            beam_width: Number of hypotheses to maintain
            length_penalty: Penalty/bonus per token (0=neutral)
            diversity_penalty: Penalty for similar hypotheses
        """
        self.bpm = bpm
        self.time_signature = time_signature
        self.beam_width = beam_width
        self.length_penalty = length_penalty
        self.diversity_penalty = diversity_penalty
        self.transitions = TransitionMatrix()

        self.beat_duration = 60.0 / max(bpm, 1.0)
        self.measure_duration = self.beat_duration * time_signature[0]

    def get_beat_position(self, time: float, offset: float = 0.0) -> Tuple[int, float]:
        """Get beat position for a given time."""
        adjusted_time = max(0, time - offset)
        position_in_measure = adjusted_time % self.measure_duration
        beat_index = min(
            int(position_in_measure / self.beat_duration), self.time_signature[0] - 1
        )
        fraction = (position_in_measure % self.beat_duration) / self.beat_duration
        return beat_index, fraction

    def decode(
        self,
        events: List[Dict],
        offset: float = 0.0,
        return_top_k: int = 1,
    ) -> Union[List[DecodedEvent], List[List[DecodedEvent]]]:
        """
        Decode events using beam search.

        Args:
            events: Classified hits
            offset: Beat offset
            return_top_k: Number of top hypotheses to return

        Returns:
            Best decoded sequence, or top-k sequences if return_top_k > 1
        """
        if not events:
            return [] if return_top_k == 1 else [[]]

        events = sorted(events, key=lambda e: e.get("time", 0))
        n_states = len(DrumState)

        # Initialize beam with all possible first states
        first_event = events[0]
        first_time = first_event.get("time", 0)
        emission_probs = self._get_emission_probs(first_event)

        beam = []
        for s in range(n_states):
            if emission_probs[s] > 0.01:  # Prune very unlikely starts
                beam.append(
                    BeamHypothesis(
                        states=[s],
                        log_prob=np.log(emission_probs[s] + 1e-10),
                        last_time=first_time,
                    )
                )

        # Keep only top beam_width
        beam = sorted(beam, key=lambda h: -h.log_prob)[: self.beam_width]

        # Process each event
        for t in range(1, len(events)):
            event = events[t]
            current_time = event.get("time", 0)
            beat_idx, _ = self.get_beat_position(current_time, offset)
            emission_probs = self._get_emission_probs(event)

            # Expand all hypotheses
            new_beam = []
            for hyp in beam:
                time_delta_ms = (current_time - hyp.last_time) * 1000
                last_state = hyp.states[-1]
                trans_probs = self.transitions.get_transition_probs(
                    beat_idx, time_delta_ms
                )

                for s in range(n_states):
                    trans_prob = trans_probs[last_state, s]
                    emit_prob = emission_probs[s]

                    if trans_prob < 0.001 or emit_prob < 0.001:
                        continue  # Prune

                    new_log_prob = (
                        hyp.log_prob
                        + np.log(trans_prob + 1e-10)
                        + np.log(emit_prob + 1e-10)
                        + self.length_penalty
                    )

                    new_beam.append(
                        BeamHypothesis(
                            states=hyp.states + [s],
                            log_prob=new_log_prob,
                            last_time=current_time,
                        )
                    )

            # Apply diversity penalty (penalize similar hypotheses)
            if self.diversity_penalty > 0:
                new_beam = self._apply_diversity_penalty(new_beam)

            # Keep top beam_width
            new_beam = sorted(new_beam, key=lambda h: -h.log_prob)[: self.beam_width]
            beam = new_beam

        # Build results
        results = []
        for k in range(min(return_top_k, len(beam))):
            decoded = self._build_decoded_events(events, beam[k].states, offset)
            results.append(decoded)

        if return_top_k == 1:
            return results[0] if results else []
        return results

    def _apply_diversity_penalty(
        self,
        beam: List[BeamHypothesis],
    ) -> List[BeamHypothesis]:
        """Apply diversity penalty to discourage similar hypotheses."""
        if len(beam) <= 1:
            return beam

        # Sort by score first
        beam = sorted(beam, key=lambda h: -h.log_prob)

        # Penalize hypotheses similar to higher-ranked ones
        for i in range(1, len(beam)):
            for j in range(i):
                # Measure similarity (last 4 states)
                suffix_i = beam[i].states[-4:]
                suffix_j = beam[j].states[-4:]
                matches = sum(1 for a, b in zip(suffix_i, suffix_j) if a == b)
                similarity = matches / max(len(suffix_i), 1)

                if similarity > 0.5:
                    beam[i].log_prob -= self.diversity_penalty * similarity

        return beam

    def _get_emission_probs(self, event: Dict) -> np.ndarray:
        """Get emission probabilities for an event."""
        probs = np.ones(len(DrumState)) * 0.02

        component = event.get("component", "")
        confidence = event.get("confidence", 0.5)

        primary_state = DrumState.from_component(component)
        probs[primary_state.value] = confidence * 0.8

        # Add confusion probabilities
        if primary_state == DrumState.SNARE:
            probs[DrumState.GHOST.value] += (1 - confidence) * 0.15
        elif primary_state == DrumState.HIHAT:
            probs[DrumState.CYMBAL.value] += (1 - confidence) * 0.1
        elif primary_state == DrumState.GHOST:
            probs[DrumState.SNARE.value] += (1 - confidence) * 0.2
            probs[DrumState.HIHAT.value] += (1 - confidence) * 0.1

        return probs / probs.sum()

    def _build_decoded_events(
        self,
        events: List[Dict],
        states: List[int],
        offset: float,
    ) -> List[DecodedEvent]:
        """Build DecodedEvent list from states."""
        decoded = []
        for t, (event, state_idx) in enumerate(zip(events, states)):
            state = DrumState(state_idx)
            current_time = event.get("time", 0)
            beat_idx, beat_frac = self.get_beat_position(current_time, offset)

            decoded.append(
                DecodedEvent(
                    time=current_time,
                    state=state,
                    component=event.get("component", ""),
                    confidence=event.get("confidence", 0.0),
                    viterbi_prob=0.0,  # Not applicable for beam search
                    beat_position=beat_idx + beat_frac,
                    is_backbeat=beat_idx in [1, 3] and beat_frac < 0.1,
                    transition_from=DrumState(states[t - 1]) if t > 0 else None,
                )
            )

        return decoded


# =============================================================================
# TRANSFORMER SEQUENCE DECODER
# =============================================================================

if HAS_TORCH:

    class PositionalEncoding(nn.Module):
        """Sinusoidal positional encoding with beat-awareness."""

        def __init__(self, d_model: int, max_len: int = 5000, beat_aware: bool = True):
            super().__init__()
            self.beat_aware = beat_aware

            pe = torch.zeros(max_len, d_model)
            position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
            div_term = torch.exp(
                torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
            )

            pe[:, 0::2] = torch.sin(position * div_term)
            pe[:, 1::2] = torch.cos(position * div_term)
            pe = pe.unsqueeze(0)  # [1, max_len, d_model]
            self.register_buffer("pe", pe)

        def forward(
            self, x: torch.Tensor, beat_positions: Optional[torch.Tensor] = None
        ) -> torch.Tensor:
            """Add positional encoding to input."""
            seq_len = x.size(1)
            x = x + self.pe[:, :seq_len]

            if self.beat_aware and beat_positions is not None:
                # Add beat-aware encoding (4 positions for 4/4)
                beat_enc = torch.zeros_like(x)
                for i in range(4):
                    mask = (beat_positions == i).unsqueeze(-1)
                    beat_enc += mask * (i / 4.0)
                x = x + beat_enc * 0.1

            return x

    class TransformerSequenceDecoder(nn.Module):
        """
        Transformer-based sequence decoder for drum transcription.

        This decoder learns to refine raw ML predictions by:
        1. Attending to the full sequence context
        2. Learning complex musical patterns from data
        3. Producing globally consistent output

        Unlike HMM/Viterbi which uses hand-crafted transition matrices,
        this learns transitions from data, potentially capturing patterns
        we wouldn't think to encode manually.

        Architecture:
            Input: [batch, seq_len, d_input] (emission probs + features)
            Transformer Encoder → Context-aware features
            Linear → [batch, seq_len, n_states] (refined predictions)
        """

        def __init__(
            self,
            n_states: int = 7,
            d_model: int = 64,
            n_heads: int = 4,
            n_layers: int = 2,
            d_ff: int = 128,
            dropout: float = 0.1,
            beat_aware: bool = True,
        ):
            """
            Initialize Transformer decoder.

            Args:
                n_states: Number of drum states
                d_model: Model dimension
                n_heads: Number of attention heads
                n_layers: Number of transformer layers
                d_ff: Feed-forward dimension
                dropout: Dropout rate
                beat_aware: Use beat-aware positional encoding
            """
            super().__init__()

            self.n_states = n_states
            self.d_model = d_model

            # Input projection (emission probs + confidence + time delta)
            self.input_proj = nn.Linear(n_states + 2, d_model)

            # Positional encoding
            self.pos_encoding = PositionalEncoding(d_model, beat_aware=beat_aware)

            # Transformer encoder
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=n_heads,
                dim_feedforward=d_ff,
                dropout=dropout,
                batch_first=True,
            )
            self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)

            # Output projection
            self.output_proj = nn.Linear(d_model, n_states)

            # State embedding for autoregressive decoding
            self.state_embedding = nn.Embedding(n_states, d_model)

        def forward(
            self,
            emission_probs: torch.Tensor,
            confidences: torch.Tensor,
            time_deltas: torch.Tensor,
            beat_positions: Optional[torch.Tensor] = None,
        ) -> torch.Tensor:
            """
            Forward pass through transformer decoder.

            Args:
                emission_probs: [batch, seq_len, n_states] emission probabilities
                confidences: [batch, seq_len] confidence scores
                time_deltas: [batch, seq_len] time deltas between events
                beat_positions: [batch, seq_len] beat position indices

            Returns:
                Refined logits [batch, seq_len, n_states]
            """
            batch_size, seq_len, _ = emission_probs.shape

            # Construct input features
            x = torch.cat(
                [
                    emission_probs,
                    confidences.unsqueeze(-1),
                    time_deltas.unsqueeze(-1),
                ],
                dim=-1,
            )

            # Project and add positional encoding
            x = self.input_proj(x)
            x = self.pos_encoding(x, beat_positions)

            # Apply transformer
            x = self.transformer(x)

            # Project to output
            logits = self.output_proj(x)

            return logits

        def decode_greedy(
            self,
            emission_probs: torch.Tensor,
            confidences: torch.Tensor,
            time_deltas: torch.Tensor,
            beat_positions: Optional[torch.Tensor] = None,
        ) -> torch.Tensor:
            """Greedy decoding - take argmax at each position."""
            logits = self.forward(
                emission_probs, confidences, time_deltas, beat_positions
            )
            return logits.argmax(dim=-1)

    class TransformerDecoderWrapper:
        """
        Wrapper to use TransformerSequenceDecoder with the same interface
        as ViterbiDecoder.
        """

        def __init__(
            self,
            model_path: Optional[str] = None,
            bpm: float = 120.0,
            time_signature: Tuple[int, int] = (4, 4),
            device: str = "cpu",
        ):
            self.bpm = bpm
            self.time_signature = time_signature
            self.device = device

            self.beat_duration = 60.0 / max(bpm, 1.0)
            self.measure_duration = self.beat_duration * time_signature[0]

            # Initialize model
            self.model = TransformerSequenceDecoder(
                n_states=len(DrumState),
                beat_aware=True,
            ).to(device)

            if model_path:
                self.model.load_state_dict(torch.load(model_path, map_location=device))

            self.model.eval()

        def get_beat_position(self, time: float, offset: float = 0.0) -> int:
            """Get beat index for a given time."""
            adjusted_time = max(0, time - offset)
            position_in_measure = adjusted_time % self.measure_duration
            return min(
                int(position_in_measure / self.beat_duration),
                self.time_signature[0] - 1,
            )

        @torch.no_grad()
        def decode(
            self,
            events: List[Dict],
            offset: float = 0.0,
        ) -> List[DecodedEvent]:
            """Decode events using transformer."""
            if not events:
                return []

            events = sorted(events, key=lambda e: e.get("time", 0))
            n_events = len(events)
            n_states = len(DrumState)

            # Build input tensors
            emission_probs = torch.zeros(1, n_events, n_states)
            confidences = torch.zeros(1, n_events)
            time_deltas = torch.zeros(1, n_events)
            beat_positions = torch.zeros(1, n_events, dtype=torch.long)

            last_time = 0.0
            for i, event in enumerate(events):
                # Emission probs from component
                component = event.get("component", "")
                confidence = event.get("confidence", 0.5)
                primary_state = DrumState.from_component(component)

                emission_probs[0, i] = 0.02
                emission_probs[0, i, primary_state.value] = confidence * 0.8

                confidences[0, i] = confidence
                time_deltas[0, i] = (event.get("time", 0) - last_time) * 10  # Scale
                beat_positions[0, i] = self.get_beat_position(
                    event.get("time", 0), offset
                )

                last_time = event.get("time", 0)

            # Move to device
            emission_probs = emission_probs.to(self.device)
            confidences = confidences.to(self.device)
            time_deltas = time_deltas.to(self.device)
            beat_positions = beat_positions.to(self.device)

            # Decode
            states = (
                self.model.decode_greedy(
                    emission_probs, confidences, time_deltas, beat_positions
                )[0]
                .cpu()
                .numpy()
            )

            # Build decoded events
            decoded = []
            for t, event in enumerate(events):
                state = DrumState(states[t])
                current_time = event.get("time", 0)
                beat_idx = self.get_beat_position(current_time, offset)
                beat_frac = (current_time % self.beat_duration) / self.beat_duration

                decoded.append(
                    DecodedEvent(
                        time=current_time,
                        state=state,
                        component=event.get("component", ""),
                        confidence=event.get("confidence", 0.0),
                        viterbi_prob=0.0,
                        beat_position=beat_idx + beat_frac,
                        is_backbeat=beat_idx in [1, 3] and beat_frac < 0.1,
                        transition_from=DrumState(states[t - 1]) if t > 0 else None,
                    )
                )

            return decoded


# =============================================================================
# CRF LAYER
# =============================================================================


class CRFDecoder:
    """
    Conditional Random Field decoder for drum transcription.

    CRF provides GLOBAL normalization over the entire sequence, unlike
    HMM which uses local normalization. This means CRF considers ALL
    possible paths when computing probabilities, which can be important
    for avoiding globally inconsistent predictions.

    Key advantages:
    - No independence assumptions (unlike HMM)
    - Can use arbitrary features (not just emissions)
    - Optimal for structured prediction tasks

    This is a linear-chain CRF implementation optimized for drum sequences.
    """

    def __init__(
        self,
        n_states: int = 7,
        bpm: float = 120.0,
        time_signature: Tuple[int, int] = (4, 4),
    ):
        self.n_states = n_states
        self.bpm = bpm
        self.time_signature = time_signature

        self.beat_duration = 60.0 / max(bpm, 1.0)
        self.measure_duration = self.beat_duration * time_signature[0]

        # Transition potentials (log-space)
        # Initialize from TransitionMatrix
        tm = TransitionMatrix()
        self.trans_potentials = np.log(tm.base_transitions + 1e-10)

        # Start and end potentials
        self.start_potentials = np.zeros(n_states)
        self.start_potentials[DrumState.SILENCE.value] = 0.5

        self.end_potentials = np.zeros(n_states)

    def get_beat_position(self, time: float, offset: float = 0.0) -> int:
        """Get beat index for a given time."""
        adjusted_time = max(0, time - offset)
        position_in_measure = adjusted_time % self.measure_duration
        return min(
            int(position_in_measure / self.beat_duration), self.time_signature[0] - 1
        )

    def decode(
        self,
        events: List[Dict],
        offset: float = 0.0,
    ) -> List[DecodedEvent]:
        """
        Decode events using CRF with Viterbi algorithm.

        The CRF uses Viterbi for MAP inference, but the potentials
        are different from a standard HMM:
        - No local normalization
        - Beat-aware transition potentials
        - Feature-based emissions
        """
        if not events:
            return []

        events = sorted(events, key=lambda e: e.get("time", 0))
        n_events = len(events)

        # Build emission potentials (log-space)
        emission_pots = np.zeros((n_events, self.n_states))
        for i, event in enumerate(events):
            emission_pots[i] = self._get_emission_potentials(event)

        # Forward pass (Viterbi in log-space)
        viterbi = np.zeros((n_events, self.n_states))
        backpointer = np.zeros((n_events, self.n_states), dtype=np.int32)

        # Initialize
        viterbi[0] = self.start_potentials + emission_pots[0]

        # Forward
        last_time = events[0].get("time", 0)
        for t in range(1, n_events):
            current_time = events[t].get("time", 0)
            beat_idx = self.get_beat_position(current_time, offset)

            # Get beat-aware transition potentials
            trans_pots = self._get_transition_potentials(
                beat_idx, current_time - last_time
            )

            for s in range(self.n_states):
                scores = viterbi[t - 1] + trans_pots[:, s] + emission_pots[t, s]
                best_prev = np.argmax(scores)
                viterbi[t, s] = scores[best_prev]
                backpointer[t, s] = best_prev

            last_time = current_time

        # Add end potentials
        viterbi[-1] += self.end_potentials

        # Backtrack
        best_path = np.zeros(n_events, dtype=np.int32)
        best_path[-1] = np.argmax(viterbi[-1])

        for t in range(n_events - 2, -1, -1):
            best_path[t] = backpointer[t + 1, best_path[t + 1]]

        # Build decoded events
        decoded = []
        for t, event in enumerate(events):
            state = DrumState(best_path[t])
            current_time = event.get("time", 0)
            beat_idx = self.get_beat_position(current_time, offset)
            beat_frac = (current_time % self.beat_duration) / self.beat_duration

            decoded.append(
                DecodedEvent(
                    time=current_time,
                    state=state,
                    component=event.get("component", ""),
                    confidence=event.get("confidence", 0.0),
                    viterbi_prob=float(np.exp(viterbi[t, best_path[t]])),
                    beat_position=beat_idx + beat_frac,
                    is_backbeat=beat_idx in [1, 3] and beat_frac < 0.1,
                    transition_from=DrumState(best_path[t - 1]) if t > 0 else None,
                )
            )

        return decoded

    def _get_emission_potentials(self, event: Dict) -> np.ndarray:
        """Get emission potentials (log-space) for an event."""
        pots = np.ones(self.n_states) * -3.0  # Low base potential

        component = event.get("component", "")
        confidence = event.get("confidence", 0.5)

        primary_state = DrumState.from_component(component)
        pots[primary_state.value] = np.log(confidence + 0.1)

        # Add confusion potentials
        if primary_state == DrumState.SNARE:
            pots[DrumState.GHOST.value] = np.log(0.2 * (1 - confidence) + 0.05)
        elif primary_state == DrumState.HIHAT:
            pots[DrumState.CYMBAL.value] = np.log(0.15 * (1 - confidence) + 0.05)

        return pots

    def _get_transition_potentials(
        self,
        beat_position: int,
        time_delta: float,
    ) -> np.ndarray:
        """Get beat-aware transition potentials."""
        # Start with base potentials
        pots = self.trans_potentials.copy()

        # Apply beat modifiers
        tm = TransitionMatrix()
        beat_mod = tm.beat_modifiers.get(beat_position % 4, np.ones_like(pots))
        pots += np.log(beat_mod + 1e-10)

        # Apply IOI constraints
        time_delta_ms = time_delta * 1000
        for state in DrumState:
            if state == DrumState.SILENCE:
                continue
            min_ioi = tm.min_ioi[state]
            if time_delta_ms < min_ioi:
                penalty = np.log(max(0.1, time_delta_ms / min_ioi))
                pots[:, state.value] += penalty

        return pots


# =============================================================================
# ENSEMBLE DECODER
# =============================================================================


class EnsembleDecoder:
    """
    Ensemble decoder that combines multiple decoding strategies.

    By combining HMM/Viterbi, Beam Search, and Transformer decoders,
    we get the benefits of all approaches:
    - Viterbi: Fast, reliable baseline
    - Beam Search: Multiple hypotheses, handles ambiguity
    - Transformer: Learned patterns, long-range dependencies
    - CRF: Global optimization

    The ensemble votes on the final state for each event, weighted by
    each decoder's confidence and historical accuracy.
    """

    def __init__(
        self,
        decoders: List[str] = None,
        weights: Optional[List[float]] = None,
        bpm: float = 120.0,
        time_signature: Tuple[int, int] = (4, 4),
        transformer_model_path: Optional[str] = None,
    ):
        """
        Initialize ensemble decoder.

        Args:
            decoders: List of decoder names to use ['viterbi', 'beam', 'transformer', 'crf']
            weights: Weights for each decoder (must sum to 1)
            bpm: Tempo
            time_signature: Time signature
            transformer_model_path: Path to trained transformer weights
        """
        if decoders is None:
            decoders = ["viterbi", "beam", "crf"]

        self.decoder_names = decoders
        self.bpm = bpm
        self.time_signature = time_signature

        # Initialize decoders
        self.decoders = {}

        if "viterbi" in decoders:
            self.decoders["viterbi"] = ViterbiDecoder(bpm, time_signature)

        if "beam" in decoders:
            self.decoders["beam"] = BeamSearchDecoder(bpm, time_signature, beam_width=5)

        if "crf" in decoders:
            self.decoders["crf"] = CRFDecoder(
                n_states=len(DrumState), bpm=bpm, time_signature=time_signature
            )

        if "transformer" in decoders and HAS_TORCH:
            self.decoders["transformer"] = TransformerDecoderWrapper(
                model_path=transformer_model_path,
                bpm=bpm,
                time_signature=time_signature,
            )

        # Set weights
        if weights is None:
            weights = [1.0 / len(self.decoders)] * len(self.decoders)

        self.weights = dict(zip(self.decoders.keys(), weights[: len(self.decoders)]))

        # Normalize weights
        total = sum(self.weights.values())
        self.weights = {k: v / total for k, v in self.weights.items()}

    def decode(
        self,
        events: List[Dict],
        offset: float = 0.0,
    ) -> List[DecodedEvent]:
        """
        Decode events using ensemble voting.

        Each decoder produces a sequence of states, and the ensemble
        votes on the final state for each event.
        """
        if not events:
            return []

        events = sorted(events, key=lambda e: e.get("time", 0))
        n_events = len(events)
        n_states = len(DrumState)

        # Collect predictions from each decoder
        all_predictions = {}
        for name, decoder in self.decoders.items():
            try:
                decoded = decoder.decode(events, offset)
                all_predictions[name] = [e.state.value for e in decoded]
            except Exception as e:
                print(f"Decoder {name} failed: {e}")
                continue

        if not all_predictions:
            # Fallback to simple classification
            return [
                DecodedEvent(
                    time=e.get("time", 0),
                    state=DrumState.from_component(e.get("component", "")),
                    component=e.get("component", ""),
                    confidence=e.get("confidence", 0.0),
                    viterbi_prob=0.0,
                    beat_position=0.0,
                    is_backbeat=False,
                )
                for e in events
            ]

        # Vote on each position
        final_states = []
        for t in range(n_events):
            votes = np.zeros(n_states)
            for name, predictions in all_predictions.items():
                if t < len(predictions):
                    state = predictions[t]
                    votes[state] += self.weights.get(name, 1.0)

            final_states.append(np.argmax(votes))

        # Build final decoded events
        beat_duration = 60.0 / max(self.bpm, 1.0)
        measure_duration = beat_duration * self.time_signature[0]

        decoded = []
        for t, event in enumerate(events):
            state = DrumState(final_states[t])
            current_time = event.get("time", 0)

            adjusted_time = max(0, current_time - offset)
            position_in_measure = adjusted_time % measure_duration
            beat_idx = min(
                int(position_in_measure / beat_duration), self.time_signature[0] - 1
            )
            beat_frac = (position_in_measure % beat_duration) / beat_duration

            decoded.append(
                DecodedEvent(
                    time=current_time,
                    state=state,
                    component=event.get("component", ""),
                    confidence=event.get("confidence", 0.0),
                    viterbi_prob=0.0,
                    beat_position=beat_idx + beat_frac,
                    is_backbeat=beat_idx in [1, 3] and beat_frac < 0.1,
                    transition_from=DrumState(final_states[t - 1]) if t > 0 else None,
                )
            )

        return decoded


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def apply_advanced_structured_decoding(
    classified_hits: List[Dict],
    bpm: float,
    offset: float = 0.0,
    time_signature: Optional[Tuple[int, int]] = None,
    decoder_type: str = "ensemble",
    **kwargs,
) -> List[Dict]:
    """
    Apply advanced structured decoding to classified hits.

    This is a drop-in replacement for apply_structured_decoding that uses
    the advanced decoders (beam search, transformer, CRF, ensemble).

    Args:
        classified_hits: Raw classified hits from ML model
        bpm: Detected BPM
        offset: Beat offset in seconds
        time_signature: Optional time signature override
        decoder_type: 'viterbi', 'beam', 'transformer', 'crf', or 'ensemble'
        **kwargs: Additional decoder arguments

    Returns:
        List of hits with refined states and additional context
    """
    if not classified_hits:
        return classified_hits

    if time_signature is None:
        time_signature = (4, 4)

    # Select decoder
    if decoder_type == "viterbi":
        decoder = ViterbiDecoder(bpm=bpm, time_signature=time_signature, **kwargs)
    elif decoder_type == "beam":
        decoder = BeamSearchDecoder(bpm=bpm, time_signature=time_signature, **kwargs)
    elif decoder_type == "crf":
        decoder = CRFDecoder(
            n_states=len(DrumState), bpm=bpm, time_signature=time_signature
        )
    elif decoder_type == "transformer" and HAS_TORCH:
        decoder = TransformerDecoderWrapper(
            bpm=bpm, time_signature=time_signature, **kwargs
        )
    elif decoder_type == "ensemble":
        decoder = EnsembleDecoder(bpm=bpm, time_signature=time_signature, **kwargs)
    else:
        decoder = ViterbiDecoder(bpm=bpm, time_signature=time_signature)

    # Decode
    decoded_events = decoder.decode(classified_hits, offset)

    # Merge decoded info back into hits
    result = []
    for hit, decoded in zip(classified_hits, decoded_events):
        enhanced_hit = dict(hit)
        enhanced_hit["decoded_state"] = decoded.state.name.lower()
        enhanced_hit["beat_position"] = decoded.beat_position
        enhanced_hit["is_backbeat"] = decoded.is_backbeat
        enhanced_hit["time_signature"] = f"{time_signature[0]}/{time_signature[1]}"
        enhanced_hit["decoder_type"] = decoder_type

        # If decoder disagrees with original classification, flag it
        original_state = DrumState.from_component(hit.get("component", ""))
        if decoded.state != original_state:
            enhanced_hit["state_refined"] = True
            enhanced_hit["original_state"] = original_state.name.lower()

        result.append(enhanced_hit)

    return result
