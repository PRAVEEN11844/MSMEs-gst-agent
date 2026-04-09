import ChatInterface from "@/components/ChatInterface";

const Chat = () => {
  return (
    <div className="h-screen flex flex-col p-4 md:p-6 max-w-3xl mx-auto">
      <div className="mb-4">
        <h1 className="text-xl font-bold text-foreground">AI Assistant</h1>
        <p className="text-sm text-muted-foreground">Ask anything about your financial data</p>
      </div>
      <div className="flex-1 min-h-0">
        <ChatInterface />
      </div>
    </div>
  );
};

export default Chat;
