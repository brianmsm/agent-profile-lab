import { useTheme } from 'next-themes'

export default function ThemeControl() {
  const { setTheme, theme } = useTheme()

  return (
    <div className="theme-control">
      <label className="theme-control-label" htmlFor="theme-select">Tema</label>
      <select
        id="theme-select"
        className="theme-control-select"
        aria-label="Tema de apariencia"
        value={theme ?? 'system'}
        onChange={event => setTheme(event.currentTarget.value)}
      >
        <option value="system">Sistema</option>
        <option value="light">Claro</option>
        <option value="dark">Oscuro</option>
      </select>
    </div>
  )
}
