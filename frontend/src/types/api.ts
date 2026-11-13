export interface Envelope<T> { data: T; request_id: string }
export interface Identity { user_id: string; display_name: string; token: string }
export interface Health { status: string; milestone: string; port?: number; schema_revision?: string }
