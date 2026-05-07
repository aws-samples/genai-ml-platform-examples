export default function AvailabilityGrid({ data }) {
  if (!data) return null
  const { doctor_name, date, slots = [] } = data

  return (
    <div className="bg-graphite rounded-xl border border-border-subtle p-4 animate-[count-up-fade_400ms_ease-out]">
      <p className="text-secondary text-sm mb-3">
        <span className="text-primary font-medium">{doctor_name}</span>
        {date && <span className="text-tertiary"> — {date}</span>}
      </p>
      <div className="grid grid-cols-5 gap-1.5">
        {slots.map((slot, i) => (
          <button
            key={i}
            disabled={slot.booked}
            className={`
              text-xs py-2 rounded-lg font-medium transition-all
              ${slot.booked
                ? 'bg-ash text-tertiary cursor-default'
                : 'border border-mint/30 text-mint hover:bg-mint/10 cursor-pointer'
              }
            `}
          >
            {slot.time}
          </button>
        ))}
      </div>
    </div>
  )
}
