import { motion } from "framer-motion";
import { User, Shield, Bell, Palette } from "lucide-react";

const SettingsPage = () => {
  return (
    <div className="p-4 md:p-6 space-y-6 max-w-2xl mx-auto">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <h1 className="text-xl font-bold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground">Manage your preferences</p>
      </motion.div>

      {[
        { icon: User, title: "Profile", desc: "Name, email, and account details" },
        { icon: Shield, title: "Privacy & Security", desc: "Data handling and export options" },
        { icon: Bell, title: "Notifications", desc: "Reminder and insight alerts" },
        { icon: Palette, title: "Appearance", desc: "Theme and display preferences" },
      ].map((item, i) => (
        <motion.div
          key={item.title}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.1 }}
          className="bg-card rounded-xl p-5 shadow-soft border border-border flex items-center gap-4 cursor-pointer hover:shadow-elevated transition-shadow"
        >
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <item.icon className="w-5 h-5 text-primary" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">{item.title}</p>
            <p className="text-xs text-muted-foreground">{item.desc}</p>
          </div>
        </motion.div>
      ))}
    </div>
  );
};

export default SettingsPage;
