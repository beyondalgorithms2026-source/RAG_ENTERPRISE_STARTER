import { ChatWorkspace } from "@/components/chat-workspace";

export default async function ThreadPage({ params }: { params: Promise<{ thread: string }> }) {
  const { thread } = await params;
  return <ChatWorkspace initialThreadId={thread} />;
}
