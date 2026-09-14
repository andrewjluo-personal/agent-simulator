import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import brief from './content/research_brief.md?raw'

export function ResearchPage({ onBack }: { onBack: () => void }) {
  return (
    <main className="research">
      <button type="button" className="link back-link" onClick={onBack}>
        ← Back to bench
      </button>
      <article className="research-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{brief}</ReactMarkdown>
      </article>
    </main>
  )
}
