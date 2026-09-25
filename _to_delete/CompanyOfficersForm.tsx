import { useState, type FormEvent } from "react"
import { ApiError } from "../../shared/api/authApi"
import {
  replaceOfficers,
  type CompanyOfficerBatchItem,
  type CompanyOfficerRead,
  type ProjectAssociateRead,
  type RoleDirigeant,
} from "../api/projectApi"

/**
 * Éditeur des dirigeants (modale de CompanyOfficersSection — service 1.1.4,
 * lot 5 du 24/09/2026). Brouillon local, envoyé EN ENTIER au clic
 * « Enregistrer » (PUT /officers), comme "Équipe & capital".
 *
 * Pour chaque dirigeant, « Qui ? » propose les associés du projet (leur
 * identité est alors reprise automatiquement, jamais ressaisie), une autre
 * personne physique, ou une autre société. Seuls les champs utiles au choix
 * sont affichés.
 */

const AUTRE_PP = "__autre_pp__"
const AUTRE_PM = "__autre_pm__"

interface OfficerDraft {
  key: number
  id: string | null
  role: RoleDirigeant
  /** id d'associé, AUTRE_PP ou AUTRE_PM */
  qui: string
  duree_fonctions: string
  nom_complet: string
  adresse: string
  denomination_sociale: string
  forme_juridique: string
  capital_social: string
  siege_social: string
  lieu_immatriculation: string
  siren: string
  representant_prenom: string
  representant_nom: string
}

const ROLES: { role: RoleDirigeant; titre: string; aide: string; multiple: boolean; avecDuree: boolean }[] = [
  { role: "president", titre: "Président", aide: "Obligatoire : représente la société (article 39).", multiple: false, avecDuree: true },
  {
    role: "directeur_general",
    titre: "Directeur Général",
    aide: "Seulement si vous choisissez l'article « Directeur(s) Général(aux) » dans les statuts (article 40).",
    multiple: false,
    avecDuree: true,
  },
  {
    role: "membre_comite",
    titre: "Membres du Comité de Direction",
    aide: "Seulement si vous choisissez l'article « Comité de Direction » (article 41).",
    multiple: true,
    avecDuree: true,
  },
  {
    role: "mandataire",
    titre: "Mandataire pour les actes avant immatriculation",
    aide: "L'associé qui signera les actes de la société avant son immatriculation (article 44 et annexe III).",
    multiple: false,
    avecDuree: false,
  },
]

let prochaineCle = 1
function nouvelleCle() {
  return prochaineCle++
}

function draftVide(role: RoleDirigeant, qui: string): OfficerDraft {
  return {
    key: nouvelleCle(), id: null, role, qui, duree_fonctions: "", nom_complet: "", adresse: "",
    denomination_sociale: "", forme_juridique: "", capital_social: "", siege_social: "",
    lieu_immatriculation: "", siren: "", representant_prenom: "", representant_nom: "",
  }
}

function draftDepuis(o: CompanyOfficerRead): OfficerDraft {
  return {
    key: nouvelleCle(),
    id: o.id,
    role: o.role,
    qui: o.associate_id ?? (o.type_personne === "personne_morale" ? AUTRE_PM : AUTRE_PP),
    duree_fonctions: o.duree_fonctions ?? "",
    nom_complet: o.nom_complet ?? "",
    adresse: o.adresse ?? "",
    denomination_sociale: o.denomination_sociale ?? "",
    forme_juridique: o.forme_juridique ?? "",
    capital_social: o.capital_social ?? "",
    siege_social: o.siege_social ?? "",
    lieu_immatriculation: o.lieu_immatriculation ?? "",
    siren: o.siren ?? "",
    representant_prenom: o.representant_prenom ?? "",
    representant_nom: o.representant_nom ?? "",
  }
}

const vide = (v: string) => (v.trim() === "" ? null : v.trim())

/** Brouillon -> élément du PUT. N'envoie que les champs utiles au choix
 * « Qui ? » : le backend vide de toute façon l'identité d'un associé. */
function versPayload(d: OfficerDraft, associes: ProjectAssociateRead[]): CompanyOfficerBatchItem {
  const associe = associes.find((a) => a.id === d.qui)
  const estPm = d.qui === AUTRE_PM || associe?.type_personne === "personne_morale"
  const avecDuree = ROLES.find((r) => r.role === d.role)?.avecDuree ?? true
  return {
    id: d.id,
    role: d.role,
    associate_id: associe ? associe.id : null,
    type_personne: estPm ? "personne_morale" : "personne_physique",
    duree_fonctions: avecDuree ? vide(d.duree_fonctions) : null,
    nom_complet: d.qui === AUTRE_PP ? vide(d.nom_complet) : null,
    adresse: associe ? null : vide(d.adresse),
    denomination_sociale: d.qui === AUTRE_PM ? vide(d.denomination_sociale) : null,
    forme_juridique: d.qui === AUTRE_PM ? vide(d.forme_juridique) : null,
    capital_social: d.qui === AUTRE_PM ? vide(d.capital_social.replace(/\s/g, "").replace(",", ".")) : null,
    siege_social: d.qui === AUTRE_PM ? vide(d.siege_social) : null,
    lieu_immatriculation: d.qui === AUTRE_PM ? vide(d.lieu_immatriculation) : null,
    siren: d.qui === AUTRE_PM ? vide(d.siren.replace(/\s/g, "")) : null,
    representant_prenom: estPm ? vide(d.representant_prenom) : null,
    representant_nom: estPm ? vide(d.representant_nom) : null,
  }
}

/** Mêmes règles que le backend (schéma + service), pour un message clair. */
function valider(drafts: OfficerDraft[]): string | null {
  for (const d of drafts) {
    const titre = ROLES.find((r) => r.role === d.role)?.titre ?? d.role
    if (d.qui === AUTRE_PP && !d.nom_complet.trim()) return `${titre} : indiquez le nom de la personne.`
    if (d.qui === AUTRE_PM && !d.denomination_sociale.trim()) return `${titre} : indiquez la dénomination de la société.`
    if (d.qui === AUTRE_PM && d.siren.trim() && !/^\d{9}$/.test(d.siren.replace(/\s/g, ""))) {
      return `${titre} : le SIREN doit contenir 9 chiffres.`
    }
  }
  return null
}

const inputClass = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
const labelClass = "text-xs font-medium text-gray-700"

interface Props {
  projectId: string
  accessToken: string
  officers: CompanyOfficerRead[]
  associes: ProjectAssociateRead[]
  /** Appelé après un enregistrement réussi, ou à l'annulation. */
  onClose: (saved: boolean) => void
}

export default function CompanyOfficersForm({ projectId, accessToken, officers, associes, onClose }: Props) {
  const [drafts, setDrafts] = useState<OfficerDraft[]>(() => officers.map(draftDepuis))
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const quiParDefaut = associes[0]?.id ?? AUTRE_PP

  function modifier(key: number, champ: keyof OfficerDraft, valeur: string) {
    setDrafts((prev) => prev.map((d) => (d.key === key ? { ...d, [champ]: valeur } : d)))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const erreur = valider(drafts)
    if (erreur) {
      setError(erreur)
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      await replaceOfficers(accessToken, projectId, drafts.map((d) => versPayload(d, associes)))
      onClose(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      {ROLES.map(({ role, titre, aide, multiple, avecDuree }) => {
        const duRole = drafts.filter((d) => d.role === role)
        return (
          <div key={role} className="flex flex-col gap-2">
            <div>
              <p className="text-sm font-medium text-gray-800">{titre}</p>
              <p className="text-xs text-gray-400">{aide}</p>
            </div>

            {duRole.map((d) => {
              const associe = associes.find((a) => a.id === d.qui)
              const estPm = d.qui === AUTRE_PM || associe?.type_personne === "personne_morale"
              return (
                <div key={d.key} className="flex flex-col gap-3 rounded-lg border border-gray-100 bg-gray-50 p-3">
                  <div className="flex items-end gap-2">
                    <label className="flex flex-1 flex-col gap-1.5">
                      <span className={labelClass}>Qui ?</span>
                      <select value={d.qui} onChange={(e) => modifier(d.key, "qui", e.target.value)} className={inputClass}>
                        {associes.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.nom_complet} (associé)
                          </option>
                        ))}
                        <option value={AUTRE_PP}>Une autre personne (non associée)</option>
                        <option value={AUTRE_PM}>Une autre société (non associée)</option>
                      </select>
                    </label>
                    <button
                      type="button"
                      onClick={() => setDrafts((prev) => prev.filter((x) => x.key !== d.key))}
                      className="rounded-lg border border-gray-300 px-3 py-2 text-xs text-gray-600 hover:border-gray-400"
                    >
                      Retirer
                    </button>
                  </div>

                  {associe && (
                    <p className="text-xs text-gray-400">Son identité est reprise depuis « Équipe & capital ».</p>
                  )}

                  {d.qui === AUTRE_PP && (
                    <div className="grid grid-cols-2 gap-3">
                      <label className="flex flex-col gap-1.5">
                        <span className={labelClass}>Nom complet</span>
                        <input value={d.nom_complet} onChange={(e) => modifier(d.key, "nom_complet", e.target.value)} className={inputClass} />
                      </label>
                      <label className="flex flex-col gap-1.5">
                        <span className={labelClass}>Adresse</span>
                        <input value={d.adresse} onChange={(e) => modifier(d.key, "adresse", e.target.value)} className={inputClass} />
                      </label>
                    </div>
                  )}

                  {d.qui === AUTRE_PM && (
                    <div className="grid grid-cols-2 gap-3">
                      <label className="flex flex-col gap-1.5">
                        <span className={labelClass}>Dénomination sociale</span>
                        <input value={d.denomination_sociale} onChange={(e) => modifier(d.key, "denomination_sociale", e.target.value)} className={inputClass} />
                      </label>
                      <label className="flex flex-col gap-1.5">
                        <span className={labelClass}>Forme juridique</span>
                        <input value={d.forme_juridique} onChange={(e) => modifier(d.key, "forme_juridique", e.target.value)} placeholder="Ex : SAS" className={inputClass} />
                      </label>
                      <label className="flex flex-col gap-1.5">
                        <span className={labelClass}>Capital (€)</span>
                        <input value={d.capital_social} inputMode="decimal" onChange={(e) => modifier(d.key, "capital_social", e.target.value)} className={inputClass} />
                      </label>
                      <label className="flex flex-col gap-1.5">
                        <span className={labelClass}>SIREN</span>
                        <input value={d.siren} onChange={(e) => modifier(d.key, "siren", e.target.value)} placeholder="9 chiffres" className={inputClass} />
                      </label>
                      <label className="flex flex-col gap-1.5">
                        <span className={labelClass}>Siège social</span>
                        <input value={d.siege_social} onChange={(e) => modifier(d.key, "siege_social", e.target.value)} className={inputClass} />
                      </label>
                      <label className="flex flex-col gap-1.5">
                        <span className={labelClass}>Ville du greffe (RCS)</span>
                        <input value={d.lieu_immatriculation} onChange={(e) => modifier(d.key, "lieu_immatriculation", e.target.value)} className={inputClass} />
                      </label>
                    </div>
                  )}

                  {estPm && (
                    <div className="grid grid-cols-3 gap-3">
                      <label className="flex flex-col gap-1.5">
                        <span className={labelClass}>Prénom du représentant</span>
                        <input value={d.representant_prenom} onChange={(e) => modifier(d.key, "representant_prenom", e.target.value)} className={inputClass} />
                      </label>
                      <label className="flex flex-col gap-1.5">
                        <span className={labelClass}>Nom du représentant</span>
                        <input value={d.representant_nom} onChange={(e) => modifier(d.key, "representant_nom", e.target.value)} className={inputClass} />
                      </label>
                      {d.qui === AUTRE_PM && (
                        <label className="flex flex-col gap-1.5">
                          <span className={labelClass}>Adresse du représentant</span>
                          <input value={d.adresse} onChange={(e) => modifier(d.key, "adresse", e.target.value)} className={inputClass} />
                        </label>
                      )}
                    </div>
                  )}

                  {avecDuree && (
                    <label className="flex flex-col gap-1.5">
                      <span className={labelClass}>Durée des fonctions</span>
                      <input
                        value={d.duree_fonctions}
                        onChange={(e) => modifier(d.key, "duree_fonctions", e.target.value)}
                        placeholder="Ex : une durée indéterminée, 3 ans…"
                        className={inputClass}
                      />
                    </label>
                  )}
                </div>
              )
            })}

            {(multiple || duRole.length === 0) && (
              <button
                type="button"
                onClick={() => setDrafts((prev) => [...prev, draftVide(role, quiParDefaut)])}
                className="self-start rounded-lg border border-dashed border-gray-300 px-3 py-1.5 text-xs text-gray-600 hover:border-gray-400"
              >
                + Ajouter {multiple ? "un membre" : titre.toLowerCase().startsWith("mandataire") ? "le mandataire" : `le ${titre}`}
              </button>
            )}
          </div>
        )
      })}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={() => onClose(false)}
          disabled={isSubmitting}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-gray-400 disabled:opacity-50"
        >
          Annuler
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {isSubmitting ? "Enregistrement..." : "Enregistrer"}
        </button>
      </div>
    </form>
  )
}
