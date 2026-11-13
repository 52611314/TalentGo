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
  provider: 'mock' | 'deepseek'; model_name: string | null; rubric_version: string | null; prompt_version: string | null
  current_question: { id: string; ordinal: number; topic: string; content: string; followup_count: number; difficulty: number; hint_used: boolean } | null
  active_operation_id: string | null; latest_operation: Operation | null; coverage: Coverage
}
export interface InterviewMessage {
  id: string; seq: number; speaker: 'user' | 'assistant' | 'system'; kind: string; content: string
  question_id: string | null; operation_id: string | null; created_at: string
}
export interface Page<T> { items: T[]; next_cursor: string | null }
export interface InterviewReport {
  id?: string; session_id?: string; status: string; is_mock: boolean; total_score: number | null
  coverage: Coverage; summary?: string; messages?: InterviewMessage[]; dimension_scores?: Record<string, number | null>
  weights?: Record<string, number>; model_name?: string; rubric_version?: string; prompt_version?: string
  strengths?: ReviewItem[]; gaps?: ReviewItem[]; recommendations?: ReviewItem[]; question_evaluations?: QuestionEvaluation[]
}
export interface ReviewItem { text: string; question_ids: string[] }
export interface QuestionEvaluation {
  id: string; question_id: string; question: string; ordinal: number; topic: string; hint_used: boolean
  question_score: number | null; missing_points: string[]; suggestion: string
  dimensions: Record<string, { score: number | null; reason: string; evidence: { message_id: string; quote: string }[] }>
}
export interface SkillTrace { id: string; skill_key: string; skill_version: string; phase: string; status: string; model_name: string; attempt_no: number; error_code: string | null; usage: { input_tokens: number | null; output_tokens: number | null; latency_ms: number | null; attempts: number | null } }
export interface ModelStatus { default_provider: 'mock' | 'deepseek'; providers: { id: string; available: boolean; model: string | null; description: string }[] }
export const DIMENSION_LABELS: Record<string, string> = { relevance: '切题程度', accuracy_consistency: '准确与一致性', reasoning: '分析与推理', evidence_detail: '证据与细节', communication: '表达沟通' }
export const STATUS_LABELS: Record<InterviewSession['status'], string> = {
  clarifying: '确认目标', ready: '准备开始', interviewing: '练习中', paused: '已暂停',
  evaluating: '整理总结', completed: '已完成', aborted: '已取消',
}
export const MODE_LABELS = { technical: '技术面试', behavioral: '行为面试', pressure: '压力面试' }
