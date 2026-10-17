import { useCallback, useEffect, useRef, useState } from 'react'
import type { ItineraryCollaborationCommand, ItineraryCollaborationEvent } from '../types'

export type CollaborationConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting'

interface UseItineraryCollaborationOptions {
  url: string | null
  onEvent: (event: ItineraryCollaborationEvent) => void
  identityKey?: string
  inviteToken?: string
}

const MAX_RETRIES = 8
const BASE_RETRY_MS = 500
const MAX_RETRY_MS = 10_000

function parseEvent(payload: string): ItineraryCollaborationEvent | null {
  try {
    const value: unknown = JSON.parse(payload)
    if (typeof value !== 'object' || value === null || !('type' in value)) return null
    const event = value as Record<string, unknown>
    switch (event.type) {
      case 'authenticated':
        return value as ItineraryCollaborationEvent
      case 'presence':
        return typeof event.count === 'number' ? value as ItineraryCollaborationEvent : null
      case 'proposal_created':
        return typeof event.current_version === 'number' && typeof event.proposal === 'object'
          ? value as ItineraryCollaborationEvent
          : null
      case 'proposal_reviewed':
        return typeof event.current_version === 'number' && typeof event.proposal === 'object'
          ? value as ItineraryCollaborationEvent
          : null
      case 'itinerary_updated':
        return typeof event.itinerary_id === 'string' && typeof event.current_version === 'number'
          ? value as ItineraryCollaborationEvent
          : null
      case 'error':
        return typeof event.code === 'string' && typeof event.message === 'string'
          ? value as ItineraryCollaborationEvent
          : null
      default:
        return null
    }
  } catch {
    return null
  }
}

function websocketUrl(url: string): string {
  const target = new URL(url, window.location.href)
  target.protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return target.toString()
}

export function useItineraryCollaboration({ url, onEvent, identityKey, inviteToken }: UseItineraryCollaborationOptions) {
  const [state, setState] = useState<CollaborationConnectionState>('disconnected')
  const socketRef = useRef<WebSocket | null>(null)
  const eventHandlerRef = useRef(onEvent)

  useEffect(() => {
    eventHandlerRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    if (!url) {
      setState('disconnected')
      return
    }

    let mounted = true
    let retries = 0
    let retryTimer: number | undefined
    let activeSocket: WebSocket | null = null

    const scheduleReconnect = () => {
      if (!mounted || retries >= MAX_RETRIES) {
        setState('disconnected')
        return
      }
      const delay = Math.min(BASE_RETRY_MS * (2 ** retries), MAX_RETRY_MS)
      retries += 1
      setState('reconnecting')
      retryTimer = window.setTimeout(connect, delay)
    }

    const connect = () => {
      if (!mounted) return
      setState(retries === 0 ? 'connecting' : 'reconnecting')
      try {
        const socket = new WebSocket(websocketUrl(url))
        activeSocket = socket
        socketRef.current = socket
        socket.onopen = () => {
          if (!mounted) {
            socket.close()
            return
          }
          if (inviteToken) {
            socket.send(JSON.stringify({ type: 'authenticate', token: inviteToken }))
          } else {
            retries = 0
            setState('connected')
          }
        }
        socket.onmessage = (event) => {
          if (typeof event.data !== 'string') return
          const collaborationEvent = parseEvent(event.data)
          if (collaborationEvent?.type === 'authenticated') {
            retries = 0
            setState('connected')
          }
          if (collaborationEvent) eventHandlerRef.current(collaborationEvent)
        }
        socket.onerror = () => {
          if (mounted) setState('reconnecting')
          socket.close()
        }
        socket.onclose = () => {
          if (socketRef.current === socket) socketRef.current = null
          if (mounted) scheduleReconnect()
        }
      } catch {
        scheduleReconnect()
      }
    }

    connect()
    return () => {
      mounted = false
      if (retryTimer !== undefined) window.clearTimeout(retryTimer)
      if (socketRef.current === activeSocket) socketRef.current = null
      activeSocket?.close(1000, 'Collaboration view closed')
    }
  }, [url, identityKey, inviteToken])

  const send = useCallback((command: ItineraryCollaborationCommand): boolean => {
    const socket = socketRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) return false
    socket.send(JSON.stringify(command))
    return true
  }, [])

  return { state, connected: state === 'connected', send }
}
