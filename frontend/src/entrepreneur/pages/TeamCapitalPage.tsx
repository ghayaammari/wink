import { useEffect, useState } from "react"
import { useOutletContext } from "react-router-dom"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import Modal from "../../shared/components/Modal"
import SectionCard from "../../shared/components/SectionCard"
import {
  getAssociates,
  replaceAssociates,
  type AssociateTypeApport,
  type AssociateTypePersonne,
  type ProjectAssociateBatchItem,
  type ProjectAssociateRead,
} from "../api/projectApi"
import type { MyProjectOutletContext } from "./MyProjectLayout"

/** Brouillon local d'un associé : id null = non encore enregistré (création). */
type DraftAssociate = {
  id: string | null
  nom_complet: string
  type_personne: AssociateTypePersonne
  date_naissance: string | null
  lieu_naissance: string | null
  situation_et_regime_matrimonial: string | null
  nationalite: string | null
  adresse: string | null
  pourcentage_capital: string
  pourcentage_droits_vote: string | null
  type_apport: AssociateTypeApport
  description_apport_nature: string | null
  est_dirigeant: boolean
  fonction_dirigeant: string | null
  /** id de la ligne de l'associé dirigeant (chef de foyer) auquel cette personne
   * est rattachée fiscalement (conjoint/PACS/enfant à charge) — NULL sinon. */
  foyer_fiscal_dirigeant_associate_id: string | null
  est_partie_au_pacte_fondateurs: boolean
  /** Distingue Associé Fondateur / Associé Investisseur pour le préambule
   * du pacte de fondateurs (v2) — voir ProjectAssociateRead.est_fondateur
   * côté API. Non exposé si `est_partie_au_pacte_fondateurs` est faux : sans
   * intérêt hors contexte pacte. */
  est_fondateur: boolean
  /** AJOUT 24/09/2026 — pertinents seulement si `type_personne === "personne_morale"`.
   * `nom_complet` reste rempli automatiquement (= denomination_sociale) pour ce
   * type : la colonne `nom_complet` est NOT NULL en base et sert d'étiquette
   * d'affichage générique (liste, badges, sélecteur de foyer fiscal) — pas la
   * peine de redemander la même information deux fois à l'utilisateur. */
  denomination_sociale: string | null
  type_societe: string | null
  capital_social: string | null
  siege_social: string | null
  lieu_immatriculation: string | null
  numero_siren: string | null
  representant_nom: string | null
  representant_prenom: string | null
  representant_qualite: string | null
}

type AssociateFormState = {
  nom_complet: string
  type_personne: AssociateTypePersonne
  date_naissance: string
  lieu_naissance: string
  situation_et_regime_matrimonial: string
  nationalite: string
  adresse: string
  pourcentage_capital: string
  pourcentage_droits_vote_defined: boolean
  pourcentage_droits_vote: string
  type_apport: AssociateTypeApport
  description_apport_nature: string
  est_dirigeant: boolean
  fonction_dirigeant: string
  foyer_fiscal_dirigeant_associate_id: string
  est_partie_au_pacte_fondateurs: boolean
  est_fondateur: boolean
  denomination_sociale: string
  type_societe: string
  capital_social: string
  siege_social: string
  lieu_immatriculation: string
  numero_siren: string
  representant_nom: string
  representant_prenom: string
  representant_qualite: string
}

const EMPTY_FORM: AssociateFormState = {
  nom_complet: "",
  type_personne: "personne_physique",
  date_naissance: "",
  lieu_naissance: "",
  situation_et_regime_matrimonial: "",
  nationalite: "",
  adresse: "",
  pourcentage_capital: "",
  pourcentage_droits_vote_defined: false,
  pourcentage_droits_vote: "",
  type_apport: "numeraire",
  description_apport_nature: "",
  est_dirigeant: false,
  fonction_dirigeant: "",
  foyer_fiscal_dirigeant_associate_id: "",
  est_partie_au_pacte_fondateurs: false,
  est_fondateur: false,
  denomination_sociale: "",
  type_societe: "",
  capital_social: "",
  siege_social: "",
  lieu_immatriculation: "",
  numero_siren: "",
  representant_nom: "",
  representant_prenom: "",
  representant_qualite: "",
}

function draftFromAssociate(a: ProjectAssociateRead): DraftAssociate {
  return {
    id: a.id,
    nom_complet: a.nom_complet,
    type_personne: a.type_personne,
    date_naissance: a.date_naissance,
    lieu_naissance: a.lieu_naissance,
    situation_et_regime_matrimonial: a.situation_et_regime_matrimonial,
    nationalite: a.nationalite,
    adresse: a.adresse,
    pourcentage_capital: a.pourcentage_capital,
    pourcentage_droits_vote: a.pourcentage_droits_vote,
    type_apport: a.type_apport,
    description_apport_nature: a.description_apport_nature,
    est_dirigeant: a.est_dirigeant,
    fonction_dirigeant: a.fonction_dirigeant,
    foyer_fiscal_dirigeant_associate_id: a.foyer_fiscal_dirigeant_associate_id,
    est_partie_au_pacte_fondateurs: a.est_partie_au_pacte_fondateurs,
    est_fondateur: a.est_fondateur,
    denomination_sociale: a.denomination_sociale,
    type_societe: a.type_societe,
    capital_social: a.capital_social,
    siege_social: a.siege_social,
    lieu_immatriculation: a.lieu_immatriculation,
    numero_siren: a.numero_siren,
    representant_nom: a.representant_nom,
    representant_prenom: a.representant_prenom,
    representant_qualite: a.representant_qualite,
  }
}

function formFromDraft(d: DraftAssociate): AssociateFormState {
  return {
    nom_complet: d.nom_complet,
    type_personne: d.type_personne,
    date_naissance: d.date_naissance ?? "",
    lieu_naissance: d.lieu_naissance ?? "",
    situation_et_regime_matrimonial: d.situation_et_regime_matrimonial ?? "",
    nationalite: d.nationalite ?? "",
    adresse: d.adresse ?? "",
    pourcentage_capital: d.pourcentage_capital,
    pourcentage_droits_vote_defined: d.pourcentage_droits_vote !== null,
    pourcentage_droits_vote: d.pourcentage_droits_vote ?? "",
    type_apport: d.type_apport,
    description_apport_nature: d.description_apport_nature ?? "",
    est_dirigeant: d.est_dirigeant,
    fonction_dirigeant: d.fonction_dirigeant ?? "",
    foyer_fiscal_dirigeant_associate_id: d.foyer_fiscal_dirigeant_associate_id ?? "",
    est_partie_au_pacte_fondateurs: d.est_partie_au_pacte_fondateurs,
    est_fondateur: d.est_fondateur,
    denomination_sociale: d.denomination_sociale ?? "",
    type_societe: d.type_societe ?? "",
    capital_social: d.capital_social ?? "",
    siege_social: d.siege_social ?? "",
    lieu_immatriculation: d.lieu_immatriculation ?? "",
    numero_siren: d.numero_siren ?? "",
    representant_nom: d.representant_nom ?? "",
    representant_prenom: d.representant_prenom ?? "",
    representant_qualite: d.representant_qualite ?? "",
  }
}

function formToDraft(form: AssociateFormState, id: string | null): DraftAssociate {
  const isMorale = form.type_personne === "personne_morale"
  return {
    id,
    // Pour une personne morale, `nom_complet` (NOT NULL en base) reflète la
    // dénomination sociale — pas de champ redondant à remplir deux fois côté
    // utilisateur (voir DraftAssociate.denomination_sociale ci-dessus).
    nom_complet: isMorale ? form.denomination_sociale.trim() : form.nom_complet.trim(),
    type_personne: form.type_personne,
    date_naissance: form.date_naissance || null,
    lieu_naissance: form.lieu_naissance.trim() || null,
    // Personne physique uniquement (en-tête des statuts).
    situation_et_regime_matrimonial: isMorale ? null : form.situation_et_regime_matrimonial.trim() || null,
    nationalite: form.nationalite.trim() || null,
    adresse: form.adresse.trim() || null,
    pourcentage_capital: parseDecimal(form.pourcentage_capital).toFixed(2),
    pourcentage_droits_vote: form.pourcentage_droits_vote_defined
      ? parseDecimal(form.pourcentage_droits_vote).toFixed(2)
      : null,
    type_apport: form.type_apport,
    // Vidée si le type n'est plus "nature" (même règle que le backend).
    description_apport_nature:
      form.type_apport === "nature" ? form.description_apport_nature.trim() || null : null,
    est_dirigeant: form.est_dirigeant,
    fonction_dirigeant: form.fonction_dirigeant.trim() || null,
    foyer_fiscal_dirigeant_associate_id: form.foyer_fiscal_dirigeant_associate_id || null,
    est_partie_au_pacte_fondateurs: form.est_partie_au_pacte_fondateurs,
    // Une case décochée pour "partie au pacte" annule aussi "fondateur" —
    // évite un état incohérent en base (fondateur=true sur un associé qui
    // n'est plus partie au pacte) si l'utilisateur décoche l'une après l'autre.
    est_fondateur: form.est_partie_au_pacte_fondateurs ? form.est_fondateur : false,
    denomination_sociale: isMorale ? form.denomination_sociale.trim() || null : null,
    type_societe: isMorale ? form.type_societe.trim() || null : null,
    capital_social: isMorale && form.capital_social ? parseDecimal(form.capital_social).toFixed(2) : null,
    siege_social: isMorale ? form.siege_social.trim() || null : null,
    lieu_immatriculation: isMorale ? form.lieu_immatriculation.trim() || null : null,
    // Retire les espaces (format d'affichage habituel "123 456 789") avant
    // l'envoi : le backend attend exactement 9 chiffres (max_length=9), pas
    // la peine d'imposer à l'utilisateur de taper sans espaces.
    numero_siren: isMorale ? form.numero_siren.replace(/\s/g, "").trim() || null : null,
    representant_nom: isMorale ? form.representant_nom.trim() || null : null,
    representant_prenom: isMorale ? form.representant_prenom.trim() || null : null,
    representant_qualite: isMorale ? form.representant_qualite.trim() || null : null,
  }
}

function parseDecimal(s: string): number {
  const n = Number.parseFloat(s.replace(",", "."))
  return Number.isFinite(n) ? n : 0
}

/** Les champs métier comparés pour détecter un brouillon non enregistré. */
function draftFieldKey(d: DraftAssociate) {
  return JSON.stringify({
    key: d.id ?? "new",
    nom_complet: d.nom_complet,
    type_personne: d.type_personne,
    date_naissance: d.date_naissance,
    lieu_naissance: d.lieu_naissance,
    situation_et_regime_matrimonial: d.situation_et_regime_matrimonial,
    nationalite: d.nationalite,
    adresse: d.adresse,
    pourcentage_capital: d.pourcentage_capital,
    pourcentage_droits_vote: d.pourcentage_droits_vote,
    type_apport: d.type_apport,
    description_apport_nature: d.description_apport_nature,
    est_dirigeant: d.est_dirigeant,
    fonction_dirigeant: d.fonction_dirigeant,
    foyer_fiscal_dirigeant_associate_id: d.foyer_fiscal_dirigeant_associate_id,
    est_partie_au_pacte_fondateurs: d.est_partie_au_pacte_fondateurs,
    est_fondateur: d.est_fondateur,
    denomination_sociale: d.denomination_sociale,
    type_societe: d.type_societe,
    capital_social: d.capital_social,
    siege_social: d.siege_social,
    lieu_immatriculation: d.lieu_immatriculation,
    numero_siren: d.numero_siren,
    representant_nom: d.representant_nom,
    representant_prenom: d.representant_prenom,
    representant_qualite: d.representant_qualite,
  })
}

/** Droits de vote d'un associé : explicites si renseignés, sinon = capital (1 action = 1 voix). */
function droitsDeVote(d: DraftAssociate): number {
  return parseDecimal(d.pourcentage_droits_vote ?? d.pourcentage_capital)
}

/** Condition e21 (art. 239 bis AB du CGI) : somme des droits de vote des
 * dirigeants + de leur foyer fiscal. Reproduit dataframe de roadmap_service. */
function totalDirigeantsEtFoyer(draft: DraftAssociate[]): number {
  const dirigeants = draft.filter((d) => d.est_dirigeant).reduce((s, d) => s + droitsDeVote(d), 0)
  const foyer = draft
    .filter((d) => !d.est_dirigeant && d.foyer_fiscal_dirigeant_associate_id !== null)
    .reduce((s, d) => s + droitsDeVote(d), 0)
  return dirigeants + foyer
}

function itemsToPayload(items: DraftAssociate[]): ProjectAssociateBatchItem[] {
  return items
}

const TYPE_APPORT_LABELS: Record<AssociateTypeApport, string> = {
  numeraire: "Numéraire (argent)",
  nature: "Nature (bien)",
  industrie: "Industrie (compétences)",
}

/**
 * "Mon Projet" → Équipe & capital (table `project_associates`).
 *
 * Modèle d'édition "brouillon + enregistrement global" (décision de conception
 * validée) : les ajouts/modifs/suppressions dans la modal ne touchent QUE l'état
 * local de la page. Le clic "Enregistrer" PUT la liste COMPLÈTE vers
 * /projects/{id}/associates, où le backend valide l'état cible (somme des parts
 * = 100 %, ≥ 1 dirigeant, représentant légal non retirable, cohérence foyer
 * fiscal) avant d'écrire. Un total intermédiaire ≠ 100 % est toléré en brouillon
 * (alerte rouge), refusé à l'enregistrement (400).
 *
 * Foyer fiscal (art. 239 bis AB du CGI) : un associé non-dirigeant peut être
 * rattaché au foyer fiscal d'un dirigeant (conjoint/PACS/enfant à charge) —
 * ligne "Foyer fiscal de {dirigeant}" et indicateur e21 sous le total reflètent
 * la condition de la roadmap (dirigeants + foyer > 34 %).
 *
 * La ligne du fondateur (associé = propriétaire, 100 % solo, dirigeant) est
 * matérialisée par le backend au premier GET /associates. `linked_user_id`
 * n'est pas éditable ici.
 * (réalisé par OPENCODE)
 */
export default function TeamCapitalPage() {
  const { accessToken } = useAuth()
  const { project, refresh } = useOutletContext<MyProjectOutletContext>()
  const [draft, setDraft] = useState<DraftAssociate[]>([])
  const [serverKey, setServerKey] = useState<string>("")
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editing, setEditing] = useState<DraftAssociate | null>(null)
  const [form, setForm] = useState<AssociateFormState>(EMPTY_FORM)
  const [isSaving, setIsSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const draftKey = draft.map(draftFieldKey).sort().join("|")
  const isDirty = draftKey !== serverKey

  const totalCapital = draft.reduce((sum, a) => sum + parseDecimal(a.pourcentage_capital), 0)
  const hasDirigeant = draft.some((a) => a.est_dirigeant)

  function setField<K extends keyof AssociateFormState>(key: K, value: AssociateFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  useEffect(() => {
    if (!accessToken) return
    setIsLoading(true)
    getAssociates(accessToken, project.id)
      .then((list) => {
        const drafts = list.map(draftFromAssociate)
        setDraft(drafts)
        setServerKey(drafts.map(draftFieldKey).sort().join("|"))
        setSaveError(null)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Impossible de charger les associés."))
      .finally(() => setIsLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage et si le projet change
  }, [accessToken, project.id])

  function openCreate() {
    setEditing(null)
    setForm({ ...EMPTY_FORM, est_partie_au_pacte_fondateurs: false })
    setFormError(null)
    setIsModalOpen(true)
  }

  function openEdit(associate: DraftAssociate) {
    setEditing(associate)
    setForm(formFromDraft(associate))
    setFormError(null)
    setIsModalOpen(true)
  }

  function closeModal() {
    setIsModalOpen(false)
  }

  /** Applique le formulaire au BROUILLON local (aucun appel serveur). */
  async function handleFormSubmit() {
    if (form.type_personne === "personne_morale") {
      if (!form.denomination_sociale.trim()) {
        setFormError("La dénomination sociale est obligatoire.")
        return
      }
    } else if (!form.nom_complet.trim()) {
      setFormError("Le nom de l'associé est obligatoire.")
      return
    }
    if (form.est_dirigeant && !form.fonction_dirigeant.trim()) {
      setFormError("Un dirigeant doit avoir une fonction renseignée.")
      return
    }
    if (form.type_apport === "nature" && !form.description_apport_nature.trim()) {
      setFormError("Décrivez le bien apporté en nature : cette description est reprise dans les statuts.")
      return
    }
    if (form.type_apport === "industrie" && parseDecimal(form.pourcentage_capital) !== 0) {
      setFormError("Un apport en industrie ne concourt jamais au capital (art. 1843-2).")
      return
    }

    setFormError(null)
    const next = formToDraft(form, editing?.id ?? null)
    setDraft((prev) => {
      if (editing) return prev.map((d) => (d.id === editing.id ? next : d))
      return [...prev, next]
    })
    setSaveError(null)
    setIsModalOpen(false)
  }

  function handleDelete(associate: DraftAssociate) {
    if (!window.confirm(`Retirer ${associate.nom_complet} de la répartition ?`)) return
    setDraft((prev) => prev.filter((d) => d.id !== associate.id))
    setSaveError(null)
  }

  function resetDraft() {
    getAssociates(accessToken!, project.id)
      .then((list) => {
        const drafts = list.map(draftFromAssociate)
        setDraft(drafts)
        setServerKey(drafts.map(draftFieldKey).sort().join("|"))
        setSaveError(null)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Impossible de recharger les associés."))
  }

  /** PUT global de la liste complète — le backend valide l'état cible. */
  async function handleSaveAll() {
    if (!accessToken) return
    setIsSaving(true)
    setSaveError(null)
    try {
      const saved = await replaceAssociates(accessToken, project.id, itemsToPayload(draft))
      const drafts = saved.map(draftFromAssociate)
      setDraft(drafts)
      setServerKey(drafts.map(draftFieldKey).sort().join("|"))
      refresh()
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Une erreur est survenue lors de l'enregistrement.")
    } finally {
      setIsSaving(false)
    }
  }

  const isEditing = editing !== null

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Équipe & capital</h1>
          <p className="mt-1 text-xs text-gray-500">
            Répartition du capital et des droits de vote — utilisée par les étapes
            statuts (1.1.4), pacte de fondateurs (1.1.13) et DBE (1.1.6).
          </p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400"
        >
          Ajouter un associé
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <>
          <SectionCard title="Associés">
            <div className="flex flex-col gap-3">
              {draft.length === 0 && <p className="text-sm text-gray-500">Aucun associé enregistré.</p>}
              {draft.map((a) => (
                <div
                  key={a.id ?? a.nom_complet}
                  className="flex flex-col gap-2 rounded-lg border border-gray-200 p-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex flex-col gap-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-gray-900">{a.nom_complet}</span>
                      {a.id === null && (
                        <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
                          Non enregistré
                        </span>
                      )}
                      {a.est_dirigeant && (
                        <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
                          Dirigeant{a.fonction_dirigeant ? ` · ${a.fonction_dirigeant}` : ""}
                        </span>
                      )}
                      {a.est_partie_au_pacte_fondateurs && (
                        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                          Pacte fondateurs{a.est_fondateur ? " · Fondateur" : " · Investisseur"}
                        </span>
                      )}
                      {a.foyer_fiscal_dirigeant_associate_id !== null && (
                        <span className="rounded-full bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-700">
                          Foyer fiscal de{" "}
                          {draft.find((d) => d.id === a.foyer_fiscal_dirigeant_associate_id)?.nom_complet ?? "…"}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500">
                      {a.type_personne === "personne_morale" ? "Personne morale" : a.nom_complet} ·{" "}
                      {a.pourcentage_capital} % capital ·{" "}
                      {a.pourcentage_droits_vote === null
                        ? "votes = capital"
                        : `${a.pourcentage_droits_vote} % droits de vote`}{" "}
                      · {TYPE_APPORT_LABELS[a.type_apport]}
                      {a.date_naissance ? ` · née le ${a.date_naissance}` : ""}
                      {a.nationalite ? ` · ${a.nationalite}` : ""}
                      {a.adresse ? ` · ${a.adresse}` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => openEdit(a)}
                      className="rounded-md border border-gray-300 px-2.5 py-1 text-xs font-medium text-gray-600 transition hover:border-gray-400"
                    >
                      Modifier
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(a)}
                      className="rounded-md border border-gray-300 px-2.5 py-1 text-xs font-medium text-red-600 transition hover:border-red-400"
                    >
                      Supprimer
                    </button>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 flex items-center justify-between border-t border-gray-100 pt-3">
              <dt className="text-xs text-gray-400">Total capital</dt>
              <dd
                className={`text-sm font-medium ${
                  Math.abs(totalCapital - 100) < 0.01 ? "text-gray-900" : "text-red-600"
                }`}
              >
                {totalCapital.toFixed(2)} %{Math.abs(totalCapital - 100) >= 0.01 && " — doit valoir 100 %"}
              </dd>
            </div>
            {draft.length > 0 && (
              <div className="mt-2 flex items-center justify-between border-t border-gray-100 pt-3">
                <dt className="text-xs text-gray-400">Droits de vote (dirigeants + foyer fiscal)</dt>
                <dd
                  className={`text-sm font-medium ${
                    totalDirigeantsEtFoyer(draft) > 34 ? "text-emerald-700" : "text-gray-500"
                  }`}
                >
                  {totalDirigeantsEtFoyer(draft).toFixed(2)} % —{" "}
                  {totalDirigeantsEtFoyer(draft) > 34
                    ? "> 34 : régime IR (e21) accessible"
                    : "≤ 34 : étape e21 masquée dans le plan"}
                </dd>
              </div>
            )}
            {!hasDirigeant && draft.length > 0 && (
              <p className="text-xs text-red-600">Au moins un associé doit être dirigeant avant l'enregistrement.</p>
            )}
          </SectionCard>

          {isDirty && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex flex-col gap-0.5">
                  <p className="text-sm font-medium text-amber-800">Modifications non enregistrées</p>
                  <p className="text-xs text-amber-700">
                    La répartition complète est validée au clic "Enregistrer" (somme = 100 %, ≥ 1 dirigeant).
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={resetDraft}
                    className="rounded-lg border border-amber-300 px-3 py-2 text-sm font-medium text-amber-700 transition hover:border-amber-400"
                  >
                    Réinitialiser
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveAll}
                    disabled={isSaving}
                    className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {isSaving ? "Enregistrement..." : "Enregistrer"}
                  </button>
                </div>
              </div>
              {saveError && <p className="mt-2 text-sm text-red-600">{saveError}</p>}
            </div>
          )}
        </>
      )}

      {isModalOpen && (
        <Modal title={isEditing ? "Modifier l'associé" : "Ajouter un associé"} onClose={closeModal}>
          <form
            className="flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault()
              handleFormSubmit()
            }}
          >
            {/* Type de personne EN PREMIER (24/09/2026) : détermine quels champs
                d'identité suivent (nom complet + naissance pour une personne
                physique, dénomination sociale + représentant pour une personne
                morale) — le choisir après aurait laissé "Nom complet" affiché à
                tort pour une personne morale, sans aucun champ de remplacement. */}
            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-500">Type de personne</span>
              <select
                value={form.type_personne}
                onChange={(e) => setField("type_personne", e.target.value as AssociateTypePersonne)}
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
              >
                <option value="personne_physique">Personne physique</option>
                <option value="personne_morale">Personne morale</option>
              </select>
            </label>

            {form.type_personne === "personne_physique" ? (
              <>
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-gray-500">Nom complet *</span>
                  <input
                    type="text"
                    value={form.nom_complet}
                    onChange={(e) => setField("nom_complet", e.target.value)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                  />
                </label>

                <div className="flex flex-col gap-1">
                  <span className="text-xs text-gray-500">Identité (requise pour rédiger les statuts)</span>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="date"
                      value={form.date_naissance}
                      onChange={(e) => setField("date_naissance", e.target.value)}
                      className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                      placeholder="Date de naissance"
                    />
                    <input
                      type="text"
                      value={form.lieu_naissance}
                      onChange={(e) => setField("lieu_naissance", e.target.value)}
                      className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                      placeholder="Lieu de naissance"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      value={form.nationalite}
                      onChange={(e) => setField("nationalite", e.target.value)}
                      className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                      placeholder="Nationalité"
                    />
                    <input
                      type="text"
                      value={form.adresse}
                      onChange={(e) => setField("adresse", e.target.value)}
                      className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                      placeholder="Adresse"
                    />
                  </div>
                  <input
                    type="text"
                    value={form.situation_et_regime_matrimonial}
                    onChange={(e) => setField("situation_et_regime_matrimonial", e.target.value)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    placeholder="Situation et régime matrimonial (ex : célibataire, marié(e) sous le régime de la communauté)"
                  />
                  <span className="text-xs text-gray-400">
                    Date et lieu de naissance, adresse et situation matrimoniale figurent dans vos statuts.
                  </span>
                </div>
              </>
            ) : (
              <div className="flex flex-col gap-2">
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-gray-500">Dénomination sociale *</span>
                  <input
                    type="text"
                    value={form.denomination_sociale}
                    onChange={(e) => setField("denomination_sociale", e.target.value)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                  />
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    value={form.type_societe}
                    onChange={(e) => setField("type_societe", e.target.value)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    placeholder="Type de société (ex : SAS)"
                  />
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.capital_social}
                    onChange={(e) => setField("capital_social", e.target.value)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    placeholder="Capital social (€)"
                  />
                </div>
                <input
                  type="text"
                  value={form.siege_social}
                  onChange={(e) => setField("siege_social", e.target.value)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                  placeholder="Siège social"
                />
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    value={form.lieu_immatriculation}
                    onChange={(e) => setField("lieu_immatriculation", e.target.value)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    placeholder="Lieu d'immatriculation (RCS)"
                  />
                  <input
                    type="text"
                    value={form.numero_siren}
                    onChange={(e) => setField("numero_siren", e.target.value)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    placeholder="Numéro Siren"
                  />
                </div>
                <span className="mt-1 text-xs text-gray-500">Représentant légal (facultatif)</span>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    value={form.representant_prenom}
                    onChange={(e) => setField("representant_prenom", e.target.value)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    placeholder="Prénom"
                  />
                  <input
                    type="text"
                    value={form.representant_nom}
                    onChange={(e) => setField("representant_nom", e.target.value)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    placeholder="Nom"
                  />
                </div>
                <input
                  type="text"
                  value={form.representant_qualite}
                  onChange={(e) => setField("representant_qualite", e.target.value)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                  placeholder="Qualité (ex : Président)"
                />
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-1">
                <span className="text-xs text-gray-500">Part de capital (%) *</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  value={form.pourcentage_capital}
                  onChange={(e) => setField("pourcentage_capital", e.target.value)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-gray-500">Type d'apport</span>
                <select
                  value={form.type_apport}
                  onChange={(e) => setField("type_apport", e.target.value as AssociateTypeApport)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                >
                  {Object.entries(TYPE_APPORT_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {form.type_apport === "nature" && (
              <label className="flex flex-col gap-1">
                <span className="text-xs text-gray-500">Bien apporté</span>
                <textarea
                  rows={2}
                  value={form.description_apport_nature}
                  onChange={(e) => setField("description_apport_nature", e.target.value)}
                  placeholder="Ex : un fonds de commerce situé 12 rue…, un brevet n°…, du matériel informatique (liste)…"
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
                <span className="text-xs text-gray-400">Repris automatiquement dans les statuts (article 6).</span>
              </label>
            )}

            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={form.pourcentage_droits_vote_defined}
                onChange={(e) => setField("pourcentage_droits_vote_defined", e.target.checked)}
              />
              Droits de vote différents du capital (= parts spécifiques)
            </label>

            {form.pourcentage_droits_vote_defined && (
              <label className="flex flex-col gap-1">
                <span className="text-xs text-gray-500">Droits de vote (%)</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  value={form.pourcentage_droits_vote}
                  onChange={(e) => setField("pourcentage_droits_vote", e.target.value)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </label>
            )}

            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={form.est_dirigeant}
                  onChange={(e) => {
                    const value = e.target.checked
                    setField("est_dirigeant", value)
                    // Un dirigeant est "chef de foyer" : il ne peut pas être rattaché à un autre.
                    if (value) setField("foyer_fiscal_dirigeant_associate_id", "")
                  }}
                />
                Dirigeant
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={form.est_partie_au_pacte_fondateurs}
                  onChange={(e) => {
                    const value = e.target.checked
                    setField("est_partie_au_pacte_fondateurs", value)
                    if (!value) setField("est_fondateur", false)
                  }}
                />
                Membre du pacte de fondateurs
              </label>
              {form.est_partie_au_pacte_fondateurs && (
                <label className="flex items-center gap-2 pl-4 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={form.est_fondateur}
                    onChange={(e) => setField("est_fondateur", e.target.checked)}
                  />
                  Associé fondateur (sinon : Associé investisseur)
                </label>
              )}
            </div>

            {form.est_dirigeant && (
              <label className="flex flex-col gap-1">
                <span className="text-xs text-gray-500">Fonction du dirigeant</span>
                <input
                  type="text"
                  value={form.fonction_dirigeant}
                  onChange={(e) => setField("fonction_dirigeant", e.target.value)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                  placeholder="ex: Président, Gérant"
                />
              </label>
            )}

            {!form.est_dirigeant && (
              <label className="flex flex-col gap-1">
                <span className="text-xs text-gray-500">
                  Fait partie du foyer fiscal du dirigeant (art. 239 bis AB)
                </span>
                <select
                  value={form.foyer_fiscal_dirigeant_associate_id}
                  onChange={(e) => setField("foyer_fiscal_dirigeant_associate_id", e.target.value)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="">Aucun</option>
                  {draft
                    .filter((d) => d.est_dirigeant && d.id !== (editing?.id ?? null))
                    .map((d) => (
                      <option key={d.id ?? "new"} value={d.id ?? ""}>
                        {d.nom_complet}
                        {d.id === null ? " (non enregistré)" : ""}
                      </option>
                    ))}
                </select>
              </label>
            )}

            {formError && <p className="text-sm text-red-600">{formError}</p>}

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={closeModal}
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400"
              >
                Annuler
              </button>
              <button
                type="submit"
                className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700"
              >
                {isEditing ? "Appliquer" : "Ajouter"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}