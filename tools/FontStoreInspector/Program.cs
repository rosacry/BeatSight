using System;
using System.Linq;
using System.Reflection;
using osu.Framework.Graphics;

Console.WriteLine("osu! FontStore.AddFont overloads:");
var drawableType = typeof(osu.Framework.Graphics.Drawable);
Console.WriteLine($"Drawable type? {drawableType.FullName}");
Console.WriteLine($"Assembly: {drawableType.Assembly.FullName}");

var fontStoreType = drawableType.Assembly.GetTypes().FirstOrDefault(t => t.Name == "FontStore");

if (fontStoreType == null)
{
    Console.WriteLine("FontStore type not found. Make sure osu.Framework is referenced.");
    return;
}

Console.WriteLine($"FontStore type resolved to {fontStoreType.FullName}");

var addFontMethods = fontStoreType
    .GetMethods(BindingFlags.Public | BindingFlags.Instance)
    .Where(m => m.Name == "AddFont")
    .OrderBy(m => m.ToString());

foreach (var method in addFontMethods)
{
    Console.WriteLine($" - {method}");
}
