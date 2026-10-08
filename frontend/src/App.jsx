import { useEffect, useState } from 'react'
import { Briefcase, GraduationCap, LayoutDashboard, ListChecks, Users, Wallet } from 'lucide-react'
import Executive from './pages/Executive.jsx'
import Recruitment from './pages/Recruitment.jsx'
import Deployment from './pages/Deployment.jsx'
import Cohort from './pages/Cohort.jsx'
import Economics from './pages/Economics.jsx'
import Actions from './pages/Actions.jsx'

const PAGES = [
  { id: 'executive', label: 'Executive', icon: LayoutDashboard, Page: Executive },
  { id: 'recruitment', label: 'Recruitment', icon: Users, Page: Recruitment },
  { id: 'deployment', label: 'Deployment', icon: Briefcase, Page: Deployment },
  { id: 'cohort', label: 'Cohort health', icon: GraduationCap, Page: Cohort },
  { id: 'economics', label: 'Economics', icon: Wallet, Page: Economics },
  { id: 'actions', label: 'Leadership actions', icon: ListChecks, Page: Actions },
]

function readHash() {
  const id = window.location.hash.replace('#', '')
  return PAGES.some((page) => page.id === id) ? id : 'executive'
}

export default function App() {
  const [pageId, setPageId] = useState(readHash)

  useEffect(() => {
    const onHash = () => setPageId(readHash())
    window.addEventListener('hashchange', onHash)
    if (!window.location.hash) window.location.replace('#executive')
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const current = PAGES.find((page) => page.id === pageId) || PAGES[0]
  const Page = current.Page

  return (
    <div className="min-h-screen bg-paper text-ink">
      <div className="h-1 bg-moss" />
      <div className="lg:grid lg:grid-cols-[232px_minmax(0,1fr)]">
        <aside className="bg-ink text-white lg:sticky lg:top-0 lg:h-screen lg:flex lg:flex-col">
          <div className="px-4 pt-5 pb-4">
            <p className="text-[10px] tracking-[0.2em] uppercase text-white/45">Coforge</p>
            <p className="font-semibold text-lg leading-tight mt-1">Momentuum Blue</p>
            <p className="text-xs text-white/50 mt-0.5">Operations</p>
          </div>
          <nav className="flex lg:flex-col gap-1 px-2 pb-4 overflow-x-auto">
            {PAGES.map((page) => {
              const Icon = page.icon
              const active = page.id === current.id
              return (
                <a
                  key={page.id}
                  href={`#${page.id}`}
                  aria-current={active ? 'page' : undefined}
                  className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm whitespace-nowrap ${
                    active ? 'bg-white/10 text-white' : 'text-white/65 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  {page.label}
                </a>
              )
            })}
          </nav>
          <div className="hidden lg:flex mt-auto px-4 py-4 text-xs text-white/45 items-center gap-2">
            <span className="live-dot inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
            Live · refreshes every 10s
          </div>
        </aside>
        <main className="min-w-0">
          <Page />
        </main>
      </div>
    </div>
  )
}
