import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const THIS_FILE = fileURLToPath(import.meta.url);
const REPOSITORY_ROOT = resolve(dirname(THIS_FILE), "..");
const DEFAULT_HOST = "127.0.0.1";
const DEFAULT_PORT = 8797;
const MAX_INPUT_BYTES = 512_000;
const MAX_OUTPUT_BYTES = 8_000_000;
const TOOL_TIMEOUT_MS = 120_000;

const dependencyBases = [
  process.env.CAREER_MCP_REQUIRE_BASE,
  resolve(REPOSITORY_ROOT, "package.json"),
].filter(Boolean);

const loadRuntimeDependency = (name) => {
  for (const base of dependencyBases) {
    if (!existsSync(base)) continue;
    try {
      const require = createRequire(base);
      return require(name);
    } catch {
      // Try the next already-installed dependency base.
    }
  }
  throw new Error(
    `missing-runtime-dependency:${name}; set CAREER_MCP_REQUIRE_BASE to a package.json with the official MCP SDK installed`,
  );
};

const { McpServer, createMcpHandler } = loadRuntimeDependency("@modelcontextprotocol/server");
const { z } = loadRuntimeDependency("zod");
const asToolResult = (value) => ({
  content: [{ type: "text", text: JSON.stringify(value) }],
  structuredContent: value,
});

const asToolError = (reason, detail = undefined) => ({
  isError: true,
  content: [{
    type: "text",
    text: JSON.stringify({ ok: false, reason, ...(detail ? { detail } : {}) }),
  }],
});

const runCareerScan = ({
  careerContext,
  poolMode,
  mode,
  discovery,
}) => new Promise((resolvePromise, rejectPromise) => {
  const payload = JSON.stringify({
    careerContext,
    poolMode,
    mode,
    discovery,
  });
  if (Buffer.byteLength(payload, "utf8") > MAX_INPUT_BYTES) {
    rejectPromise(new Error("input-too-large"));
    return;
  }

  const python = [
    "import json,sys",
    "from scripts.career_scan import run_scan_review",
    "p=json.load(sys.stdin)",
    "r=run_scan_review(None,p.get('careerContext') or {},use_configured_sources=True,use_current_career_context=True,pool_mode=p.get('poolMode','BROAD'),mode=p.get('mode','hybrid_discovery'),discovery=p.get('discovery'))",
    "print(json.dumps(r,ensure_ascii=False))",
  ].join(";");

  const child = spawn("python3", ["-c", python], {
    cwd: REPOSITORY_ROOT,
    stdio: ["pipe", "pipe", "pipe"],
  });
  const stdout = [];
  const stderr = [];
  let outputBytes = 0;
  let settled = false;
  const timer = setTimeout(() => {
    if (settled) return;
    child.kill("SIGTERM");
    settled = true;
    rejectPromise(new Error("scan-timeout"));
  }, TOOL_TIMEOUT_MS);

  child.stdout.on("data", (chunk) => {
    outputBytes += chunk.length;
    if (outputBytes > MAX_OUTPUT_BYTES) {
      child.kill("SIGTERM");
      return;
    }
    stdout.push(Buffer.from(chunk));
  });
  child.stderr.on("data", (chunk) => stderr.push(Buffer.from(chunk)));
  child.on("error", (error) => {
    if (settled) return;
    settled = true;
    clearTimeout(timer);
    rejectPromise(error);
  });
  child.on("close", (code) => {
    if (settled) return;
    settled = true;
    clearTimeout(timer);
    if (outputBytes > MAX_OUTPUT_BYTES) {
      rejectPromise(new Error("output-too-large"));
      return;
    }
    if (code !== 0) {
      const message = Buffer.concat(stderr).toString("utf8").trim();
      rejectPromise(new Error(message || `scan-exit-${code}`));
      return;
    }
    try {
      resolvePromise(JSON.parse(Buffer.concat(stdout).toString("utf8")));
    } catch {
      rejectPromise(new Error("invalid-scan-json"));
    }
  });
  child.stdin.end(payload);
});

const trimResult = (result, detailLevel) => {
  const visible = {
    schema_version: result.schema_version,
    operation: result.operation,
    mode: result.mode,
    candidate_status: result.candidate_status,
    scan_config_source: result.scan_config_source,
    source_scope: result.source_scope,
    pool_view: result.pool_view,
    discovery: result.discovery,
    summary: result.summary,
    boundary: result.boundary,
  };
  if (detailLevel === "review" || detailLevel === "full") {
    visible.review = result.review;
  }
  if (detailLevel === "full") {
    visible.scan = result.scan;
  }
  return visible;
};

const careerContextSchema = z.object({
  review_states: z.array(
    z.enum(["REVIEW_PRIORITY", "REVIEW", "VERIFY", "DEPRIORITIZE", "CLOSE"]),
  ).optional(),
  candidate_context: z.record(z.string(), z.unknown()).optional(),
  preference_context: z.record(z.string(), z.unknown()).optional(),
  market_discovery_profile: z.record(z.string(), z.unknown()).optional().describe(
    "Optional caller-scoped Market Discovery profile. Omit to use the public neutral defaults; see references/market-discovery-profile.example.json.",
  ),
  existing_roles: z.array(z.record(z.string(), z.unknown())).optional(),
  company_constraints: z.record(
    z.string(),
    z.array(z.record(z.string(), z.unknown())),
  ).optional(),
}).passthrough();

const scanModeSchema = z.enum([
  "configured_review",
  "market_discovery",
  "hybrid_discovery",
]).describe(
  "configured_review uses only configured adapters; market_discovery uses the external-Web handoff and supplied candidates; hybrid_discovery merges both paths.",
);

const officialSourceSchema = z.object({
  url: z.string().optional(),
  exact_role_verified: z.boolean().optional(),
  inspected_original: z.boolean().optional(),
}).passthrough();

const companyCoverageBucketSchema = z.enum([
  "LARGE_INTERNET_TECH",
  "MID_LARGE_TECH",
  "MATURE_SME",
  "SAAS_ENTERPRISE_SOFTWARE",
  "AI_NATIVE_APPLICATION",
  "CONSUMER_TECH",
  "GAME_CONTENT",
  "FOREIGN_INTERNATIONAL_TEAM",
  "TRADITIONAL_DIGITAL_INNOVATION",
  "STARTUP_SCALEUP",
  "UNKNOWN",
]).describe(
  "Search-coverage classification only. It helps detect result-set concentration and is not an employer-quality or market-distribution judgment.",
);

const discoveryCandidateSchema = z.object({
  company: z.string().min(1).describe("Employer name."),
  role: z.string().min(1).optional().describe("Exact role title."),
  exactRole: z.string().min(1).optional().describe("Camel-case alias for exact role title."),
  exact_role: z.string().min(1).optional().describe("Snake-case alias for exact role title."),
  role_title: z.string().min(1).optional().describe("Search Execution alias for exact role title."),
  external_job_id: z.string().optional(),
  location: z.unknown().optional(),
  officialSource: officialSourceSchema.optional(),
  official_source: officialSourceSchema.optional(),
  liveStatus: z.string().optional(),
  live_status: z.string().optional(),
  qualificationFacts: z.array(z.string()).optional(),
  qualification_facts: z.array(z.string()).optional(),
  deadline: z.unknown().optional(),
  applicationRule: z.unknown().optional(),
  application_rule: z.unknown().optional(),
  provenance: z.array(z.record(z.string(), z.unknown())).optional(),
  uncertainty: z.array(z.string()).optional(),
  roleFamily: z.string().optional(),
  role_family: z.string().optional(),
  companyCoverageBucket: companyCoverageBucketSchema.optional(),
  company_coverage_bucket: companyCoverageBucketSchema.optional(),
  companyType: z.string().optional(),
  company_type: z.string().optional(),
  aiInvolvement: z.string().optional(),
  ai_involvement: z.string().optional(),
  whyMatched: z.unknown().optional(),
  why_matched: z.unknown().optional(),
  evidenceRefs: z.array(z.string()).optional(),
  evidence_refs: z.array(z.string()).optional(),
  risk: z.array(z.string()).optional(),
}).passthrough().describe(
  "One standardized external discovery candidate. company and one of role, exactRole, exact_role or role_title are required by runtime validation.",
);

const roleHypothesisSchema = z.object({
  id: z.string(),
  role_or_family: z.string(),
  capability_root_refs: z.array(z.string()).optional(),
  company_targets: z.array(z.string()).optional(),
  search_terms: z.record(z.string(), z.unknown()).optional(),
}).passthrough();

const discoverySchema = z.object({
  provider: z.enum(["EXTERNAL_WEB_DISCOVERY_HANDOFF"]).optional(),
  providerRun: z.record(z.string(), z.unknown()).optional().describe(
    "Optional external executor provenance such as executor, observed_at or search_id.",
  ),
  capabilityProfile: z.record(z.string(), z.unknown()).optional(),
  roleHypotheses: z.array(roleHypothesisSchema).optional().describe(
    "Role-family hypotheses used to create the external-Web discovery handoff.",
  ),
  candidates: z.array(discoveryCandidateSchema).optional().describe(
    "Standardized results returned by the external Web executor. Candidate-only result-ingest calls are accepted.",
  ),
  locationScope: z.array(z.unknown()).optional(),
  companyTypes: z.array(z.string()).optional(),
  candidateConstraints: z.union([
    z.record(z.string(), z.unknown()),
    z.array(z.string()),
  ]).optional(),
  marketScope: z.array(z.unknown()).optional(),
  inputRefs: z.array(z.string()).optional(),
  taxonomyRef: z.string().optional(),
}).passthrough().describe(
  "Market-discovery request or external result-ingest payload.",
);

const scanConfigCompatibilitySchema = z.object({
  mode: scanModeSchema.optional(),
  discovery: discoverySchema.optional(),
}).strict().describe(
  "Compatibility envelope for clients that expose one scanConfig object. It accepts only mode and discovery; configured source adapters, URLs and limits cannot be overridden.",
);

const normalizeToolRequest = ({ mode, discovery, scanConfig }) => {
  if (mode && scanConfig?.mode && mode !== scanConfig.mode) {
    throw new Error("conflicting-mode-input");
  }
  if (discovery && scanConfig?.discovery) {
    throw new Error("conflicting-discovery-input");
  }
  return {
    mode: mode ?? scanConfig?.mode ?? "hybrid_discovery",
    discovery: discovery ?? scanConfig?.discovery,
  };
};

const scanSummarySchema = z.object({
  scan_id: z.string().nullable().optional(),
  captured_at: z.string().nullable().optional(),
  source_results: z.array(z.record(z.string(), z.unknown())).optional(),
  raw_record_count: z.number().int().nonnegative(),
  deduped_count: z.number().int().nonnegative(),
  screening_counts: z.record(z.string(), z.number().int().nonnegative()),
  review_packet_count: z.number().int().nonnegative(),
  review_state_counts: z.record(z.string(), z.number().int().nonnegative()),
  review_priority_candidates: z.array(z.record(z.string(), z.unknown())),
  pool_mode: z.enum(["BROAD", "FOCUSED"]),
  retained_candidate_count: z.number().int().nonnegative(),
  career_context_source: z.string().nullable().optional(),
  career_context_version: z.string().nullable().optional(),
  external_action: z.boolean(),
  human_review_required: z.boolean(),
});

const scanOutputSchema = z.object({
  schema_version: z.string(),
  operation: z.literal("SCAN_AND_REVIEW"),
  mode: z.enum(["configured_review", "market_discovery", "hybrid_discovery"]),
  candidate_status: z.string(),
  scan_config_source: z.enum([
    "CURRENT_CONFIGURED_SOURCES",
    "DISCOVERY_INPUT",
    "CURRENT_CONFIGURED_SOURCES_PLUS_DISCOVERY_INPUT",
    "CALLER_SUPPLIED",
  ]),
  source_scope: z.object({
    immutable_for_pool_mode: z.literal(true),
    sources: z.array(z.record(z.string(), z.unknown())),
    fingerprint: z.string(),
  }),
  pool_view: z.object({
    mode: z.enum(["BROAD", "FOCUSED"]),
    retained_states: z.array(z.string()),
    retained_candidate_count: z.number().int().nonnegative(),
    candidate_keys: z.array(z.string()),
    candidates: z.array(z.object({
      company: z.string().nullable().optional(),
      external_job_id: z.string().nullable().optional(),
      role: z.string().nullable().optional(),
      location: z.unknown().optional(),
      verification_status: z.string().nullable().optional(),
      screening_state: z.string().nullable().optional(),
      screening_reasons: z.unknown().optional(),
      source_url: z.string().nullable().optional(),
      exact_role: z.string().nullable().optional(),
      official_source: z.unknown().optional(),
      live_status: z.string().nullable().optional(),
      qualification_facts: z.unknown().optional(),
      deadline: z.unknown().optional(),
      application_rule: z.unknown().optional(),
      provenance: z.unknown().optional(),
      uncertainty: z.unknown().optional(),
      role_family: z.string().nullable().optional(),
      company_coverage_bucket: z.string().nullable().optional(),
      ai_involvement: z.string().nullable().optional(),
      why_matched: z.unknown().optional(),
      evidence_refs: z.unknown().optional(),
      risk: z.unknown().optional(),
      next_action: z.unknown().optional(),
    })),
    source_scope_changed: z.literal(false),
  }),
  discovery: z.record(z.string(), z.unknown()).optional(),
  summary: scanSummarySchema,
  review: z.record(z.string(), z.unknown()).optional(),
  scan: z.record(z.string(), z.unknown()).optional(),
  boundary: z.object({
    read_only_public_sources: z.boolean(),
    canonical_write: z.boolean(),
    application: z.boolean(),
    login: z.boolean(),
    upload: z.boolean(),
    external_contact: z.boolean(),
    cv_edit: z.boolean(),
    portfolio_edit: z.boolean(),
  }),
});

const serverInfoOutputSchema = z.object({
  service: z.string(),
  version: z.string(),
  stateless: z.boolean(),
  contextProvider: z.string(),
  contextPersistenceWrites: z.boolean(),
  supportedAdapters: z.record(z.string(), z.string()),
  discoveryModes: z.array(z.string()),
  genericDiscovery: z.object({
    provider: z.string(),
    execution: z.literal("EXTERNAL"),
    builtInWebDiscovery: z.literal(false),
    resultIngest: z.string(),
    dedicatedAdaptersAreMarketBoundary: z.literal(false),
    officialExactRoleVerification: z.string(),
  }),
  marketDiscoveryDefaults: z.object({
    profileId: z.string(),
    profileVersion: z.string(),
    source: z.string(),
    companySizePriority: z.literal("NEUTRAL"),
    bigTechPriority: z.literal("NO_PRIORITY_BONUS"),
    configuredAdapterPriority: z.literal("NO_PRIORITY_BONUS"),
    familiarBrandPriority: z.literal("NO_PRIORITY_BONUS"),
    companyCoverageBuckets: z.array(z.string()),
    decisionPriority: z.array(z.string()),
    locationOrdering: z.array(z.string()),
    coverageSafeguard: z.literal("DISCOVERY_COVERAGE_IMBALANCE"),
  }),
  configuredSourcePreset: z.string(),
  externalAction: z.boolean(),
  application: z.boolean(),
  canonicalWrite: z.boolean(),
});

export const createCareerMcpServer = () => {
  const server = new McpServer(
    { name: "career-intelligence-remote", version: "0.2.10" },
    {
      instructions:
        "Read-only Career Intelligence scanning and discovery. career.scan_and_review supports configured_review, market_discovery and hybrid_discovery. Configured adapters improve verification for known sources but do not define the market boundary. Market discovery uses public neutral defaults and accepts a caller-scoped market_discovery_profile. If returned results are materially concentrated in a configured head-company bucket without supporting market evidence, mark DISCOVERY_COVERAGE_IMBALANCE and request one bounded supplemental external-Web pass. This runtime has no built-in generic Web browser; market discovery uses an external-Web handoff and standardized result ingest. Never treat discovery or triage as final Fit or submission authority.",
      cacheHints: { "tools/list": { ttlMs: 60_000, cacheScope: "private" } },
    },
  );

  server.registerTool(
    "career.server_info",
    {
      title: "Get Career Intelligence server capabilities",
      description:
        "Return read-only runtime boundaries, configured official source adapters, discovery modes and the generic external-Web handoff capability. Dedicated adapters improve verification quality but do not define the discoverable market.",
      inputSchema: z.object({}),
      outputSchema: serverInfoOutputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => asToolResult({
      service: "career-intelligence-remote",
      version: "0.2.10",
      stateless: true,
      contextProvider: "CALLER_SCOPED_OR_HOST_CONFIGURED_CONTEXT",
      contextPersistenceWrites: false,
      supportedAdapters: {
        sap: "discovery-and-detail",
        tencent: "detail",
        kuaishou: "social-discovery-and-detail",
      },
      discoveryModes: ["configured_review", "market_discovery", "hybrid_discovery"],
      genericDiscovery: {
        provider: "EXTERNAL_WEB_DISCOVERY_HANDOFF",
        execution: "EXTERNAL",
        builtInWebDiscovery: false,
        resultIngest: "career.scan_and_review.discovery.candidates",
        dedicatedAdaptersAreMarketBoundary: false,
        officialExactRoleVerification: "REQUIRED_WHERE_AVAILABLE",
      },
      marketDiscoveryDefaults: {
        profileId: "PUBLIC_NEUTRAL_MARKET_DISCOVERY_PROFILE",
        profileVersion: "0.2.10",
        source: "PUBLIC_NEUTRAL_DEFAULT",
        companySizePriority: "NEUTRAL",
        bigTechPriority: "NO_PRIORITY_BONUS",
        configuredAdapterPriority: "NO_PRIORITY_BONUS",
        familiarBrandPriority: "NO_PRIORITY_BONUS",
        companyCoverageBuckets: [
          "LARGE_INTERNET_TECH",
          "MID_LARGE_TECH",
          "MATURE_SME",
          "SAAS_ENTERPRISE_SOFTWARE",
          "AI_NATIVE_APPLICATION",
          "CONSUMER_TECH",
          "GAME_CONTENT",
          "FOREIGN_INTERNATIONAL_TEAM",
          "TRADITIONAL_DIGITAL_INNOVATION",
          "STARTUP_SCALEUP",
        ],
        decisionPriority: [],
        locationOrdering: [],
        coverageSafeguard: "DISCOVERY_COVERAGE_IMBALANCE",
      },
      configuredSourcePreset: "CURRENT_CONFIGURED_SOURCES_V01",
      externalAction: false,
      application: false,
      canonicalWrite: false,
    }),
  );
  server.registerTool(
    "career.scan_and_review",
    {
      title: "Scan public jobs and create Career review packets",
      description:
        "Run one bounded read-only scan/review cycle. configured_review preserves the configured adapter preset. market_discovery returns an external-Web discovery handoff and ingests standardized results for any company. hybrid_discovery combines both paths and deduplicates them. Dedicated adapters improve source-specific verification but never define the market boundary. Public defaults are company-size, big-tech, brand and adapter neutral; a caller may supply careerContext.market_discovery_profile. Returned-batch concentration can trigger DISCOVERY_COVERAGE_IMBALANCE plus one same-scope supplemental external-Web handoff. The tool does not browse by itself, apply, log in, upload, edit CV/Portfolio, or write Career canonical state.",
      inputSchema: z.object({
        poolMode: z.enum(["BROAD", "FOCUSED"]).default("BROAD"),
        careerContext: careerContextSchema.default({}),
        mode: scanModeSchema.optional().describe(
          "Requested routing mode. Omitted requests remain backward-compatible and default to hybrid_discovery.",
        ),
        discovery: discoverySchema.optional(),
        scanConfig: scanConfigCompatibilitySchema.optional(),
        detailLevel: z.enum(["summary", "review", "full"]).default("review"),
      }),
      outputSchema: scanOutputSchema,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    async ({
      poolMode,
      careerContext,
      mode,
      discovery,
      scanConfig,
      detailLevel,
    }) => {
      try {
        const normalized = normalizeToolRequest({ mode, discovery, scanConfig });
        const result = await runCareerScan({
          careerContext,
          poolMode,
          mode: normalized.mode,
          discovery: normalized.discovery,
        });
        return asToolResult(trimResult(result, detailLevel));
      } catch (error) {
        return asToolError(
          "scan-failed",
          error instanceof Error ? error.message : "unknown-error",
        );
      }
    },
  );

  return server;
};

const handler = createMcpHandler(
  () => createCareerMcpServer(),
  { legacy: "stateless", responseMode: "auto" },
);
const nodeRequestToWebRequest = async (request, host) => {
  const chunks = [];
  for await (const chunk of request) chunks.push(Buffer.from(chunk));
  const body = Buffer.concat(chunks);
  const headers = new Headers();
  for (const [name, value] of Object.entries(request.headers)) {
    if (value !== undefined) {
      headers.set(name, Array.isArray(value) ? value.join(", ") : value);
    }
  }
  return new Request(`http://${host}${request.url}`, {
    method: request.method,
    headers,
    body: body.length > 0 && request.method !== "GET" && request.method !== "HEAD"
      ? body
      : undefined,
    duplex: "half",
  });
};

const writeWebResponse = async (response, nodeResponse) => {
  nodeResponse.statusCode = response.status;
  response.headers.forEach((value, key) => nodeResponse.setHeader(key, value));
  if (!response.body) {
    nodeResponse.end();
    return;
  }
  const reader = response.body.getReader();
  try {
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      nodeResponse.write(Buffer.from(next.value));
    }
  } finally {
    reader.releaseLock();
    nodeResponse.end();
  }
};
export const startCareerMcpHttpServer = async ({
  host = process.env.CAREER_MCP_HTTP_HOST ?? DEFAULT_HOST,
  port = Number(process.env.CAREER_MCP_HTTP_PORT ?? DEFAULT_PORT),
} = {}) => {
  if (host !== "127.0.0.1") throw new Error("career-mcp-must-bind-loopback");
  const httpServer = createServer(async (request, response) => {
    try {
      const url = new URL(request.url, `http://${request.headers.host ?? `${host}:${port}`}`);
      if (url.pathname === "/healthz") {
        response.writeHead(200, { "content-type": "application/json; charset=utf-8" });
        response.end(JSON.stringify({
          ok: true,
          service: "career-intelligence-remote",
          version: "0.2.10",
          stateless: true,
        }));
        return;
      }
      if (url.pathname !== "/mcp") {
        response.writeHead(404, { "content-type": "application/json; charset=utf-8" });
        response.end(JSON.stringify({ error: "not-found" }));
        return;
      }
      const requestHost = typeof request.headers.host === "string"
        ? request.headers.host
        : `${host}:${port}`;
      const webRequest = await nodeRequestToWebRequest(request, requestHost);
      await writeWebResponse(await handler.fetch(webRequest), response);
    } catch (error) {
      response.writeHead(500, { "content-type": "application/json; charset=utf-8" });
      response.end(JSON.stringify({
        error: "internal-error",
        detail: error instanceof Error ? error.message : "unknown-error",
      }));
    }
  });

  await new Promise((resolvePromise, rejectPromise) => {
    httpServer.once("error", rejectPromise);
    httpServer.listen(port, host, resolvePromise);
  });
  const address = httpServer.address();
  return {
    server: httpServer,
    host,
    port: typeof address === "object" && address ? address.port : port,
  };
};

const isEntrypoint = process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url;
if (isEntrypoint) {
  startCareerMcpHttpServer().then(({ host, port }) => {
    console.error(`[career-mcp] listening on http://${host}:${port}/mcp`);
  }).catch((error) => {
    console.error(`[career-mcp] startup failed: ${error instanceof Error ? error.message : error}`);
    process.exitCode = 1;
  });
}
