"use client";

import { MaterialIcon } from "@/components/icons";
import { useState } from "react";

import { browserApiUrl } from "@/lib/api-browser";

export function LogoutButton() {
  const [loading, setLoading] = useState(false);

  function handleLogout() {
    setLoading(true);
    window.location.assign(browserApiUrl("/auth/logout"));
  }

  return (
    <button className="stitch-button stitch-button-secondary stitch-button-block" type="button" onClick={handleLogout} disabled={loading}>
      <MaterialIcon name="logout" />
      {loading ? "Logging Out..." : "Log Out"}
    </button>
  );
}
