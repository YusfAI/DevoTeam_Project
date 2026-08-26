import { useEffect, useState } from 'react'
import { getHotDeals } from '../api'

// Le tableau des affaires chaudes, rendu par l'application et non par Bruin DAC.
//
// DAC ne sait pas faire défiler un tableau verticalement : l'élément externe de son
// widget porte `overflow-x-auto`, sans hauteur ni `overflow-y`, à l'intérieur d'un
// cadre `overflow-hidden`. Borner la hauteur de la ligne le CLIPPE au lieu de le
// rendre défilable, et le schéma n'accepte ni hauteur de widget ni CSS de thème.
// Sortir ce seul tableau de l'iframe est la seule façon d'obtenir la molette sans
// amputer la liste — les 105 affaires sont toutes là, pas les dix premières.
//
// Contrepartie assumée, dite en toutes lettres dans l'en-tête : ce tableau ne suit
// PAS le filtre de période du dashboard, qui vit dans l'iframe et lui est inaccessible.
// Il montre donc toujours l'ensemble. Un filtre silencieusement ignoré serait un
// piège ; annoncé, c'est une portée.

const euros = new Intl.NumberFormat('fr-FR', {
  style: 'currency', currency: 'EUR', maximumFractionDigits: 0,
})

function jour(valeur) {
  if (!valeur) return '—'
  const date = new Date(valeur)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString('fr-FR')
}

export default function HotDealsTable() {
  const [donnees, setDonnees] = useState(null)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    let annule = false
    getHotDeals()
      .then((d) => { if (!annule) setDonnees(d) })
      .catch((e) => { if (!annule) setErreur(e.message || 'Chargement impossible.') })
    return () => { annule = true }
  }, [])

  return (
    <section className="hot-deals">
      <header className="hot-deals-header">
        <div>
          <h3>Détail des affaires chaudes</h3>
          <p>
            {donnees
              ? `Les ${donnees.total} opportunités à ${Math.round(donnees.seuil * 100)} % de
                 probabilité ou plus, la plus forte espérance de gain d'abord — sur tout
                 l'historique, indépendamment du filtre de période ci-dessus.`
              : 'Chargement…'}
          </p>
        </div>
        {donnees && (
          <div className="hot-deals-totaux">
            <span>{euros.format(donnees.budget_total || 0)}</span>
            <small>{euros.format(donnees.pondere_total || 0)} pondérés</small>
          </div>
        )}
      </header>

      {erreur ? (
        <p className="hot-deals-erreur">{erreur}</p>
      ) : (
        <div className="hot-deals-scroll">
          <table>
            <thead>
              <tr>
                <th>Opportunité</th>
                <th>Client</th>
                <th>Practice</th>
                <th>Statut</th>
                <th className="num">Budget</th>
                <th className="num">Pondération</th>
                <th className="num">Montant pondéré</th>
                <th>Échéance</th>
              </tr>
            </thead>
            <tbody>
              {(donnees?.affaires ?? []).map((a, i) => (
                <tr key={`${a.buyer}-${a.description}-${i}`}>
                  <td title={a.description}>{a.description || '—'}</td>
                  <td title={a.buyer}>{a.buyer || '—'}</td>
                  <td>{a.practice || '—'}</td>
                  <td>{a.status || '—'}</td>
                  <td className="num">{a.budget == null ? '—' : euros.format(a.budget)}</td>
                  <td className="num">
                    {a.win_probability == null ? '—' : `${Math.round(a.win_probability * 100)} %`}
                  </td>
                  <td className="num">
                    {a.weighted_amount == null ? '—' : euros.format(a.weighted_amount)}
                  </td>
                  <td>{jour(a.deadline)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {donnees && donnees.total === 0 && (
            <p className="hot-deals-erreur">Aucune affaire chaude sur ce périmètre.</p>
          )}
        </div>
      )}
    </section>
  )
}
