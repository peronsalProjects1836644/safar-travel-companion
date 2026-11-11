import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/AuthProvider";
import Layout from "./components/Layout";
import { Skeleton } from "./components/ui";

// Pages load on demand so the first screen stays small and fast.
const Home = lazy(() => import("./pages/Home"));
const Explore = lazy(() => import("./pages/Explore"));
const PlaceDetail = lazy(() => import("./pages/PlaceDetail"));
const Plan = lazy(() => import("./pages/Plan"));
const Trips = lazy(() => import("./pages/Trips"));
const TripDetail = lazy(() => import("./pages/TripDetail"));
const Live = lazy(() => import("./pages/Live"));
const Safety = lazy(() => import("./pages/Safety"));
const Profile = lazy(() => import("./pages/Profile"));
const Admin = lazy(() => import("./pages/Admin"));
const Auth = lazy(() => import("./pages/Auth"));
const SharePage = lazy(() => import("./pages/SharePage"));
const NotFound = lazy(() => import("./pages/NotFound"));

function Fallback() {
  return (
    <div className="mx-auto max-w-7xl space-y-4 px-4 py-8 md:px-8" aria-busy>
      <Skeleton className="h-10 w-64" />
      <Skeleton className="h-52 w-full rounded-3xl" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((i) => <Skeleton key={i} className="h-60 rounded-3xl" />)}
      </div>
    </div>
  );
}

export function RequireAuth({ children, admin }: { children: ReactNode; admin?: boolean }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <Fallback />;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  if (admin && user.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Suspense fallback={<Fallback />}>
      <Routes>
        <Route path="/login" element={<Auth mode="login" />} />
        <Route path="/register" element={<Auth mode="register" />} />
        <Route path="/s/:token" element={<SharePage />} />
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="explore" element={<Explore />} />
          <Route path="places/:id" element={<PlaceDetail />} />
          <Route path="plan" element={<RequireAuth><Plan /></RequireAuth>} />
          <Route path="trips" element={<RequireAuth><Trips /></RequireAuth>} />
          <Route path="trips/:id" element={<RequireAuth><TripDetail /></RequireAuth>} />
          <Route path="live" element={<RequireAuth><Live /></RequireAuth>} />
          <Route path="safety" element={<Safety />} />
          <Route path="profile" element={<RequireAuth><Profile /></RequireAuth>} />
          <Route path="admin" element={<RequireAuth admin><Admin /></RequireAuth>} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
