import { useEffect, useState } from "react"
import { Document, Page, pdfjs } from "react-pdf"
import { Icon, ICON_CHEVRON_LEFT, ICON_CHEVRON_RIGHT, ICON_MINUS, ICON_PLUS } from "./pacteIcons"
import "react-pdf/dist/Page/AnnotationLayer.css"
import "react-pdf/dist/Page/TextLayer.css"
import type { PDFDocumentProxy } from "pdfjs-dist"

// Worker chargé depuis pdfjs-dist plutôt qu'un CDN : évite une dépendance
// réseau externe au runtime (cohérent avec le reste de l'app, servi
// uniquement par le backend Wink), et une seule version à faire correspondre
// (pdfjs-dist est une dépendance transitive figée de react-pdf).
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString()

interface OutlineEntry {
  title: string
  pageNumber: number | null
}

interface PacteDocumentPreviewV2Props {
  /** `null` tant qu'aucun aperçu n'a encore été chargé (avant la 1ère
   * section validée, ou pendant un rechargement) — voir PacteFondateursV2Page. */
  pdfBlob: Blob | null
  isLoading: boolean
}

const MIN_SCALE = 0.6
const MAX_SCALE = 2.2
const SCALE_STEP = 0.2

/**
 * Volet droit v2 — rendu PDF réel du document (couleurs + signets produits
 * par `pdf_rendering_service.render_document_as_pdf`), remplace le
 * `PacteDocumentPreview` v1 (texte brut) : le PDF est la seule source de
 * vérité ici, plus de reconstruction cliente du texte des clauses (voir
 * `renderClauseTexte` côté v1, devenu inutile puisque l'aperçu vient
 * directement de l'endpoint `.../preview`, jamais persisté côté backend).
 *
 * Navigation par sommaire : construite depuis `pdf.getOutline()` (les
 * signets posés par `_DocumentAvecSommaire.afterFlowable` côté backend), pas
 * dupliquée côté frontend à partir des sections du formulaire — une seule
 * source de vérité pour la structure du document.
 */
export default function PacteDocumentPreviewV2({ pdfBlob, isLoading }: PacteDocumentPreviewV2Props) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [numPages, setNumPages] = useState(0)
  const [pageNumber, setPageNumber] = useState(1)
  const [scale, setScale] = useState(1)
  const [outline, setOutline] = useState<OutlineEntry[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  // Sommaire repliable (24/09/2026, demande utilisateur) : replié par défaut
  // sur un petit écran, ouvert sinon -- le contenu du PDF est très étroit
  // quand le sommaire prend toute la largeur restante à côté du formulaire.
  const [sidebarOpen, setSidebarOpen] = useState(true)

  // Un blob URL par blob reçu — révoqué au démontage/changement pour ne pas
  // accumuler des URLs objet en mémoire à chaque rafraîchissement de section.
  useEffect(() => {
    if (!pdfBlob) {
      setPdfUrl(null)
      return
    }
    const url = URL.createObjectURL(pdfBlob)
    setPdfUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [pdfBlob])

  async function handleLoadSuccess(pdf: PDFDocumentProxy) {
    setLoadError(null)
    setNumPages(pdf.numPages)
    setPageNumber((prev) => Math.min(prev, pdf.numPages))

    try {
      const rawOutline = await pdf.getOutline()
      if (!rawOutline) {
        setOutline([])
        return
      }
      const entries = await Promise.all(
        rawOutline.map(async (item) => {
          let pageNum: number | null = null
          try {
            const dest = typeof item.dest === "string" ? await pdf.getDestination(item.dest) : item.dest
            if (dest) {
              const pageIndex = await pdf.getPageIndex(dest[0])
              pageNum = pageIndex + 1
            }
          } catch {
            // Signet sans destination résoluble — affiché sans navigation plutôt
            // que de faire échouer tout le sommaire pour une entrée.
          }
          return { title: item.title, pageNumber: pageNum }
        }),
      )
      setOutline(entries)
    } catch {
      setOutline([])
    }
  }

  if (isLoading && !pdfUrl) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-center text-sm text-gray-400">
        Génération de l'aperçu…
      </div>
    )
  }

  if (!pdfUrl) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-center text-sm text-gray-400">
        Le document apparaîtra ici au fur et à mesure de tes réponses.
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-gray-200 px-4 py-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={pageNumber <= 1}
            onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
            title="Page précédente"
            className="rounded border border-gray-300 p-1 text-gray-600 hover:border-gray-400 hover:bg-gray-50 disabled:opacity-40"
          >
            <Icon path={ICON_CHEVRON_LEFT} className="h-3.5 w-3.5" />
          </button>
          <span className="text-xs text-gray-600">
            Page {pageNumber} / {numPages || "…"}
          </span>
          <button
            type="button"
            disabled={pageNumber >= numPages}
            onClick={() => setPageNumber((p) => Math.min(numPages, p + 1))}
            title="Page suivante"
            className="rounded border border-gray-300 p-1 text-gray-600 hover:border-gray-400 hover:bg-gray-50 disabled:opacity-40"
          >
            <Icon path={ICON_CHEVRON_RIGHT} className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={scale <= MIN_SCALE}
            onClick={() => setScale((s) => Math.max(MIN_SCALE, +(s - SCALE_STEP).toFixed(2)))}
            title="Réduire"
            className="rounded border border-gray-300 p-1 text-gray-600 hover:border-gray-400 hover:bg-gray-50 disabled:opacity-40"
          >
            <Icon path={ICON_MINUS} className="h-3.5 w-3.5" />
          </button>
          <span className="text-xs text-gray-600">{Math.round(scale * 100)}%</span>
          <button
            type="button"
            disabled={scale >= MAX_SCALE}
            onClick={() => setScale((s) => Math.min(MAX_SCALE, +(s + SCALE_STEP).toFixed(2)))}
            title="Agrandir"
            className="rounded border border-gray-300 p-1 text-gray-600 hover:border-gray-400 hover:bg-gray-50 disabled:opacity-40"
          >
            <Icon path={ICON_PLUS} className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {outline.length > 0 && sidebarOpen && (
          <nav className="w-48 shrink-0 overflow-y-auto border-r border-gray-200 p-3">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Sommaire</p>
              <button
                type="button"
                onClick={() => setSidebarOpen(false)}
                title="Fermer le sommaire"
                className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              >
                <Icon path={ICON_CHEVRON_LEFT} className="h-3.5 w-3.5" />
              </button>
            </div>
            <ul className="flex flex-col gap-1">
              {outline.map((entry, index) => (
                <li key={`${entry.title}-${index}`}>
                  <button
                    type="button"
                    disabled={entry.pageNumber === null}
                    onClick={() => entry.pageNumber && setPageNumber(entry.pageNumber)}
                    className={`w-full rounded px-2 py-1 text-left text-xs ${
                      entry.pageNumber === pageNumber
                        ? "bg-indigo-50 text-indigo-700"
                        : "text-gray-600 hover:bg-gray-50"
                    } disabled:cursor-not-allowed disabled:opacity-40`}
                  >
                    {entry.title}
                  </button>
                </li>
              ))}
            </ul>
          </nav>
        )}
        {outline.length > 0 && !sidebarOpen && (
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            title="Ouvrir le sommaire"
            className="flex shrink-0 items-center border-r border-gray-200 px-1.5 text-gray-400 hover:bg-gray-50 hover:text-gray-600"
          >
            <Icon path={ICON_CHEVRON_RIGHT} className="h-3.5 w-3.5" />
          </button>
        )}

        <div className="flex-1 overflow-auto bg-gray-100 p-4">
          {loadError ? (
            <p className="text-sm text-red-600">{loadError}</p>
          ) : (
            <Document
              file={pdfUrl}
              onLoadSuccess={handleLoadSuccess}
              onLoadError={() => setLoadError("Impossible d'afficher l'aperçu du document.")}
              loading={<p className="text-sm text-gray-400">Chargement du PDF…</p>}
            >
              <Page pageNumber={pageNumber} scale={scale} />
            </Document>
          )}
        </div>
      </div>
    </div>
  )
}
