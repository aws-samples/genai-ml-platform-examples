import { User, Phone, Mail, AlertTriangle, FileText, Bot } from 'lucide-react'
import { useApp } from '../../context/AppContext'

export default function PatientCard({ data }) {
  const { navigateTo, sendToAgent } = useApp()
  if (!data) return null
  const initials = `${(data.first_name || '')[0] || ''}${(data.last_name || '')[0] || ''}`.toUpperCase()
  const fullName = `${data.first_name || ''} ${data.last_name || ''}`.trim()

  const handleViewProfile = () => {
    if (!data.id) return
    navigateTo('patients', { patientId: data.id, patientName: fullName })
  }

  const handleBookAppt = () => {
    if (!fullName) return
    sendToAgent(`Book an appointment for ${fullName}`)
  }

  return (
    <div className="bg-graphite rounded-xl border border-border-subtle p-4 animate-[count-up-fade_400ms_ease-out]">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-mint/15 flex items-center justify-center text-mint text-sm font-semibold flex-shrink-0">
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-primary text-[15px] font-medium tracking-tight">{fullName}</p>
          {data.dob && (
            <p className="text-tertiary text-xs mt-0.5">DOB: {data.dob}</p>
          )}
          <div className="flex flex-wrap gap-3 mt-2 text-xs">
            {data.phone && (
              <span className="flex items-center gap-1 text-secondary">
                <Phone size={12} /> {data.phone}
              </span>
            )}
            {data.email && (
              <span className="flex items-center gap-1 text-secondary">
                <Mail size={12} /> {data.email}
              </span>
            )}
          </div>
        </div>
      </div>
      {/* Flags */}
      <div className="flex gap-2 mt-3">
        {data.no_show_count > 0 && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gold/10 text-gold text-[11px] font-medium">
            <AlertTriangle size={11} /> {data.no_show_count} no-show{data.no_show_count > 1 ? 's' : ''}
          </span>
        )}
        {data.notes && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/5 text-secondary text-[11px]">
            <FileText size={11} /> Has notes
          </span>
        )}
      </div>
      {/* Actions */}
      <div className="flex gap-3 mt-3">
        <button
          onClick={handleViewProfile}
          disabled={!data.id}
          className="text-xs text-mint hover:text-mint/80 font-medium transition-all duration-200 ease-out active:scale-95 disabled:opacity-40 disabled:cursor-default"
        >
          View Profile
        </button>
        <button
          onClick={handleBookAppt}
          className="flex items-center gap-1.5 text-xs text-mint hover:text-mint/80 font-medium transition-all duration-200 ease-out active:scale-95"
        >
          <Bot size={11} /> Book Appt
        </button>
      </div>
    </div>
  )
}
