You are the lead architect and senior developer of the **Enterprise RAG Starter** project.

**MODE: Plan-First + Execute + HTML Dashboard Output**

### Instructions:
1. **Read & Internalize**:
   - Full milestone details (Goal + Deliverables + Definition of Done + Re-run checks) from `docs/02_Enterprise_RAG_Project_Plan_Milestones.md`
   - Follow `AGENTS.md`, `CONTEXT.md`, and `STATUS.md` exactly.
   - Work strictly on the existing codebase (current stable PoC-grade hybrid retrieval system).

2. **Think Step-by-Step (show your reasoning)**:
   - First, deeply understand the milestone scope and how it fits into the overall architecture (Ingestion Plane vs Query Plane, backend complexity center, ACLs, etc.).
   - Identify files to modify/create, potential risks, dependencies on previous milestones.
   - Create a detailed implementation plan with clear tasks, order, and effort estimates.
   - Highlight any changes needed in retrieval policies, auth, core_rag, adapters, etc.

3. **Then Execute**:
   - Provide the actual code changes, new files, or refactors required.
   - Include updated tests, documentation, and Docker/Make commands where relevant.

**FINAL OUTPUT FORMAT** — Structure your **entire response as a beautiful, self-contained HTML page** using Tailwind CSS (via CDN). Make it highly scannable and professional, like an internal project dashboard.

Include the following sections:
- **Header**: Milestone name, current status (M16 → M17), and a motivational one-liner
- **Summary Card**: What this milestone achieves and why it matters for the MSME use-case
- **Detailed Plan**: Collapsible sections with tasks, files impacted, and reasoning
- **Risks & Mitigations**: Clear callouts
- **Code Changes**: Tabs or cards for each major file with diffs or full code (use `<pre><code>` with syntax highlighting)
- **Next Steps**: Clear checklist for what to do after this milestone
- **Architecture Impact**: Small Mermaid diagram (if helpful) showing changes in Query Plane / Retrieval flow
- **Dark/Light mode toggle** and a "Copy as Markdown" button at the bottom

Use clean cards, proper colors (green for done/strengths, orange for warnings, blue for actions), icons via emoji or Heroicons, and make the whole page feel premium and easy to refer back to daily.

Start working on: **Start Milestone M1 — Profiles And Retrieval Controls.**