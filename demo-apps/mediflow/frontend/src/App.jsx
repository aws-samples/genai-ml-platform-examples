import { useEffect, useRef, useState } from 'react'
import { AppProvider } from './context/AppContext'
import { useApp } from './context/AppContext'
import Sidebar from './components/layout/Sidebar'
import AppHeader from './components/layout/AppHeader'
import AgentPanel from './components/layout/AgentPanel'
import AgentToggle from './components/layout/AgentToggle'
import ResizeHandle from './components/layout/ResizeHandle'
import ViewTransition from './components/ViewTransition'
import TodayView from './components/views/TodayView'
import CalendarView from './components/views/CalendarView'
import PatientsView from './components/views/PatientsView'
import PractitionersView from './components/views/PractitionersView'
import CommsView from './components/views/CommsView'
import InsightsView from './components/views/InsightsView'

const views = {
  today: TodayView,
  calendar: CalendarView,
  patients: PatientsView,
  practitioners: PractitionersView,
  comms: CommsView,
  insights: InsightsView,
}

function Layout() {
  const { activeView, agentPanelOpen, agentPanelWidth, agentPanelResizing } = useApp()
  const ViewComponent = views[activeView] || TodayView
  const [isTransitioning, setIsTransitioning] = useState(false)
  const prevOpen = useRef(agentPanelOpen)

  // Flip to "transitioning" whenever the panel open state changes; clear on transitionend.
  useEffect(() => {
    if (prevOpen.current !== agentPanelOpen) {
      setIsTransitioning(true)
      prevOpen.current = agentPanelOpen
    }
  }, [agentPanelOpen])

  const handlePanelTransitionEnd = (e) => {
    // Only clear when the wrapper's own transform/margin finishes (not child transitions bubbling up)
    if (e.target !== e.currentTarget) return
    if (e.propertyName === 'translate' || e.propertyName === 'margin-left') {
      setIsTransitioning(false)
    }
  }

  return (
    <div className="h-screen w-screen flex flex-col overflow-clip bg-void">
      <AppHeader />
      <div className="flex flex-1 min-h-0 overflow-x-clip">
        <Sidebar />
        <main
          className={`flex-1 min-w-0 ${isTransitioning ? 'overflow-hidden' : 'overflow-auto'}`}
        >
          <ViewTransition key={activeView} viewKey={activeView}>
            <ViewComponent />
          </ViewTransition>
        </main>
        <div
          onTransitionEnd={handlePanelTransitionEnd}
          className={`relative flex-shrink-0 transition-[translate,margin] duration-300 ease-out
            ${agentPanelOpen ? 'translate-x-0' : 'translate-x-full'}
            ${agentPanelResizing ? 'panel-no-transition' : ''}
          `}
          style={{
            width: agentPanelWidth,
            marginLeft: agentPanelOpen ? 0 : -agentPanelWidth,
          }}
          aria-hidden={!agentPanelOpen}
          {...(!agentPanelOpen ? { inert: '' } : {})}
        >
          {agentPanelOpen && <ResizeHandle />}
          <AgentPanel />
        </div>
        <AgentToggle />
      </div>
    </div>
  )
}

export default function App() {
  return (
    <AppProvider>
      <Layout />
    </AppProvider>
  )
}
