// Copyright (c) BeatSight. Licensed under the MIT Licence.
// Extracted from SettingsScreen.cs on December 3, 2025 for maintainability.
// See ENGINEERING_ACTION_TRACKER.md item 2.2

using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Logging;
using osu.Framework.Platform;
using osuTK;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;

namespace BeatSight.Game.Screens.Settings
{
    /// <summary>
    /// Settings section for AI processing configuration.
    /// Includes developer mode unlock for local AI pipeline settings.
    /// </summary>
    public partial class AISettingsSection : SettingsSection
    {
        private readonly BeatSightConfigManager config;
        private readonly GameHost host;
        private FillFlowContainer developerContent = null!;
        private Container developerUnlockSection = null!;
        private Bindable<bool> developerModeEnabled = null!;

        /// <summary>
        /// SHA-256 hash of the developer password.
        /// The actual password should be set via BEATSIGHT_DEV_PASSWORD environment variable
        /// or entered by the developer. This hash is for the default dev password.
        /// </summary>
        /// <remarks>
        /// SECURITY NOTE: This hash is visible in the open-source code. For production use,
        /// developers should set their own password via the BEATSIGHT_DEV_PASSWORD environment variable.
        /// The default password is intentionally weak for local development convenience.
        /// </remarks>
        private const string DEVELOPER_PASSWORD_HASH = "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"; // SHA-256 of "123"

        public AISettingsSection(BeatSightConfigManager config, GameHost host, Container dropdownOverlay, SettingsTooltipOverlay tooltipOverlay)
            : base("AI / Processing", dropdownOverlay, tooltipOverlay)
        {
            this.config = config;
            this.host = host;
        }

        protected override Drawable createContent()
        {
            developerModeEnabled = config.GetBindable<bool>(BeatSightSetting.DeveloperModeEnabled);

            developerContent = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 12),
                Alpha = developerModeEnabled.Value ? 1 : 0
            };

            developerUnlockSection = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y
            };

            updateDeveloperUI();
            developerModeEnabled.BindValueChanged(_ => updateDeveloperUI(), true);

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 12),
                Children = new Drawable[]
                {
                    createInfoBox(),
                    developerUnlockSection,
                    developerContent
                }
            };
        }

        private void updateDeveloperUI()
        {
            if (developerModeEnabled.Value)
            {
                developerContent.ClearTransforms();
                developerContent.FadeIn(200);
                populateDeveloperContent();
                developerUnlockSection.Child = createDeveloperDisableButton();
            }
            else
            {
                developerContent.ClearTransforms();
                developerContent.FadeOut(200);
                developerUnlockSection.Child = createDeveloperUnlockUI();
            }
        }

        private Drawable createInfoBox()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Masking = true,
                CornerRadius = 8,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.AccentPrimary.Opacity(0.1f)
                    },
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Padding = new MarginPadding(16),
                        Spacing = new Vector2(0, 8),
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = "AI Processing",
                                Font = BeatSightFont.Section(18f),
                                Colour = UITheme.AccentPrimary
                            },
                            new SpriteText
                            {
                                Text = "BeatSight uses server-side AI processing to analyze your songs.",
                                Font = BeatSightFont.Body(14f),
                                Colour = UITheme.TextSecondary
                            },
                            new SpriteText
                            {
                                Text = "All AI computation runs on our servers - no local GPU or processing required.",
                                Font = BeatSightFont.Body(14f),
                                Colour = UITheme.TextSecondary
                            },
                            new SpriteText
                            {
                                Text = "This ensures consistent results and keeps your computer running smoothly.",
                                Font = BeatSightFont.Body(14f),
                                Colour = UITheme.TextMuted
                            }
                        }
                    }
                }
            };
        }

        private Drawable createDeveloperUnlockUI()
        {
            BasicTextBox passwordBox = null!;

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 8),
                Margin = new MarginPadding { Top = 20 },
                Children = new Drawable[]
                {
                    new SpriteText
                    {
                        Text = "Developer Mode",
                        Font = BeatSightFont.Caption(14f),
                        Colour = UITheme.TextMuted
                    },
                    new SpriteText
                    {
                        Text = "For BeatSight developers only. Enables local AI processing.",
                        Font = BeatSightFont.Caption(12f),
                        Colour = UITheme.TextMuted
                    },
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(8, 0),
                        Children = new Drawable[]
                        {
                            passwordBox = new BasicTextBox
                            {
                                Width = 200,
                                Height = 32,
                                PlaceholderText = "Enter password...",
                                CommitOnFocusLost = false
                            },
                            new BeatSightButton
                            {
                                Text = "Unlock",
                                Width = 80,
                                Height = 32,
                                Action = () =>
                                {
                                    if (verifyDeveloperPassword(passwordBox.Text))
                                    {
                                        developerModeEnabled.Value = true;
                                        Logger.Log("Developer mode enabled", LoggingTarget.Runtime, LogLevel.Important);
                                    }
                                    else
                                    {
                                        passwordBox.Text = string.Empty;
                                        passwordBox.FlashColour(UITheme.AccentError, 500);
                                    }
                                },
                                BackgroundColour = UITheme.SurfaceAlt
                            }
                        }
                    }
                }
            };
        }

        private Drawable createDeveloperDisableButton()
        {
            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 8),
                Margin = new MarginPadding { Top = 20 },
                Children = new Drawable[]
                {
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(8, 0),
                        Children = new Drawable[]
                        {
                            new Container
                            {
                                AutoSizeAxes = Axes.Both,
                                Masking = true,
                                CornerRadius = 4,
                                Children = new Drawable[]
                                {
                                    new Box
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Colour = UITheme.AccentSuccess.Opacity(0.2f)
                                    },
                                    new SpriteText
                                    {
                                        Text = "DEVELOPER MODE ACTIVE",
                                        Font = BeatSightFont.Caption(12f),
                                        Colour = UITheme.AccentSuccess,
                                        Padding = new MarginPadding { Horizontal = 8, Vertical = 4 }
                                    }
                                }
                            },
                            new BeatSightButton
                            {
                                Text = "Disable",
                                Width = 80,
                                Height = 28,
                                Action = () =>
                                {
                                    developerModeEnabled.Value = false;
                                    Logger.Log("Developer mode disabled", LoggingTarget.Runtime, LogLevel.Important);
                                },
                                BackgroundColour = UITheme.AccentError
                            }
                        }
                    }
                }
            };
        }

        private void populateDeveloperContent()
        {
            developerContent.Clear();
            developerContent.AddRange(new Drawable[]
            {
                createHeader("Local AI Pipeline (Developer Only)"),
                new SpriteText
                {
                    Text = "Warning: These settings use your local computer for AI processing.",
                    Font = BeatSightFont.Caption(12f),
                    Colour = UITheme.AccentWarning,
                    Margin = new MarginPadding { Bottom = 8 }
                },
                createTextBox("Python Environment Path", config.GetBindable<string>(BeatSightSetting.PythonPath)),
                createDropdown("Model Checkpoints", config.GetBindable<string>(BeatSightSetting.ModelVersion), new[] { "v1.0", "v2.0" }),
                CreateCheckbox("Use GPU / CUDA", config.GetBindable<bool>(BeatSightSetting.UseGpu)),
                createTextBox("Custom Model Path", config.GetBindable<string>(BeatSightSetting.CustomModelPath)),

                createHeader("External Services"),
                createTextBox("AcoustID API Key", config.GetBindable<string>(BeatSightSetting.AcoustIdApiKey), masked: true),

                createHeader("Default Generation Settings"),
                createDropdown("Default Quantization", config.GetBindable<string>(BeatSightSetting.DefaultQuantization), new[] { "quarter", "eighth", "sixteenth" }),
                CreateSlider("Default Sensitivity", config.GetBindable<double>(BeatSightSetting.DefaultSensitivity), 0, 100, 1),
                CreateCheckbox("Auto-generate on Import", config.GetBindable<bool>(BeatSightSetting.AutoGenerateOnImport)),

                createHeader("Cache Management"),
                createButton("Clear Feature Cache", () =>
                {
                    try
                    {
                        string currentDir = Directory.GetCurrentDirectory();
                        string featureCachePath = Path.Combine(currentDir, "data", "feature_cache");

                        if (!Directory.Exists(featureCachePath))
                        {
                            var dir = new DirectoryInfo(currentDir);
                            while (dir != null)
                            {
                                string check = Path.Combine(dir.FullName, "data", "feature_cache");
                                if (Directory.Exists(check))
                                {
                                    featureCachePath = check;
                                    break;
                                }
                                dir = dir.Parent;
                            }
                        }

                        if (Directory.Exists(featureCachePath))
                        {
                            Directory.Delete(featureCachePath, true);
                            Directory.CreateDirectory(featureCachePath);
                            Logger.Log($"Cleared feature cache at {featureCachePath}", LoggingTarget.Runtime, LogLevel.Important);
                        }
                        else
                        {
                            Logger.Log("Feature cache directory not found.", LoggingTarget.Runtime, LogLevel.Important);
                        }
                    }
                    catch (Exception ex)
                    {
                        Logger.Log($"Failed to clear feature cache: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
                    }
                }),
                createButton("Clear Separation Temp", () =>
                {
                    try
                    {
                        string tempPath = Path.Combine(Path.GetTempPath(), "beatsight_demucs");
                        if (Directory.Exists(tempPath))
                        {
                            Directory.Delete(tempPath, true);
                            Logger.Log($"Cleared separation temp at {tempPath}", LoggingTarget.Runtime, LogLevel.Important);
                        }
                        else
                        {
                            Logger.Log("Separation temp directory not found.", LoggingTarget.Runtime, LogLevel.Important);
                        }
                    }
                    catch (Exception ex)
                    {
                        Logger.Log($"Failed to clear separation temp: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
                    }
                })
            });
        }

        private Drawable createHeader(string text)
        {
            return new SpriteText
            {
                Text = text,
                Font = BeatSightFont.Section(20f),
                Colour = UITheme.AccentPrimary,
                Margin = new MarginPadding { Top = 20, Bottom = 5 }
            };
        }

        private SettingItem createTextBox(string label, Bindable<string> bindable, bool masked = false)
        {
            var textBox = new BasicTextBox
            {
                RelativeSizeAxes = Axes.X,
                Height = 30,
                Current = bindable
            };

            return CreateSettingItem(label, null, textBox);
        }

        private SettingItem createDropdown(string label, Bindable<string> bindable, IEnumerable<string> items)
        {
            var dropdown = new BeatSight.Game.UI.Components.Dropdown<string>
            {
                RelativeSizeAxes = Axes.X,
                Items = items,
                Current = bindable
            };

            return CreateSettingItem(label, null, dropdown);
        }

        private Drawable createButton(string text, Action action)
        {
            return new BeatSightButton
            {
                Text = text,
                RelativeSizeAxes = Axes.X,
                Height = 40,
                Action = action,
                BackgroundColour = UITheme.SurfaceAlt
            };
        }

        /// <summary>
        /// Verifies a developer password against the environment variable or default hash.
        /// </summary>
        /// <param name="password">The password entered by the user.</param>
        /// <returns>True if the password is valid.</returns>
        private static bool verifyDeveloperPassword(string password)
        {
            if (string.IsNullOrEmpty(password))
                return false;

            // First, check if a custom password is set via environment variable
            string? envPassword = Environment.GetEnvironmentVariable("BEATSIGHT_DEV_PASSWORD");
            if (!string.IsNullOrEmpty(envPassword))
            {
                // Direct comparison for environment-set password (assumed to be secure)
                return password == envPassword;
            }

            // Otherwise, compare against the default password hash
            string inputHash = computeSha256Hash(password);
            return string.Equals(inputHash, DEVELOPER_PASSWORD_HASH, StringComparison.OrdinalIgnoreCase);
        }

        /// <summary>
        /// Computes a SHA-256 hash of the input string.
        /// </summary>
        private static string computeSha256Hash(string input)
        {
            byte[] bytes = SHA256.HashData(Encoding.UTF8.GetBytes(input));
            StringBuilder builder = new StringBuilder();
            foreach (byte b in bytes)
            {
                builder.Append(b.ToString("x2"));
            }
            return builder.ToString();
        }
    }
}
