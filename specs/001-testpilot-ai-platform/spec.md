# Feature Specification: TestPilot AI — AI-Powered Web Application Testing Platform

**Feature Branch**: `001-testpilot-ai-platform`

**Created**: 2026-08-05

**Status**: Draft

**Input**: User description: "Build the complete product specification for a production-ready SaaS platform called 'TestPilot AI'. TestPilot AI is an AI-powered web application testing platform that helps QA engineers, developers, and teams test websites and web applications using AI. The goal is to create a real-world, scalable SaaS product rather than a simple demo. Core product vision: allow a user to provide a website URL, analyze the application, generate intelligent test scenarios and test cases, execute automated browser tests, detect failures and UI issues, and provide clear AI-generated reports. Full requirements captured across 22 areas: authentication & user management; SaaS dashboard; project management; AI test case generator; automated browser testing (Playwright-based, extensible); test execution; AI-powered failure analysis; bug/issue management; AI QA assistant; reports & analytics; test case management; notifications; modern UI/UX; security; multi-tenant SaaS architecture; subscription architecture; technology direction (Next.js + TypeScript, Tailwind, FastAPI, PostgreSQL, SQLModel, provider-agnostic LLM layer, Playwright, Docker, Kubernetes-ready); observability; scalability; MVP scope; quality requirements; spec-driven development. Product specification only — no application code at this stage."

**Clarifications resolved during specification**:

1. **Site-under-test credentials**: MVP tests unauthenticated/public pages and flows only. TestPilot never stores or handles login credentials for the website being tested in the MVP; authenticated-flow testing is future scope.
2. **Multi-tenancy timing**: Every signup automatically receives its own single-member Organization, so the data model is multi-tenant and org-scoped from day one. Team invites, multi-member roles, and permission-management UI ship post-MVP on top of this same model.
3. **AI/LLM data handling**: MVP uses cloud LLM providers only, accessed through a provider-agnostic adapter interface. Self-hosted/local LLM support is future scope.

---

## Product Overview

TestPilot AI is a multi-tenant SaaS platform that lets QA engineers, developers, and product
teams point the system at a website URL and receive AI-generated test scenarios, automated
Playwright-driven browser test execution, AI-explained failure analysis, and QA reporting —
without hand-writing automation scripts or manually triaging every failure. It replaces the
slow loop of "write tests → run tests → read raw logs → guess what broke" with an AI-assisted
loop that goes from URL to test coverage to actionable bug reports.

## Problem Statement

Automated web testing today requires either (a) engineering effort to write and maintain
Selenium/Playwright scripts, which many startups, agencies, and small QA teams cannot
consistently staff for, or (b) purely manual QA, which is slow, inconsistent, and does not
scale with release frequency. When automated tests do exist and fail, the output is typically a
stack trace or a screenshot that still requires a human to interpret before anyone can act on
it. Teams need a way to get meaningful test coverage quickly from a URL, and to get failures
explained in language a developer can act on immediately, rather than raw logs.

## Goals

- Let a user go from "here is our website URL" to a first set of AI-generated, reviewable test
  cases in minutes, without writing automation code.
- Execute those test cases as real browser sessions and produce pass/fail results with
  screenshots and logs as evidence.
- Turn every test failure into a plain-language explanation with a likely root cause, severity,
  and suggested fix, not just a stack trace.
- Give teams a single system of record linking test cases, test runs, results, and bugs/issues
  together, with reporting on quality trends over time.
- Operate as a secure, multi-tenant SaaS product from day one: every organization's data is
  isolated, and the architecture is ready for team collaboration and paid subscription tiers
  even where those specific features are not part of the MVP.

## Non-Goals

- **Native mobile app testing** (iOS/Android app automation) is out of scope; TestPilot AI
  tests web applications reachable by URL only.
- **Backend/API contract testing or load/performance testing** is out of scope for this
  specification; TestPilot AI operates at the browser/UI layer.
- **Pixel-level visual regression (image diffing)** is out of scope; UI validation in this
  spec means presence/content/state of elements, not pixel comparison.
- **Authenticated-flow testing** (logging into the site under test) is out of scope for the
  MVP — see Clarifications above. It is explicitly future scope.
- **Full payment/billing processing implementation** is out of scope for this spec; subscription
  *architecture* is required, but wiring a live payment gateway is not.
- **Self-hosted/on-premise deployment of TestPilot itself, or self-hosted LLMs**, are out of
  scope for the MVP; TestPilot is delivered as cloud SaaS using cloud LLM providers.

## User Personas

- **QA Engineer (Priya)** — Primary user. Creates projects, reviews and edits AI-generated test
  cases, runs test suites before releases, triages failures, files bugs. Wants fast coverage
  without writing Playwright scripts by hand.
- **Software Developer (Dev)** — Consumes AI failure analysis and bug reports linked to failing
  tests to reproduce and fix issues quickly. May trigger targeted re-runs after a fix.
- **QA Team Lead / Product Manager (Lee)** — Reviews reports and quality trends across projects,
  monitors pass rates and open bugs, makes ship/no-ship calls informed by dashboard data.
- **Startup Founder / Generalist (Sam)** — Runs a small team without a dedicated QA function;
  relies heavily on AI-generated test cases and AI failure explanations because they lack deep
  test-automation expertise.
- **Agency / Software House Account Handler (Ari)** — Manages testing for multiple client
  websites; needs each client's project data cleanly separated and easy to switch between.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sign up and manage an account (Priority: P1)

A new user creates a TestPilot AI account, verifies/logs in, and can manage their profile and
session securely, including recovering access if they forget their password.

**Why this priority**: Nothing else in the product is reachable without an account. This is the
first-run gate for every other story.

**Independent Test**: Can be fully tested by signing up with an email/password, logging out,
logging back in, and completing a forgot-password flow — independent of any project or test
data existing yet.

**Acceptance Scenarios**:

1. **Given** a new visitor on the sign-up page, **When** they submit a valid email and password,
   **Then** an account and its personal Organization are created and they land in the dashboard
   in a logged-in state.
2. **Given** a registered user on the login page, **When** they submit correct credentials,
   **Then** they are authenticated and redirected to their dashboard with a valid session.
3. **Given** a logged-in user, **When** they request a password reset via "forgot password" with
   their account email, **Then** they receive a reset link/token that lets them set a new
   password and invalidates the old password.
4. **Given** an authenticated user, **When** they choose "log out", **Then** their session is
   terminated and protected pages become inaccessible until they log in again.

---

### User Story 2 - Create a project and configure a website to test (Priority: P1)

A logged-in user creates a project, attaches a target website URL, and configures basic project
settings so the project is ready for AI test generation.

**Why this priority**: A project + URL is the prerequisite input for every AI generation and
test execution capability; there is no value to deliver before this exists.

**Independent Test**: Can be fully tested by creating a project with a URL and viewing it in the
projects list and project detail page, independent of AI generation or test execution being
implemented.

**Acceptance Scenarios**:

1. **Given** a logged-in user on the Projects page, **When** they create a new project with a
   name and a valid website URL, **Then** the project appears in their project list with status
   "Ready" and an empty testing history.
2. **Given** an existing project, **When** the owner edits its name, URL, or settings, **Then**
   the changes are saved and reflected immediately in the project detail view.
3. **Given** an existing project with test history, **When** the owner archives it, **Then** it
   is hidden from the default active-projects view but its history remains accessible and
   nothing is permanently deleted.
4. **Given** a project creation form, **When** the user submits an invalid or unreachable URL
   format, **Then** the system rejects the submission with a clear, specific validation message
   before a project is created.

---

### User Story 3 - Generate AI test cases from a project URL (Priority: P1)

From a configured project, a user triggers AI analysis of the website and receives a set of
generated test scenarios and detailed test cases, which they can review, edit, approve, reject,
or regenerate.

**Why this priority**: This is TestPilot's core differentiator — going from a URL to
ready-to-run test coverage without manual authoring is the primary value proposition.

**Independent Test**: Can be fully tested by triggering generation on a project with a real URL
and confirming a reviewable, editable list of test cases is produced — independent of whether
those test cases have been executed yet.

**Acceptance Scenarios**:

1. **Given** a project with a configured URL, **When** the user requests AI test case
   generation, **Then** the system analyzes reachable public pages and returns a set of test
   cases covering key user flows, each with steps, expected results, a priority, a severity, and
   a plain-language purpose explanation.
2. **Given** a set of AI-generated test cases, **When** the user reviews them, **Then** they can
   edit any field, approve individual cases, reject individual cases, or request regeneration of
   a specific case or the whole batch.
3. **Given** a generation request for a site with mixed flow types, **When** generation
   completes, **Then** the resulting set includes both positive (expected-success) and negative
   (expected-failure/invalid-input) test cases, plus at least one edge case per major flow
   identified.
4. **Given** an in-progress generation request, **When** the AI provider fails or times out,
   **Then** the user sees a clear failure state with the option to retry, and no partial/corrupt
   test cases are silently saved as approved.

---

### User Story 4 - Execute automated browser tests and view results (Priority: P1)

A user selects approved test cases, creates a test run, executes them as real browser sessions,
and monitors pass/fail results with supporting evidence.

**Why this priority**: Generated test cases only create value once they can actually be run
against the live site and produce trustworthy pass/fail evidence.

**Independent Test**: Can be fully tested by selecting one or more approved test cases, starting
a test run, and observing it reach a terminal state (passed/failed/skipped) with logs and
screenshots — independent of AI failure analysis being available yet.

**Acceptance Scenarios**:

1. **Given** one or more approved test cases in a project, **When** the user selects them and
   starts a test run, **Then** the system executes each test case in a real browser session
   against the project URL and records a per-test result.
2. **Given** a running test run, **When** the user views its status, **Then** they see live
   progress (queued/running/passed/failed/skipped counts) that updates as execution proceeds.
3. **Given** a completed test run, **When** the user opens a specific test result, **Then** they
   can see the step-by-step execution log and any screenshots captured during that test,
   including a failure screenshot if the test failed.
4. **Given** a test run containing failed tests, **When** the user chooses to retry failed
   tests, **Then** only the previously failed test cases are re-executed and their results are
   updated without affecting the passed results from the original run.

---

### User Story 5 - Get AI-powered explanation of a test failure (Priority: P1)

When a test fails, the user opens the failure and receives an AI-generated explanation of what
went wrong, a likely root cause, severity, and a suggested fix — instead of raw logs alone.

**Why this priority**: Raw pass/fail plus logs is not enough to make the product feel
"AI-powered" or save real triage time; this is the second core differentiator after test
generation and completes the MVP loop from URL to actionable insight.

**Independent Test**: Can be fully tested by triggering AI analysis on a single failed test
result and confirming a structured explanation is produced — independent of bug/issue tracking
being implemented.

**Acceptance Scenarios**:

1. **Given** a failed test result with logs and a screenshot, **When** the user requests AI
   failure analysis, **Then** the system returns a plain-language explanation of the failure, a
   likely root cause, a severity rating, and a suggested fix.
2. **Given** a failed test result, **When** AI analysis completes, **Then** the analysis
   explicitly references the expected vs. actual behavior observed during that test step.
3. **Given** an AI analysis request, **When** the AI provider errors or returns an unusable
   response, **Then** the user sees a clear failure state distinct from "no failure occurred,"
   with an option to retry analysis.

---

### User Story 6 - Manage a searchable library of test cases (Priority: P2)

A user manages the full set of test cases in a project — AI-generated and manually authored —
through search, filtering, sorting, and tagging.

**Why this priority**: As projects accumulate test cases across multiple generation cycles, the
library becomes unusable without organization; this builds directly on Story 3.

**Independent Test**: Can be fully tested by creating/generating several test cases with varying
priority, severity, status, and tags, then confirming search/filter/sort against those
attributes returns correct subsets.

**Acceptance Scenarios**:

1. **Given** a project with many test cases, **When** the user filters by priority, severity,
   status, or tag, **Then** only matching test cases are shown.
2. **Given** a project's test case list, **When** the user searches by keyword, **Then** test
   cases whose title, description, or steps match the keyword are returned.
3. **Given** the test case list, **When** the user manually creates a new test case, **Then** it
   is saved with a "manual" source alongside AI-generated cases and is fully editable the same
   way.

---

### User Story 7 - Track bugs/issues found by testing (Priority: P2)

A user turns a failed test result into a tracked issue, with severity, priority, status, and
attachments, linked back to the test case and test run that found it.

**Why this priority**: Finding a bug is only useful if it is tracked to resolution; this closes
the loop from AI failure analysis to developer action.

**Independent Test**: Can be fully tested by creating an issue directly from a failed test
result and confirming it appears in an issues list linked to that test case and run,
independent of notifications or reporting being implemented.

**Acceptance Scenarios**:

1. **Given** a failed test result, **When** the user creates an issue from it, **Then** an issue
   is created pre-filled with a title/description, the failure's screenshots/logs attached, and
   links back to the originating test case and test run.
2. **Given** an existing issue, **When** the user updates its status, severity, priority, or
   assignee, **Then** the change is saved and visible in the issue list and detail view.
3. **Given** an issue list, **When** the user filters by status or severity, **Then** only
   matching issues are shown.

---

### User Story 8 - View reports and quality analytics (Priority: P2)

A user views a project's testing health at a glance — pass/fail/skip counts, pass percentage,
coverage, bug severity distribution, and trends over time.

**Why this priority**: Team leads and product owners need a summarized view to make ship
decisions; this depends on test runs and issues already existing (Stories 4 and 7).

**Independent Test**: Can be fully tested by running several test runs and creating a few issues
in a project, then confirming the report screen's aggregate numbers match that underlying data.

**Acceptance Scenarios**:

1. **Given** a project with completed test runs, **When** the user opens its report view,
   **Then** they see total/passed/failed/skipped test counts, pass percentage, and failure
   percentage for a selected time range.
2. **Given** a project with tracked issues, **When** the user views the report, **Then** they
   see issue counts broken down by severity.
3. **Given** multiple test runs over time, **When** the user views the trend view, **Then** they
   see pass-rate trend across runs, reflecting whether quality is improving or regressing.

---

### User Story 9 - Receive notifications about test activity (Priority: P2)

A user is notified in-app when relevant testing events occur, so they don't have to keep a
dashboard open to know when something needs attention.

**Why this priority**: Once test runs and AI analysis take real time to complete (Stories 4-5),
users need to know when to come back without polling.

**Independent Test**: Can be fully tested by completing a test run and a failure analysis and
confirming corresponding notifications are created and marked read/unread correctly.

**Acceptance Scenarios**:

1. **Given** a test run reaches a terminal state, **When** it finishes, **Then** the initiating
   user receives a notification indicating success or failure counts.
2. **Given** a test run contains a critical-severity failure, **When** that failure is detected,
   **Then** a distinctly flagged critical-issue notification is created in addition to the
   run-completion notification.
3. **Given** unread notifications, **When** the user opens the notification center, **Then**
   they can view, mark as read, and navigate directly to the related test run, result, or issue.

---

### User Story 10 - Ask the AI QA Assistant about project quality (Priority: P3)

A user asks natural-language questions about their project's testing state — coverage, recent
failures, open bugs, QA strategy suggestions — and gets answers grounded in that project's
actual data.

**Why this priority**: High-value but not required for the core "URL to tested and reported"
loop; it is a productivity layer on top of data already produced by Stories 2-8.

**Independent Test**: Can be fully tested by asking the assistant a question about an existing
project's test runs/issues and confirming the answer reflects that project's actual current
data, not generic text.

**Acceptance Scenarios**:

1. **Given** a project with test runs and issues, **When** the user asks the assistant about
   current failure trends, **Then** the response reflects that project's actual recent test and
   issue data.
2. **Given** a question outside what project data can answer (e.g. general QA strategy advice),
   **When** the user asks it, **Then** the assistant gives a helpful general answer while making
   clear it is not derived from project-specific data.
3. **Given** an assistant conversation, **When** the underlying AI provider is unavailable,
   **Then** the user sees a clear error state rather than a hallucinated or silently wrong
   answer.

---

### User Story 11 - Invite teammates into an Organization (Priority: P3)

An Organization owner invites teammates to collaborate on the same set of projects, assigning
each member a role that governs what they can do.

**Why this priority**: The MVP already isolates data per Organization (every signup gets one),
but multi-member collaboration is additive value layered on top, not required for a single user
to get full value from Stories 1-9.

**Independent Test**: Can be fully tested by inviting a second user into an existing
Organization, confirming they gain access scoped to that Organization's projects only, and
confirming their role restricts/allows actions as configured.

**Acceptance Scenarios**:

1. **Given** an Organization owner, **When** they invite a teammate by email with a role,
   **Then** the invitee can join and see only that Organization's projects, scoped by their
   assigned role's permissions.
2. **Given** a member with a restricted role (e.g. read-only), **When** they attempt an action
   outside their permissions (e.g. deleting a project), **Then** the action is blocked with a
   clear permission error.
3. **Given** an Organization with multiple members, **When** the owner removes a member,
   **Then** that member immediately loses access to the Organization's projects and data.

---

### User Story 12 - Operate under a subscription plan with usage limits (Priority: P3)

An Organization operates under a subscription plan (Free/Starter/Professional/Enterprise) that
governs how many projects, test executions, AI operations, and team members it may use, with
clear feedback when a limit is reached.

**Why this priority**: Monetization and plan-based gating are necessary for a real SaaS
business but are not required for the product to deliver testing value in the MVP; the
architecture must support this from day one even though enforcement UI can ship later.

**Independent Test**: Can be fully tested by configuring an Organization on a plan with a low
limit (e.g. max 1 project) and confirming the system blocks a second project creation with a
clear upgrade-prompting message, without affecting Organizations on unlimited/higher plans.

**Acceptance Scenarios**:

1. **Given** an Organization on a plan with a defined project limit, **When** a member attempts
   to create a project beyond that limit, **Then** creation is blocked with a message explaining
   the limit and how to upgrade.
2. **Given** an Organization approaching its monthly AI-usage or test-execution limit, **When**
   the threshold is reached, **Then** the system reflects the exhausted usage clearly at the
   point of the next attempted AI generation or test run.
3. **Given** an Organization's current plan and usage, **When** a member views billing/plan
   settings, **Then** they see the current plan, its limits, and current usage against each
   limit.

---

### Edge Cases

- What happens when a submitted project URL is well-formed but unreachable (DNS failure,
  connection refused, TLS error) at generation or execution time? System must surface a clear,
  distinct error state rather than a silent empty result.
- What happens when AI test case generation is requested against a site that requires login to
  see any meaningful content? System must generate what it can from publicly reachable pages and
  clearly note that authenticated areas were not analyzed (per MVP unauthenticated-only scope).
  What happens if the URL immediately redirects to a login page with no public content at all?
  System must report that no testable public content was found rather than fabricating cases.
- What happens when a user requests regeneration of test cases while a previous generation
  request for the same project is still in progress? System must prevent duplicate concurrent
  generation jobs for the same project and surface the existing job's status instead.
- What happens when a test run is started while another test run is already executing for the
  same project? System must support this (e.g., queue or run in parallel) without corrupting
  either run's results, per the scalability requirement for parallel execution.
- What happens when the target website's structure changes between test case generation and
  test execution (e.g., an element the test expects no longer exists)? The test must fail with a
  clear "element not found" result rather than hang indefinitely; execution must enforce a
  timeout per step and per test case.
- What happens when a browser session crashes mid-test? The test must be marked as
  "error"/"failed" with whatever logs/screenshots were captured before the crash, and the test
  run must continue with remaining tests rather than aborting entirely.
- What happens when AI failure analysis is requested for a test result that has since been
  deleted or belongs to an archived project? The system must reject the request with a clear
  "not found" style error.
- What happens when a user attempts to access a project, test run, or issue belonging to a
  different Organization (by guessing an ID, stale link, etc.)? The system must deny access as
  if the resource does not exist — no cross-tenant data must ever be observable, including
  through error message contents.
- What happens when an AI provider call fails, times out, or returns malformed output during
  test generation or failure analysis? The system must retry within a bounded limit, then
  surface a distinct "AI analysis unavailable" state, and must never silently save fabricated or
  partial AI output as if it were a complete, trustworthy result.
- What happens when a screenshot or log artifact fails to upload to storage during test
  execution? The test result must still be recorded with its pass/fail outcome, flagged as
  having incomplete evidence, rather than the whole test run failing.
- What happens when a password-reset token is reused after being consumed, or used after
  expiry? The system must reject it and require a fresh reset request.
- What happens when an Organization's usage limit is reached mid-test-run (e.g., limit resets or
  is hit while tests are already queued)? In-flight/already-queued work in the current run
  should be allowed to complete; only new generation/run requests are blocked by the limit.
- What happens when a user deletes/archives a project that has an in-progress test run? The
  in-progress run must either be allowed to finish or be explicitly cancelled — the system must
  not leave orphaned "running" state with no way to reach a terminal status.

## Requirements *(mandatory)*

Each requirement below is tagged **(MVP)** or **(Future)** per the MVP Scope / Future Scope
sections. All MVP requirements are in scope for the first implementation; Future requirements
describe the direction the architecture must not preclude.

### Functional Requirements

#### Authentication & Account Management

- **FR-001** (MVP): System MUST allow a visitor to sign up for an account with an email address
  and password, enforcing a minimum password strength policy.
- **FR-002** (MVP): System MUST allow a registered user to log in with email and password and
  receive a secure, expiring session.
- **FR-003** (MVP): System MUST allow an authenticated user to log out, immediately invalidating
  their active session.
- **FR-004** (MVP): System MUST provide a "forgot password" flow that emails a time-limited,
  single-use reset token/link to the account's registered email address.
- **FR-005** (MVP): System MUST allow a user with a valid, unexpired reset token to set a new
  password, after which the token becomes invalid.
- **FR-006** (MVP): System MUST allow an authenticated user to view and edit their profile
  (name, email, password) from a dedicated profile/settings area.
- **FR-007** (MVP): System MUST enforce that all dashboard, project, test, and reporting pages
  and their underlying APIs are accessible only to authenticated users.
- **FR-008** (MVP): System MUST expire idle sessions after a bounded inactivity period and
  require re-authentication afterward.
- **FR-009** (MVP): System MUST rate-limit authentication attempts (login, password reset
  requests) per account/IP to mitigate credential-stuffing and brute-force attacks.
- **FR-010** (MVP): System MUST NOT expose whether a given email address has an existing account
  through timing or response differences on login/forgot-password flows (anti-enumeration).
- **FR-011** (Future): System MUST support additional authentication methods (e.g., SSO/OAuth)
  without requiring a redesign of the account/session data model.

#### Organizations, Membership & Access

- **FR-012** (MVP): System MUST automatically create a personal, single-member Organization for
  every new user at signup, and every project MUST belong to exactly one Organization.
- **FR-013** (MVP): System MUST scope all projects, test cases, test runs, results, issues,
  reports, and notifications to their owning Organization at the data layer.
- **FR-014** (MVP): System MUST prevent any user from reading or modifying data belonging to an
  Organization they are not a member of, regardless of how the resource is addressed (ID
  guessing, stale links, etc.). This is the overall tenant-isolation *guarantee* (the outcome);
  FR-133 is the corresponding *enforcement-point* requirement — it specifies where this
  guarantee must be enforced (every API endpoint, not merely hidden by the UI). The two are
  complementary, not duplicates: FR-014 could theoretically be satisfied by UI-only hiding, which
  would not be acceptable — FR-133 closes exactly that gap.
- **FR-015** (MVP): System MUST record, for every user, which Organization(s) they belong to and
  their role within each, even though the MVP only ever creates single-member Organizations.
- **FR-016** (Future): System MUST allow an Organization owner to invite additional members by
  email and assign each a role.
- **FR-017** (Future): System MUST support at least the roles Owner, Admin, and Member, with
  Owner able to manage billing/members, Admin able to manage projects/tests, and Member able to
  work within projects per Admin-configured permissions.
- **FR-018** (Future): System MUST allow an Organization owner/admin to remove a member, which
  immediately revokes that member's access to the Organization's data.
- **FR-019** (Future): System MUST allow a single user account to belong to more than one
  Organization and switch between them.

#### Dashboard & Navigation

- **FR-020** (MVP): System MUST provide a persistent primary navigation (sidebar) exposing
  Overview, Projects, Test Runs, Test Cases, Reports, Bugs/Issues, and Settings.
- **FR-021** (MVP): System MUST provide an Overview page summarizing the Organization's active
  projects, recent test run activity, and outstanding critical issues at a glance.
- **FR-022** (MVP): System MUST reflect a user's actual data (or an explicit empty state) on
  first login rather than placeholder/sample content.
- **FR-023** (Future): System MUST include an AI Assistant entry point in primary navigation
  once User Story 10 ships.
- **FR-024** (MVP): System MUST make the currently selected project's context (name, URL)
  visible while the user is inside any project-scoped screen (test cases, test runs, reports).

#### Project Management

- **FR-025** (MVP): System MUST allow a user to create a project with a name and a target
  website URL.
- **FR-026** (MVP): System MUST validate submitted URLs for well-formedness before allowing
  project creation, and MUST attempt a reachability check that surfaces a clear warning (not a
  hard block) if the URL cannot currently be reached.
- **FR-027** (MVP): System MUST allow a user to edit a project's name, URL, and settings after
  creation.
- **FR-028** (MVP): System MUST allow a user to archive a project, removing it from the default
  active list while preserving its full history and remaining reachable via an archived view.
- **FR-029** (MVP): System MUST allow a user to permanently delete a project, and MUST require
  explicit confirmation before doing so given the destructive, irreversible nature of the
  action.
- **FR-030** (MVP): System MUST show a project's testing history (past test runs and their
  outcomes) on its detail page.
- **FR-031** (MVP): System MUST support project-level settings including, at minimum, the target
  URL and any AI-generation preferences (e.g., which flow types to prioritize).
- **FR-032** (MVP): System MUST prevent a test run or AI generation request against an archived
  project.
- **FR-033** (MVP): System MUST list all projects belonging to the user's Organization with
  status indicators (e.g., active/archived, last run outcome).
- **FR-034** (Future): System MUST support tagging/grouping projects (e.g., by client, by
  environment) for Organizations managing many projects (notably agencies).
- **FR-035** (MVP): System MUST reject project URLs that resolve to non-public/internal network
  addresses (see FR-135, SSRF protection) at creation time.

#### AI Test Case Generation

- **FR-036** (MVP): System MUST allow a user to trigger AI-driven analysis of a project's
  configured URL to identify reachable public pages and candidate user flows.
- **FR-037** (MVP): System MUST generate a set of test scenarios covering the significant user
  flows identified during analysis.
- **FR-038** (MVP): System MUST generate, for each scenario, one or more detailed test cases
  containing ordered steps, expected results, a priority, a severity, and a plain-language
  explanation of the test's purpose.
- **FR-039** (MVP): System MUST include both positive (expected-success) and negative
  (expected-failure / invalid-input) test cases across a generation batch where the underlying
  flow supports both (e.g., a form supports both valid and invalid submission).
- **FR-040** (MVP): System MUST include at least one edge-case test per major identified flow
  (e.g., empty input, boundary values, unusual navigation order) where applicable.
- **FR-041** (MVP): System MUST allow a user to edit any field of a generated test case before
  or after approval.
- **FR-042** (MVP): System MUST allow a user to approve or reject an individual generated test
  case; rejected cases MUST be excluded from execution but retained (not silently deleted) for
  audit/reference.
- **FR-043** (MVP): System MUST allow a user to request regeneration of a single test case or an
  entire generation batch.
- **FR-044** (MVP): System MUST record whether a test case's source is "AI-generated" or
  "manual," and preserve that provenance through edits.
- **FR-045** (MVP): System MUST NOT analyze pages or flows that require authentication in the
  MVP (per the unauthenticated-only clarification); if the target URL redirects to a login page
  with no public content, generation MUST report that no testable public content was found.
- **FR-046** (MVP): System MUST bound AI generation requests with a timeout and a bounded retry
  policy, surfacing a distinct failure state to the user if generation cannot complete.
- **FR-047** (MVP): System MUST prevent starting a second concurrent generation job for the same
  project while one is already in progress, surfacing the in-progress job's status instead.
- **FR-048** (Future): System MUST support authenticated-flow analysis (post-credential-handling
  design) without requiring a redesign of the test case data model.

#### Test Case Management (Library)

- **FR-049** (MVP): System MUST provide a list view of all test cases in a project, showing
  title, priority, severity, status, source (AI/manual), and tags.
- **FR-050** (MVP): System MUST support free-text search over test case title, description, and
  steps.
- **FR-051** (MVP): System MUST support filtering the test case list by priority, severity,
  status, tag, and source.
- **FR-052** (MVP): System MUST support sorting the test case list by at least priority,
  severity, status, and last-updated time.
- **FR-053** (MVP): System MUST allow a user to manually create a test case with the same
  structure (steps, expected results, priority, severity, tags) as an AI-generated one.
- **FR-054** (MVP): System MUST allow a user to add, edit, and remove tags on a test case.
- **FR-055** (MVP): System MUST track a test case's lifecycle status (e.g., draft, approved,
  rejected) distinct from its most recent execution outcome.
- **FR-056** (MVP): System MUST record, for each test case, its most recent actual result
  (passed/failed/skipped/not yet run) alongside its defined expected result.
- **FR-057** (MVP): System MUST prevent a test case from being selected into a new test run if
  its status is "rejected."
- **FR-058** (Future): System MUST support bulk operations (bulk tag, bulk approve, bulk
  archive) on test cases.

#### Automated Browser Testing (Execution Engine)

- **FR-059** (MVP): System MUST execute test cases using real browser automation capable of
  opening the target website and navigating between pages.
- **FR-060** (MVP): System MUST support simulating user interactions required by generated test
  steps, at minimum: clicking elements, entering text into fields, and submitting forms.
- **FR-061** (MVP): System MUST support validating the resulting page URL against an expected
  value or pattern as a test assertion.
- **FR-062** (MVP): System MUST support validating page content (visible text) against expected
  values as a test assertion.
- **FR-063** (MVP): System MUST support validating the presence, absence, or state of specific
  UI elements as a test assertion.
- **FR-064** (MVP): System MUST capture a screenshot at, at minimum, the point of test failure,
  and MUST support capturing screenshots at other defined checkpoints in a test case.
- **FR-065** (MVP): System MUST record a step-by-step execution log for every test case run,
  including which step failed and why when applicable.
- **FR-066** (MVP): System MUST enforce a timeout on individual test steps and on overall test
  case execution so a single hung interaction cannot block a test run indefinitely.
- **FR-067** (MVP): System MUST isolate each test case's browser session so that state (cookies,
  local storage, navigation) from one test case cannot leak into another within the same run.
- **FR-068** (MVP): The execution engine's architecture MUST allow additional interaction types,
  assertion types, and browser targets to be added without redesigning the core test case or
  result data model (extensibility for future scale).

#### Test Runs & Execution Monitoring

- **FR-069** (MVP): System MUST allow a user to select one or more approved test cases and start
  a test run against the parent project's configured URL.
- **FR-070** (MVP): System MUST execute all test cases in a run and record, per test case, a
  terminal status of passed, failed, or skipped.
- **FR-071** (MVP): System MUST expose live/near-live status of an in-progress test run,
  including counts of queued, running, passed, failed, and skipped test cases.
- **FR-072** (MVP): System MUST let a user open a specific test result within a run to view its
  execution log and captured screenshots.
- **FR-073** (MVP): System MUST allow a user to retry only the failed test cases from a
  completed run without re-running or altering the results of tests that already passed.
- **FR-074** (MVP): System MUST record start time, end time, and duration for each test run and
  each test case execution within it.
- **FR-075** (MVP): System MUST continue executing remaining test cases in a run if an individual
  test case's browser session errors or crashes, marking only that test case as
  failed/errored.
- **FR-076** (MVP): System MUST retain historical test run data (not just the most recent run)
  so trend reporting (Story 8) has data to compute against.
- **FR-077** (Future): System MUST support executing multiple test cases within a run in
  parallel, and executing multiple test runs for the same or different projects concurrently,
  as usage scales.
- **FR-078** (Future): System MUST support cancelling an in-progress test run.

#### AI-Powered Failure Analysis

- **FR-079** (MVP): System MUST allow a user to request AI analysis of any failed test result.
- **FR-080** (MVP): AI analysis input MUST include the failed step's error message/log excerpt,
  the test case's defined steps, the expected result, the actual observed result, and any
  screenshot captured at failure.
- **FR-081** (MVP): AI analysis output MUST include a plain-language failure explanation, a
  likely root cause, a severity rating, and a suggested fix framed for a developer audience.
- **FR-082** (MVP): System MUST explicitly present the expected-vs-actual comparison that
  informed the AI's explanation, not only the AI's narrative summary.
- **FR-083** (MVP): System MUST bound AI analysis requests with a timeout and bounded retry
  policy, and MUST surface a distinct "analysis unavailable" state on failure rather than
  fabricating a result.
- **FR-084** (MVP): System MUST persist AI analysis results attached to their originating test
  result so they can be viewed later without re-running analysis.
- **FR-085** (MVP): System MUST allow a user to re-request analysis for the same failed result
  (e.g., after a provider outage), replacing or versioning the prior analysis.
- **FR-086** (MVP): System MUST restrict AI analysis of screenshots/logs sent to the LLM
  provider to data belonging to the requesting user's own Organization.

#### Bug / Issue Management

- **FR-087** (MVP): System MUST allow a user to create an issue directly from a failed test
  result, pre-filled with a title, description, and the failure's screenshots/logs attached.
- **FR-088** (MVP): System MUST allow a user to create an issue manually, independent of any
  specific test result.
- **FR-089** (MVP): System MUST require a severity and a priority on every issue.
- **FR-090** (MVP): System MUST support a defined issue status lifecycle (e.g., open, in
  progress, resolved, closed, won't fix).
- **FR-091** (MVP): System MUST link every issue created from a test result to that test case
  and to the test run in which the failure occurred.
- **FR-092** (MVP): System MUST allow attaching additional screenshots or log excerpts to an
  issue after creation.
- **FR-093** (MVP): System MUST allow filtering and sorting the issue list by status, severity,
  priority, and linked project.
- **FR-094** (Future): System MUST allow assigning an issue to a specific Organization member
  once multi-member Organizations (FR-016) exist.
- **FR-095** (MVP): System MUST allow a user to view, from a test case's detail page, all issues
  that have ever been linked to it.
- **FR-096** (MVP): System MUST preserve an issue's link to its originating test case/run even
  if that test case is later edited or the run's data is superseded by newer runs.

#### AI QA Assistant

- **FR-097** (Future — Implemented): System MUST provide a conversational interface where a user
  can ask natural-language questions about their Organization's projects, test cases, test runs,
  failures, and issues. Delivered via `POST /assistant/chat` and the `/assistant` chat UI — see
  tasks.md Phase 15's post-implementation record.
- **FR-098** (Future — Implemented): System MUST ground assistant answers about a specific
  project in that project's actual current data (test cases, recent runs, open issues) rather
  than generic text, and MUST scope that data access to the requesting user's Organization.
  Delivered via `assistant/context_builder.py`'s bounded, Organization+Project-scoped context
  builder.
- **FR-099** (Future — Implemented): System MUST allow the assistant to answer general
  QA-strategy questions that are not grounded in a specific project's data, while distinguishing
  such answers from data-grounded ones. Delivered via the optional `project_id`, the response's
  `grounded` flag, and the UI's "Grounded in X" / "General assistant" indicator.
- **FR-100** (Future — Implemented): System MUST surface a clear error state in the assistant UI
  when the underlying AI provider is unavailable, rather than silently failing or fabricating an
  answer. Delivered via `AssistantUnavailableError` (503) and the chat UI's inline error+retry.
- **FR-101** (Future — Implemented): System MUST retain assistant conversation history per user
  so a multi-turn conversation retains context within a session. Delivered via
  `assistant_conversations`/`assistant_messages` persistence, isolated per user+Organization, and
  threaded into each subsequent provider call.
- **FR-102** (Future): The assistant MUST cite or link to the specific project entities (test
  case, run, issue) it references when answering a data-grounded question. **Not yet
  implemented** — `ChatResponse.referenced_entities` exists in the schema but is never populated;
  no entity-citation mechanism was built in this pass.
- **FR-103** (Future — Implemented): System MUST rate-limit assistant usage per Organization
  consistent with its subscription plan's AI usage limits (FR-125). Delivered via
  `billing_service.check_and_reserve_period_usage(metric="ai_operations")`, the same mechanism
  `ai_generation`/`ai_analysis` use.

#### Reports & Analytics

- **FR-104** (MVP): System MUST provide a project-level report showing total, passed, failed,
  and skipped test counts, pass percentage, and failure percentage for a selectable time range.
- **FR-105** (MVP): System MUST show test coverage as the count/percentage of approved test
  cases that have been executed at least once within the selected time range.
- **FR-106** (MVP): System MUST show issue counts broken down by severity for a project.
- **FR-107** (MVP): System MUST show a project's test execution history as a navigable list of
  past runs with their summary outcomes.
- **FR-108** (Future): System MUST show a pass-rate trend line across test runs over time to
  indicate whether a project's quality is improving or regressing.
- **FR-109** (Future): System MUST allow report data to be exported (e.g., PDF/CSV) without
  requiring a redesign of the underlying reporting data model — the MVP MUST structure report
  data so an export capability can be added additively.
- **FR-110** (MVP): System MUST scope every report strictly to the requesting user's
  Organization; no cross-Organization aggregation may be shown by default.
- **FR-111** (Future): System MUST provide an Organization-level rollup report across all of an
  Organization's projects, not only single-project reports.

#### Notifications

- **FR-112** (MVP): System MUST create a notification for the initiating user when a test run
  they started reaches a terminal state, summarizing pass/fail/skip counts.
- **FR-113** (MVP): System MUST create a distinctly flagged notification when a test run
  produces a critical-severity failure or issue.
- **FR-114** (MVP): System MUST create a notification when AI failure analysis completes for a
  result the user has requested analysis on.
- **FR-115** (MVP): System MUST provide a notification center where a user can view, mark as
  read, and navigate from a notification to its related test run, result, or issue.
- **FR-116** (MVP): System MUST track read/unread state per notification per user.
- **FR-117** (Future): System MUST support notification delivery channels beyond in-app (e.g.,
  email, webhook) without redesigning the notification data model.
- **FR-118** (Future): System MUST allow a user to configure which event types generate
  notifications for them.

#### Subscription Plans & Usage Limits

- **FR-119** (MVP): System MUST assign every Organization a subscription plan (defaulting new
  Organizations to a Free plan) at creation time.
- **FR-120** (MVP): The data model MUST support at least the plan tiers Free, Starter,
  Professional, and Enterprise, each with independently configurable limits.
- **FR-121** (MVP): The data model MUST support, per plan, configurable limits on: number of
  active projects, test executions per billing period, AI operations (generation + analysis)
  per billing period, and number of Organization members.
- **FR-122** (MVP): System MUST track current usage against each limit type per Organization per
  billing period.
- **FR-123** (MVP): System MUST block an action that would exceed the Organization's current
  plan limit (e.g., creating a project beyond the project limit) with a clear, specific message
  identifying which limit was hit.
- **FR-124** (MVP): System MUST allow already-queued or in-progress test executions to complete
  even if a usage limit is reached during their execution; only new requests are blocked.
- **FR-125** (MVP): System MUST expose an Organization's current plan, its limits, and current
  usage against each limit in a settings/billing view.
- **FR-126** (Future): System MUST support changing an Organization's plan (upgrade/downgrade).
- **FR-127** (Future): System MUST integrate with a payment provider to process paid plan
  subscriptions; the MVP is not required to process real payments but MUST NOT require a data
  model change to add this later.

#### Platform Security, Audit & Administration

- **FR-128** (MVP): System MUST log security-relevant events (login, logout, failed login,
  password reset request/completion, project deletion, permission-relevant changes) with actor,
  timestamp, and affected resource.
- **FR-129** (MVP): System MUST make an Organization's audit log viewable by that Organization's
  owner/admin, scoped strictly to that Organization's own events.
- **FR-130** (MVP): System MUST validate and sanitize all user-supplied input at the API
  boundary, rejecting malformed requests before they reach business logic.
- **FR-131** (MVP): System MUST store all secrets (AI provider API keys, database credentials,
  session-signing keys) outside of source control and outside of client-reachable
  configuration, accessible only to backend services that require them.
- **FR-132** (MVP): System MUST apply rate limiting to authentication endpoints, AI generation
  endpoints, AI analysis endpoints, and test-execution-triggering endpoints.
- **FR-133** (MVP): System MUST enforce Organization-scoped authorization checks on every API
  endpoint that reads or writes project, test, issue, or report data — not only at the UI layer.
  This is the *enforcement-point* requirement that makes FR-014's tenant-isolation guarantee hold
  even against direct API calls that bypass the UI entirely; see FR-014 for the outcome-level
  guarantee this requirement makes concrete.
- **FR-134** (MVP): System MUST protect against common web application vulnerabilities,
  including at minimum: injection (SQL and command), cross-site scripting, cross-site request
  forgery, and insecure direct object references (verified via FR-014/FR-133).
- **FR-135** (MVP): System MUST validate that user-submitted target URLs (project URLs) do not
  resolve to private/internal/loopback network ranges before the execution engine is permitted
  to navigate to them, to prevent server-side request forgery via the browser automation layer.
- **FR-136** (MVP): System MUST return generic "not found" responses (not "forbidden") for
  cross-Organization resource access attempts, so error responses do not themselves leak
  resource existence across tenants.
- **FR-137** (MVP): System MUST provide a health-check endpoint suitable for automated
  infrastructure monitoring, independent of user authentication.
- **FR-138** (MVP): System MUST emit structured logs and expose operational metrics (e.g., test
  execution throughput, AI request latency/error rate, API error rate) suitable for external
  monitoring/alerting.

### Key Entities

- **User**: An individual account holder. Attributes: email, hashed password, name, profile
  settings, email-verification state. Belongs to one or more Organizations via Membership.
- **Organization**: The tenant boundary (referred to as a "workspace" informally in places, but
  "Organization" is the canonical name used throughout this spec, the data model, and the API).
  Attributes: name, subscription plan, creation date. Owns Projects, Members, and a Subscription.
  Auto-created 1:1 with a User at signup in the MVP; may later contain multiple Members.
- **Membership**: Join of User and Organization with a Role (Owner/Admin/Member). MVP always
  produces exactly one Owner membership per Organization at signup.
- **Project**: A website/application under test. Attributes: name, target URL, settings, status
  (active/archived), creation date. Belongs to one Organization; owns Test Cases and Test Runs.
- **TestCase**: A single testable scenario. Attributes: title, description/purpose, ordered
  steps, expected result, priority, severity, status (draft/approved/rejected), tags, source
  (AI-generated/manual), most recent actual result. Belongs to one Project.
- **TestStep**: An ordered action within a Test Case. Attributes: action type (navigate, click,
  type, submit, assert-URL, assert-content, assert-element), target descriptor, input value
  (if any), expected assertion.
- **GenerationRun**: A single AI test-case generation job for a Project (FR-036, FR-047).
  Attributes: scope (full batch or single-case regeneration), status
  (queued/running/completed/failed), failure reason. Used to track generation progress for
  polling and to enforce the "no two concurrent generation jobs per project" rule (FR-047).
- **TestRun**: A single execution batch of one or more Test Cases against a Project. Attributes:
  status, start/end time, initiating user, summary counts (queued/running/passed/failed/
  skipped).
- **TestResult**: The outcome of one Test Case within one Test Run. Attributes: status
  (passed/failed/skipped/error), execution log, duration, linked screenshots/artifacts.
- **Artifact**: A stored file produced during execution (screenshot, log excerpt). Attributes:
  type, storage location, capture timestamp. Belongs to one Test Result.
- **AIAnalysis**: An AI-generated explanation attached to a failed Test Result. Attributes:
  explanation, root cause, severity rating, suggested fix, generation timestamp, provider used.
- **Issue (Bug)**: A tracked defect. Attributes: title, description, severity, priority, status,
  assignee (future), attachments. Optionally linked to an originating Test Case and Test Run.
- **Notification**: An event-driven message to a User. Attributes: type, related entity
  reference, read/unread state, creation timestamp.
- **Report**: A computed aggregation (not necessarily persisted verbatim) of Test Run, Test
  Result, and Issue data for a Project over a time range — total/pass/fail/skip counts,
  coverage, severity distribution, trend series.
- **Subscription (Plan)**: The plan tier assigned to an Organization. Attributes: tier name,
  configured limits (projects, test executions, AI operations, members) per billing period.
- **UsageRecord**: Tracked consumption against a Subscription's limits for an Organization
  within the current billing period, per limit type.
- **AuditLogEntry**: A recorded security-relevant event. Attributes: actor (User), action,
  affected resource reference, timestamp, Organization scope.
- **AssistantConversation** *(future)*: A thread of natural-language exchanges between a User
  and the AI QA Assistant, optionally scoped to a Project for grounded answers.

## Non-Functional Requirements

### Performance

- **NFR-001**: A dashboard or project list page MUST load its primary content within 2 seconds
  under normal load for an Organization with typical data volumes (tens of projects, hundreds
  of test cases).
- **NFR-002**: Triggering a test run MUST acknowledge the request (queued state visible to the
  user) within 1 second, independent of how long actual execution takes.
- **NFR-003**: Report views MUST render aggregate metrics within 3 seconds for a project with up
  to one year of test run history.

### Scalability & Reliability

- **NFR-004**: Test execution MUST run as background/worker jobs, not inline with the
  user-facing API request, so long-running browser automation never blocks API responsiveness.
- **NFR-005**: The execution architecture MUST support horizontal scaling of test-execution
  workers independent of the API layer, to accommodate growth in concurrent test runs.
- **NFR-006**: The system MUST support queue-based distribution of test execution jobs so that
  execution throughput can scale by adding workers rather than requiring architectural change.
- **NFR-007**: A single test case's browser session failure MUST NOT cause other test cases in
  the same run, or other concurrent runs, to fail or hang (fault isolation).
- **NFR-008**: The system SHOULD support caching of frequently read, rarely changed data (e.g.,
  project metadata, plan limits) to reduce database load as tenant count grows.

### Observability

- **NFR-009**: All backend services MUST emit structured (machine-parseable) logs including a
  correlation/request ID traceable across a single user action (e.g., one test run).
- **NFR-010**: The system MUST provide health-check endpoints for all independently deployable
  services, suitable for use by container orchestration liveness/readiness probes.
- **NFR-011**: The system MUST expose metrics on test execution throughput, AI request
  latency/error rate, and API error rate suitable for external monitoring and alerting.
- **NFR-012**: Errors that reach an unhandled state MUST be captured with enough context
  (stack trace, request ID, user/Organization scope) to diagnose without reproducing manually.

### Accessibility & UX Quality

- **NFR-013**: The web application MUST be usable with a keyboard alone for all primary flows
  (navigation, project creation, test case review, test run monitoring).
- **NFR-014**: The web application MUST meet WCAG 2.1 AA-equivalent contrast and semantic
  markup expectations for interactive components (buttons, forms, status indicators).
- **NFR-015**: The web application MUST be usable on desktop, tablet, and mobile viewport
  widths, with primary flows (not necessarily dense data tables) fully functional on mobile.
- **NFR-016**: The system MUST provide distinct, clearly designed empty, loading, and error
  states for every primary data view (projects, test cases, test runs, reports, issues).

### Maintainability

- **NFR-017**: All persisted data structures MUST have explicit, enforced types at the API
  boundary (request/response validation), rejecting malformed payloads rather than coercing
  them silently.
- **NFR-018**: The AI provider integration MUST be implemented behind a provider-agnostic
  interface such that swapping the underlying LLM provider does not require changes to callers
  of that interface.
- **NFR-019**: The browser automation layer MUST be implemented behind an interface that allows
  additional interaction/assertion types to be added without changing the test case data model
  or existing callers.

## Security Requirements

- **SEC-001**: Passwords MUST be stored using a modern, salted, adaptive hashing algorithm;
  plaintext or reversibly-encrypted passwords MUST NOT be stored.
- **SEC-002**: Sessions MUST use secure, expiring tokens (e.g., signed, short-lived access
  tokens with rotation), transmitted only over encrypted connections (HTTPS/TLS).
- **SEC-003**: Every API endpoint MUST enforce both authentication (who is this) and
  authorization (what may this Organization/role do) independently — authentication alone MUST
  NOT be treated as sufficient for access to another Organization's data.
- **SEC-004**: All secrets (AI provider keys, database credentials, signing keys) MUST be
  injected via a secrets-management mechanism at deploy time, never committed to source control
  or bundled into client-side code.
- **SEC-005**: TestPilot MUST NOT store credentials for the website under test in the MVP (per
  the unauthenticated-only clarification); this constraint MUST be enforced by the absence of
  any such storage capability, not merely by policy.
- **SEC-006**: The browser automation layer MUST be prevented from navigating to
  private/loopback/link-local network addresses when executing a user-submitted project URL, to
  prevent the platform from being used as an SSRF vector into internal infrastructure.
- **SEC-007**: All user input MUST be validated server-side (never trusting client-side
  validation alone) and output MUST be safely encoded to prevent stored/reflected XSS in
  AI-generated content, test case fields, and issue descriptions.
- **SEC-008**: State-changing requests MUST be protected against cross-site request forgery.
- **SEC-009**: Authentication endpoints, AI generation/analysis endpoints, and test-execution
  trigger endpoints MUST be rate-limited per account and per IP.
- **SEC-010**: Security-relevant events (auth events, permission changes, deletions) MUST be
  captured in an audit log that is append-only from the application's perspective (no in-app
  edit/delete of audit entries).
- **SEC-011**: Cross-tenant resource access attempts MUST fail closed (denied) and MUST return
  responses indistinguishable from "resource does not exist" to avoid leaking cross-tenant
  resource existence.
- **SEC-012**: Screenshots and logs sent to third-party AI providers for analysis MUST be
  restricted to data already belonging to the requesting user's own Organization; no
  cross-tenant content may be included in an AI request payload.
- **SEC-013**: File/artifact uploads and storage (screenshots, logs) MUST validate content type
  and size, and MUST be stored in a way that prevents them from being served as executable
  content.

## UX Requirements

- **UX-001**: The interface MUST present a visual design consistent with a professional SaaS
  testing/QA product, verified against the following objective, checkable criteria rather than
  subjective impression alone:
  (a) every screen is built exclusively from the shared design-token set and component library
  (colors, spacing, typography, radii) defined in plan.md's Design System — no component may
  hard-code a raw hex color, pixel font-size, or ad hoc spacing value outside that token set;
  (b) status-driven color coding (pass/fail/running/queued) is applied via the shared
  `StatusBadge`/`SeverityBadge`/`PriorityBadge` components (see UX-003) on every screen that
  shows test or issue status, never a one-off inline badge;
  (c) data-dense views (test case library, test runs, issues, reports) use the shared
  `DataTable`/chart components rather than ad hoc markup;
  (d) the interface is not built from generic, unstyled CRUD form scaffolding — every form uses
  the shared form primitives (`TextField`, `Select`, etc.) and layout components.
  Compliance is verified by code review confirming (a)-(d) hold in the component source, not by
  aesthetic judgment.
- **UX-002**: The interface MUST use a persistent sidebar navigation exposing the primary
  sections (Overview, Projects, Test Runs, Test Cases, Reports, Bugs/Issues, AI Assistant,
  Settings) with clear active-state indication.
- **UX-003**: The interface MUST use consistent status badges (e.g., passed/failed/skipped/
  running/queued, priority, severity) with distinguishable color and text, not color alone, to
  remain accessible to colorblind users.
- **UX-004**: In-progress test runs MUST show a live execution progress indicator, not just a
  static "running" label with no sense of proportion completed.
- **UX-005**: Every primary list/detail view MUST have a defined empty state (first-time/no-data
  guidance), loading state, and error state, distinct from one another.
- **UX-006**: Transient outcomes (save success, action failure, generation complete) MUST be
  communicated via toast notifications that do not block the underlying page.
- **UX-007**: The interface's component architecture MUST support both a light and a dark theme,
  even if only one is enabled at MVP launch, without requiring a rebuild of individual screens
  to add the second theme later.
- **UX-008**: Data tables (test cases, test runs, issues) MUST support in-context search,
  filter, and sort controls directly on the table view, not only via a separate search page.
- **UX-009**: Charts used in Reports MUST label axes/legends in plain QA terminology (pass rate,
  severity, coverage) understandable to a non-technical stakeholder.

## Data Requirements

- **DATA-001**: All application data MUST be scoped to an Organization at the schema level
  (an `organization_id`-style scoping key on every tenant-owned table), enforced in every query
  path, not only in application-layer filtering.
- **DATA-002**: Screenshots and log artifacts MUST be stored in object storage (not the
  relational database) with only references/metadata persisted relationally.
- **DATA-003**: The system MUST define a retention policy for test execution artifacts
  (screenshots, logs) with a configurable retention window; expiry MUST NOT delete the
  associated Test Result's pass/fail outcome or metadata, only the large binary artifacts.
- **DATA-004**: Deleting a User account MUST remove or anonymize that user's personal data while
  preserving the integrity of Organization-owned records they created (e.g., test runs remain
  attributed to a placeholder if the acting user is deleted) — full mechanics are an
  implementation detail, but data MUST NOT be orphaned in a way that breaks referential
  integrity.
- **DATA-005**: Deleting a Project MUST cascade-remove or archive its Test Cases, Test Runs,
  Results, and Artifacts consistently — no dangling references to a nonexistent Project may
  remain queryable.
- **DATA-006**: AI-generated content (test cases, failure analyses) MUST be persisted as-is at
  generation time (not regenerated on read), so a user reviewing history sees exactly what was
  produced, even if the underlying AI provider or model later changes.
- **DATA-007**: Usage counters (test executions, AI operations) MUST be tracked per Organization
  per billing period with enough granularity to reconstruct what consumed the usage (which
  project/run/generation).

## Integration Requirements

- **INT-001**: The system MUST integrate with browser automation tooling (Playwright, per
  Technology Direction) through an internal abstraction layer, so the execution engine is not
  hard-wired to a single automation library's API throughout the codebase.
- **INT-002**: The system MUST integrate with one or more cloud LLM providers through a
  provider-agnostic interface (per Clarification 3), allowing the configured provider/model to
  change via configuration rather than code changes in calling code.
- **INT-003**: The system MUST integrate with a transactional email delivery service for
  account-related email (password reset, and future notification-by-email).
- **INT-004**: The system MUST integrate with object/file storage (S3-compatible or equivalent)
  for screenshots and execution artifacts.
- **INT-005** (Future): The system MUST be able to integrate with a payment/billing provider to
  process subscription payments without requiring a redesign of the Subscription/UsageRecord
  data model.
- **INT-006** (Future): The system MUST support triggering a test run via an external webhook
  (e.g., from a CI/CD pipeline) as an additive integration on top of the existing test-run
  creation capability.
- **INT-007** (Future): The system MUST support outbound webhook or chat-platform (e.g., Slack)
  notification delivery as an additional notification channel alongside in-app notifications.

## MVP Scope

The first implementation MUST deliver, end-to-end:

1. Authentication & account management (FR-001–FR-010), including personal Organization
   auto-creation (FR-012–FR-015).
2. Core dashboard navigation and Overview (FR-020–FR-022, FR-024).
3. Project creation, editing, archiving, deletion, and URL configuration (FR-025–FR-033,
   FR-035).
4. AI test case generation from a URL, scoped to unauthenticated/public content
   (FR-036–FR-047).
5. Test case library management: list, search, filter, sort, manual creation, tagging
   (FR-049–FR-057).
6. Playwright-based automated browser test execution supporting navigate/click/type/submit and
   URL/content/element assertions, with screenshots and logs (FR-059–FR-068).
7. Test run creation, execution monitoring, result viewing, and failed-test retry
   (FR-069–FR-076).
8. AI-powered failure analysis producing explanation, root cause, severity, and suggested fix
   (FR-079–FR-086).
9. Bug/issue creation (from failures and manually), status/severity/priority tracking, and
   linkage to test cases/runs (FR-087–FR-093, FR-095–FR-096).
10. Basic project-level reports: totals, pass/fail/skip, pass percentage, coverage, issue
    severity distribution, run history (FR-104–FR-107, FR-110).
11. In-app notifications for run completion, critical failures, and AI analysis completion
    (FR-112–FR-116).
12. Subscription/plan data model with Free-plan default and enforced usage limits, without a
    live payment gateway (FR-119–FR-125).
13. All Security Requirements (SEC-001–SEC-013) and Data Requirements (DATA-001–DATA-007) — the
    MVP is not permitted to defer tenant isolation, SSRF protection, or secret handling.
14. All Non-Functional Requirements (NFR-001–NFR-019) — background/worker-based execution,
    structured logging, health checks, and accessibility/responsive UX are MVP-required, not
    future polish.

## Future Scope

Explicitly deferred beyond the MVP:

1. Authenticated-flow testing and any storage/handling of site-under-test credentials
   (FR-048, and reversal of SEC-005's absence-of-capability constraint).
2. Full multi-member Organizations: invitations, roles beyond a single Owner, member removal
   (FR-016–FR-019, FR-094).
3. AI QA Assistant conversational interface (FR-097–FR-103, FR-023). **FR-097–FR-101 and
   FR-103 implemented** (tasks.md Phase 15 post-implementation record); **FR-102 (entity
   citations) remains unimplemented**. FR-023 status unchanged by this update.
4. Trend reporting, Organization-level rollup reports, and report export (FR-108–FR-109,
   FR-111).
5. Additional notification channels (email/webhook) and per-user notification preferences
   (FR-117–FR-118).
6. Plan upgrades/downgrades and live payment provider integration (FR-126–FR-127, INT-005).
7. Parallel test execution within and across runs, and run cancellation (FR-077–FR-078).
8. Bulk test case operations (FR-058).
9. Project tagging/grouping for agency-style multi-client management (FR-034).
10. External CI/CD webhook triggers and chat-platform notification integrations (INT-006–INT-007).
11. Self-hosted/local LLM provider option (per Clarification 3).

## Acceptance Criteria

Acceptance criteria for this specification are expressed at three levels, each independently
verifiable without reference to implementation details:

1. **Per user story**: the Given/When/Then Acceptance Scenarios under each User Story above.
2. **Per requirement**: every Functional, Non-Functional, Security, UX, Data, and Integration
   requirement is phrased as a testable MUST/SHOULD statement that a QA reviewer can verify
   directly against the running system.
3. **Per product**: the Measurable Outcomes in Success Criteria below, which define
   product-level "done" independent of any single feature.

A feature built from this specification is acceptance-ready when all P1 user stories' scenarios
pass, all MVP-tagged functional requirements are met, and the Success Criteria measurements are
achievable against a representative test project.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can go from account signup to viewing a first batch of AI-generated
  test cases for a project in under 10 minutes without external help or documentation.
- **SC-002**: At least 70% of AI-generated test cases are approved by users without requiring an
  edit, for a representative set of typical marketing/e-commerce/SaaS-style websites.
- **SC-003**: A test run of 20 typical test cases against a standard web page completes and
  returns results within 5 minutes.
- **SC-004**: AI failure analysis for a failed test result is available within 60 seconds of the
  user requesting it, in at least 95% of requests under normal AI provider conditions.
- **SC-005**: Users can locate a specific test case among 200+ test cases in a project using
  search/filter in under 10 seconds.
- **SC-006**: Dashboard and report views load their primary content in under 2 seconds for 95%
  of requests under typical Organization data volumes.
- **SC-007**: Zero cross-Organization data exposure incidents occur across all resource types
  (projects, test cases, runs, issues, reports) as verified by tenant-isolation testing.
- **SC-008**: The system sustains at least 50 concurrent test runs across all tenants without
  individual test run failure rates increasing, once parallel execution (Future Scope) is
  enabled.
- **SC-009**: 90% of users who complete their first AI-generated test run successfully create at
  least one issue or take a concrete follow-up action from the results (indicating the reports
  and failure analysis are actionable, not just informational).
- **SC-010**: Support requests related to "I don't understand why a test failed" decrease by 50%
  compared to a baseline raw-log-only experience, once AI failure analysis is in production use.

## Risks & Assumptions

### Assumptions

- Target websites for MVP testing are conventional server-rendered or client-rendered web apps
  reachable over public HTTP/HTTPS without bot-blocking measures that would prevent automated
  browser access entirely; sites that aggressively block automation are a known limitation, not
  a bug.
- Users have a modern evergreen browser for accessing the TestPilot AI dashboard itself
  (dashboard browser support is independent of what browsers the execution engine automates).
- "Provider-agnostic LLM architecture" means the application code depends on an internal
  interface, not that every provider is simultaneously active; one configured provider serves
  production traffic at a time per Organization/deployment.
- Reasonable default data retention for screenshots/logs is on the order of weeks to a few
  months unless a specific compliance requirement dictates otherwise; exact retention window is
  an implementation/config decision, not a fixed spec value.
- Standard session-based authentication (email/password) is sufficient for MVP; enterprise SSO
  is valuable but not required to prove the core product loop.
- The object storage, queue, and worker infrastructure implied by NFR-004–NFR-006 are standard
  cloud-provider services rather than custom-built infrastructure.

### Risks

- **AI output quality risk**: AI-generated test cases or failure analyses may be inaccurate,
  irrelevant, or hallucinated for complex/unusual sites. *Mitigation*: mandatory human
  review/approval step before execution (FR-041–FR-042) and explicit "analysis unavailable"
  failure states rather than silently trusting low-confidence output (FR-046, FR-083).
- **SSRF / abuse risk via arbitrary URL execution**: since the platform navigates a real browser
  to user-submitted URLs, it is a natural target for SSRF and internal-network probing.
  *Mitigation*: mandatory private/internal-address rejection (FR-035, FR-135, SEC-006) as an MVP
  (not future) requirement.
- **Third-party LLM cost/availability risk**: cloud LLM provider outages, rate limits, or cost
  spikes directly affect core generation/analysis features. *Mitigation*: provider-agnostic
  interface (NFR-018, INT-002) enabling provider switch, plus bounded retry/timeout and
  plan-based usage limits (FR-046, FR-083, FR-119–FR-125) to cap exposure.
- **Flaky test / false-failure risk**: real browser automation against live, changing websites
  is inherently prone to timing-related flakiness, which could erode user trust in results.
  *Mitigation*: per-step timeouts (FR-066), session isolation (FR-067), and a defined retry
  capability for failed tests (FR-073) rather than treating every failure as unquestionably a
  real bug.
- **Tenant isolation risk**: a multi-tenant SaaS handling other companies' website data and
  screenshots has high impact if isolation fails. *Mitigation*: Organization-scoping enforced at
  the data layer (DATA-001), explicit "not found" (not "forbidden") responses for cross-tenant
  access (FR-136, SEC-011), and audit logging (FR-128–FR-129).
- **Scope-creep risk**: the source feature description spans 22 distinct areas; without firm
  MVP/Future separation, initial delivery could stall trying to build everything at once.
  *Mitigation*: explicit MVP Scope and Future Scope sections above, with every requirement
  tagged, so `/speckit-plan` and `/speckit-tasks` can sequence work without re-litigating scope.
