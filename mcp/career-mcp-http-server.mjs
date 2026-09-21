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
  existing_roles: z.array(z.record(z.string(), z.unknown())).optional(),
  company_constraints: z.record(
    z.string(),
    z.array(z.record(z.string(), z.unknown())),
  ).optional(),
}).passthrough();

const discoverySchema = z.object({
  capabilityProfile: z.record(z.string(), z.unknown()).optional(),
  roleHypotheses: z.array(z.record(z.string(), z.unknown())).optional(),
  candidates: z.array(z.record(z.string(), z.unknown())).optional(),
  locationScope: z.array(z.unknown()).optional(),
  companyTypes: z.array(z.string()).optional(),
  candidateConstraints: z.record(z.string(), z.unknown()).optional(),
  marketScope: z.array(z.unknown()).optional(),
  inputRefs: z.array(z.string()).optional(),
  taxonomyRef: z.string().optional(),
}).passthrough().optional();

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
      role_family: z.string().nullable().optional(),
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
  configuredSourcePreset: z.string(),
  externalAction: z.boolean(),
  application: z.boolean(),
  canonicalWrite: z.boolean(),
});

export const createCareerMcpServer = () => {
  const server = new McpServer(
    { name: "career-intelligence-remote", version: "0.2.8" },
    {
      instructions:
        "Read-only Career Intelligence scanning and discovery. career.scan_and_review supports configured_review, market_discovery and hybrid_discovery; configured_review keeps the current configured source preset, while discovery modes accept a bounded Capability Profile/Role Hypothesis handoff. Never treat triage as final Fit or submission authority.",
      cacheHints: { "tools/list": { ttlMs: 60_000, cacheScope: "private" } },
    },
  );

  server.registerTool(
    "career.server_info",
    {
      title: "Get Career Intelligence server capabilities",
      description:
        "Return read-only runtime boundaries, context-provider semantics and supported official source adapters. The server may read the local Career continuity snapshot but never writes it.",
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
      version: "0.2.8",
      stateless: true,
      contextProvider: "CURRENT_LOCAL_CONTEXT",
      contextPersistenceWrites: false,
      supportedAdapters: {
        sap: "discovery-and-detail",
        tencent: "detail",
        kuaishou: "social-discovery-and-detail",
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
        "Run one bounded read-only scan cycle using the current configured source preset. This tool cannot change adapters, source URLs, discovery queries or source limits. poolMode only changes which already-discovered candidates are retained in the visible pool; it never changes source scope. Current Career continuity is loaded from the local read-only context provider by default, with careerContext used only as a request-scoped overlay. The tool does not apply, log in, upload, edit CV/Portfolio, or write Career canonical state.",
      inputSchema: z.object({
        poolMode: z.enum(["BROAD", "FOCUSED"]).default("BROAD"),
        careerContext: careerContextSchema.default({}),
        mode: z.enum(["configured_review", "market_discovery", "hybrid_discovery"]).default("hybrid_discovery"),
        discovery: discoverySchema,
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
      detailLevel,
    }) => {
      try {
        const result = await runCareerScan({
          careerContext,
          poolMode,
          mode,
          discovery,
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
          version: "0.2.8",
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
