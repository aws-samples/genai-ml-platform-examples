import { useCallback, useEffect, useRef, useState } from 'react'
import {
  useApp,
  AGENT_PANEL_MIN_WIDTH,
  AGENT_PANEL_MAX_WIDTH,
} from '../../context/AppContext'

const KEYBOARD_STEP = 16

const clamp = (n) => Math.max(AGENT_PANEL_MIN_WIDTH, Math.min(AGENT_PANEL_MAX_WIDTH, n))

/**
 * ResizeHandle — 4px hit area on the panel's left edge.
 * Drag left widens panel, drag right narrows. Bounded to [320, 640].
 * Keyboard: Tab-focusable; ArrowLeft narrows by 16px, ArrowRight widens.
 */
export default function ResizeHandle() {
  const { agentPanelWidth, setAgentPanelWidth, setAgentPanelResizing } = useApp()
  const [isDragging, setIsDragging] = useState(false)
  const [isHover, setIsHover] = useState(false)

  // Drag state held in a ref so pointermove doesn't re-close over stale values.
  const dragRef = useRef({ startX: 0, startWidth: 0 })

  // Toggle the body cursor / user-select rule while dragging.
  useEffect(() => {
    if (isDragging) {
      document.body.classList.add('resize-handle-active')
    } else {
      document.body.classList.remove('resize-handle-active')
    }
    return () => {
      document.body.classList.remove('resize-handle-active')
    }
  }, [isDragging])

  const handlePointerDown = useCallback((e) => {
    // Only respond to primary (left) button / touch / pen
    if (e.button !== undefined && e.button !== 0) return
    e.preventDefault()
    dragRef.current = { startX: e.clientX, startWidth: agentPanelWidth }
    setIsDragging(true)
    setAgentPanelResizing(true)
    try {
      e.currentTarget.setPointerCapture?.(e.pointerId)
    } catch {
      // setPointerCapture can fail in rare cases; falling back to window listeners still works
    }
  }, [agentPanelWidth, setAgentPanelResizing])

  const handlePointerMove = useCallback((e) => {
    if (!isDragging) return
    const { startX, startWidth } = dragRef.current
    // Handle sits on the panel's LEFT edge. Dragging left (smaller clientX) widens the panel.
    const delta = e.clientX - startX
    const next = clamp(startWidth - delta)
    setAgentPanelWidth(next)
  }, [isDragging, setAgentPanelWidth])

  const endDrag = useCallback((e) => {
    if (!isDragging) return
    setIsDragging(false)
    setAgentPanelResizing(false)
    try {
      e?.currentTarget?.releasePointerCapture?.(e.pointerId)
    } catch {
      // ignore
    }
  }, [isDragging, setAgentPanelResizing])

  // Safety net: if the pointer is released outside the handle and pointer capture
  // didn't deliver a pointerup event to us, window listeners guarantee cleanup.
  useEffect(() => {
    if (!isDragging) return
    const onMove = (e) => {
      const { startX, startWidth } = dragRef.current
      const delta = e.clientX - startX
      const next = clamp(startWidth - delta)
      setAgentPanelWidth(next)
    }
    const onUp = () => {
      setIsDragging(false)
      setAgentPanelResizing(false)
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
    }
  }, [isDragging, setAgentPanelWidth, setAgentPanelResizing])

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'ArrowLeft') {
      e.preventDefault()
      setAgentPanelWidth(clamp(agentPanelWidth - KEYBOARD_STEP))
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      setAgentPanelWidth(clamp(agentPanelWidth + KEYBOARD_STEP))
    } else if (e.key === 'Home') {
      e.preventDefault()
      setAgentPanelWidth(AGENT_PANEL_MIN_WIDTH)
    } else if (e.key === 'End') {
      e.preventDefault()
      setAgentPanelWidth(AGENT_PANEL_MAX_WIDTH)
    }
  }, [agentPanelWidth, setAgentPanelWidth])

  const active = isDragging || isHover
  // idle: invisible; hover: mint @ 40%; dragging: mint @ 100%
  const barClass = isDragging
    ? 'bg-mint'
    : active
      ? 'bg-mint/40'
      : 'bg-transparent'

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-valuemin={AGENT_PANEL_MIN_WIDTH}
      aria-valuemax={AGENT_PANEL_MAX_WIDTH}
      aria-valuenow={Math.round(agentPanelWidth)}
      aria-label="Resize assistant panel"
      tabIndex={0}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onPointerEnter={() => setIsHover(true)}
      onPointerLeave={() => setIsHover(false)}
      onKeyDown={handleKeyDown}
      className="absolute top-0 left-0 h-full w-1 -translate-x-1/2 z-30
        cursor-col-resize
        focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-mint/30
        group"
      style={{ touchAction: 'none' }}
    >
      {/* Visual indicator — 1px vertical line, centered in the 4px hit zone */}
      <div
        className={`absolute top-0 left-1/2 -translate-x-1/2 h-full w-px transition-colors duration-200 ease-out ${barClass}`}
      />
    </div>
  )
}
