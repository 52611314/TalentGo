export type TargetRole = 'frontend' | 'backend'
export type ExperienceLevel = 'beginner' | 'intern' | 'graduate'
export interface Profile {
  id: string; user_id: string; target_role: TargetRole | null
  experience_level: ExperienceLevel | null; tech_stack: string[]
  background: string; goals: string; feedback_style: 'concise' | 'detailed' | 'guided'
  allow_inferred_memory: boolean; version: number; memory_revision: number; updated_at: string
}
export type ProfileInput = Omit<Profile, 'id' | 'user_id' | 'version' | 'memory_revision' | 'updated_at'>

export type InterviewMode = 'technical' | 'behavioral' | 'pressure'
export interface SessionConfig {
  question_count: number; difficulty: number; max_followups: number
  pressure_level: number; pressure_consent: boolean
}
export interface Coverage { planned: number; asked: number; answered: number; skipped: number; not_reached: number; scored: number }
export interface Operation {
  id: string; session_id: string; kind: string; status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  attempt_no: number; last_event_seq: number; cancel_requested: boolean; error_code: string | null
  retryable: boolean; result_refs: Record<string, unknown>
}
export interface InterviewSession {
  id: string; title: string; role: TargetRole | null; mode: InterviewMode | null
  status: 'clarifying' | 'ready' | 'interviewing' | 'paused' | 'evaluating' | 'completed' | 'aborted'
  config: SessionConfig; version: number; is_mock: boolean; created_at: string
  current_question: { id: string; ordinal: number; topic: string; content: string; followup_count: number } | null
  active_operation_id: string | null; latest_operation: Operation | null; coverage: Coverage
}
export interface InterviewMessage {
  id: string; seq: number; speaker: 'user' | 'assistant' | 'system'; kind: string; content: string
  question_id: string | null; operation_id: string | null; created_at: string
}
export interface Page<T> { items: T[]; next_cursor: string | null }
export interface MockReport {
  id?: string; session_id?: string; status: string; is_mock: boolean; total_score: null
  coverage: Coverage; summary?: string; messages?: InterviewMessage[]; dimension_scores?: Record<string, number>
}
export const STATUS_LABELS: Record<InterviewSession['status'], string> = {
  clarifying: '确认目标', ready: '准备开始', interviewing: '练习中', paused: '已暂停',
  evaluating: '整理总结', completed: '已完成', aborted: '已取消',
}
export const MODE_LABELS = { technical: '技术面试', behavioral: '行为面试', pressure: '压力面试' }
