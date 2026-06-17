export interface ChatSession {
  id: string;
  title: string;
  pipeline: string;
}

export interface ChatMessage {
  id?: string;
  role: string;
  content: string;
  citations?: any[];
}