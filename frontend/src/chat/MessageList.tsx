// MessageList is now rendered directly inside ChatPanel.
// This file re-exports the Message interface for any future consumers.

export interface Message {
  id: string;
  role: "user" | "agent";
  content: string;
  toolsFired?: string[];
  runId?: string;
  timestamp: string;
}
