import { Receipt, Bot } from 'lucide-react'
import { useApp } from '../../context/AppContext'

const statusPill = {
  paid: 'bg-emerald/10 text-emerald',
  outstanding: 'bg-gold/10 text-gold',
  overdue: 'bg-coral/10 text-coral',
}

export default function InvoiceCard({ data }) {
  const { navigateTo, sendToAgent } = useApp()
  if (!data) return null
  const isOverdue = data.status === 'overdue'

  const handleSendReminder = () => {
    const pretty = data.patient_name || 'the patient'
    sendToAgent(`Send a payment reminder for invoice ${data.id} to ${pretty}`)
  }

  const handleViewDetails = () => {
    if (!data.patient_id) return
    navigateTo('patients', {
      patientId: data.patient_id,
      patientName: data.patient_name,
      tab: 'invoices',
      invoiceId: data.id,
    })
  }

  return (
    <div className="bg-graphite rounded-xl border border-border-subtle p-4 animate-[count-up-fade_400ms_ease-out]">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <Receipt size={14} className="text-tertiary" />
          <span className="text-primary text-sm font-medium">{data.id}</span>
        </div>
        <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider ${statusPill[data.status] || statusPill.outstanding}`}>
          {data.status}
        </span>
      </div>
      <p className="text-secondary text-sm">{data.patient_name}</p>
      <div className="mt-2 space-y-1">
        <p className="text-sm">
          <span className="text-tertiary">Amount: </span>
          <span className="text-primary font-medium">${data.amount?.toFixed(2)}</span>
        </p>
        <p className={`text-sm ${isOverdue ? 'text-coral' : 'text-tertiary'}`}>
          Due: {data.due_date}{isOverdue && data.days_overdue ? ` (${data.days_overdue} days ago)` : ''}
        </p>
        {data.chase_count > 0 && (
          <p className="text-xs text-tertiary">Chased: {data.chase_count} time{data.chase_count > 1 ? 's' : ''}</p>
        )}
      </div>
      <div className="flex gap-3 mt-3">
        <button
          onClick={handleSendReminder}
          className="flex items-center gap-1.5 text-xs text-mint hover:text-mint/80 font-medium transition-all duration-200 ease-out active:scale-95"
        >
          <Bot size={11} /> Send Reminder
        </button>
        <button
          onClick={handleViewDetails}
          disabled={!data.patient_id}
          className="text-xs text-mint hover:text-mint/80 font-medium transition-all duration-200 ease-out active:scale-95 disabled:opacity-40 disabled:cursor-default"
        >
          View Details
        </button>
      </div>
    </div>
  )
}
