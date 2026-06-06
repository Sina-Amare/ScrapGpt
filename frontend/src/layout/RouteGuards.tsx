import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";

export function ProtectedRoute() {
  const { authenticated, booting } = useAuth();
  const location = useLocation();

  if (booting) {
    return (
      <div className="grid min-h-screen place-items-center bg-porcelain text-sm font-medium text-muted">
        Restoring session...
      </div>
    );
  }

  if (!authenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}

export function PublicRoute() {
  const { authenticated, booting } = useAuth();

  if (booting) {
    return (
      <div className="grid min-h-screen place-items-center bg-porcelain text-sm font-medium text-muted">
        Restoring session...
      </div>
    );
  }

  if (authenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
