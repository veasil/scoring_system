import fetch from "node-fetch";

const TOAPIS_BASE_URL = "https://toapis.com";
const TOAPIS_SUPPORTED_RATIOS = new Set([
  "1:1", "3:2", "2:3", "4:3", "3:4", "5:4", "4:5",
  "16:9", "9:16", "2:1", "1:2", "21:9", "9:21"
]);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function gcd(a, b) {
  while (b) {
    [a, b] = [b, a % b];
  }
  return Math.abs(a);
}

export function normalizeDashScopeSize(size = "1024*1024") {
  return String(size || "1024*1024").replace("x", "*");
}

export function normalizeToApisRatio(size = "1:1") {
  const raw = String(size || "1:1").trim();
  if (TOAPIS_SUPPORTED_RATIOS.has(raw)) return raw;

  const match = raw.match(/^(\d+)\s*[x*]\s*(\d+)$/i);
  if (!match) return "1:1";

  const w = Number(match[1]);
  const h = Number(match[2]);
  if (!Number.isFinite(w) || !Number.isFinite(h) || w <= 0 || h <= 0) return "1:1";

  const divisor = gcd(w, h);
  const ratio = `${w / divisor}:${h / divisor}`;
  return TOAPIS_SUPPORTED_RATIOS.has(ratio) ? ratio : "1:1";
}

function dataUriToUpload(dataUri) {
  const match = String(dataUri || "").match(/^data:([^;,]+);base64,(.+)$/);
  if (!match) return null;
  return {
    buffer: Buffer.from(match[2], "base64"),
    filename: `reference-${Date.now()}.${match[1].split("/")[1] || "png"}`,
    mimeType: match[1]
  };
}

function pickErrorMessage(body) {
  if (!body || typeof body !== "object") return String(body || "");
  const msg = body.message || body.error || body.fail_reason;
  if (typeof msg === "string") return msg;
  if (msg && typeof msg === "object") return msg.message || JSON.stringify(msg);
  return JSON.stringify(body);
}

function normalizeToApisBaseUrl(baseUrl) {
  return String(baseUrl || TOAPIS_BASE_URL).replace(/\/+$/, "").replace(/\/v1$/i, "");
}

async function readJsonResponse(resp, label) {
  const text = await resp.text();
  let body;
  try {
    body = text ? JSON.parse(text) : {};
  } catch (_) {
    throw new Error(`${label} 返回非 JSON (${resp.status}): ${text.slice(0, 300)}`);
  }
  if (!resp.ok) {
    throw new Error(`${label} 失败(${resp.status}): ${pickErrorMessage(body)}`);
  }
  return body;
}

async function downloadAsDataUri(imageUrl) {
  const resp = await fetch(imageUrl);
  if (!resp.ok) return { dataUri: "", contentType: "" };
  const arrayBuf = await resp.arrayBuffer();
  const contentType = resp.headers.get("content-type") || "image/png";
  const base64 = Buffer.from(arrayBuf).toString("base64");
  return { dataUri: `data:${contentType};base64,${base64}`, contentType };
}

async function toApisUploadBuffer({ apiKey, baseUrl, buffer, filename, mimeType }) {
  const form = new FormData();
  form.append("file", new Blob([buffer], { type: mimeType || "application/octet-stream" }), filename || "reference.png");

  const resp = await fetch(`${baseUrl}/v1/uploads/images`, {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}` },
    body: form
  });
  const body = await readJsonResponse(resp, "ToAPI 图片上传");
  if (!body.success) {
    throw new Error(`ToAPI 图片上传失败: ${body.message || JSON.stringify(body)}`);
  }
  const url = body?.data?.url;
  if (!url) throw new Error(`ToAPI 图片上传未返回 URL: ${JSON.stringify(body)}`);
  return url;
}

async function collectToApisReferenceUrls({ apiKey, baseUrl, file, body }) {
  const urls = [];
  const appendUrl = (value) => {
    if (typeof value === "string" && /^https?:\/\//i.test(value)) urls.push(value);
  };

  let imageUrls = body?.image_urls || body?.imageUrls || body?.reference_images || body?.referenceImages;
  if (typeof imageUrls === "string") {
    try {
      imageUrls = JSON.parse(imageUrls);
    } catch (_) {
      imageUrls = imageUrls.split(",").map((item) => item.trim()).filter(Boolean);
    }
  }
  if (Array.isArray(imageUrls)) {
    for (const item of imageUrls) {
      if (typeof item === "string") appendUrl(item);
      else if (item && typeof item === "object") appendUrl(item.url);
    }
  }
  appendUrl(body?.imageUrl);
  appendUrl(body?.referenceImageUrl);

  if (file?.buffer) {
    urls.push(await toApisUploadBuffer({
      apiKey,
      baseUrl,
      buffer: file.buffer,
      filename: file.originalname,
      mimeType: file.mimetype
    }));
  }

  const dataUpload = dataUriToUpload(body?.imageDataUri || body?.referenceImageDataUri);
  if (dataUpload) {
    urls.push(await toApisUploadBuffer({ apiKey, baseUrl, ...dataUpload }));
  }

  return [...new Set(urls)];
}

function extractToApisResultUrl(body) {
  const candidates = [];
  const containers = [body];
  if (body?.data && typeof body.data === "object" && !Array.isArray(body.data)) containers.push(body.data);
  if (body?.result && typeof body.result === "object") containers.push(body.result);

  for (const container of containers) {
    if (typeof container?.url === "string") candidates.push(container.url);
    for (const key of ["data", "images", "output"]) {
      const items = container?.[key];
      if (!Array.isArray(items)) continue;
      for (const item of items) {
        if (typeof item?.url === "string") candidates.push(item.url);
      }
    }
    const resultData = container?.result?.data;
    if (Array.isArray(resultData)) {
      for (const item of resultData) {
        if (typeof item?.url === "string") candidates.push(item.url);
      }
    }
  }
  return candidates[0] || "";
}

export async function generateWithToApis({
  apiKey,
  baseUrl = TOAPIS_BASE_URL,
  prompt,
  size = "1:1",
  resolution = "1k",
  quality = "medium",
  model = "gpt-image-2",
  file,
  body = {},
  timeoutMs = 120000
}) {
  if (!apiKey) throw new Error("后端未配置 TOAPIS_API_KEY");

  const cleanBaseUrl = normalizeToApisBaseUrl(baseUrl);
  const referenceUrls = await collectToApisReferenceUrls({ apiKey, baseUrl: cleanBaseUrl, file, body });
  const payload = {
    model,
    prompt,
    n: 1,
    size: normalizeToApisRatio(size),
    resolution,
    quality,
    response_format: "url"
  };
  if (referenceUrls.length > 0) {
    payload.image_urls = referenceUrls;
  }

  const createResp = await fetch(`${cleanBaseUrl}/v1/images/generations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`
    },
    body: JSON.stringify(payload)
  });
  const createBody = await readJsonResponse(createResp, "ToAPI 生图任务创建");
  const taskId = createBody.id || createBody.task_id || createBody?.data?.id;
  if (!taskId) throw new Error(`ToAPI 生图任务未返回 id: ${JSON.stringify(createBody)}`);

  const deadline = Date.now() + timeoutMs;
  let lastStatus = "";
  while (Date.now() < deadline) {
    await sleep(2500);
    const pollResp = await fetch(`${cleanBaseUrl}/v1/images/generations/${taskId}`, {
      headers: { Authorization: `Bearer ${apiKey}` }
    });
    const pollBody = await readJsonResponse(pollResp, "ToAPI 生图任务查询");
    const status = pollBody.status || pollBody?.data?.status;
    lastStatus = status || lastStatus;
    if (status === "failed") {
      throw new Error(`ToAPI 生图任务失败: ${pickErrorMessage(pollBody)}`);
    }
    if (status === "completed") {
      const imageUrl = extractToApisResultUrl(pollBody);
      if (!imageUrl) throw new Error(`ToAPI 生图完成但未返回图片 URL: ${JSON.stringify(pollBody)}`);
      const { dataUri } = await downloadAsDataUri(imageUrl);
      return {
        ok: true,
        provider: "toapis",
        model,
        taskId,
        url: imageUrl,
        dataUri,
        referenceUrls,
        size: payload.size,
        resolution,
        quality
      };
    }
  }

  throw new Error(`ToAPI 生图超时（最后状态: ${lastStatus || "unknown"}）`);
}

export async function generateWithDashScope({ apiKey, model, prompt, size = "1024*1024" }) {
  if (!apiKey) throw new Error("后端未配置 DASHSCOPE_API_KEY");

  const createResp = await fetch(
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
        "X-DashScope-Async": "enable"
      },
      body: JSON.stringify({
        model,
        input: { prompt },
        parameters: { size: normalizeDashScopeSize(size), n: 1 }
      })
    }
  );

  if (!createResp.ok) {
    const t = await createResp.text().catch(() => "");
    throw new Error(`DashScope 生图任务创建失败(${createResp.status}) ${t.slice(0, 200)}`);
  }

  const createData = await createResp.json();
  const taskId = createData?.output?.task_id;
  if (!taskId) throw new Error("DashScope 生图任务未返回 task_id");

  let imageUrl = "";
  const deadline = Date.now() + 60000;
  while (Date.now() < deadline) {
    await sleep(2500);
    const pollResp = await fetch(`https://dashscope.aliyuncs.com/api/v1/tasks/${taskId}`, {
      headers: { Authorization: `Bearer ${apiKey}` }
    });
    if (!pollResp.ok) continue;
    const pollData = await pollResp.json();
    const status = pollData?.output?.task_status;
    if (status === "SUCCEEDED") {
      imageUrl = pollData?.output?.results?.[0]?.url || "";
      break;
    }
    if (status === "FAILED" || status === "UNKNOWN") {
      throw new Error(pollData?.output?.message || "DashScope 生图任务失败");
    }
  }

  if (!imageUrl) throw new Error("DashScope 生图超时，请稍后重试");

  const { dataUri } = await downloadAsDataUri(imageUrl);
  return { ok: true, provider: "dashscope", model, taskId, url: imageUrl, dataUri };
}
