import { Outlet } from "react-router-dom";
import AppSidebar from "./AppSidebar";
import MobileNav from "./MobileNav";

const Layout = () => {
  return (
    <div className="flex min-h-screen bg-background">
      <AppSidebar />
      <main className="flex-1 min-h-screen pb-20 md:pb-0">
        <Outlet />
      </main>
      <MobileNav />
    </div>
  );
};

export default Layout;
