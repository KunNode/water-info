import { del, get, post, withAuth } from './request'
import type { KnowledgeDocument, KnowledgeDocumentUploadResponse, KnowledgeSearchHit, KnowledgeStats } from '@/types'

export function listKnowledgeDocuments(params?: {
  status?: string
  source_type?: string
  q?: string
  limit?: number
  offset?: number
}) {
  return get<KnowledgeDocument[]>('/kb/documents', params, withAuth())
}

export function getKnowledgeStats() {
  return get<KnowledgeStats>('/kb/stats', undefined, withAuth())
}

export function uploadKnowledgeDocument(file: File, title?: string, sourceUri?: string) {
  const form = new FormData()
  form.append('file', file)
  if (title) form.append('title', title)
  if (sourceUri) form.append('source_uri', sourceUri)
  return post<KnowledgeDocumentUploadResponse>('/kb/documents', form, withAuth())
}

export function deleteKnowledgeDocument(id: string) {
  return del<{ message: string }>(`/kb/documents/${id}`, withAuth())
}

export function reindexKnowledgeDocument(id: string) {
  return post<KnowledgeDocumentUploadResponse>(`/kb/documents/${id}/reindex`, undefined, withAuth())
}

export function searchKnowledge(data: { query: string; topK?: number; sourceTypes?: string[] }) {
  return post<KnowledgeSearchHit[]>(
    '/kb/search',
    {
      query: data.query,
      top_k: data.topK ?? 5,
      source_types: data.sourceTypes,
    },
    withAuth(),
  )
}
