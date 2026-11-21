import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

const calmMotion = window.matchMedia('(prefers-reduced-motion: reduce)')

document.addEventListener('pointerdown', (event) => {
  if (calmMotion.matches) return
  const button = (event.target as HTMLElement | null)?.closest('button')
  if (!button || button.disabled) return
  const rect = button.getBoundingClientRect()
  const d = Math.hypot(rect.width, rect.height) * 2
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  const ink = document.createElement('span')
  ink.className = 'ripple-ink'
  ink.style.width = `${d}px`
  ink.style.height = `${d}px`
  ink.style.left = `${x - d / 2}px`
  ink.style.top = `${y - d / 2}px`
  button.appendChild(ink)
  ink.addEventListener('animationend', () => ink.remove(), { once: true })
})

let spotFrame = 0
document.addEventListener('pointermove', (event) => {
  const button = (event.target as HTMLElement | null)?.closest('button')
  if (!button || button.disabled || spotFrame) return
  const clientX = event.clientX
  const clientY = event.clientY
  spotFrame = requestAnimationFrame(() => {
    const rect = button.getBoundingClientRect()
    button.style.setProperty('--mx', `${clientX - rect.left}px`)
    button.style.setProperty('--my', `${clientY - rect.top}px`)
    spotFrame = 0
  })
})
