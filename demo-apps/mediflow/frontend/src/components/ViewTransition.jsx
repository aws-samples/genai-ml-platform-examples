/**
 * ViewTransition — wraps view content. Parent must set key={activeView}
 * so React remounts this on view switch, triggering the CSS animation.
 */
export default function ViewTransition({ children }) {
  return (
    <div className="view-enter h-full">
      {children}
    </div>
  )
}
