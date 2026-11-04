import { useMutation } from '@tanstack/react-query'
import { sendChatMessage } from '../api/chatbot'
import type { ChatRequestPayload, ChatResponse } from '../api/chatbot'

export function useChatbot(workspaceId: string) {
  return useMutation<ChatResponse, Error, ChatRequestPayload>({
    mutationFn: (payload) => sendChatMessage(workspaceId, payload),
  })
}

