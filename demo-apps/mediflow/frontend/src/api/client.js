const BASE = ''

async function fetchJSON(url, opts = {}) {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  // Data endpoints
  today: () => fetchJSON('/api/data/today'),
  calendar: (week) => fetchJSON(`/api/data/calendar${week ? `?week=${week}` : ''}`),
  patients: (q) => fetchJSON(`/api/data/patients${q ? `?q=${q}` : ''}`),
  patient: (id) => fetchJSON(`/api/data/patients/${id}`),
  comms: () => fetchJSON('/api/data/comms'),
  doctors: () => fetchJSON('/api/data/doctors'),
  doctor: (id) => fetchJSON(`/api/data/doctors/${id}`),
  availability: (doctorId, date) => fetchJSON(`/api/data/availability?doctor_id=${doctorId}&date=${date}`),
  bookAppointment: (data) =>
    fetchJSON('/api/data/appointments', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Doctor availability (TASK-047)
  doctorAvailabilityWindow: (doctorId, start, end) =>
    fetchJSON(`/api/data/doctors/${doctorId}/availability?start=${start}&end=${end}`),
  createDoctorUnavailability: (doctorId, data) =>
    fetchJSON(`/api/data/doctors/${doctorId}/unavailability`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  deleteDoctorUnavailability: (doctorId, unavailabilityId) =>
    fetchJSON(`/api/data/doctors/${doctorId}/unavailability/${unavailabilityId}`, {
      method: 'DELETE',
    }),
  patchDoctor: (doctorId, data) =>
    fetchJSON(`/api/data/doctors/${doctorId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  // Patient memories
  patientMemories: (patientId, type) =>
    fetchJSON(`/api/patients/${patientId}/memories${type ? `?type=${type}` : ''}`),
  addMemory: (patientId, data) =>
    fetchJSON(`/api/patients/${patientId}/memories`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateMemory: (patientId, memoryId, data) =>
    fetchJSON(`/api/patients/${patientId}/memories/${memoryId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deleteMemory: (patientId, memoryId) =>
    fetchJSON(`/api/patients/${patientId}/memories/${memoryId}`, {
      method: 'DELETE',
    }),

  // Dashboard / analysis
  dashboard: () => fetchJSON('/api/dashboard/summary'),
  memoriesSummary: () => fetchJSON('/api/memories/summary'),
  pipelineStatus: () => fetchJSON('/api/analysis/status'),
  pipelineRuns: () => fetchJSON('/api/analysis/runs'),
  runAnalysis: () => fetchJSON('/api/analysis/run', { method: 'POST' }),
  cancelAnalysis: () => fetchJSON('/api/analysis/cancel', { method: 'POST' }),
  updatePipelineConfig: (config) =>
    fetchJSON('/api/analysis/config', {
      method: 'PATCH',
      body: JSON.stringify(config),
    }),

  // Chat (SSE)
  chatSSE: (message, sessionId, onEvent, { history, viewContext } = {}) => {
    const ctrl = new AbortController()
    fetch(`${BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        history: history || undefined,
        view_context: viewContext || undefined,
      }),
      signal: ctrl.signal,
    }).then(async (res) => {
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        let currentEvent = 'message'
        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            try {
              const data = JSON.parse(line.slice(5).trim())
              onEvent(currentEvent, data)
            } catch {}
          }
        }
      }
    }).catch((err) => {
      if (err.name !== 'AbortError') onEvent('error', { error: err.message })
    })
    return ctrl
  },

  // Activity tracking (fire-and-forget)
  logActivity: (sessionId, events) =>
    fetchJSON('/api/activity', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, events }),
    }).catch(() => {}),

  // Skills (unified)
  skills: () => fetchJSON('/api/skills'),
  skill: (id) => fetchJSON(`/api/skills/${id}`),
  testSkill: (id) => fetchJSON(`/api/skills/${id}/test`, { method: 'POST' }),
  enableSkill: (id) =>
    fetchJSON(`/api/skills/${id}/enable`, { method: 'PATCH' }),
  disableSkill: (id) =>
    fetchJSON(`/api/skills/${id}/disable`, { method: 'PATCH' }),
  scheduleSkill: (id, schedule) =>
    fetchJSON(`/api/skills/${id}/schedule`, {
      method: 'PATCH',
      body: JSON.stringify(schedule),
    }),
  runSkill: (id, onEvent) => sseStream(`/api/skills/${id}/run`, onEvent),
  executeSkillSSE: (id, onEvent) => sseStream(`/api/skills/${id}/execute`, onEvent),
  approveSkill: (skillId, executionId, action, excludedItems, onEvent) =>
    sseStream(`/api/skills/${skillId}/approve/${executionId}`, onEvent, {
      action,
      excluded_items: excludedItems || [],
    }),
  skillHistory: (id, limit = 20, offset = 0) =>
    fetchJSON(`/api/skills/${id}/history?limit=${limit}&offset=${offset}`),
  skillHistoryDetail: (id, execId) =>
    fetchJSON(`/api/skills/${id}/history/${execId}`),

  // Observability metrics
  metricsSummary: () => fetchJSON('/api/metrics/summary'),
  metricsSkill: (id) => fetchJSON(`/api/metrics/skills/${id}`),
  metricsCost: () => fetchJSON('/api/metrics/cost'),
}

// Shared SSE helper used by runSkill / executeSkillSSE / approveSkill
function sseStream(url, onEvent, body = null) {
  const ctrl = new AbortController()
  const opts = {
    method: 'POST',
    signal: ctrl.signal,
  }
  if (body) {
    opts.headers = { 'Content-Type': 'application/json' }
    opts.body = JSON.stringify(body)
  }
  fetch(`${BASE}${url}`, opts).then(async (res) => {
    if (!res.ok) {
      let errText = `${res.status} ${res.statusText}`
      try {
        const body = await res.json()
        if (body?.detail) errText = body.detail
      } catch {}
      onEvent('error', { error: errText, status: res.status })
      return
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      let currentEvent = 'message'
      for (const line of lines) {
        if (line.startsWith('event:')) {
          currentEvent = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          try {
            const data = JSON.parse(line.slice(5).trim())
            onEvent(currentEvent, data)
          } catch {}
        }
      }
    }
  }).catch((err) => {
    if (err.name !== 'AbortError') onEvent('error', { error: err.message })
  })
  return ctrl
}
