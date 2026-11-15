export interface Envelope<T> { data: T; request_id: string }
export interface Identity { user_id: string; username: string; display_name: string; token: string; expires_at: string }
export interface Health { status: string; milestone: string; port?: number; schema_revision?: string }
