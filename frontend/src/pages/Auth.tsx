import { Eye, EyeOff } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { useAuth } from "@/auth/AuthProvider";
import { ContourArt } from "@/components/Art";
import { Logo } from "@/components/Layout";
import { Button, ErrorNote, Field, Input } from "@/components/ui";

const safeNext = (n: string | null) => (n && n.startsWith("/") && !n.startsWith("//") ? n : "/");

export default function Auth({ mode }: { mode: "login" | "register" }) {
  const { user, login, register } = useAuth();
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const next = safeNext(sp.get("next"));
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isLogin = mode === "login";

  if (user) return <Navigate to={next} replace />;

  const problem = (): string | null => {
    if (!isLogin && !name.trim()) return "Enter your name.";
    if (!/^\S+@\S+\.\S+$/.test(email)) return "Enter a valid email address.";
    if (!isLogin && (password.length < 8 || !/[A-Za-z]/.test(password) || !/\d/.test(password))) return "Use at least 8 characters with a letter and a number.";
    if (isLogin && !password) return "Enter your password.";
    return null;
  };
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const p = problem();
    if (p) return setError(p);
    setBusy(true);
    setError(null);
    try {
      if (isLogin) await login(email.trim(), password);
      else await register(name.trim(), email.trim(), password);
      nav(next, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_1.1fr]">
      <div className="flex flex-col justify-center px-6 py-10 sm:px-12 lg:px-20">
        <div className="mb-10"><Logo /></div>
        <h1 className="font-display text-4xl font-semibold">{isLogin ? "Welcome back" : "Create your account"}</h1>
        <p className="mt-2 text-ink-500">{isLogin ? "Sign in to see your trips and continue where you left off." : "Save your trips and get live guidance while you travel."}</p>
        <form onSubmit={submit} className="mt-8 max-w-md space-y-5" noValidate>
          {!isLogin && <Field label="Your name">{(id) => <Input id={id} autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} maxLength={60} />}</Field>}
          <Field label="Email">{(id) => <Input id={id} type="email" inputMode="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
          <Field label="Password" hint={isLogin ? undefined : "At least 8 characters, with a letter and a number."}>
            {(id) => (
              <div className="relative">
                <Input id={id} type={show ? "text" : "password"} autoComplete={isLogin ? "current-password" : "new-password"} value={password} onChange={(e) => setPassword(e.target.value)} className="pr-12" />
                <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"} className="absolute right-3 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-full text-ink-400 hover:bg-mist-100">{show ? <EyeOff size={18} /> : <Eye size={18} />}</button>
              </div>
            )}
          </Field>
          {error && <ErrorNote message={error} />}
          <Button size="lg" className="w-full" loading={busy}>{isLogin ? "Sign in" : "Create account"}</Button>
        </form>
        <p className="mt-6 text-ink-500">
          {isLogin ? "New to Safar? " : "Already have an account? "}
          <Link to={`${isLogin ? "/register" : "/login"}${next !== "/" ? `?next=${encodeURIComponent(next)}` : ""}`} className="font-semibold text-lake-700 hover:underline">{isLogin ? "Create an account" : "Sign in"}</Link>
        </p>
      </div>
      <div className="relative hidden overflow-hidden bg-ink-900 lg:block">
        <div className="absolute inset-0 opacity-70"><ContourArt seed="auth-panel" category="lakes" lines={16} className="mix-blend-soft-light" /></div>
        <div className="absolute inset-0 bg-gradient-to-br from-ink-900/60 to-lake-700/50" />
        <div className="relative flex h-full flex-col justify-end p-14 text-white">
          <p className="max-w-md font-display text-4xl font-semibold leading-tight text-balance">From Lahore's walled city to the Karakoram, with a plan that moves when you do.</p>
        </div>
      </div>
    </div>
  );
}
