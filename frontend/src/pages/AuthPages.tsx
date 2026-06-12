import { Eye, EyeOff } from "lucide-react";
import { motion } from "motion/react";
import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { useAuth } from "../lib/auth";

// ---------------------------------------------------------------------------
// Dark-mode inputs
// ---------------------------------------------------------------------------

function DarkTextField({
  label,
  type = "text",
  value,
  onChange,
  autoComplete,
  required,
  placeholder
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  required?: boolean;
  placeholder?: string;
}) {
  return (
    <label className="grid gap-1.5 text-sm font-semibold text-white/70">
      {label}
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        required={required}
        placeholder={placeholder}
        className="auth-input"
      />
    </label>
  );
}

function DarkPasswordField({
  label,
  value,
  onChange,
  autoComplete,
  required,
  hint
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  required?: boolean;
  hint?: string;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <label className="grid gap-1.5 text-sm font-semibold text-white/70">
      {label}
      <div className="relative">
        <input
          type={visible ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          required={required}
          minLength={8}
          className="auth-input pr-11"
        />
        <button
          type="button"
          tabIndex={-1}
          onClick={() => setVisible((v) => !v)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 transition hover:text-white/70"
          aria-label={visible ? "Hide password" : "Show password"}
        >
          {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
      {hint ? <span className="text-xs font-normal text-white/35">{hint}</span> : null}
    </label>
  );
}

// ---------------------------------------------------------------------------
// Shared auth frame — dark, animated
// ---------------------------------------------------------------------------

function AuthFrame({
  title,
  subtitle,
  children
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="relative min-h-screen overflow-hidden text-white"
      style={{ background: "#060611" }}
    >
      {/* Animated gradient orbs */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-[20%] -left-[10%] h-[520px] w-[520px] rounded-full bg-violet-600/25 blur-[130px] animate-float-slow" />
        <div
          className="absolute top-[25%] -right-[8%] h-[420px] w-[420px] rounded-full bg-purple-700/20 blur-[110px] animate-float-medium"
          style={{ animationDelay: "-2s" }}
        />
        <div
          className="absolute -bottom-[15%] left-[30%] h-[320px] w-[320px] rounded-full bg-cyan-600/10 blur-[90px] animate-float-slow"
          style={{ animationDelay: "-4s" }}
        />
      </div>

      {/* Dot-grid overlay */}
      <div className="auth-dot-grid pointer-events-none absolute inset-0 opacity-50" />

      {/* Horizontal scan line — very subtle */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-violet-500/40 to-transparent" />

      {/* Content grid */}
      <div className="relative z-10 mx-auto grid min-h-screen max-w-6xl items-center gap-10 px-4 py-10 lg:grid-cols-[1fr_420px]">

        {/* Hero column — desktop only */}
        <section className="hidden lg:block pr-8">
          {/* Eyebrow pill */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.05, duration: 0.4 }}
            className="mb-7 inline-flex items-center gap-2 rounded-full border border-violet-500/25 bg-violet-500/10 px-3.5 py-1.5 text-xs font-bold uppercase tracking-widest text-violet-300"
          >
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400" />
            Open-source extraction console
          </motion.div>

          {/* Gradient heading */}
          <motion.h1
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.45 }}
            className="text-[3.25rem] font-black leading-[1.08] tracking-tight"
          >
            <span className="text-white">AI extraction</span>
            <br />
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(135deg, #A78BFA 0%, #818CF8 40%, #67E8F9 100%)"
              }}
            >
              without limits.
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.18, duration: 0.4 }}
            className="mt-5 max-w-sm text-[0.95rem] leading-7 text-white/45"
          >
            BYOK-powered scraping console. Connect your LLM, configure
            extraction fields, and pull structured data from any site.
          </motion.p>

          {/* Mock terminal */}
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.28, duration: 0.45 }}
            className="mt-9 max-w-sm overflow-hidden rounded-xl border border-white/[0.07] bg-black/50 backdrop-blur-sm"
            style={{
              boxShadow:
                "0 0 0 1px rgba(124,58,237,0.12), 0 20px 40px rgba(0,0,0,0.5)"
            }}
          >
            {/* Terminal title bar */}
            <div className="flex items-center gap-2 border-b border-white/[0.06] bg-white/[0.03] px-4 py-3">
              <div className="h-2.5 w-2.5 rounded-full bg-red-500/55" />
              <div className="h-2.5 w-2.5 rounded-full bg-yellow-500/55" />
              <div className="h-2.5 w-2.5 rounded-full bg-emerald-500/55" />
              <span className="ml-2 text-[11px] text-white/20 font-mono">
                scrapegpt — console
              </span>
            </div>

            {/* Terminal body */}
            <div className="space-y-2 px-5 py-4 font-mono text-xs">
              <p>
                <span className="text-violet-400">$</span>{" "}
                <span className="text-white/65">scrapegpt analyze</span>{" "}
                <span className="text-cyan-400/70">https://arxiv.org/abs/2301.00001</span>
              </p>
              <p className="text-white/30 pl-3">
                <span className="text-violet-500/70">›</span> Fetching &amp; rendering page...
              </p>
              <p className="text-white/30 pl-3">
                <span className="text-violet-500/70">›</span> AI identifying extractable fields...
              </p>
              <p className="pl-3">
                <span className="text-emerald-400">✓</span>{" "}
                <span className="text-white/60">8 fields detected</span>{" "}
                <span className="text-violet-300/80">— 94% confidence</span>
              </p>
              <p className="text-white/30 pl-3">
                <span className="text-violet-500/70">›</span> title, authors, abstract, date, doi...
              </p>
              <p className="pl-3">
                <span className="text-emerald-400">✓</span>{" "}
                <span className="text-white/60">Spec ready. Run extract to begin.</span>
              </p>
              <p className="mt-1 flex items-center gap-1">
                <span className="text-violet-400">$</span>{" "}
                <span className="inline-block h-3.5 w-0.5 bg-violet-400 animate-pulse" />
              </p>
            </div>
          </motion.div>

          {/* Feature pills */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.45 }}
            className="mt-7 flex flex-wrap gap-2"
          >
            {["BYOK", "No credits", "Self-hosted", "Open-source"].map((tag) => (
              <span
                key={tag}
                className="rounded-full border border-white/[0.08] bg-white/[0.04] px-3 py-1 text-xs font-semibold text-white/40"
              >
                {tag}
              </span>
            ))}
          </motion.div>
        </section>

        {/* Form card — glassmorphism */}
        <motion.section
          initial={{ opacity: 0, y: 28, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="rounded-2xl border border-white/[0.07] bg-white/[0.04] p-8 backdrop-blur-2xl"
          style={{
            boxShadow:
              "0 0 0 1px rgba(124,58,237,0.1), 0 0 60px rgba(124,58,237,0.14), 0 0 120px rgba(124,58,237,0.07), 0 30px 60px rgba(0,0,0,0.55)"
          }}
        >
          {/* Logo + title */}
          <div className="mb-8">
            <div className="mb-5 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-violet-600 shadow-lg shadow-violet-900/50">
              <svg
                className="h-5 w-5 text-white"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18" />
              </svg>
            </div>
            <h2 className="text-2xl font-black text-white">{title}</h2>
            <p className="mt-1 text-sm text-white/38">{subtitle}</p>
          </div>
          {children}
        </motion.section>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Login
// ---------------------------------------------------------------------------

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthFrame
      title="Welcome back"
      subtitle="Sign in to your extraction console."
    >
      <form className="grid gap-4" onSubmit={onSubmit}>
        {error ? <Alert tone="danger">{error}</Alert> : null}

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.32 }}
        >
          <DarkTextField
            label="Email"
            type="email"
            value={email}
            onChange={setEmail}
            autoComplete="email"
            required
            placeholder="you@example.com"
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.27, duration: 0.32 }}
          className="grid gap-1.5"
        >
          <DarkPasswordField
            label="Password"
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
            required
          />
          <div className="text-right">
            <span className="text-xs text-white/25">
              Forgot password?{" "}
              <span className="cursor-default font-semibold text-violet-400/50">
                Recovery not yet available
              </span>
            </span>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.34, duration: 0.32 }}
          whileTap={{ scale: 0.97 }}
        >
          <Button
            type="submit"
            className="mt-1 h-11 w-full rounded-xl text-base shadow-lg shadow-violet-900/40"
            disabled={submitting}
          >
            {submitting ? "Signing in…" : "Sign in"}
          </Button>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.42 }}
          className="text-center text-sm text-white/30"
        >
          New here?{" "}
          <Link className="font-semibold text-violet-400 hover:text-violet-300" to="/register">
            Create an account
          </Link>
        </motion.p>
      </form>
    </AuthFrame>
  );
}

// ---------------------------------------------------------------------------
// Register
// ---------------------------------------------------------------------------

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await register(email, password);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthFrame
      title="Create account"
      subtitle="Start with providers and extraction in minutes."
    >
      <form className="grid gap-4" onSubmit={onSubmit}>
        {error ? <Alert tone="danger">{error}</Alert> : null}

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.32 }}
        >
          <DarkTextField
            label="Email"
            type="email"
            value={email}
            onChange={setEmail}
            autoComplete="email"
            required
            placeholder="you@example.com"
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.27, duration: 0.32 }}
        >
          <DarkPasswordField
            label="Password"
            value={password}
            onChange={setPassword}
            autoComplete="new-password"
            required
            hint="Minimum 8 characters."
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.34, duration: 0.32 }}
        >
          <DarkPasswordField
            label="Confirm password"
            value={confirm}
            onChange={setConfirm}
            autoComplete="new-password"
            required
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.41, duration: 0.32 }}
          whileTap={{ scale: 0.97 }}
        >
          <Button
            type="submit"
            className="mt-1 h-11 w-full rounded-xl text-base shadow-lg shadow-violet-900/40"
            disabled={submitting}
          >
            {submitting ? "Creating…" : "Create account"}
          </Button>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.49 }}
          className="text-center text-sm text-white/30"
        >
          Already have access?{" "}
          <Link className="font-semibold text-violet-400 hover:text-violet-300" to="/login">
            Sign in
          </Link>
        </motion.p>
      </form>
    </AuthFrame>
  );
}
