/**
 * User profile page - redirects to /user/{user_number} for unified URLs (osu!-style)
 * 
 * This component redirects authenticated users to their public profile URL.
 * The unified profile page at /user/:userId handles both own and other profiles.
 */

import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { PageContentWrapper } from '@/components/ui/UnifiedTransitions'

export function ProfilePage() {
    const user = useAuthStore((state) => state.user)
    const navigate = useNavigate()

    useEffect(() => {
        if (user?.user_number) {
            // Redirect to unified profile URL (osu!-style)
            navigate(`/user/${user.user_number}`, { replace: true })
        }
    }, [user?.user_number, navigate])

    if (!user) {
        return (
            <PageContentWrapper className="flex items-center justify-center min-h-[60vh]">
                <p className="text-gray-400">Please log in to view your profile.</p>
            </PageContentWrapper>
        )
    }

    // Show loading while redirecting
    return (
        <PageContentWrapper isLoading className="min-h-[60vh]">
            <div className="flex items-center justify-center h-96">
                <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
            </div>
        </PageContentWrapper>
    )
}
