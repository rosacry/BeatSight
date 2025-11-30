"""
Manual Mapping Helper

Provides workflow support for users who want to create beatmaps manually
rather than using full AI generation.

Workflow:
1. User chooses "Manual Mapping" mode
2. System prompts: "Would you like the AI to detect the number of lanes?"
   - YES → AI analyzes audio, suggests lane count, user can adjust
   - NO  → User picks lane count themselves (3-12 lanes)
3. User starts mapping with their chosen/adjusted lane configuration
4. Lane count can be changed at any time during editing

This module provides the backend API for this workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum, auto

# Import dynamic lane detection
try:
    from .dynamic_lane_layout import (
        DynamicLaneLayout,
        DynamicLaneLayoutBuilder,
        LaneDefinition,
        ComponentCategory,
        classify_component,
    )
    HAS_DYNAMIC_LANES = True
except ImportError:
    HAS_DYNAMIC_LANES = False


class LaneDetectionChoice(Enum):
    """User's choice for lane detection in manual mapping mode."""
    AI_DETECT = auto()      # Let AI detect lanes from audio
    USER_SPECIFY = auto()   # User specifies lane count manually
    

@dataclass
class LaneConfiguration:
    """
    Represents the lane configuration for a beatmap.
    
    Can be created from AI detection or user specification,
    and can be modified at any time.
    """
    lane_count: int
    source: LaneDetectionChoice
    
    # If AI-detected, contains the detected layout
    detected_layout: Optional[DynamicLaneLayout] = None
    detected_components: List[str] = field(default_factory=list)
    
    # User can override individual lane assignments
    custom_lane_names: Dict[int, str] = field(default_factory=dict)
    custom_lane_colors: Dict[int, str] = field(default_factory=dict)
    
    # Track if user modified AI suggestion
    user_modified: bool = False
    
    def set_lane_count(self, count: int) -> None:
        """
        Change the lane count (user adjustment).
        
        Args:
            count: New lane count (3-12)
        """
        if count < 3 or count > 12:
            raise ValueError("Lane count must be between 3 and 12")
        
        self.lane_count = count
        self.user_modified = True
    
    def set_lane_name(self, lane_index: int, name: str) -> None:
        """Set a custom name for a lane."""
        if lane_index < 0 or lane_index >= self.lane_count:
            raise ValueError(f"Lane index must be 0-{self.lane_count - 1}")
        self.custom_lane_names[lane_index] = name
        self.user_modified = True
    
    def set_lane_color(self, lane_index: int, color: str) -> None:
        """Set a custom color for a lane (hex format)."""
        if lane_index < 0 or lane_index >= self.lane_count:
            raise ValueError(f"Lane index must be 0-{self.lane_count - 1}")
        self.custom_lane_colors[lane_index] = color
        self.user_modified = True
    
    def get_lane_info(self) -> List[Dict[str, Any]]:
        """Get lane information for display/editing."""
        lanes = []
        
        for i in range(self.lane_count):
            lane_info = {
                "index": i,
                "name": self.custom_lane_names.get(i, f"Lane {i + 1}"),
                "color": self.custom_lane_colors.get(i, _default_lane_color(i)),
            }
            
            # If AI-detected, include component info
            if self.detected_layout and i < len(self.detected_layout.lanes):
                ai_lane = self.detected_layout.lanes[i]
                if i not in self.custom_lane_names:
                    lane_info["name"] = ai_lane.name
                if i not in self.custom_lane_colors:
                    lane_info["color"] = ai_lane.color
                lane_info["components"] = ai_lane.components
                lane_info["category"] = ai_lane.category.name
            
            lanes.append(lane_info)
        
        return lanes
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage."""
        return {
            "lane_count": self.lane_count,
            "source": self.source.name,
            "user_modified": self.user_modified,
            "detected_components": self.detected_components,
            "custom_lane_names": self.custom_lane_names,
            "custom_lane_colors": self.custom_lane_colors,
            "lanes": self.get_lane_info(),
        }


def _default_lane_color(index: int) -> str:
    """Default colors for user-specified lanes."""
    colors = [
        "#E63946",  # Red
        "#F4A261",  # Orange
        "#E9C46A",  # Gold
        "#2A9D8F",  # Teal
        "#264653",  # Dark blue
        "#9B59B6",  # Purple
        "#3498DB",  # Blue
        "#1ABC9C",  # Turquoise
        "#E74C3C",  # Crimson
        "#F39C12",  # Amber
        "#27AE60",  # Green
        "#8E44AD",  # Violet
    ]
    return colors[index % len(colors)]


# =============================================================================
# MAIN API FUNCTIONS
# =============================================================================

def detect_lanes_for_manual_mapping(
    hits: List[Dict],
    max_lanes: int = 12,
) -> LaneConfiguration:
    """
    Use AI to detect optimal lane configuration for manual mapping.
    
    This is called when user chooses "Yes" to AI lane detection.
    Returns a configuration that user can then adjust if desired.
    
    Args:
        hits: List of classified drum hits from audio analysis
        max_lanes: Maximum lanes to detect (default 12 for flexibility)
        
    Returns:
        LaneConfiguration with AI-detected settings
    """
    if not HAS_DYNAMIC_LANES or not hits:
        # Fallback: return default 7-lane config
        return LaneConfiguration(
            lane_count=7,
            source=LaneDetectionChoice.AI_DETECT,
            detected_components=[],
            user_modified=False,
        )
    
    # Build dynamic layout
    builder = DynamicLaneLayoutBuilder(
        min_lanes=3,
        max_lanes=max_lanes,
        merge_ghost_notes=True,
        merge_similar_cymbals=True,
        merge_tom_varieties=False,
    )
    layout = builder.build_from_hits(hits)
    
    return LaneConfiguration(
        lane_count=layout.lane_count,
        source=LaneDetectionChoice.AI_DETECT,
        detected_layout=layout,
        detected_components=list(layout.unique_components),
        user_modified=False,
    )


def create_user_specified_lanes(lane_count: int) -> LaneConfiguration:
    """
    Create lane configuration with user-specified count.
    
    This is called when user chooses "No" to AI detection
    and specifies their own lane count.
    
    Args:
        lane_count: Number of lanes (3-12)
        
    Returns:
        LaneConfiguration with user settings
    """
    if lane_count < 3 or lane_count > 12:
        raise ValueError("Lane count must be between 3 and 12")
    
    return LaneConfiguration(
        lane_count=lane_count,
        source=LaneDetectionChoice.USER_SPECIFY,
        detected_layout=None,
        detected_components=[],
        user_modified=False,  # User chose this, not "modified" from AI
    )


def get_lane_detection_prompt() -> Dict[str, Any]:
    """
    Get the prompt/dialog content for the lane detection choice.
    
    Returns structured data that the frontend can use to display
    the prompt to the user.
    
    Returns:
        Dictionary with prompt content
    """
    return {
        "title": "Lane Configuration",
        "message": "Would you like the AI to detect the number of lanes based on the drums in the audio?",
        "description": (
            "The AI can analyze the audio and suggest an optimal number of lanes "
            "based on what drums/cymbals are detected. You can always adjust this later."
        ),
        "options": [
            {
                "id": "ai_detect",
                "label": "Yes, detect lanes automatically",
                "description": "AI will analyze the audio and suggest lanes. You can adjust afterward.",
                "recommended": True,
            },
            {
                "id": "user_specify",
                "label": "No, I'll set it myself",
                "description": "Choose your own lane count (3-12 lanes).",
                "recommended": False,
            },
        ],
        "lane_range": {
            "min": 3,
            "max": 12,
            "default": 7,
            "presets": [
                {"count": 4, "label": "Simple (4 lanes)", "description": "Kick, Snare, Hi-hat, Crash"},
                {"count": 5, "label": "Standard (5 lanes)", "description": "Basic kit with toms"},
                {"count": 7, "label": "Full (7 lanes)", "description": "Complete drum kit"},
                {"count": 8, "label": "Extended (8 lanes)", "description": "Full kit + extras"},
            ],
        },
    }


def adjust_lane_configuration(
    config: LaneConfiguration,
    new_lane_count: Optional[int] = None,
    lane_names: Optional[Dict[int, str]] = None,
    lane_colors: Optional[Dict[int, str]] = None,
) -> LaneConfiguration:
    """
    Adjust an existing lane configuration.
    
    This allows users to modify their lane settings at any time,
    whether they chose AI detection or manual specification initially.
    
    Args:
        config: Existing configuration to modify
        new_lane_count: New lane count (optional)
        lane_names: Custom lane names to set (optional)
        lane_colors: Custom lane colors to set (optional)
        
    Returns:
        Updated configuration
    """
    if new_lane_count is not None:
        config.set_lane_count(new_lane_count)
    
    if lane_names:
        for idx, name in lane_names.items():
            config.set_lane_name(idx, name)
    
    if lane_colors:
        for idx, color in lane_colors.items():
            config.set_lane_color(idx, color)
    
    return config


# =============================================================================
# QUICK ANALYSIS (for showing preview before full detection)
# =============================================================================

def quick_lane_preview(hits: List[Dict]) -> Dict[str, Any]:
    """
    Quick preview of what lanes would be detected.
    
    Faster than full detection - just counts unique components
    without building full layout. Good for showing user a preview
    before they commit to AI detection.
    
    Args:
        hits: List of classified drum hits
        
    Returns:
        Preview information
    """
    if not hits:
        return {
            "estimated_lanes": 7,
            "components_found": 0,
            "categories": [],
            "message": "No drums detected - using default 7 lanes",
        }
    
    # Count unique components
    components = set()
    categories = set()
    
    for hit in hits:
        comp = hit.get("component", "").lower()
        if comp:
            components.add(comp)
            if HAS_DYNAMIC_LANES:
                cat = classify_component(comp)
                categories.add(cat.name)
    
    # Rough estimate: one lane per category, max 2-3 for cymbals/toms
    estimated = min(len(categories) + 2, 12)
    estimated = max(estimated, 3)
    
    return {
        "estimated_lanes": estimated,
        "components_found": len(components),
        "categories": list(categories),
        "sample_components": list(components)[:10],
        "message": f"Detected ~{len(components)} drum sounds in {len(categories)} categories",
    }
