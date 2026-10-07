import React from 'react'
import { CheckCircle2, Server, Database, Layout } from 'lucide-react'

export default function App() {
  const stackItems = [
    {
      title: 'Backend API',
      tech: 'FastAPI + Uvicorn',
      status: 'Ready',
      icon: Server,
      color: 'text-emerald-600 bg-emerald-50 border-emerald-200',
    },
    {
      title: 'Frontend UI',
      tech: 'React 19 + Vite + Tailwind CSS',
      status: 'Ready',
      icon: Layout,
      color: 'text-blue-600 bg-blue-50 border-blue-200',
    },
    {
      title: 'Database',
      tech: 'SQLite + SQLAlchemy ORM',
      status: 'Ready',
      icon: Database,
      color: 'text-purple-600 bg-purple-50 border-purple-200',
    },
  ]

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6">
      <div className="max-w-2xl w-full bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-3 bg-indigo-50 text-indigo-600 rounded-xl">
            <CheckCircle2 className="w-8 h-8" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Recruitment Pipeline</h1>
            <p className="text-sm text-slate-500">Full-Stack Development Environment Ready</p>
          </div>
        </div>

        <div className="grid gap-4 mt-6">
          {stackItems.map((item, idx) => {
            const Icon = item.icon
            return (
              <div
                key={idx}
                className="flex items-center justify-between p-4 rounded-xl border border-slate-100 hover:border-slate-200 bg-slate-50/50 transition-all"
              >
                <div className="flex items-center gap-4">
                  <div className={`p-2.5 rounded-lg border ${item.color}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-slate-800 text-sm">{item.title}</h3>
                    <p className="text-xs text-slate-500">{item.tech}</p>
                  </div>
                </div>
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                  {item.status}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
