# BmFontGenerator

> **Status:** Placeholder - Not Yet Implemented

## Intended Purpose

This tool is intended to generate BMFont (Bitmap Font) files for use with osu!framework's font rendering system.

## BMFont Format

BMFont is a bitmap font format originally created by AngelCode. It stores:
- **Glyph metrics** - Position, size, bearing, advance for each character
- **Texture atlas** - Pre-rendered glyphs packed into PNG images
- **Font metadata** - Family name, size, style, etc.

## Planned Features

- [ ] Convert TTF/OTF fonts to BMFont format
- [ ] Generate texture atlases with configurable padding
- [ ] Support for multiple font sizes in one atlas
- [ ] SDF (Signed Distance Field) generation for scalable fonts
- [ ] Export to `.fnt` text format compatible with osu!framework

## Related Tools

- [BMFont](https://www.angelcode.com/products/bmfont/) - Original AngelCode tool (Windows only)
- [msdf-atlas-gen](https://github.com/Chlumsky/msdf-atlas-gen) - Multi-channel SDF generator
- [Hiero](https://libgdx.com/wiki/tools/hiero) - Cross-platform bitmap font tool

## Usage (When Implemented)

```bash
cd tools/BmFontGenerator
# TBD
```

## Contributing

If you'd like to implement this tool, please:
1. Review how BeatSight currently loads fonts (see `BeatSightGame.cs`)
2. Check osu!framework's `FontStore` requirements
3. Open a PR with your implementation
