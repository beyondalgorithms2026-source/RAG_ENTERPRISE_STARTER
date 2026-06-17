import Link from "next/link";

export default function AccessDeniedPage() {
  return (
    <main className="login-shell">
      <div className="login-layout login-layout-compact">
        <section className="login-card">
          <div className="login-card-head">
            <h1>Access Denied</h1>
            <p>This area is reserved for operators with the admin or approver role.</p>
          </div>
          <Link href="/console/workspace/chat" className="stitch-button stitch-button-primary stitch-button-block">
            Go To Workspace
          </Link>
        </section>
      </div>
    </main>
  );
}
