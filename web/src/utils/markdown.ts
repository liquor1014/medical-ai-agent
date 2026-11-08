import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true
})

export function renderMarkdown(text: string): string {
  if (!text) return ''
  return DOMPurify.sanitize(md.render(text))
}
