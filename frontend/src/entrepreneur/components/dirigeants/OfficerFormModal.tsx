import { useState, type FormEvent } from "react"
import { ApiError } from "../../../shared/api/authApi"
import Modal from "../../../shared/components/Modal"
import {
  createOfficer,
  updateOfficer,
  type CompanyOfficerRead,
  type CompanyOfficerWrite,
  type ProjectAssociateRead,
  type RoleDirigeant,
} from "../../api/projectApi"
import { configDuRole } from "./officerRoles"

type Qui = "associe" | "personne" | "societe"

interface Props {
  role: RoleDirigeant
  /** null = ajout, sinon modification de ce dirigeant. */
  officer: CompanyOfficerRead | null
  associes: ProjectAssociateRead[]
  projectId: string
  accessToken: string
  onSaved: () => void
  onClose: () => void
}

const inputClass = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
const labelClass = "text-xs font-medium text-gray-700"

function quiInitial(officer: CompanyOfficerRead | null, associes: ProjectAssociateRead[]): Qui {
  if (officer) {
    if (officer.associate_id) return "associe"
    return officer.type_personne === "personne_morale" ? "societe" : "personne"
  }
  return associes.length > 0 ? "associe" : "personne"
}

/**
 * Fenêtre d'ajout / modification d'UN dirigeant (page Dirigeants, lot 5).
 * Enregistre immédiatement (POST ou PATCH) — pas de brouillon global.
 *
 * « Qui ? » en 3 boutons (associé / autre personne / autre société) : seuls
 * les champs utiles au choix sont affichés. Pour un associé, l'identité vient
 * d'« Équipe & capital » et n'est jamais ressaisie ici.
 */
export default function OfficerFormModal({ role, officer, associes, projectId, accessToken, onSaved, onClose }: Props) {
  const config = configDuRole(role)
  const [qui, setQui] = useState<Qui>(() => quiInitial(officer, associes))
  const [associateId, setAssociateId] = useState(officer?.associate_id ?? associes[0]?.id ?? "")
  const [champs, setChamps] = useState({
    duree_fonctions: officer?.duree_fonctions ?? "",
    nom_complet: officer?.nom_complet ?? "",
    adresse: officer?.adresse ?? "",
    denomination_sociale: officer?.denomination_sociale ?? "",
    forme_juridique: officer?.forme_juridique ?? "",
    capital_social: officer?.capital_social ?? "",
    siege_social: officer?.siege_social ?? "",
    lieu_immatriculation: officer?.lieu_immatriculation ?? "",
    siren: officer?.siren ?? "",
    representant_prenom: officer?.representant_prenom ?? "",
    representant_nom: officer?.representant_nom ?? "",
  })
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const associeChoisi = qui === "associe" ? associes.find((a) => a.id === associateId) : undefined
  const estSociete = qui === "societe" || associeChoisi?.type_personne === "personne_morale"

  function set(champ: keyof typeof champs, valeur: string) {
    setChamps((prev) => ({ ...prev, [champ]: valeur }))
  }

  const vide = (v: string) => (v.trim() === "" ? null : v.trim())

  /** Corps envoyé : seulement les champs utiles au choix « Qui ? ». Le
   * backend vide de toute façon l'identité d'un associé (anti-redondance). */
  function payload(): CompanyOfficerWrite {
    const externeSociete = qui === "societe"
    return {
      role,
      associate_id: qui === "associe" ? associateId : null,
      type_personne: estSociete ? "personne_morale" : "personne_physique",
      duree_fonctions: config.avecDuree ? vide(champs.duree_fonctions) : null,
      nom_complet: qui === "personne" ? vide(champs.nom_complet) : null,
      adresse: qui === "associe" ? null : vide(champs.adresse),
      denomination_sociale: externeSociete ? vide(champs.denomination_sociale) : null,
      forme_juridique: externeSociete ? vide(champs.forme_juridique) : null,
      capital_social: externeSociete ? vide(champs.capital_social.replace(/\s/g, "").replace(",", ".")) : null,
      siege_social: externeSociete ? vide(champs.siege_social) : null,
      lieu_immatriculation: externeSociete ? vide(champs.lieu_immatriculation) : null,
      siren: externeSociete ? vide(champs.siren.replace(/\s/g, "")) : null,
      representant_prenom: estSociete ? vide(champs.representant_prenom) : null,
      representant_nom: estSociete ? vide(champs.representant_nom) : null,
    }
  }

  /** Mêmes règles que le backend, pour un message clair avant l'appel. */
  function valider(): string | null {
    if (qui === "associe" && !associateId) return "Choisissez l'associé."
    if (qui === "personne" && !champs.nom_complet.trim()) return "Indiquez le nom de la personne."
    if (qui === "societe" && !champs.denomination_sociale.trim()) return "Indiquez la dénomination de la société."
    if (qui === "societe" && champs.siren.trim() && !/^\d{9}$/.test(champs.siren.replace(/\s/g, ""))) {
      return "Le SIREN doit contenir 9 chiffres."
    }
    return null
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const erreur = valider()
    if (erreur) {
      setError(erreur)
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      if (officer) await updateOfficer(accessToken, projectId, officer.id, payload())
      else await createOfficer(accessToken, projectId, payload())
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
      setIsSubmitting(false)
    }
  }

  const options: { valeur: Qui; libelle: string; desactive: boolean }[] = [
    { valeur: "associe", libelle: "Un associé", desactive: associes.length === 0 },
    { valeur: "personne", libelle: "Une autre personne", desactive: false },
    { valeur: "societe", libelle: "Une autre société", desactive: false },
  ]

  return (
    <Modal title={`${officer ? "Modifier" : "Ajouter"} — ${config.titre}`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <span className={labelClass}>Qui ?</span>
          <div className="grid grid-cols-3 gap-2" role="radiogroup">
            {options.map((o) => (
              <button
                key={o.valeur}
                type="button"
                role="radio"
                aria-checked={qui === o.valeur}
                disabled={o.desactive}
                onClick={() => setQui(o.valeur)}
                className={`rounded-lg border px-3 py-2 text-sm transition disabled:opacity-40 ${
                  qui === o.valeur
                    ? "border-indigo-500 bg-indigo-50 font-medium text-indigo-700"
                    : "border-gray-300 text-gray-700 hover:border-gray-400"
                }`}
              >
                {o.libelle}
              </button>
            ))}
          </div>
        </div>

        {qui === "associe" && (
          <label className="flex flex-col gap-1.5">
            <span className={labelClass}>Associé</span>
            <select value={associateId} onChange={(e) => setAssociateId(e.target.value)} className={inputClass}>
              {associes.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.nom_complet}
                </option>
              ))}
            </select>
            <span className="text-xs text-gray-400">Son identité est reprise depuis « Équipe & capital ».</span>
          </label>
        )}

        {qui === "personne" && (
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1.5">
              <span className={labelClass}>Nom complet</span>
              <input value={champs.nom_complet} onChange={(e) => set("nom_complet", e.target.value)} className={inputClass} />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className={labelClass}>Adresse</span>
              <input value={champs.adresse} onChange={(e) => set("adresse", e.target.value)} className={inputClass} />
            </label>
          </div>
        )}

        {qui === "societe" && (
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1.5">
              <span className={labelClass}>Dénomination sociale</span>
              <input value={champs.denomination_sociale} onChange={(e) => set("denomination_sociale", e.target.value)} className={inputClass} />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className={labelClass}>Forme juridique</span>
              <input value={champs.forme_juridique} onChange={(e) => set("forme_juridique", e.target.value)} placeholder="Ex : SAS" className={inputClass} />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className={labelClass}>Capital (€)</span>
              <input value={champs.capital_social} inputMode="decimal" onChange={(e) => set("capital_social", e.target.value)} className={inputClass} />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className={labelClass}>SIREN</span>
              <input value={champs.siren} onChange={(e) => set("siren", e.target.value)} placeholder="9 chiffres" className={inputClass} />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className={labelClass}>Siège social</span>
              <input value={champs.siege_social} onChange={(e) => set("siege_social", e.target.value)} className={inputClass} />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className={labelClass}>Ville du greffe (RCS)</span>
              <input value={champs.lieu_immatriculation} onChange={(e) => set("lieu_immatriculation", e.target.value)} className={inputClass} />
            </label>
          </div>
        )}

        {estSociete && (
          <div className="flex flex-col gap-1.5">
            <span className={labelClass}>Représentant de la société</span>
            <div className="grid grid-cols-2 gap-3">
              <input value={champs.representant_prenom} onChange={(e) => set("representant_prenom", e.target.value)} placeholder="Prénom" className={inputClass} />
              <input value={champs.representant_nom} onChange={(e) => set("representant_nom", e.target.value)} placeholder="Nom" className={inputClass} />
              {qui === "societe" && (
                <input
                  value={champs.adresse}
                  onChange={(e) => set("adresse", e.target.value)}
                  placeholder="Adresse du représentant"
                  className={`${inputClass} col-span-2`}
                />
              )}
            </div>
          </div>
        )}

        {config.avecDuree && (
          <label className="flex flex-col gap-1.5">
            <span className={labelClass}>Durée des fonctions</span>
            <input
              value={champs.duree_fonctions}
              onChange={(e) => set("duree_fonctions", e.target.value)}
              placeholder="Ex : une durée indéterminée, 3 ans…"
              className={inputClass}
            />
          </label>
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
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
    </Modal>
  )
}
