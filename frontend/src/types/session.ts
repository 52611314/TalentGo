export type TargetRole = 'frontend' | 'backend'
export type ExperienceLevel = 'beginner' | 'intern' | 'graduate'
export interface Profile {
  id: string; user_id: string; target_role: TargetRole | null
  experience_level: ExperienceLevel | null; tech_stack: string[]
  background: string; goals: string; feedback_style: 'concise' | 'detailed' | 'guided'
  allow_inferred_memory: boolean; version: number; memory_revision: number; updated_at: string
}
export type ProfileInput = Omit<Profile, 'id' | 'user_id' | 'version' | 'memory_revision' | 'updated_at'>
