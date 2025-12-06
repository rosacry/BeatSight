/**
 * Centralized external links configuration.
 * Update these values when setting up community infrastructure.
 */

export const EXTERNAL_LINKS = {
    // GitHub
    github: {
        org: 'https://github.com/beatsight',
        repo: 'https://github.com/beatsight/beatsight',
        issues: 'https://github.com/beatsight/beatsight/issues',
        discussions: 'https://github.com/beatsight/beatsight/discussions',
    },

    // Community
    community: {
        discord: 'https://discord.gg/T57fDWcHDQ',
        // Use GitHub Discussions as fallback community space
        forum: 'https://github.com/beatsight/beatsight/discussions',
    },

    // Documentation (update when docs site is deployed)
    docs: {
        // TODO: Update when documentation site is deployed
        main: null as string | null, // e.g., 'https://docs.beatsight.io'
        api: null as string | null, // e.g., 'https://docs.beatsight.io/api'
        // Fallback to GitHub docs folder
        github: 'https://github.com/beatsight/beatsight/tree/main/docs',
    },

    // Desktop app downloads (update when releases are published)
    downloads: {
        windows: null as string | null,
        mac: null as string | null,
        linux: null as string | null,
        // Fallback to GitHub releases
        releases: 'https://github.com/beatsight/beatsight/releases',
    },

    // Legal pages
    legal: {
        privacy: '/privacy', // Internal route
        terms: '/terms', // Internal route
        contact: 'mailto:support@beatsight.io',
    },

    // Social media
    social: {
        twitter: null as string | null,
        youtube: null as string | null,
    },
} as const

/**
 * Get community link with fallback to GitHub Discussions
 */
export function getCommunityLink(): string {
    return EXTERNAL_LINKS.community.discord ?? EXTERNAL_LINKS.community.forum
}

/**
 * Get documentation link with fallback to GitHub docs
 */
export function getDocsLink(): string {
    return EXTERNAL_LINKS.docs.main ?? EXTERNAL_LINKS.docs.github
}

/**
 * Get API documentation link with fallback
 */
export function getApiDocsLink(): string {
    return EXTERNAL_LINKS.docs.api ?? EXTERNAL_LINKS.docs.github + '/API_REFERENCE.md'
}

/**
 * Get desktop download link with fallback to releases page
 */
export function getDownloadLink(): string {
    return EXTERNAL_LINKS.downloads.releases
}

/**
 * Check if Discord is configured
 */
export function hasDiscord(): boolean {
    return EXTERNAL_LINKS.community.discord !== null
}

/**
 * Check if docs site is configured
 */
export function hasDocsSite(): boolean {
    return EXTERNAL_LINKS.docs.main !== null
}
