import { useEffect, useRef } from 'react'
import embed from 'vega-embed'

export function useVegaEmbed(spec, theme) {
  const ref = useRef(null)

  useEffect(() => {
    if (!ref.current || !spec) return undefined

    let view
    let cancelled = false
    const vegaTheme = theme === 'dark' ? 'dark' : 'quartz'

    embed(ref.current, spec, { actions: false, theme: vegaTheme })
      .then((result) => {
        if (cancelled) {
          result.view.finalize()
          return
        }
        view = result.view
      })
      .catch((err) => console.error('Erreur de rendu Vega :', err))

    return () => {
      cancelled = true
      if (view) view.finalize()
    }
  }, [spec, theme])

  return ref
}
