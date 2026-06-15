"use client";

import { EvalEvidencePanel } from "./admin-profiles/EvalEvidencePanel";
import { GovernanceOpsPanel } from "./admin-profiles/GovernanceOpsPanel";
import { QueryMiningPanel } from "./admin-profiles/QueryMiningPanel";
import { TuningLabPanel } from "./admin-profiles/TuningLabPanel";
import { TuningWorkspaceProvider, useTuningWorkspace } from "./admin-profiles/tuning-workspace-context";

function ProfilesWorkspace() {
  const { error } = useTuningWorkspace();
  return (
    <div className="admin-route-page">
      <div className="section-head">
              <div>
                <p className="admin-route-eyebrow">Governed Tuning</p>
                <h1>Model Tuning &amp; Experimentation</h1>
                <p>Compare a governed sandbox candidate against the production live configuration without mutating runtime active profiles.</p>
              </div>
            </div>

            {error ? <div className="error-banner">{error}</div> : null}
      <TuningLabPanel />
      <EvalEvidencePanel />
      <GovernanceOpsPanel />
      <QueryMiningPanel />
    </div>
  );
}

export function ProfilesAdminPanel() {
  return (
    <TuningWorkspaceProvider>
      <ProfilesWorkspace />
    </TuningWorkspaceProvider>
  );
}
