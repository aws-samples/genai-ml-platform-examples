export default function AppHeader() {
  return (
    <header className="h-12 flex-shrink-0 bg-slate border-b border-border-subtle flex items-center px-6">
      <div className="flex items-center gap-3">
        <div className="w-6 h-6 rounded-md bg-mint/10 flex items-center justify-center">
          <span className="text-mint text-xs font-semibold tracking-tight">M</span>
        </div>
        <span className="text-primary text-sm font-semibold tracking-tight">MediFlow AI</span>
        <span className="text-tertiary text-xs">·</span>
        <span className="text-tertiary text-xs">Harbour Medical Centre · Practice Management</span>
      </div>
    </header>
  )
}
