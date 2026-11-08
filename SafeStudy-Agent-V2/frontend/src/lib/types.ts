export interface User { id: string; email: string; display_name: string }
export interface Source { chunk_id: string; document_id: string; title: string; topic: string; text: string; score: number }
export interface Msg { id: string; role: "user" | "assistant"; content: string; sources?: Source[] | null; is_safe?: boolean; model?: string | null }
export interface Conversation { id: string; title: string; updated_at: string }
export interface Doc { id: string; title: string; topic: string; filename: string | null; status: string; chunk_count: number; builtin: boolean; created_at: string }
export interface Summary {
  questions: number; conversations: number; grounded_rate: number | null; helpful: number; not_helpful: number;
  topics: { topic: string; questions: number; grounded: number; last: string }[];
  activity: { day: string; questions: number }[];
}
export interface Health { status: string; llm: string; vector_store: string; embeddings: string }
