import type { ProjectLegalProfileRead, ProjectLegalProfileUpdate } from "../api/projectApi"

/**
 * Bloc "Pour la rédaction des statuts" du formulaire Informations légales
 * (service 1.1.4, lot 1 du 24/09/2026). Chaque champ ici est lu
 * AUTOMATIQUEMENT par le générateur de statuts (type `auto_profil_juridique`)
 * et n'est donc plus demandé pendant la rédaction : c'est le seul endroit de
 * l'appli où l'entrepreneur les saisit.
 *
 * Composant séparé de UpdateLegalProfileForm (qui gère le PATCH, la
 * vérification SIREN et la modale) : une responsabilité par fichier, et ce
 * bloc grossira avec les prochains documents (1.1.5…).
 *
 * Contrôlé : l'état vit dans le parent (`values`/`onChange`), ce composant
 * n'affiche que les champs. `toPayload`/`validate` sont exportés pour que le
 * parent construise le PATCH sans dupliquer les règles.
 */

export interface StatutsFieldsValues {
  objetSocial: string
  dureeSociete: string
  sigle: string
  raisonDEtre: string
  objectifsEss: string
  capitalSocial: string
  nombreActions: string
  valeurNominale: string
  lieuImmatriculation: string
  // Siège social (`registered_address`, JSON {ligne1, ligne2, code_postal,
  // ville} -- même clés que `_formater_siege_social` côté backend). Ajouté le
  // 24/09/2026 : aucun écran ne permettait de le saisir.
  siegeLigne1: string
  siegeLigne2: string
  siegeCodePostal: string
  siegeVille: string
}

function champSiege(p: ProjectLegalProfileRead | null, cle: string): string {
  const valeur = p?.registered_address?.[cle]
  return typeof valeur === "string" ? valeur : ""
}

export function initialStatutsFields(p: ProjectLegalProfileRead | null): StatutsFieldsValues {
  return {
    objetSocial: p?.objet_social ?? "",
    dureeSociete: p?.duree_societe != null ? String(p.duree_societe) : "",
    sigle: p?.sigle ?? "",
    raisonDEtre: p?.raison_d_etre ?? "",
    objectifsEss: p?.objectifs_ess ?? "",
    capitalSocial: p?.capital_social ?? "",
    nombreActions: p?.nombre_actions != null ? String(p.nombre_actions) : "",
    valeurNominale: p?.valeur_nominale ?? "",
    lieuImmatriculation: p?.lieu_immatriculation ?? "",
    siegeLigne1: champSiege(p, "ligne1"),
    siegeLigne2: champSiege(p, "ligne2"),
    siegeCodePostal: champSiege(p, "code_postal"),
    siegeVille: champSiege(p, "ville"),
  }
}

/** Montant saisi ("1 000,50") -> centimes entiers, ou null si invalide.
 * Calcul en centimes : évite les erreurs d'arrondi des flottants dans le
 * contrôle capital = actions × valeur nominale. */
function toCents(montant: string): number | null {
  const normalise = montant.replace(/\s/g, "").replace(",", ".")
  if (!/^\d+(\.\d{1,2})?$/.test(normalise)) return null
  return Math.round(Number(normalise) * 100)
}

function normaliserMontant(montant: string): string {
  return montant.replace(/\s/g, "").replace(",", ".")
}

/** Message d'erreur lisible, ou null si tout est valide. Mêmes règles que le
 * backend (schéma + project_service._verifier_coherence_capital), vérifiées
 * ici pour un message clair plutôt qu'un 422/400 brut. */
export function validateStatutsFields(v: StatutsFieldsValues): string | null {
  const siege = [v.siegeLigne1, v.siegeCodePostal, v.siegeVille].map((x) => x.trim())
  const siegeCommence = siege.some(Boolean) || v.siegeLigne2.trim() !== ""
  if (siegeCommence && siege.some((x) => x === "")) {
    return "Adresse du siège : renseignez l'adresse, le code postal et la ville."
  }
  if (siege[1] && !/^\d{5}$/.test(siege[1])) return "Le code postal du siège doit contenir 5 chiffres."
  const duree = v.dureeSociete.trim()
  if (duree !== "") {
    const n = Number(duree)
    if (!Number.isInteger(n) || n < 1 || n > 99) {
      return "La durée de la société doit être un nombre entier d'années entre 1 et 99."
    }
  }
  const capital = v.capitalSocial.trim() === "" ? undefined : toCents(v.capitalSocial)
  const nominale = v.valeurNominale.trim() === "" ? undefined : toCents(v.valeurNominale)
  const actionsTrim = v.nombreActions.trim()
  const actions = actionsTrim === "" ? undefined : Number(actionsTrim)
  if (capital === null || (capital !== undefined && capital <= 0)) return "Le capital social doit être un montant positif (ex : 1000 ou 1000,50)."
  if (nominale === null || (nominale !== undefined && nominale <= 0)) return "La valeur nominale doit être un montant positif (ex : 1 ou 0,10)."
  if (actions !== undefined && (!Number.isInteger(actions) || actions < 1)) return "Le nombre d'actions doit être un entier positif."
  if (capital !== undefined && nominale !== undefined && actions !== undefined && actions * nominale !== capital) {
    return messageIncoherenceCapital(capital, actions, nominale)
  }
  return null
}

const formatEuros = (cents: number) =>
  (cents / 100).toLocaleString("fr-FR", { minimumFractionDigits: 0, maximumFractionDigits: 2 }) + " €"

/** Explique l'écart ET propose des corrections chiffrées (demande
 * utilisateur 24/09/2026) : seules les options qui tombent juste sont
 * proposées -- un nombre d'actions entier, une valeur au centime près. */
function messageIncoherenceCapital(capital: number, actions: number, nominale: number): string {
  const options: string[] = []
  if (capital % nominale === 0) {
    options.push(`mettre ${(capital / nominale).toLocaleString("fr-FR")} actions (à ${formatEuros(nominale)} l'une)`)
  }
  if (capital % actions === 0) {
    options.push(`mettre une valeur d'action de ${formatEuros(capital / actions)} (pour ${actions.toLocaleString("fr-FR")} actions)`)
  }
  options.push(`mettre un capital de ${formatEuros(actions * nominale)}`)
  return (
    `Le calcul ne tombe pas juste : ${actions.toLocaleString("fr-FR")} actions × ${formatEuros(nominale)} = ` +
    `${formatEuros(actions * nominale)}, alors que le capital saisi est de ${formatEuros(capital)}. ` +
    `Le capital doit toujours être égal au nombre d'actions multiplié par la valeur d'une action. ` +
    `Pour corriger, vous pouvez : ${options.join(" ; ou ")}.`
  )
}

/** Champs vides OMIS du PATCH, jamais envoyés comme "" : une chaîne vide
 * serait imprimée telle quelle dans les statuts (texte vide, sans le signal
 * "(non renseigné)"). Limite assumée, déjà en place pour l'objet social : on
 * ne peut pas vider un champ depuis ce formulaire. */
export function statutsFieldsToPayload(v: StatutsFieldsValues): ProjectLegalProfileUpdate {
  const texte = (valeur: string) => (valeur.trim() === "" ? undefined : valeur.trim())
  const payload: ProjectLegalProfileUpdate = {
    objet_social: texte(v.objetSocial),
    duree_societe: v.dureeSociete.trim() === "" ? undefined : Number(v.dureeSociete.trim()),
    sigle: texte(v.sigle),
    raison_d_etre: texte(v.raisonDEtre),
    objectifs_ess: texte(v.objectifsEss),
    capital_social: v.capitalSocial.trim() === "" ? undefined : normaliserMontant(v.capitalSocial),
    nombre_actions: v.nombreActions.trim() === "" ? undefined : Number(v.nombreActions.trim()),
    valeur_nominale: v.valeurNominale.trim() === "" ? undefined : normaliserMontant(v.valeurNominale),
    lieu_immatriculation: texte(v.lieuImmatriculation),
    // Envoyé seulement si l'adresse est complète (contrôlé par validate) ;
    // `ligne2` facultative. Remplace l'objet entier : ce formulaire est le
    // seul à écrire le siège.
    registered_address: v.siegeLigne1.trim()
      ? {
          ligne1: v.siegeLigne1.trim(),
          ...(v.siegeLigne2.trim() ? { ligne2: v.siegeLigne2.trim() } : {}),
          code_postal: v.siegeCodePostal.trim(),
          ville: v.siegeVille.trim(),
        }
      : undefined,
  }
  return Object.fromEntries(Object.entries(payload).filter(([, val]) => val !== undefined)) as ProjectLegalProfileUpdate
}

const inputClass = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
const labelClass = "text-xs font-medium text-gray-700"
const hintClass = "text-xs text-gray-400"

interface Props {
  values: StatutsFieldsValues
  onChange: (values: StatutsFieldsValues) => void
}

export default function StatutsRedactionFields({ values, onChange }: Props) {
  function set<K extends keyof StatutsFieldsValues>(key: K, value: string) {
    onChange({ ...values, [key]: value })
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-gray-100 bg-gray-50 p-3">
      <p className="text-xs font-medium text-gray-700">Pour la rédaction des statuts</p>
      <p className={hintClass}>Ces informations sont reprises automatiquement dans vos statuts : vous n'aurez pas à les ressaisir.</p>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="statuts-objet-social">Objet social</label>
        <textarea id="statuts-objet-social" rows={3} value={values.objetSocial} onChange={(e) => set("objetSocial", e.target.value)}
          placeholder="Ex : la conception, le développement et la commercialisation de logiciels…" className={inputClass} />
        <p className={hintClass}>L'activité que la société va exercer (article 2).</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5">
          <label className={labelClass} htmlFor="statuts-duree">Durée de la société (années)</label>
          <input id="statuts-duree" type="number" min={1} max={99} step={1} value={values.dureeSociete}
            onChange={(e) => set("dureeSociete", e.target.value)} placeholder="99" className={inputClass} />
          <p className={hintClass}>99 ans maximum (article 5).</p>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className={labelClass} htmlFor="statuts-sigle">Sigle (facultatif)</label>
          <input id="statuts-sigle" type="text" maxLength={120} value={values.sigle}
            onChange={(e) => set("sigle", e.target.value)} placeholder="Ex : ACME" className={inputClass} />
          <p className={hintClass}>Abréviation de la dénomination (article 3).</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="flex flex-col gap-1.5">
          <label className={labelClass} htmlFor="statuts-capital">Capital social (€)</label>
          <input id="statuts-capital" type="text" inputMode="decimal" value={values.capitalSocial}
            onChange={(e) => set("capitalSocial", e.target.value)} placeholder="1000" className={inputClass} />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className={labelClass} htmlFor="statuts-nombre-actions">Nombre d'actions</label>
          <input id="statuts-nombre-actions" type="number" min={1} step={1} value={values.nombreActions}
            onChange={(e) => set("nombreActions", e.target.value)} placeholder="1000" className={inputClass} />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className={labelClass} htmlFor="statuts-valeur-nominale">Valeur d'une action (€)</label>
          <input id="statuts-valeur-nominale" type="text" inputMode="decimal" value={values.valeurNominale}
            onChange={(e) => set("valeurNominale", e.target.value)} placeholder="1" className={inputClass} />
        </div>
      </div>
      <p className={hintClass}>Nombre d'actions × valeur d'une action = capital (articles 6 et 7).</p>

      <div className="flex flex-col gap-1.5">
        <span className={labelClass}>Adresse du siège social</span>
        <input type="text" value={values.siegeLigne1} onChange={(e) => set("siegeLigne1", e.target.value)}
          placeholder="Numéro et rue" className={inputClass} />
        <input type="text" value={values.siegeLigne2} onChange={(e) => set("siegeLigne2", e.target.value)}
          placeholder="Complément (facultatif)" className={inputClass} />
        <div className="grid grid-cols-3 gap-3">
          <input type="text" inputMode="numeric" maxLength={5} value={values.siegeCodePostal}
            onChange={(e) => set("siegeCodePostal", e.target.value)} placeholder="Code postal" className={inputClass} />
          <input type="text" value={values.siegeVille} onChange={(e) => set("siegeVille", e.target.value)}
            placeholder="Ville" className={`${inputClass} col-span-2`} />
        </div>
        <p className={hintClass}>Reprise dans l'en-tête et l'article 4 des statuts.</p>
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="statuts-lieu-immatriculation">Ville du greffe (RCS)</label>
        <input id="statuts-lieu-immatriculation" type="text" maxLength={120} value={values.lieuImmatriculation}
          onChange={(e) => set("lieuImmatriculation", e.target.value)} placeholder="Ex : Paris" className={inputClass} />
        <p className={hintClass}>Le greffe où la société sera immatriculée, en général celui du siège.</p>
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="statuts-raison-d-etre">Raison d'être (facultatif)</label>
        <textarea id="statuts-raison-d-etre" rows={2} value={values.raisonDEtre} onChange={(e) => set("raisonDEtre", e.target.value)}
          placeholder="Les principes et valeurs que la société se donne, au-delà du profit" className={inputClass} />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="statuts-objectifs-ess">Objectifs d'utilité sociale — ESS (facultatif)</label>
        <textarea id="statuts-objectifs-ess" rows={2} value={values.objectifsEss} onChange={(e) => set("objectifsEss", e.target.value)}
          placeholder="Seulement si la société relève de l'économie sociale et solidaire" className={inputClass} />
      </div>
    </div>
  )
}
