import { useCallback, useEffect, useRef, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import * as Tabs from '@radix-ui/react-tabs'
import { motion } from 'motion/react'
import {
  Check, CircleCheck, CircleX, ExternalLink, Link2, LoaderCircle, RefreshCw, ScanSearch,
  Stethoscope, TriangleAlert, X,
} from 'lucide-react'
import { getDataSource, postSheetTabs, postSheetsSync, postSource, postSourceTest } from '../api'
import { dacDashboardUrl, DATA_QUALITY_DASHBOARD_NAME } from '../dac'

// La source de données, vue depuis l'interface. Deux onglets d'une même fenêtre,
// parce qu'ils parlent de la même chose et s'appellent l'un l'autre : un diagnostic
// en échec mène naturellement à « lier une autre feuille », et une feuille tout
// juste liée se vérifie dans « santé des données ».
//
//   - Santé des données : la lecture du Google Sheet marche-t-elle, que contient la
//     feuille, et à quoi ressemblent ses premières lignes.
//   - Lier une feuille Google : remplace l'étape 5/7 d'INSTALLER.bat, qui demandait
//     une invite de commandes. La feuille est TESTÉE avant d'être liée, et le bouton
//     qui l'enregistre n'apparaît qu'une fois le test concluant.

const STATUTS = {
  ok: { Icone: CircleCheck, titre: 'La lecture du Google Sheet fonctionne' },
  attention: { Icone: TriangleAlert, titre: 'La lecture fonctionne, avec des points à vérifier' },
  erreur: { Icone: CircleX, titre: 'La lecture du Google Sheet échoue' },
}

// Ce qui apparaît (verdict, résultat d'un test) entre d'un mouvement bref plutôt
// que de surgir : on voit QUE quelque chose vient de changer, et où.
const APPARITION = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.2, ease: 'easeOut' },
}

const nombre = (n) => (n == null ? '—' : Number(n).toLocaleString('fr-FR'))

function dateCourte(iso) {
  if (!iso) return '—'
  const [a, m, j] = String(iso).slice(0, 10).split('-')
  return `${j}/${m}/${a}`
}

function ilYa(iso) {
  if (!iso) return 'jamais'
  const secondes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000))
  if (secondes < 60) return "à l'instant"
  const minutes = Math.round(secondes / 60)
  if (minutes < 60) return `il y a ${minutes} min`
  const heures = Math.round(minutes / 60)
  if (heures < 24) return `il y a ${heures} h`
  return `le ${new Date(iso).toLocaleDateString('fr-FR')}`
}

function cellule(valeur, indexColonne) {
  if (valeur == null || valeur === '') return '—'
  if (indexColonne === 4) return nombre(valeur) // budget
  if (indexColonne === 5) return dateCourte(valeur) // deadline
  return valeur
}

// --- Briques communes aux deux onglets ---------------------------------------

function BandeauStatut({ statut, erreur, avertissements }) {
  const s = STATUTS[statut] || STATUTS.erreur
  return (
    <motion.div className={`data-status data-status-${statut}`} role="status" {...APPARITION}>
      <s.Icone className="data-status-icon" size={22} aria-hidden="true" />
      <div>
        <strong>{s.titre}</strong>
        {erreur && <p>{erreur}</p>}
        {(avertissements || []).map((a) => <p key={a}>{a}</p>)}
      </div>
    </motion.div>
  )
}

function Mesures({ donnees }) {
  const { lignes, colonnes, indicateurs } = donnees
  if (!lignes) return null
  const obligatoires = colonnes.attendues.filter((c) => c !== 'id')
  const trouvees = colonnes.trouvees.filter((c) => c !== 'id')
  const periode = indicateurs?.periode
  const tuiles = [
    ['Lignes chargées', nombre(lignes.chargees)],
    ['Lignes ignorées', nombre(lignes.ignorees)],
    ['Cellules à corriger', nombre(lignes.cellules_corrigees)],
    ['Colonnes reconnues', `${trouvees.length} / ${obligatoires.length}`],
    ['Échéances couvertes', periode ? `${dateCourte(periode.debut)} → ${dateCourte(periode.fin)}` : '—'],
    ['Pays', nombre(indicateurs?.pays)],
    ['Practices', nombre(indicateurs?.practices)],
    ['Budget total (DT)', nombre(indicateurs?.budget_total)],
  ]
  return (
    <>
      <div className="data-metrics">
        {tuiles.map(([libelle, valeur]) => (
          <div key={libelle} className="data-metric">
            <span className="data-metric-label">{libelle}</span>
            <span className="data-metric-value">{valeur}</span>
          </div>
        ))}
      </div>
      {/* Le total diffère de celui des tableaux de bord, qui excluent les affaires
          perdues : sans cette précision, deux chiffres « justes » se contredisent. */}
      <p className="data-note">
        Budget total de toutes les lignes, affaires perdues comprises — les tableaux de
        bord, eux, les excluent.
      </p>
    </>
  )
}

function Colonnes({ colonnes }) {
  if (!colonnes || (!colonnes.manquantes.length && !colonnes.non_reconnues.length)) return null
  return (
    <section className="data-section">
      <h3>Colonnes</h3>
      {colonnes.manquantes.length > 0 && (
        <p className="data-chips">
          <span>Obligatoires absentes :</span>
          {colonnes.manquantes.map((c) => <span key={c} className="data-chip data-chip-missing">{c}</span>)}
        </p>
      )}
      {colonnes.non_reconnues.length > 0 && (
        <p className="data-chips">
          <span>Ignorées (nom non reconnu) :</span>
          {colonnes.non_reconnues.map((c) => <span key={c} className="data-chip">{c}</span>)}
        </p>
      )}
    </section>
  )
}

function ACorriger({ lignes }) {
  if (!lignes?.length) return null
  return (
    <section className="data-section">
      <h3>À corriger dans la feuille</h3>
      <p className="data-note">
        Ces cellules ne sont pas reconnues : la ligne est conservée, mais la valeur compte
        pour « Non renseigné » dans les chiffres.
      </p>
      <div className="data-table-wrap">
        <table className="data-table">
          <thead><tr><th>Ligne</th><th>Colonne</th><th>Valeur actuelle</th></tr></thead>
          <tbody>
            {lignes.map((l) => (
              <tr key={`${l.ligne}-${l.colonne}`}>
                <td>{l.ligne}</td><td>{l.colonne}</td><td>« {l.valeur} »</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function Apercu({ apercu }) {
  if (!apercu?.lignes?.length) return null
  return (
    <section className="data-section">
      <h3>Aperçu — {apercu.lignes.length} premières lignes</h3>
      <div className="data-table-wrap">
        <table className="data-table">
          <thead><tr>{apercu.colonnes.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>
            {apercu.lignes.map((ligne, i) => (
              <tr key={i}>{ligne.map((v, j) => <td key={j}>{cellule(v, j)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function Diagnostic({ donnees }) {
  return (
    <>
      <BandeauStatut statut={donnees.statut} erreur={donnees.erreur} avertissements={donnees.avertissements} />
      <Mesures donnees={donnees} />
      <ACorriger lignes={donnees.a_corriger} />
      <Colonnes colonnes={donnees.colonnes} />
      <Apercu apercu={donnees.apercu} />
    </>
  )
}

// --- Onglet « Santé des données » --------------------------------------------

function Sante({ onLier, onRelu }) {
  const [etat, setEtat] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [occupe, setOccupe] = useState(false)

  const charger = useCallback(async () => {
    setErreur(null)
    try {
      setEtat(await getDataSource())
    } catch (e) {
      setErreur(e.message)
    }
  }, [])

  useEffect(() => { charger() }, [charger])

  async function relire() {
    setOccupe(true)
    try {
      const resume = await postSheetsSync()
      onRelu(resume)
      await charger()
    } catch (e) {
      setErreur(e.message)
    } finally {
      setOccupe(false)
    }
  }

  if (erreur && !etat) {
    return (
      <BandeauStatut
        statut="erreur"
        erreur={`Le serveur de l'application ne répond pas (${erreur}). Relancez-la depuis le raccourci du Bureau.`}
      />
    )
  }
  if (!etat) return <p className="data-loading">Lecture de l'état des données…</p>

  const tdb = etat.tableaux_de_bord
  return (
    <>
      <dl className="data-source">
        <div>
          <dt>Feuille</dt>
          <dd>
            {etat.source.url
              ? (
                <a href={etat.source.url} target="_blank" rel="noreferrer" className="data-link">
                  Ouvrir dans Google Sheets <ExternalLink size={13} aria-hidden="true" />
                </a>
              )
              : 'aucune'}
          </dd>
        </div>
        <div><dt>Onglet</dt><dd>« {etat.source.tab} »</dd></div>
        <div>
          <dt>Dernière lecture</dt>
          <dd>
            {ilYa(etat.lecture.at)}
            {etat.lecture.duree_ms != null &&
              ` — ${(etat.lecture.duree_ms / 1000).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} s`}
          </dd>
        </div>
        <div>
          <dt>Tableaux de bord</dt>
          <dd className={tdb?.ok ? 'data-ok' : 'data-ko'}>
            {tdb?.ok ? 'opérationnels' : tdb?.repond ? 'calculs en échec' : 'service arrêté'}
          </dd>
        </div>
      </dl>

      <Diagnostic donnees={etat} />
      {erreur && <p className="data-inline-error">{erreur}</p>}

      <div className="data-actions">
        <button type="button" className="data-button data-button-primary" onClick={relire} disabled={occupe}>
          <RefreshCw size={15} className={occupe ? 'spin' : undefined} aria-hidden="true" />
          {occupe ? 'Lecture en cours…' : 'Relire la feuille maintenant'}
        </button>
        <button type="button" className="data-button" onClick={onLier}>
          <Link2 size={15} aria-hidden="true" />
          Lier une autre feuille
        </button>
        <a
          className="data-button"
          href={dacDashboardUrl(DATA_QUALITY_DASHBOARD_NAME)}
          target="_blank"
          rel="noreferrer"
        >
          Qualité détaillée
          <ExternalLink size={14} aria-hidden="true" />
        </a>
      </div>
    </>
  )
}

// --- Onglet « Lier une feuille Google » --------------------------------------

function Lier({ onLiee }) {
  const [lien, setLien] = useState('')
  const [onglets, setOnglets] = useState(null) // null : liste inconnue → saisie libre
  const [onglet, setOnglet] = useState('')
  const [rechercheOnglets, setRechercheOnglets] = useState(false)
  const [diag, setDiag] = useState(null)
  const [teste, setTeste] = useState(null) // { lien, onglet } effectivement testés
  const [etape, setEtape] = useState(null) // 'test' | 'liaison'
  const [erreur, setErreur] = useState(null)
  const demande = useRef(0)

  // Les onglets se cherchent dès que le lien est collé : c'est la liste réelle de la
  // feuille, ce qui évite le piège d'un nom mal tapé (Google renverrait alors le
  // premier onglet, sans erreur). Un petit délai évite une requête par frappe.
  useEffect(() => {
    const saisie = lien.trim()
    setDiag(null)
    setErreur(null)
    if (!saisie) {
      setOnglets(null)
      return undefined
    }
    const numero = ++demande.current
    const minuteur = setTimeout(async () => {
      setRechercheOnglets(true)
      try {
        const r = await postSheetTabs(saisie)
        if (numero !== demande.current) return
        if (r.erreur) {
          setOnglets(null)
          setErreur(r.erreur)
          return
        }
        setOnglets(r.onglets)
        setOnglet((precedent) => {
          if (!r.onglets) return precedent || 'opportunities'
          if (r.onglet_du_lien) return r.onglet_du_lien
          return r.onglets.includes(precedent) ? precedent : r.onglets[0]
        })
      } catch (e) {
        if (numero === demande.current) setErreur(e.message)
      } finally {
        if (numero === demande.current) setRechercheOnglets(false)
      }
    }, 500)
    return () => clearTimeout(minuteur)
  }, [lien])

  const testActuel = teste && teste.lien === lien.trim() && teste.onglet === onglet && diag
  const peutLier = testActuel && diag.statut !== 'erreur'

  async function tester() {
    setEtape('test')
    setErreur(null)
    try {
      const resultat = await postSourceTest(lien.trim(), onglet)
      setDiag(resultat)
      setTeste({ lien: lien.trim(), onglet })
      // L'onglet retenu est le nom EXACT (la casse a pu être corrigée).
      if (resultat.source?.tab && resultat.source.tab !== onglet) {
        setOnglet(resultat.source.tab)
        setTeste({ lien: lien.trim(), onglet: resultat.source.tab })
      }
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEtape(null)
    }
  }

  async function lier() {
    setEtape('liaison')
    setErreur(null)
    try {
      onLiee(await postSource(lien.trim(), onglet))
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEtape(null)
    }
  }

  return (
    <>
      <ol className="data-steps">
        <li>
          Dans Google Sheets : <strong>Partager</strong> › Accès général ›{' '}
          <strong>« Toute personne disposant du lien »</strong>, rôle <strong>Lecteur</strong>.
          L'application ne fait que lire : elle ne peut rien modifier.
        </li>
        <li>Ouvrez l'onglet qui contient les opportunités, copiez l'adresse du navigateur, collez-la ci-dessous.</li>
      </ol>

      <label className="data-field">
        <span>Lien de la feuille Google</span>
        <input
          type="url"
          value={lien}
          onChange={(e) => setLien(e.target.value)}
          placeholder="https://docs.google.com/spreadsheets/d/…"
          autoFocus
          spellCheck={false}
        />
      </label>

      <label className="data-field">
        <span>
          Onglet
          {rechercheOnglets && <em> — recherche des onglets…</em>}
          {onglets && <em> — {onglets.length} onglet(s) dans cette feuille</em>}
        </span>
        {onglets ? (
          <select value={onglet} onChange={(e) => setOnglet(e.target.value)}>
            {onglets.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        ) : (
          <input
            type="text"
            value={onglet}
            onChange={(e) => setOnglet(e.target.value)}
            placeholder="opportunities"
            disabled={!lien.trim()}
          />
        )}
      </label>
      {!onglets && lien.trim() && !rechercheOnglets && !erreur && (
        <p className="data-note">
          La liste des onglets n'a pas pu être lue : saisissez le nom exactement comme il
          apparaît en bas de la feuille.
        </p>
      )}

      {erreur && <BandeauStatut statut="erreur" erreur={erreur} />}

      <div className="data-actions">
        <button
          type="button"
          className="data-button"
          onClick={tester}
          disabled={!lien.trim() || !onglet.trim() || etape !== null || rechercheOnglets}
        >
          {etape === 'test'
            ? <LoaderCircle size={15} className="spin" aria-hidden="true" />
            : <ScanSearch size={15} aria-hidden="true" />}
          {etape === 'test' ? 'Lecture de la feuille…' : '1 · Tester la lecture'}
        </button>
        <button
          type="button"
          className="data-button data-button-primary"
          onClick={lier}
          disabled={!peutLier || etape !== null}
          title={peutLier ? undefined : "Testez d'abord la feuille : elle n'est liée que si la lecture réussit."}
        >
          {etape === 'liaison'
            ? <LoaderCircle size={15} className="spin" aria-hidden="true" />
            : <Check size={15} aria-hidden="true" />}
          {etape === 'liaison' ? 'Liaison en cours…' : '2 · Utiliser cette feuille'}
        </button>
      </div>

      {testActuel && (
        <motion.div className="data-result" {...APPARITION}>
          <Diagnostic donnees={diag} />
        </motion.div>
      )}
    </>
  )
}

// --- La fenêtre ---------------------------------------------------------------
//
// Radix Dialog : focus piégé dans la fenêtre puis rendu à l'élément d'origine,
// Échap, clic à l'extérieur, défilement de la page bloqué, rôles ARIA — tout ce
// que la première version faisait à la main, et en partie seulement. La fenêtre
// reste montée pendant son animation de fermeture (`ouvert` piloté par App.jsx),
// au lieu de disparaître d'un coup.
//
// Radix Tabs : onglets au clavier (flèches gauche/droite), rôles tab/tabpanel.

export default function DataSourcePanel({ ouvert, vue, onChangerVue, onClose, onRelu, onSourceChangee }) {
  return (
    <Dialog.Root open={ouvert} onOpenChange={(etat) => { if (!etat) onClose() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="data-modal-backdrop" />
        <Dialog.Content className="data-modal" aria-describedby={undefined}>
          <Tabs.Root value={vue} onValueChange={onChangerVue} className="data-modal-tabs-root">
            <div className="data-modal-header">
              <Dialog.Title className="data-modal-title">Source de données</Dialog.Title>
              <Tabs.List className="data-modal-tabs" aria-label="Source de données">
                <Tabs.Trigger value="sante">
                  <Stethoscope size={15} aria-hidden="true" />
                  Santé des données
                </Tabs.Trigger>
                <Tabs.Trigger value="lier">
                  <Link2 size={15} aria-hidden="true" />
                  Lier une feuille Google
                </Tabs.Trigger>
              </Tabs.List>
              <Dialog.Close asChild>
                <button type="button" className="history-close" aria-label="Fermer">
                  <X size={16} aria-hidden="true" />
                </button>
              </Dialog.Close>
            </div>

            <div className="data-modal-body">
              <Tabs.Content value="sante" className="data-tab">
                <Sante onLier={() => onChangerVue('lier')} onRelu={onRelu} />
              </Tabs.Content>
              <Tabs.Content value="lier" className="data-tab">
                <Lier onLiee={(resultat) => { onSourceChangee(resultat); onChangerVue('sante') }} />
              </Tabs.Content>
            </div>
          </Tabs.Root>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
