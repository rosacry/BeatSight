// @ts-check
import { themes as prismThemes } from "prism-react-renderer";

/** @type {import('@docusaurus/types').Config} */
const config = {
    title: "BeatSight",
    tagline: "AI-powered drum transcription for drummers",
    favicon: "img/favicon.ico",

    url: "https://docs.beatsight.io",
    baseUrl: "/",

    organizationName: "rosacry",
    projectName: "BeatSight",

    onBrokenLinks: "warn",
    onBrokenMarkdownLinks: "warn",

    i18n: {
        defaultLocale: "en",
        locales: ["en"],
    },

    presets: [
        [
            "classic",
            /** @type {import('@docusaurus/preset-classic').Options} */
            ({
                docs: {
                    sidebarPath: "./sidebars.js",
                    editUrl: "https://github.com/rosacry/BeatSight/tree/main/docs-site/",
                },
                blog: {
                    showReadingTime: true,
                    editUrl: "https://github.com/rosacry/BeatSight/tree/main/docs-site/",
                },
                theme: {
                    customCss: "./src/css/custom.css",
                },
            }),
        ],
    ],

    themeConfig:
        /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
        ({
            image: "img/beatsight-social-card.png",
            navbar: {
                title: "BeatSight",
                logo: {
                    alt: "BeatSight Logo",
                    src: "img/logo.png",
                },
                items: [
                    {
                        type: "docSidebar",
                        sidebarId: "tutorialSidebar",
                        position: "left",
                        label: "Documentation",
                    },
                    {
                        to: "/docs/api",
                        label: "API Reference",
                        position: "left",
                    },
                    { to: "/blog", label: "Blog", position: "left" },
                    {
                        href: "https://github.com/rosacry/BeatSight",
                        label: "GitHub",
                        position: "right",
                    },
                ],
            },
            footer: {
                style: "dark",
                links: [
                    {
                        title: "Docs",
                        items: [
                            {
                                label: "Getting Started",
                                to: "/docs/intro",
                            },
                            {
                                label: "API Reference",
                                to: "/docs/api",
                            },
                            {
                                label: "Beatmap Format",
                                to: "/docs/beatmap-format",
                            },
                        ],
                    },
                    {
                        title: "Community",
                        items: [
                            {
                                label: "Discord",
                                href: "https://discord.gg/T57fDWcHDQ",
                            },
                            {
                                label: "GitHub Discussions",
                                href: "https://github.com/rosacry/BeatSight/discussions",
                            },
                        ],
                    },
                    {
                        title: "More",
                        items: [
                            {
                                label: "Blog",
                                to: "/blog",
                            },
                            {
                                label: "GitHub",
                                href: "https://github.com/rosacry/BeatSight",
                            },
                        ],
                    },
                ],
                copyright: `Copyright © ${new Date().getFullYear()} BeatSight. Built with Docusaurus.`,
            },
            prism: {
                theme: prismThemes.github,
                darkTheme: prismThemes.dracula,
                additionalLanguages: ["bash", "json", "python", "csharp"],
            },
            colorMode: {
                defaultMode: "dark",
                disableSwitch: false,
                respectPrefersColorScheme: true,
            },
            algolia: {
                // TODO: Set up Algolia DocSearch when ready
                appId: "YOUR_APP_ID",
                apiKey: "YOUR_SEARCH_API_KEY",
                indexName: "beatsight",
                contextualSearch: true,
            },
        }),
};

export default config;
