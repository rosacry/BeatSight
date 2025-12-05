/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
    tutorialSidebar: [
        'intro',
        {
            type: 'category',
            label: 'Getting Started',
            items: [
                'getting-started/installation',
                'getting-started/first-transcription',
            ],
        },
        {
            type: 'category',
            label: 'API Reference',
            items: [
                'api/overview',
            ],
        },
    ],
};

export default sidebars;
