/**
 * React Query hooks for global search.
 */

import { useQuery } from '@tanstack/react-query'
import {
    globalSearch,
    searchUsersExtended,
    searchMapsExtended,
    type GlobalSearchResponse,
    type PaginatedUsersResponse,
    type PaginatedMapsResponse,
} from './search'

// Query keys
export const searchQueryKeys = {
    global: (query: string) => ['search', 'global', query] as const,
    users: (query: string, page: number) => ['search', 'users', query, page] as const,
    maps: (query: string, verifiedOnly: boolean, page: number) => ['search', 'maps', query, verifiedOnly, page] as const,
}

/**
 * Global search hook - searches across all content types.
 */
export function useGlobalSearch(query: string, enabled = true) {
    return useQuery<GlobalSearchResponse>({
        queryKey: searchQueryKeys.global(query),
        queryFn: () => globalSearch(query),
        enabled: enabled && query.length >= 1,
        staleTime: 30000, // 30 seconds
        placeholderData: (previousData) => previousData,
    })
}

/**
 * Extended user search with pagination.
 */
export function useSearchUsers(query: string, page: number = 1, enabled = true) {
    return useQuery<PaginatedUsersResponse>({
        queryKey: searchQueryKeys.users(query, page),
        queryFn: () => searchUsersExtended(query, page),
        enabled: enabled && query.length >= 1,
        staleTime: 30000,
    })
}

/**
 * Extended map search with pagination.
 */
export function useSearchMaps(
    query: string,
    verifiedOnly: boolean = false,
    page: number = 1,
    enabled = true
) {
    return useQuery<PaginatedMapsResponse>({
        queryKey: searchQueryKeys.maps(query, verifiedOnly, page),
        queryFn: () => searchMapsExtended(query, verifiedOnly, page),
        enabled: enabled && query.length >= 1,
        staleTime: 30000,
    })
}
