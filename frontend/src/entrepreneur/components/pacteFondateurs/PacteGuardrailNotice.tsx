import type { GuardrailBlockedDetail } from "../../api/documentGenerationApi"

interface PacteGuardrailNoticeProps {
  detail: GuardrailBlockedDetail
}

/**
 * Étape 3 du scénario — garde-fou juridique non contournable. Affiche le
 * motif, l'article de loi cité (`article_cite`, peut être absent si le LLM
 * s'appuie sur une jurisprudence constante plutôt qu'un texte précis — voir
 * GuardrailResult côté backend) et la reformulation proposée. Purement
 * informatif : ne modifie rien, l'utilisateur corrige lui-même son texte dans
 * le champ concerné (le formulaire reste rempli, rien n'est perdu).
 */
export default function PacteGuardrailNotice({ detail }: PacteGuardrailNoticeProps) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900">
      <p className="font-medium">{detail.message}</p>
      {detail.article_cite && (
        <p>
          <span className="font-medium">Référence légale : </span>
          {detail.article_cite}
        </p>
      )}
      {detail.reformulation_proposee && (
        <div className="rounded-lg bg-white p-3 text-gray-800">
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500">
            Reformulation proposée
          </p>
          <p>{detail.reformulation_proposee}</p>
        </div>
      )}
    </div>
  )
}
