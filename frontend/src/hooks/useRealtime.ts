/**
 * Real-time Connection Manager Hook
 * 
 * Manages WebSocket and SSE connections with automatic reconnection,
 * heartbeat monitoring, and connection state tracking.
 */

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';

// ============================================================================
// Types
// ============================================================================

export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'reconnecting' | 'error';

export interface ConnectionStats {
    state: ConnectionState;
    latency: number | null;
    reconnectAttempts: number;
    lastConnected: Date | null;
    lastError: string | null;
    messagesReceived: number;
    messagesSent: number;
}

export interface UseRealtimeOptions {
    url: string;
    protocols?: string | string[];
    reconnect?: boolean;
    reconnectAttempts?: number;
    reconnectInterval?: number;
    heartbeatInterval?: number;
    onOpen?: (event: Event) => void;
    onClose?: (event: CloseEvent) => void;
    onError?: (event: Event) => void;
    onMessage?: (data: unknown) => void;
    onReconnect?: (attempt: number) => void;
    onStateChange?: (state: ConnectionState) => void;
}

interface RealtimeMessage {
    type: string;
    payload?: unknown;
    timestamp?: number;
}

// ============================================================================
// Hook Implementation
// ============================================================================

export function useRealtime(options: UseRealtimeOptions) {
    const {
        url,
        protocols,
        reconnect = true,
        reconnectAttempts = 5,
        reconnectInterval = 3000,
        heartbeatInterval = 30000,
        onOpen,
        onClose,
        onError,
        onMessage,
        onReconnect,
        onStateChange,
    } = options;

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>();
    const heartbeatIntervalRef = useRef<ReturnType<typeof setInterval>>();
    const reconnectCountRef = useRef(0);
    const lastPongRef = useRef<number>(Date.now());

    const [state, setState] = useState<ConnectionState>('disconnected');
    const [stats, setStats] = useState<ConnectionStats>({
        state: 'disconnected',
        latency: null,
        reconnectAttempts: 0,
        lastConnected: null,
        lastError: null,
        messagesReceived: 0,
        messagesSent: 0,
    });

    // Update connection state
    const updateState = useCallback((newState: ConnectionState) => {
        setState(newState);
        setStats(prev => ({ ...prev, state: newState }));
        onStateChange?.(newState);
    }, [onStateChange]);

    // Send message through WebSocket
    const send = useCallback((data: RealtimeMessage | string) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            const message = typeof data === 'string' ? data : JSON.stringify(data);
            wsRef.current.send(message);
            setStats(prev => ({ ...prev, messagesSent: prev.messagesSent + 1 }));
            return true;
        }
        return false;
    }, []);

    // Send ping for latency measurement
    const sendPing = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            send({ type: 'ping', timestamp: Date.now() });
        }
    }, [send]);

    // Connect to WebSocket
    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            return;
        }

        updateState('connecting');

        try {
            wsRef.current = new WebSocket(url, protocols);

            wsRef.current.onopen = (event) => {
                updateState('connected');
                reconnectCountRef.current = 0;
                setStats(prev => ({
                    ...prev,
                    lastConnected: new Date(),
                    reconnectAttempts: 0,
                    lastError: null,
                }));

                // Start heartbeat
                if (heartbeatInterval > 0) {
                    heartbeatIntervalRef.current = setInterval(() => {
                        sendPing();

                        // Check for stale connection (no pong in 2x heartbeat interval)
                        if (Date.now() - lastPongRef.current > heartbeatInterval * 2) {
                            console.warn('[WebSocket] Connection stale, reconnecting...');
                            wsRef.current?.close();
                        }
                    }, heartbeatInterval);
                }

                onOpen?.(event);
            };

            wsRef.current.onclose = (event) => {
                updateState('disconnected');
                clearInterval(heartbeatIntervalRef.current);

                if (reconnect && reconnectCountRef.current < reconnectAttempts) {
                    updateState('reconnecting');
                    reconnectCountRef.current++;
                    setStats(prev => ({ ...prev, reconnectAttempts: reconnectCountRef.current }));
                    onReconnect?.(reconnectCountRef.current);

                    // Exponential backoff
                    const delay = reconnectInterval * Math.pow(1.5, reconnectCountRef.current - 1);
                    reconnectTimeoutRef.current = setTimeout(connect, Math.min(delay, 30000));
                }

                onClose?.(event);
            };

            wsRef.current.onerror = (event) => {
                updateState('error');
                setStats(prev => ({ ...prev, lastError: 'Connection error' }));
                onError?.(event);
            };

            wsRef.current.onmessage = (event) => {
                setStats(prev => ({ ...prev, messagesReceived: prev.messagesReceived + 1 }));

                try {
                    const data = JSON.parse(event.data);

                    // Handle pong messages for latency calculation
                    if (data.type === 'pong' && data.timestamp) {
                        const latency = Date.now() - data.timestamp;
                        lastPongRef.current = Date.now();
                        setStats(prev => ({ ...prev, latency }));
                        return;
                    }

                    onMessage?.(data);
                } catch {
                    // Not JSON, pass raw data
                    onMessage?.(event.data);
                }
            };
        } catch (error) {
            updateState('error');
            setStats(prev => ({
                ...prev,
                lastError: error instanceof Error ? error.message : 'Unknown error'
            }));
        }
    }, [url, protocols, reconnect, reconnectAttempts, reconnectInterval, heartbeatInterval,
        updateState, sendPing, onOpen, onClose, onError, onMessage, onReconnect]);

    // Disconnect from WebSocket
    const disconnect = useCallback(() => {
        clearTimeout(reconnectTimeoutRef.current);
        clearInterval(heartbeatIntervalRef.current);
        reconnectCountRef.current = reconnectAttempts; // Prevent reconnection
        wsRef.current?.close();
        wsRef.current = null;
        updateState('disconnected');
    }, [reconnectAttempts, updateState]);

    // Auto-connect on mount
    useEffect(() => {
        connect();
        return () => {
            disconnect();
        };
    }, [connect, disconnect]);

    // Reconnect on visibility change
    useEffect(() => {
        const handleVisibilityChange = () => {
            if (document.visibilityState === 'visible' && state === 'disconnected') {
                reconnectCountRef.current = 0;
                connect();
            }
        };

        document.addEventListener('visibilitychange', handleVisibilityChange);
        return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
    }, [connect, state]);

    return useMemo(() => ({
        state,
        stats,
        send,
        connect,
        disconnect,
        isConnected: state === 'connected',
    }), [state, stats, send, connect, disconnect]);
}

// ============================================================================
// Server-Sent Events Hook
// ============================================================================

export interface UseSSEOptions {
    url: string;
    withCredentials?: boolean;
    onMessage?: (data: unknown) => void;
    onError?: (event: Event) => void;
    onOpen?: () => void;
}

export function useSSE(options: UseSSEOptions) {
    const { url, withCredentials = false, onMessage, onError, onOpen } = options;

    const eventSourceRef = useRef<EventSource | null>(null);
    const [state, setState] = useState<ConnectionState>('disconnected');
    const [lastEvent, setLastEvent] = useState<unknown>(null);

    const connect = useCallback(() => {
        if (eventSourceRef.current) {
            return;
        }

        setState('connecting');

        eventSourceRef.current = new EventSource(url, { withCredentials });

        eventSourceRef.current.onopen = () => {
            setState('connected');
            onOpen?.();
        };

        eventSourceRef.current.onerror = (event) => {
            setState('error');
            onError?.(event);
        };

        eventSourceRef.current.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                setLastEvent(data);
                onMessage?.(data);
            } catch {
                setLastEvent(event.data);
                onMessage?.(event.data);
            }
        };
    }, [url, withCredentials, onMessage, onError, onOpen]);

    const disconnect = useCallback(() => {
        eventSourceRef.current?.close();
        eventSourceRef.current = null;
        setState('disconnected');
    }, []);

    useEffect(() => {
        connect();
        return () => disconnect();
    }, [connect, disconnect]);

    return {
        state,
        lastEvent,
        connect,
        disconnect,
        isConnected: state === 'connected',
    };
}

// ============================================================================
// Presence Hook (who's online)
// ============================================================================

export interface PresenceUser {
    id: string;
    name: string;
    avatar?: string;
    status: 'online' | 'away' | 'busy';
    lastSeen: Date;
}

export function usePresence(channelUrl: string) {
    const [users, setUsers] = useState<Map<string, PresenceUser>>(new Map());

    const { send, isConnected } = useRealtime({
        url: channelUrl,
        onMessage: (data) => {
            const message = data as { type: string; user?: PresenceUser; userId?: string };

            switch (message.type) {
                case 'presence:join':
                    if (message.user) {
                        setUsers(prev => new Map(prev).set(message.user!.id, message.user!));
                    }
                    break;
                case 'presence:leave':
                    if (message.userId) {
                        setUsers(prev => {
                            const next = new Map(prev);
                            next.delete(message.userId!);
                            return next;
                        });
                    }
                    break;
                case 'presence:update':
                    if (message.user) {
                        setUsers(prev => new Map(prev).set(message.user!.id, message.user!));
                    }
                    break;
                case 'presence:sync': {
                    // Full sync of all users
                    const syncData = data as { users: PresenceUser[] };
                    if (syncData.users) {
                        setUsers(new Map(syncData.users.map(u => [u.id, u])));
                    }
                    break;
                }
            }
        },
    });

    const updateStatus = useCallback((status: PresenceUser['status']) => {
        send({ type: 'presence:status', payload: { status } });
    }, [send]);

    return {
        users: Array.from(users.values()),
        userCount: users.size,
        isConnected,
        updateStatus,
    };
}
