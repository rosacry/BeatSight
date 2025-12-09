/**
 * useDocumentTitle - Hook for managing document title
 * 
 * Updates the browser tab title dynamically based on the current page.
 * Similar to osu!'s approach: "page | BeatSight"
 */

import { useEffect, useRef } from 'react'

const DEFAULT_TITLE = 'BeatSight'
const TITLE_SEPARATOR = ' | '

/**
 * Set the document title with the BeatSight suffix
 */
export function useDocumentTitle(title?: string) {
    const previousTitle = useRef(document.title)

    useEffect(() => {
        // Store the previous title to restore on unmount
        previousTitle.current = document.title

        // Set new title
        document.title = title
            ? `${title}${TITLE_SEPARATOR}${DEFAULT_TITLE}`
            : DEFAULT_TITLE

        // Restore previous title on unmount (optional behavior)
        return () => {
            // Don't restore - let the new page set its own title
        }
    }, [title])
}

/**
 * Set document title imperatively (for use outside React components)
 */
export function setDocumentTitle(title?: string) {
    document.title = title
        ? `${title}${TITLE_SEPARATOR}${DEFAULT_TITLE}`
        : DEFAULT_TITLE
}

export default useDocumentTitle
