import { useVegaEmbed } from '../hooks/useVegaEmbed'

export default function VegaChart({ spec, theme }) {
  const ref = useVegaEmbed(spec, theme)
  return <div className="vega-container" ref={ref} />
}
