"""
Dynamic Lane Layout System

Instead of forcing all songs into a fixed 7-lane layout, this module
analyzes what drum components are actually present in the transcription
and creates an optimal lane layout for that specific song.

Key innovations:
1. Automatic component detection - only create lanes for what's used
2. Smart grouping - combine similar components when lane count is limited
3. Visual clarity - space lanes for readability
4. Ergonomic ordering - place lanes based on physical kit layout
5. Adaptive merging - reduce lanes for simpler songs

Examples:
- Simple rock (kick, snare, hat, crash): 4 lanes
- Full kit with ghost notes: 7 lanes
- Electronic (kick, clap, hat): 3 lanes
- Prog metal (2 kicks, snare, hats, 4 toms, 3 crashes, china): 10+ lanes

This creates charts that LOOK like the song SOUNDS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Set
from enum import Enum, auto
from collections import Counter


class ComponentCategory(Enum):
    """High-level drum component categories for grouping."""

    KICK = auto()
    SNARE = auto()
    HIHAT = auto()
    TOM = auto()
    CYMBAL = auto()
    PERCUSSION = auto()
    GHOST = auto()  # Low-velocity snare hits


@dataclass
class LaneDefinition:
    """Definition of a single lane in the layout."""

    index: int
    name: str
    short_name: str
    category: ComponentCategory
    components: List[str]  # Which component names map to this lane
    color: str  # Hex color for visualization
    priority: int = 0  # Higher = more important (stays when merging)

    def matches(self, component: str) -> bool:
        """Check if a component belongs to this lane."""
        comp_lower = component.lower()
        return any(
            c.lower() in comp_lower or comp_lower in c.lower() for c in self.components
        )


@dataclass
class DynamicLaneLayout:
    """
    A dynamically generated lane layout based on song content.
    """

    lanes: List[LaneDefinition] = field(default_factory=list)
    component_to_lane: Dict[str, int] = field(default_factory=dict)

    # Statistics
    total_components_detected: int = 0
    unique_components: Set[str] = field(default_factory=set)

    @property
    def lane_count(self) -> int:
        return len(self.lanes)

    def get_lane(self, component: str) -> int:
        """Get the lane index for a component."""
        # Direct lookup first
        comp_lower = component.lower()
        if comp_lower in self.component_to_lane:
            return self.component_to_lane[comp_lower]

        # Fuzzy match against lane definitions
        for lane in self.lanes:
            if lane.matches(component):
                self.component_to_lane[comp_lower] = lane.index
                return lane.index

        # Fallback: center lane or last lane
        return self.lane_count // 2

    def to_dict(self) -> Dict:
        """Serialize layout for .bsm file."""
        return {
            "lane_count": self.lane_count,
            "lanes": [
                {
                    "index": lane.index,
                    "name": lane.name,
                    "short_name": lane.short_name,
                    "category": lane.category.name,
                    "color": lane.color,
                    "components": lane.components,
                }
                for lane in self.lanes
            ],
            "component_map": self.component_to_lane,
        }


# =============================================================================
# COMPONENT CLASSIFICATION
# =============================================================================

# Canonical component names and their categories
COMPONENT_CATEGORIES: Dict[str, ComponentCategory] = {
    # Kick drums
    "kick": ComponentCategory.KICK,
    "bass": ComponentCategory.KICK,
    "kick1": ComponentCategory.KICK,
    "kick2": ComponentCategory.KICK,
    "bass_drum": ComponentCategory.KICK,
    # Snare drums
    "snare": ComponentCategory.SNARE,
    "snare_center": ComponentCategory.SNARE,
    "snare_rimshot": ComponentCategory.SNARE,
    "snare_cross_stick": ComponentCategory.SNARE,
    "sidestick": ComponentCategory.SNARE,
    "rimshot": ComponentCategory.SNARE,
    "rim": ComponentCategory.SNARE,
    "clap": ComponentCategory.SNARE,  # Electronic equivalent
    # Ghost notes (separate category for optional merging)
    "ghost": ComponentCategory.GHOST,
    "ghost_snare": ComponentCategory.GHOST,
    # Hi-hats
    "hihat": ComponentCategory.HIHAT,
    "hihat_closed": ComponentCategory.HIHAT,
    "hihat_open": ComponentCategory.HIHAT,
    "hihat_half": ComponentCategory.HIHAT,
    "hihat_pedal": ComponentCategory.HIHAT,
    "hihat_foot": ComponentCategory.HIHAT,
    "hihat_choke": ComponentCategory.HIHAT,
    # Toms
    "tom": ComponentCategory.TOM,
    "tom_high": ComponentCategory.TOM,
    "tom_mid": ComponentCategory.TOM,
    "tom_low": ComponentCategory.TOM,
    "tom_floor": ComponentCategory.TOM,
    "rack_tom": ComponentCategory.TOM,
    "floor_tom": ComponentCategory.TOM,
    # Ranked toms from pitch ranker
    "tom_1": ComponentCategory.TOM,
    "tom_2": ComponentCategory.TOM,
    "tom_3": ComponentCategory.TOM,
    "tom_4": ComponentCategory.TOM,
    # Cymbals
    "crash": ComponentCategory.CYMBAL,
    "crash1": ComponentCategory.CYMBAL,
    "crash2": ComponentCategory.CYMBAL,
    "crash_1": ComponentCategory.CYMBAL,
    "crash_2": ComponentCategory.CYMBAL,
    "crash_3": ComponentCategory.CYMBAL,
    "crash_4": ComponentCategory.CYMBAL,
    "ride": ComponentCategory.CYMBAL,
    "ride_bell": ComponentCategory.CYMBAL,
    "ride_bow": ComponentCategory.CYMBAL,
    "ride_bell_1": ComponentCategory.CYMBAL,
    "ride_bell_2": ComponentCategory.CYMBAL,
    "ride_bow_1": ComponentCategory.CYMBAL,
    "ride_bow_2": ComponentCategory.CYMBAL,
    "china": ComponentCategory.CYMBAL,
    "china_1": ComponentCategory.CYMBAL,
    "china_2": ComponentCategory.CYMBAL,
    "splash": ComponentCategory.CYMBAL,
    "splash_1": ComponentCategory.CYMBAL,
    "splash_2": ComponentCategory.CYMBAL,
    "stack": ComponentCategory.CYMBAL,
    # Percussion
    "cowbell": ComponentCategory.PERCUSSION,
    "tambourine": ComponentCategory.PERCUSSION,
    "shaker": ComponentCategory.PERCUSSION,
    "woodblock": ComponentCategory.PERCUSSION,
    "clave": ComponentCategory.PERCUSSION,
    "agogo": ComponentCategory.PERCUSSION,
    "timbale": ComponentCategory.PERCUSSION,
    "bongo": ComponentCategory.PERCUSSION,
    "conga": ComponentCategory.PERCUSSION,
}


def classify_component(component: str) -> ComponentCategory:
    """Classify a component into a category."""
    comp = component.lower().strip()

    # Direct lookup
    if comp in COMPONENT_CATEGORIES:
        return COMPONENT_CATEGORIES[comp]

    # Pattern matching
    if "kick" in comp or "bass" in comp:
        return ComponentCategory.KICK
    if "ghost" in comp:
        return ComponentCategory.GHOST
    if "snare" in comp or "rim" in comp or "clap" in comp:
        return ComponentCategory.SNARE
    if "hat" in comp or "hh" in comp:
        return ComponentCategory.HIHAT
    if "tom" in comp or "rack" in comp or "floor" in comp:
        return ComponentCategory.TOM
    if any(x in comp for x in ["crash", "ride", "china", "splash", "cymbal", "bell"]):
        return ComponentCategory.CYMBAL

    return ComponentCategory.PERCUSSION


# =============================================================================
# LANE COLORS (for visualization)
# =============================================================================

CATEGORY_COLORS: Dict[ComponentCategory, str] = {
    ComponentCategory.KICK: "#E63946",  # Red
    ComponentCategory.SNARE: "#F4A261",  # Orange
    ComponentCategory.GHOST: "#FFE5B4",  # Peach (lighter snare)
    ComponentCategory.HIHAT: "#2A9D8F",  # Teal
    ComponentCategory.TOM: "#264653",  # Dark blue
    ComponentCategory.CYMBAL: "#E9C46A",  # Gold
    ComponentCategory.PERCUSSION: "#9B59B6",  # Purple
}


# =============================================================================
# LANE LAYOUT BUILDER
# =============================================================================


class DynamicLaneLayoutBuilder:
    """
    Builds an optimal lane layout based on detected components.
    """

    def __init__(
        self,
        min_lanes: int = 3,
        max_lanes: int = 12,
        merge_ghost_notes: bool = True,
        merge_similar_cymbals: bool = True,
        merge_tom_varieties: bool = False,
    ):
        """
        Initialize the builder.

        Args:
            min_lanes: Minimum lanes (even for simple songs)
            max_lanes: Maximum lanes (for readability)
            merge_ghost_notes: Combine ghost notes with snare
            merge_similar_cymbals: Combine crash1/crash2 etc.
            merge_tom_varieties: Combine all toms into one lane
        """
        self.min_lanes = min_lanes
        self.max_lanes = max_lanes
        self.merge_ghost_notes = merge_ghost_notes
        self.merge_similar_cymbals = merge_similar_cymbals
        self.merge_tom_varieties = merge_tom_varieties

    def build_from_hits(self, hits: List[Dict]) -> DynamicLaneLayout:
        """
        Build a lane layout from classified hits.

        Args:
            hits: List of classified drum hits with 'component' field

        Returns:
            DynamicLaneLayout optimized for this song
        """
        # Step 1: Collect all unique components and their frequencies
        component_counts = Counter()
        for hit in hits:
            comp = hit.get("component", "").lower()
            if comp:
                component_counts[comp] += 1

        if not component_counts:
            return self._create_default_layout()

        # Step 2: Group components by category
        category_components: Dict[ComponentCategory, List[Tuple[str, int]]] = {}
        for comp, count in component_counts.items():
            category = classify_component(comp)
            if category not in category_components:
                category_components[category] = []
            category_components[category].append((comp, count))

        # Sort within each category by frequency
        for cat in category_components:
            category_components[cat].sort(key=lambda x: -x[1])

        # Step 3: Build lanes based on what's present
        lanes = self._build_lanes(category_components, component_counts)

        # Step 4: Apply merging rules if needed
        if len(lanes) > self.max_lanes:
            lanes = self._merge_lanes(lanes, component_counts)

        # Step 5: Ensure minimum lanes
        while len(lanes) < self.min_lanes:
            lanes = self._expand_lanes(lanes)

        # Step 6: Reorder for ergonomic layout
        lanes = self._reorder_lanes(lanes)

        # Step 7: Assign final indices and build mapping
        layout = DynamicLaneLayout()
        for i, lane in enumerate(lanes):
            lane.index = i
            layout.lanes.append(lane)
            for comp in lane.components:
                layout.component_to_lane[comp.lower()] = i

        layout.unique_components = set(component_counts.keys())
        layout.total_components_detected = sum(component_counts.values())

        return layout

    def _build_lanes(
        self,
        category_components: Dict[ComponentCategory, List[Tuple[str, int]]],
        all_counts: Counter,
    ) -> List[LaneDefinition]:
        """Build initial lane list from categorized components."""
        lanes = []

        # Kick lane(s)
        if ComponentCategory.KICK in category_components:
            kick_comps = category_components[ComponentCategory.KICK]
            if len(kick_comps) > 1 and not self._should_merge_kicks(kick_comps):
                # Multiple distinct kicks (double bass pedal)
                for i, (comp, _) in enumerate(kick_comps[:2]):  # Max 2 kick lanes
                    lanes.append(
                        LaneDefinition(
                            index=0,
                            name=f"Kick {i + 1}",
                            short_name=f"K{i + 1}",
                            category=ComponentCategory.KICK,
                            components=[comp],
                            color=CATEGORY_COLORS[ComponentCategory.KICK],
                            priority=10,
                        )
                    )
            else:
                # Single kick lane
                lanes.append(
                    LaneDefinition(
                        index=0,
                        name="Kick",
                        short_name="K",
                        category=ComponentCategory.KICK,
                        components=[c for c, _ in kick_comps],
                        color=CATEGORY_COLORS[ComponentCategory.KICK],
                        priority=10,
                    )
                )

        # Snare lane
        if ComponentCategory.SNARE in category_components:
            snare_comps = [c for c, _ in category_components[ComponentCategory.SNARE]]

            # Optionally merge ghost notes
            if (
                self.merge_ghost_notes
                and ComponentCategory.GHOST in category_components
            ):
                ghost_comps = [
                    c for c, _ in category_components[ComponentCategory.GHOST]
                ]
                snare_comps.extend(ghost_comps)
                del category_components[ComponentCategory.GHOST]

            lanes.append(
                LaneDefinition(
                    index=0,
                    name="Snare",
                    short_name="S",
                    category=ComponentCategory.SNARE,
                    components=snare_comps,
                    color=CATEGORY_COLORS[ComponentCategory.SNARE],
                    priority=9,
                )
            )

        # Ghost note lane (if not merged)
        if ComponentCategory.GHOST in category_components:
            ghost_comps = [c for c, _ in category_components[ComponentCategory.GHOST]]
            lanes.append(
                LaneDefinition(
                    index=0,
                    name="Ghost",
                    short_name="G",
                    category=ComponentCategory.GHOST,
                    components=ghost_comps,
                    color=CATEGORY_COLORS[ComponentCategory.GHOST],
                    priority=4,
                )
            )

        # Hi-hat lane(s)
        if ComponentCategory.HIHAT in category_components:
            hat_comps = category_components[ComponentCategory.HIHAT]

            # Separate pedal from stick hits?
            pedal_comps = [c for c, _ in hat_comps if "pedal" in c or "foot" in c]
            stick_comps = [
                c for c, _ in hat_comps if "pedal" not in c and "foot" not in c
            ]

            if stick_comps:
                lanes.append(
                    LaneDefinition(
                        index=0,
                        name="Hi-Hat",
                        short_name="HH",
                        category=ComponentCategory.HIHAT,
                        components=stick_comps,
                        color=CATEGORY_COLORS[ComponentCategory.HIHAT],
                        priority=8,
                    )
                )

            if pedal_comps and not self.merge_ghost_notes:
                # Only separate pedal if we have room
                lanes.append(
                    LaneDefinition(
                        index=0,
                        name="HH Pedal",
                        short_name="HP",
                        category=ComponentCategory.HIHAT,
                        components=pedal_comps,
                        color="#1D7A70",  # Darker teal
                        priority=3,
                    )
                )
            elif pedal_comps:
                # Merge pedal into main hi-hat
                for lane in lanes:
                    if lane.category == ComponentCategory.HIHAT:
                        lane.components.extend(pedal_comps)
                        break

        # Tom lanes
        if ComponentCategory.TOM in category_components:
            tom_comps = category_components[ComponentCategory.TOM]

            if self.merge_tom_varieties:
                # Merge all toms into one lane explicitly
                lanes.append(
                    LaneDefinition(
                        index=0,
                        name="Toms",
                        short_name="T",
                        category=ComponentCategory.TOM,
                        components=[c for c, _ in tom_comps],
                        color=CATEGORY_COLORS[ComponentCategory.TOM],
                        priority=6,
                    )
                )
            else:
                # Separate by pitch (high/mid/low)
                # Support both legacy names (tom_high, tom_low) and ranked labels (tom_1, tom_2)
                high_toms = [c for c, _ in tom_comps if "high" in c or "rack" in c or c == "tom_1"]
                mid_toms = [c for c, _ in tom_comps if "mid" in c or c == "tom_2"]
                low_toms = [c for c, _ in tom_comps if "low" in c or "floor" in c or c in ("tom_3", "tom_4")]
                generic_toms = [
                    c for c, _ in tom_comps if c not in high_toms + mid_toms + low_toms
                ]

                if high_toms:
                    lanes.append(
                        LaneDefinition(
                            index=0,
                            name="High Tom",
                            short_name="HT",
                            category=ComponentCategory.TOM,
                            components=high_toms,
                            color="#3D5A6C",
                            priority=5,
                        )
                    )
                if mid_toms or generic_toms:
                    lanes.append(
                        LaneDefinition(
                            index=0,
                            name="Mid Tom",
                            short_name="MT",
                            category=ComponentCategory.TOM,
                            components=mid_toms + generic_toms,
                            color=CATEGORY_COLORS[ComponentCategory.TOM],
                            priority=5,
                        )
                    )
                if low_toms:
                    lanes.append(
                        LaneDefinition(
                            index=0,
                            name="Floor Tom",
                            short_name="FT",
                            category=ComponentCategory.TOM,
                            components=low_toms,
                            color="#1A3440",
                            priority=5,
                        )
                    )

        # Cymbal lanes
        if ComponentCategory.CYMBAL in category_components:
            cymbal_comps = category_components[ComponentCategory.CYMBAL]

            if self.merge_similar_cymbals:
                # Group: crashes together, ride separate
                crashes = [
                    c
                    for c, _ in cymbal_comps
                    if "crash" in c or "china" in c or "splash" in c or "stack" in c
                ]
                rides = [c for c, _ in cymbal_comps if "ride" in c or "bell" in c]

                if crashes:
                    lanes.append(
                        LaneDefinition(
                            index=0,
                            name="Crash",
                            short_name="CR",
                            category=ComponentCategory.CYMBAL,
                            components=crashes,
                            color=CATEGORY_COLORS[ComponentCategory.CYMBAL],
                            priority=7,
                        )
                    )
                if rides:
                    lanes.append(
                        LaneDefinition(
                            index=0,
                            name="Ride",
                            short_name="RD",
                            category=ComponentCategory.CYMBAL,
                            components=rides,
                            color="#D4A84B",
                            priority=7,
                        )
                    )
            else:
                # Individual cymbal lanes
                for comp, count in cymbal_comps:
                    if count > 5:  # Only if used meaningfully
                        lanes.append(
                            LaneDefinition(
                                index=0,
                                name=comp.replace("_", " ").title(),
                                short_name=comp[:2].upper(),
                                category=ComponentCategory.CYMBAL,
                                components=[comp],
                                color=CATEGORY_COLORS[ComponentCategory.CYMBAL],
                                priority=6,
                            )
                        )

        # Percussion lane
        if ComponentCategory.PERCUSSION in category_components:
            perc_comps = [
                c for c, _ in category_components[ComponentCategory.PERCUSSION]
            ]
            if perc_comps:
                lanes.append(
                    LaneDefinition(
                        index=0,
                        name="Percussion",
                        short_name="PC",
                        category=ComponentCategory.PERCUSSION,
                        components=perc_comps,
                        color=CATEGORY_COLORS[ComponentCategory.PERCUSSION],
                        priority=2,
                    )
                )

        return lanes

    def _should_merge_kicks(self, kick_comps: List[Tuple[str, int]]) -> bool:
        """Determine if multiple kick components should be merged."""
        if len(kick_comps) <= 1:
            return True

        # If one kick is much more frequent, the other is probably an alternate
        counts = [c for _, c in kick_comps]
        if max(counts) > 5 * min(counts):
            return True

        return False

    def _merge_lanes(
        self,
        lanes: List[LaneDefinition],
        counts: Counter,
    ) -> List[LaneDefinition]:
        """Merge lanes to fit within max_lanes."""
        while len(lanes) > self.max_lanes:
            # Find lowest priority lane
            lanes.sort(key=lambda lane: lane.priority)
            lowest = lanes[0]

            # Find best lane to merge into (same category preferred)
            best_target = None
            for lane in lanes[1:]:
                if lane.category == lowest.category:
                    best_target = lane
                    break

            if best_target is None:
                # Merge into closest category
                best_target = lanes[1]

            # Merge
            best_target.components.extend(lowest.components)
            best_target.name = f"{best_target.name}+"
            lanes.remove(lowest)

        return lanes

    def _expand_lanes(self, lanes: List[LaneDefinition]) -> List[LaneDefinition]:
        """Expand lanes if below minimum."""
        # Add empty placeholder lanes for visual spacing
        if len(lanes) < self.min_lanes:
            lanes.append(
                LaneDefinition(
                    index=0,
                    name="Empty",
                    short_name="-",
                    category=ComponentCategory.PERCUSSION,
                    components=[],
                    color="#666666",
                    priority=0,
                )
            )
        return lanes

    def _reorder_lanes(self, lanes: List[LaneDefinition]) -> List[LaneDefinition]:
        """
        Reorder lanes for ergonomic layout.

        Standard ordering (left to right):
        1. Hi-hat pedal / aux
        2. Snare / Ghost
        3. High Tom
        4. Kick (CENTER)
        5. Mid/Low Tom
        6. Hi-hat (stick)
        7. Cymbals
        8. Percussion
        """
        category_order = [
            (ComponentCategory.HIHAT, lambda ln: "pedal" in ln.name.lower()),
            (ComponentCategory.SNARE, None),
            (ComponentCategory.GHOST, None),
            (ComponentCategory.TOM, lambda ln: "high" in ln.name.lower()),
            (ComponentCategory.KICK, None),
            (ComponentCategory.TOM, lambda ln: "high" not in ln.name.lower()),
            (ComponentCategory.HIHAT, lambda ln: "pedal" not in ln.name.lower()),
            (ComponentCategory.CYMBAL, None),
            (ComponentCategory.PERCUSSION, None),
        ]

        ordered = []
        used = set()

        for category, filter_fn in category_order:
            for lane in lanes:
                if id(lane) in used:
                    continue
                if lane.category == category:
                    if filter_fn is None or filter_fn(lane):
                        ordered.append(lane)
                        used.add(id(lane))

        # Add any remaining lanes
        for lane in lanes:
            if id(lane) not in used:
                ordered.append(lane)

        return ordered

    def _create_default_layout(self) -> DynamicLaneLayout:
        """Create a sensible default layout when no hits are detected."""
        layout = DynamicLaneLayout()

        default_lanes = [
            LaneDefinition(
                0,
                "Kick",
                "K",
                ComponentCategory.KICK,
                ["kick", "bass"],
                CATEGORY_COLORS[ComponentCategory.KICK],
                10,
            ),
            LaneDefinition(
                1,
                "Snare",
                "S",
                ComponentCategory.SNARE,
                ["snare", "ghost", "rim"],
                CATEGORY_COLORS[ComponentCategory.SNARE],
                9,
            ),
            LaneDefinition(
                2,
                "Hi-Hat",
                "HH",
                ComponentCategory.HIHAT,
                ["hihat"],
                CATEGORY_COLORS[ComponentCategory.HIHAT],
                8,
            ),
            LaneDefinition(
                3,
                "Cymbal",
                "CY",
                ComponentCategory.CYMBAL,
                ["crash", "ride"],
                CATEGORY_COLORS[ComponentCategory.CYMBAL],
                7,
            ),
        ]

        for lane in default_lanes:
            layout.lanes.append(lane)
            for comp in lane.components:
                layout.component_to_lane[comp] = lane.index

        return layout


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_dynamic_layout(
    hits: List[Dict],
    max_lanes: int = 10,
    merge_ghosts: bool = True,
) -> DynamicLaneLayout:
    """
    Convenience function to create a dynamic lane layout.

    Args:
        hits: Classified drum hits
        max_lanes: Maximum lanes to create
        merge_ghosts: Whether to merge ghost notes with snare

    Returns:
        DynamicLaneLayout tailored to the song
    """
    builder = DynamicLaneLayoutBuilder(
        max_lanes=max_lanes,
        merge_ghost_notes=merge_ghosts,
    )
    return builder.build_from_hits(hits)


def apply_dynamic_layout(
    hits: List[Dict],
    layout: DynamicLaneLayout,
) -> List[Dict]:
    """
    Apply a dynamic lane layout to hits.

    Args:
        hits: Classified drum hits
        layout: Dynamic lane layout

    Returns:
        Hits with 'lane' field assigned
    """
    result = []
    for hit in hits:
        new_hit = hit.copy()
        component = hit.get("component", "")
        new_hit["lane"] = layout.get_lane(component)
        result.append(new_hit)
    return result


def analyze_kit_complexity(hits: List[Dict]) -> Dict:
    """
    Analyze the complexity of the drum kit used in a song.

    Returns statistics useful for deciding lane count.
    """
    components = Counter(h.get("component", "").lower() for h in hits)
    categories = Counter(classify_component(c).name for c in components)

    return {
        "unique_components": len(components),
        "total_hits": len(hits),
        "components": dict(components),
        "categories": dict(categories),
        "recommended_lanes": min(12, max(3, len(components))),
        "kit_type": _classify_kit_type(categories),
    }


def _classify_kit_type(categories: Counter) -> str:
    """Classify the type of drum kit based on components used."""
    if len(categories) <= 2:
        return "minimal"
    if categories.get("TOM", 0) >= 3:
        return "extended"
    if categories.get("CYMBAL", 0) >= 4:
        return "cymbal_heavy"
    if categories.get("PERCUSSION", 0) >= 2:
        return "percussion_heavy"
    return "standard"
