import { Link, useLocation } from "react-router-dom";
import {
  Upload,
  LayoutDashboard,
  MessageSquare,
  BarChart3,
  Receipt,
} from "lucide-react";

const items = [
  { icon: Upload, label: "Upload", path: "/" },
  { icon: LayoutDashboard, label: "Home", path: "/dashboard" },
  { icon: Receipt, label: "History", path: "/transactions" },
  { icon: MessageSquare, label: "Chat", path: "/chat" },
  { icon: BarChart3, label: "Analytics", path: "/analytics" },
];

const MobileNav = () => {
  const location = useLocation();
  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 glass border-t border-border">
      <div className="flex items-center justify-around h-16 px-2">
        {items.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex flex-col items-center gap-1 py-1 px-3 rounded-lg transition-colors ${
                isActive ? "text-primary" : "text-muted-foreground"
              }`}
            >
              <item.icon className="w-5 h-5" />
              <span className="text-[10px] font-medium">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
};

export default MobileNav;
