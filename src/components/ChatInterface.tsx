import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Sparkles, ThumbsUp, ThumbsDown, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { sendMessageToGemini, resetChat } from "@/lib/gemini";

interface Message {
  id: number;
  role: "user" | "ai";
  content: string;
  isError?: boolean;
}

const quickActions = [
  "How much did I spend in total?",
  "What's my highest transaction?",
  "Show my top merchants",
  "How many transactions do I have?",
];

const initialMessages: Message[] = [
  {
    id: 1,
    role: "ai",
    content:
      "Hi! I'm **FinSight AI**, your financial data assistant. Upload a document and I'll answer questions based on your **actual transaction data**. What would you like to know?",
  },
];

const ChatInterface = ({ compact = false }: { compact?: boolean }) => {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  // Reset chat session when component mounts
  useEffect(() => {
    resetChat();
  }, []);

  const sendMessage = async (text: string) => {
    if (!text.trim() || isTyping) return;

    const userMsg: Message = { id: Date.now(), role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);

    try {
      const response = await sendMessageToGemini(text);
      const aiMsg: Message = {
        id: Date.now() + 1,
        role: "ai",
        content: response,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (error) {
      const errorMsg: Message = {
        id: Date.now() + 1,
        role: "ai",
        content:
          error instanceof Error
            ? `⚠️ ${error.message}`
            : "⚠️ Something went wrong. Please try again.",
        isError: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className={`flex flex-col bg-card rounded-xl shadow-soft border border-border overflow-hidden ${compact ? "h-[400px]" : "h-full"}`}>
      {/* Header */}
      <div className="flex items-center gap-2 px-5 py-3 border-b border-border">
        <div className="w-7 h-7 rounded-lg gradient-primary flex items-center justify-center">
          <Sparkles className="w-3.5 h-3.5 text-primary-foreground" />
        </div>
        <div>
          <p className="text-sm font-semibold text-foreground">FinSight AI</p>
          <p className="text-[10px] text-muted-foreground">Powered by Gemini · Your financial assistant</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <AnimatePresence>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${msg.role === "user"
                  ? "gradient-primary text-primary-foreground rounded-br-md"
                  : msg.isError
                    ? "bg-destructive/10 text-destructive border border-destructive/20 rounded-bl-md"
                    : "bg-secondary text-secondary-foreground rounded-bl-md"
                  }`}
              >
                {msg.isError && (
                  <div className="flex items-center gap-1.5 mb-1">
                    <AlertCircle className="w-3.5 h-3.5" />
                    <span className="text-xs font-medium">Error</span>
                  </div>
                )}
                <p dangerouslySetInnerHTML={{ __html: msg.content.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>") }} />
                {msg.role === "ai" && !msg.isError && (
                  <div className="flex items-center gap-2 mt-2">
                    <button className="opacity-40 hover:opacity-100 transition-opacity">
                      <ThumbsUp className="w-3 h-3" />
                    </button>
                    <button className="opacity-40 hover:opacity-100 transition-opacity">
                      <ThumbsDown className="w-3 h-3" />
                    </button>
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {isTyping && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-1.5 px-4 py-3">
            <span className="w-2 h-2 rounded-full bg-muted-foreground/40 animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="w-2 h-2 rounded-full bg-muted-foreground/40 animate-bounce" style={{ animationDelay: "150ms" }} />
            <span className="w-2 h-2 rounded-full bg-muted-foreground/40 animate-bounce" style={{ animationDelay: "300ms" }} />
          </motion.div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick actions */}
      {messages.length <= 1 && (
        <div className="px-4 pb-2 flex flex-wrap gap-2">
          {quickActions.map((action) => (
            <button
              key={action}
              onClick={() => sendMessage(action)}
              className="text-xs px-3 py-1.5 rounded-full border border-border text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
            >
              {action}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="p-3 border-t border-border">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage(input);
          }}
          className="flex items-center gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your finances..."
            disabled={isTyping}
            className="flex-1 bg-secondary rounded-xl px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground outline-none focus:ring-2 focus:ring-primary/20 transition-shadow disabled:opacity-50"
          />
          <Button
            type="submit"
            size="icon"
            disabled={!input.trim() || isTyping}
            className="rounded-xl gradient-primary text-primary-foreground h-10 w-10 shrink-0"
          >
            <Send className="w-4 h-4" />
          </Button>
        </form>
      </div>
    </div>
  );
};

export default ChatInterface;
