# FontStoreInspector

A diagnostic utility for inspecting the `FontStore.AddFont` method overloads in the osu!framework library.

## Purpose

This tool helps developers understand the available font registration APIs when working with osu!framework's font system. It uses reflection to enumerate all public `AddFont` method signatures from the `FontStore` class.

## Usage

```bash
cd tools/FontStoreInspector
dotnet run
```

## Output

The tool will print:
- The resolved `FontStore` type and its assembly
- All `AddFont` method overloads with their full signatures

## Example Output

```
osu! FontStore.AddFont overloads:
Drawable type? osu.Framework.Graphics.Drawable
Assembly: osu.Framework, Version=...
FontStore type resolved to osu.Framework.IO.Stores.FontStore
 - Void AddFont(osu.Framework.IO.Stores.IResourceStore`1[System.Byte[]], ...)
 - ...
```

## Requirements

- .NET 8.0 SDK
- Automatically downloads ppy.osu.Framework NuGet package

## When to Use

- Investigating font loading issues in BeatSight
- Understanding osu!framework font API changes after upgrades
- Debugging font registration problems
