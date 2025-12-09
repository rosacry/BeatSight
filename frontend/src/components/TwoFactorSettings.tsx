/**
 * TwoFactorSettings - Component for managing Two-Factor Authentication.
 * Allows users to enable/disable 2FA and manage backup codes.
 */

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    useTwoFactorStatus,
    useTwoFactorSetup,
    useTwoFactorEnable,
    useTwoFactorDisable,
    useTwoFactorRegenerateBackupCodes,
} from '@/hooks/useTwoFactor'
import { useToast } from '@/components/Toast'

type SetupStep = 'idle' | 'qr' | 'verify' | 'backup' | 'complete'

export function TwoFactorSettings() {
    const { success, error: showError } = useToast()
    const { data: status, isLoading: statusLoading } = useTwoFactorStatus()
    const setupMutation = useTwoFactorSetup()
    const enableMutation = useTwoFactorEnable()
    const disableMutation = useTwoFactorDisable()
    const regenerateBackupCodesMutation = useTwoFactorRegenerateBackupCodes()

    const [setupStep, setSetupStep] = useState<SetupStep>('idle')
    const [qrCode, setQrCode] = useState<string | null>(null)
    const [backupCodes, setBackupCodes] = useState<string[]>([])
    const [verificationCode, setVerificationCode] = useState('')
    const [password, setPassword] = useState('')
    const [showDisableModal, setShowDisableModal] = useState(false)
    const [showBackupCodesModal, setShowBackupCodesModal] = useState(false)

    const handleStartSetup = async () => {
        try {
            const result = await setupMutation.mutateAsync()
            setQrCode(result.qr_code_base64)
            setBackupCodes(result.backup_codes)
            setSetupStep('qr')
        } catch (err) {
            showError('Setup Failed', err instanceof Error ? err.message : 'Failed to start 2FA setup')
        }
    }

    const handleVerify = async () => {
        if (verificationCode.length !== 6) {
            showError('Invalid Code', 'Please enter a 6-digit code')
            return
        }

        try {
            await enableMutation.mutateAsync({ verificationCode })
            setSetupStep('backup')
            success('2FA Enabled', 'Two-factor authentication is now active')
        } catch (err) {
            showError('Verification Failed', err instanceof Error ? err.message : 'Invalid code')
        }
    }

    const handleDisable = async () => {
        if (!password) {
            showError('Password Required', 'Please enter your password')
            return
        }

        try {
            await disableMutation.mutateAsync({ password })
            setShowDisableModal(false)
            setPassword('')
            success('2FA Disabled', 'Two-factor authentication has been disabled')
        } catch (err) {
            showError('Error', err instanceof Error ? err.message : 'Failed to disable 2FA')
        }
    }

    const handleRegenerateBackupCodes = async () => {
        try {
            const result = await regenerateBackupCodesMutation.mutateAsync()
            setBackupCodes(result.backup_codes)
            setShowBackupCodesModal(true)
            success('Codes Generated', 'New backup codes have been created')
        } catch (err) {
            showError('Error', err instanceof Error ? err.message : 'Failed to regenerate codes')
        }
    }

    const copyBackupCodes = () => {
        navigator.clipboard.writeText(backupCodes.join('\n'))
        success('Copied', 'Backup codes copied to clipboard')
    }

    if (statusLoading) {
        return (
            <div className="space-y-4">
                {/* Loading skeleton that matches the actual layout */}
                <div className="p-4 rounded-xl bg-slate-800/30 border border-slate-700/50">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-slate-700/50 animate-pulse" />
                            <div className="space-y-2">
                                <div className="h-4 w-40 bg-slate-700/50 rounded animate-pulse" />
                                <div className="h-3 w-24 bg-slate-700/50 rounded animate-pulse" />
                            </div>
                        </div>
                        <div className="h-9 w-20 bg-slate-700/50 rounded-lg animate-pulse" />
                    </div>
                </div>
            </div>
        )
    }

    const is2FAEnabled = status?.enabled ?? false

    return (
        <div className="space-y-4">
            {/* Main 2FA Card */}
            <div className="p-4 rounded-xl bg-slate-800/30 border border-slate-700/50">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${is2FAEnabled ? 'bg-green-500/20' : 'bg-slate-700/50'
                            }`}>
                            <svg
                                className={`w-5 h-5 ${is2FAEnabled ? 'text-green-400' : 'text-slate-400'}`}
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"
                                />
                            </svg>
                        </div>
                        <div>
                            <p className="text-white font-medium">Two-Factor Authentication</p>
                            <p className="text-sm text-gray-400">
                                {is2FAEnabled
                                    ? `Enabled • ${status?.backup_codes_remaining || 0} backup codes remaining`
                                    : 'Add an extra layer of security to your account'
                                }
                            </p>
                        </div>
                    </div>
                    {is2FAEnabled ? (
                        <div className="flex items-center gap-2">
                            <button
                                onClick={handleRegenerateBackupCodes}
                                disabled={regenerateBackupCodesMutation.isPending}
                                className="px-3 py-1.5 text-sm text-cyan-400 hover:text-cyan-300 
                                         hover:bg-cyan-500/10 rounded-lg transition-colors"
                            >
                                Backup Codes
                            </button>
                            <button
                                onClick={() => setShowDisableModal(true)}
                                className="px-3 py-1.5 text-sm text-red-400 hover:text-red-300 
                                         hover:bg-red-500/10 rounded-lg transition-colors"
                            >
                                Disable
                            </button>
                        </div>
                    ) : (
                        <button
                            onClick={handleStartSetup}
                            disabled={setupMutation.isPending || setupStep !== 'idle'}
                            className="px-4 py-2 text-sm font-medium text-white bg-cyan-500 
                                     hover:bg-cyan-400 rounded-lg transition-colors
                                     disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {setupMutation.isPending ? 'Setting up...' : 'Enable 2FA'}
                        </button>
                    )}
                </div>
            </div>

            {/* Setup Flow */}
            <AnimatePresence mode="wait">
                {setupStep === 'qr' && qrCode && (
                    <motion.div
                        key="qr"
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="p-6 rounded-xl bg-slate-800/50 border border-cyan-500/30"
                    >
                        <h3 className="text-lg font-medium text-white mb-4">
                            Step 1: Scan QR Code
                        </h3>
                        <p className="text-gray-400 text-sm mb-4">
                            Open your authenticator app (like Google Authenticator, Authy, or 1Password)
                            and scan this QR code:
                        </p>
                        <div className="flex justify-center mb-6">
                            <div className="p-4 bg-white rounded-xl">
                                <img
                                    src={`data:image/png;base64,${qrCode}`}
                                    alt="2FA QR Code"
                                    className="w-48 h-48"
                                />
                            </div>
                        </div>
                        <button
                            onClick={() => setSetupStep('verify')}
                            className="w-full py-2.5 text-sm font-medium text-white bg-cyan-500 
                                     hover:bg-cyan-400 rounded-lg transition-colors"
                        >
                            I've Scanned the Code
                        </button>
                    </motion.div>
                )}

                {setupStep === 'verify' && (
                    <motion.div
                        key="verify"
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="p-6 rounded-xl bg-slate-800/50 border border-cyan-500/30"
                    >
                        <h3 className="text-lg font-medium text-white mb-4">
                            Step 2: Enter Verification Code
                        </h3>
                        <p className="text-gray-400 text-sm mb-4">
                            Enter the 6-digit code from your authenticator app:
                        </p>
                        <div className="flex justify-center mb-6">
                            <input
                                type="text"
                                value={verificationCode}
                                onChange={(e) => {
                                    const value = e.target.value.replace(/\D/g, '').slice(0, 6)
                                    setVerificationCode(value)
                                }}
                                placeholder="000000"
                                className="w-40 px-4 py-3 text-center text-2xl font-mono tracking-[0.5em] 
                                         bg-slate-700/50 border border-slate-600 rounded-xl
                                         text-white placeholder:text-slate-500
                                         focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none"
                                autoFocus
                            />
                        </div>
                        <div className="flex gap-3">
                            <button
                                onClick={() => setSetupStep('qr')}
                                className="flex-1 py-2.5 text-sm font-medium text-gray-400 
                                         hover:text-white bg-slate-700/50 hover:bg-slate-700
                                         rounded-lg transition-colors"
                            >
                                Back
                            </button>
                            <button
                                onClick={handleVerify}
                                disabled={verificationCode.length !== 6 || enableMutation.isPending}
                                className="flex-1 py-2.5 text-sm font-medium text-white bg-cyan-500 
                                         hover:bg-cyan-400 rounded-lg transition-colors
                                         disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {enableMutation.isPending ? 'Verifying...' : 'Verify & Enable'}
                            </button>
                        </div>
                    </motion.div>
                )}

                {setupStep === 'backup' && (
                    <motion.div
                        key="backup"
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="p-6 rounded-xl bg-slate-800/50 border border-green-500/30"
                    >
                        <div className="flex items-center gap-2 mb-4">
                            <svg className="w-6 h-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <h3 className="text-lg font-medium text-white">
                                2FA Enabled Successfully!
                            </h3>
                        </div>
                        <p className="text-gray-400 text-sm mb-4">
                            Save these backup codes in a secure place. You can use them to access your
                            account if you lose your authenticator device:
                        </p>
                        <div className="grid grid-cols-2 gap-2 p-4 bg-slate-900/50 rounded-lg mb-4 font-mono text-sm">
                            {backupCodes.map((code, i) => (
                                <div key={i} className="text-gray-300">{code}</div>
                            ))}
                        </div>
                        <div className="flex gap-3">
                            <button
                                onClick={copyBackupCodes}
                                className="flex-1 py-2.5 text-sm font-medium text-cyan-400 
                                         bg-cyan-500/10 hover:bg-cyan-500/20
                                         rounded-lg transition-colors"
                            >
                                Copy Codes
                            </button>
                            <button
                                onClick={() => {
                                    setSetupStep('idle')
                                    setQrCode(null)
                                    setBackupCodes([])
                                    setVerificationCode('')
                                }}
                                className="flex-1 py-2.5 text-sm font-medium text-white bg-cyan-500 
                                         hover:bg-cyan-400 rounded-lg transition-colors"
                            >
                                Done
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Disable 2FA Modal */}
            <AnimatePresence>
                {showDisableModal && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
                        onClick={() => setShowDisableModal(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.95, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.95, opacity: 0 }}
                            className="w-full max-w-md p-6 bg-slate-800 rounded-2xl border border-slate-700 shadow-2xl"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <h3 className="text-lg font-semibold text-white mb-2">Disable 2FA</h3>
                            <p className="text-gray-400 text-sm mb-4">
                                Enter your password to confirm disabling two-factor authentication.
                            </p>
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="Your password"
                                className="w-full px-4 py-3 bg-slate-700/50 border border-slate-600 rounded-lg
                                         text-white placeholder:text-slate-500
                                         focus:border-red-500 focus:ring-1 focus:ring-red-500 focus:outline-none mb-4"
                                autoFocus
                            />
                            <div className="flex gap-3">
                                <button
                                    onClick={() => {
                                        setShowDisableModal(false)
                                        setPassword('')
                                    }}
                                    className="flex-1 py-2.5 text-sm font-medium text-gray-400 
                                             hover:text-white bg-slate-700/50 hover:bg-slate-700
                                             rounded-lg transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleDisable}
                                    disabled={!password || disableMutation.isPending}
                                    className="flex-1 py-2.5 text-sm font-medium text-white bg-red-500 
                                             hover:bg-red-400 rounded-lg transition-colors
                                             disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {disableMutation.isPending ? 'Disabling...' : 'Disable 2FA'}
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Backup Codes Modal */}
            <AnimatePresence>
                {showBackupCodesModal && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
                        onClick={() => setShowBackupCodesModal(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.95, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.95, opacity: 0 }}
                            className="w-full max-w-md p-6 bg-slate-800 rounded-2xl border border-slate-700 shadow-2xl"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <h3 className="text-lg font-semibold text-white mb-2">New Backup Codes</h3>
                            <p className="text-gray-400 text-sm mb-4">
                                Your old backup codes have been invalidated. Save these new codes:
                            </p>
                            <div className="grid grid-cols-2 gap-2 p-4 bg-slate-900/50 rounded-lg mb-4 font-mono text-sm">
                                {backupCodes.map((code, i) => (
                                    <div key={i} className="text-gray-300">{code}</div>
                                ))}
                            </div>
                            <div className="flex gap-3">
                                <button
                                    onClick={copyBackupCodes}
                                    className="flex-1 py-2.5 text-sm font-medium text-cyan-400 
                                             bg-cyan-500/10 hover:bg-cyan-500/20
                                             rounded-lg transition-colors"
                                >
                                    Copy Codes
                                </button>
                                <button
                                    onClick={() => setShowBackupCodesModal(false)}
                                    className="flex-1 py-2.5 text-sm font-medium text-white bg-cyan-500 
                                             hover:bg-cyan-400 rounded-lg transition-colors"
                                >
                                    Done
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}
