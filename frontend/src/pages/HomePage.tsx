import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getQueueLength, getQuota } from '@/api/client'

export function HomePage() {
    const { data: queueData } = useQuery({
        queryKey: ['queueLength'],
        queryFn: getQueueLength,
        refetchInterval: 30000, // Refresh every 30s
    })

    const { data: quotaData } = useQuery({
        queryKey: ['quota'],
        queryFn: getQuota,
    })

    return (
        <div className="space-y-8">
            {/* Hero Section */}
            <div className="text-center py-12">
                <h1 className="text-4xl font-bold text-white mb-4">
                    AI Drum Beatmap Generator
                </h1>
                <p className="text-xl text-gray-400 max-w-2xl mx-auto">
                    Upload any song and get an AI-generated drum practice beatmap in minutes.
                    Perfect for drummers of all skill levels.
                </p>

                <div className="mt-8 flex justify-center gap-4">
                    <button className="btn btn-primary text-lg px-8 py-3">
                        Upload Song
                    </button>
                    <Link to="/jobs" className="btn btn-secondary text-lg px-8 py-3">
                        View Queue
                    </Link>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="card text-center">
                    <div className="text-3xl font-bold text-primary-400">
                        {queueData?.queue_length ?? '-'}
                    </div>
                    <div className="text-gray-400 mt-1">Jobs in Queue</div>
                </div>

                <div className="card text-center">
                    <div className="text-3xl font-bold text-green-400">
                        {quotaData?.remaining_today ?? '-'}
                    </div>
                    <div className="text-gray-400 mt-1">Generations Available Today</div>
                </div>

                <div className="card text-center">
                    <div className="text-3xl font-bold text-accent-400">
                        ~2-5 min
                    </div>
                    <div className="text-gray-400 mt-1">Average Processing Time</div>
                </div>
            </div>

            {/* Features Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-12">
                <div className="card">
                    <div className="w-12 h-12 bg-primary-500/20 rounded-lg flex items-center justify-center mb-4">
                        <svg className="w-6 h-6 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                        </svg>
                    </div>
                    <h3 className="text-lg font-medium text-white mb-2">Any Song Format</h3>
                    <p className="text-gray-400">
                        Upload MP3, WAV, or FLAC files. Our AI analyzes the audio and extracts drum patterns.
                    </p>
                </div>

                <div className="card">
                    <div className="w-12 h-12 bg-green-500/20 rounded-lg flex items-center justify-center mb-4">
                        <svg className="w-6 h-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                    </div>
                    <h3 className="text-lg font-medium text-white mb-2">Fast Processing</h3>
                    <p className="text-gray-400">
                        Most songs are processed in 2-5 minutes using our optimized GPU pipeline.
                    </p>
                </div>

                <div className="card">
                    <div className="w-12 h-12 bg-accent-500/20 rounded-lg flex items-center justify-center mb-4">
                        <svg className="w-6 h-6 text-accent-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                        </svg>
                    </div>
                    <h3 className="text-lg font-medium text-white mb-2">Customizable</h3>
                    <p className="text-gray-400">
                        Edit and customize generated beatmaps in our built-in editor.
                    </p>
                </div>
            </div>

            {/* How It Works */}
            <div className="mt-16">
                <h2 className="text-2xl font-bold text-white text-center mb-8">How It Works</h2>
                <div className="flex flex-col md:flex-row items-center justify-center gap-8">
                    <div className="flex flex-col items-center text-center">
                        <div className="w-12 h-12 bg-gray-700 rounded-full flex items-center justify-center text-white font-bold mb-3">1</div>
                        <p className="text-white font-medium">Upload Song</p>
                        <p className="text-gray-400 text-sm">Any MP3, WAV, or FLAC</p>
                    </div>
                    <div className="hidden md:block w-16 h-0.5 bg-gray-700" />
                    <div className="flex flex-col items-center text-center">
                        <div className="w-12 h-12 bg-gray-700 rounded-full flex items-center justify-center text-white font-bold mb-3">2</div>
                        <p className="text-white font-medium">AI Processing</p>
                        <p className="text-gray-400 text-sm">Drum separation & analysis</p>
                    </div>
                    <div className="hidden md:block w-16 h-0.5 bg-gray-700" />
                    <div className="flex flex-col items-center text-center">
                        <div className="w-12 h-12 bg-gray-700 rounded-full flex items-center justify-center text-white font-bold mb-3">3</div>
                        <p className="text-white font-medium">Get Beatmap</p>
                        <p className="text-gray-400 text-sm">Download & practice</p>
                    </div>
                </div>
            </div>
        </div>
    )
}
