import { BmobSMS } from "../bmob.js";
import { config } from "../config.js";

// Bmob 短信客户端：惰性初始化（在 loadConfig() 之后调用 initSms()）。
// 未配置 Bmob 时为 null，走开发环境的内存模拟验证码（mockCode）。
export let bmobSMS = null;
export function initSms() {
  bmobSMS = config.BMOB_APP_ID && config.BMOB_REST_KEY
    ? new BmobSMS(config.BMOB_APP_ID, config.BMOB_REST_KEY)
    : null;
  return bmobSMS;
}

// 开发环境验证码存储：phone => { code, expiresAt, lastSent }
export const smsStore = new Map();
// 验证码有效期 / 重发间隔，可用环境变量覆盖（默认 5 分钟 / 60 秒；测试可设 0）
export const SMS_CODE_TTL_MS = Number(process.env.SMS_CODE_TTL_MS ?? 5 * 60 * 1000);
export const SMS_RESEND_INTERVAL_MS = Number(process.env.SMS_RESEND_INTERVAL_MS ?? 60 * 1000);

export function normalizePhone(input) {
  if (!input) return "";
  return String(input).replace(/\D/g, "");
}

export function generateSmsCode() {
  return String(Math.floor(100000 + Math.random() * 900000));
}

/**
 * 发送验证码。
 * @returns {Promise<{ok:boolean, status?:number, error?:string, mockCode?:string, smsId?:string, expiresInSeconds?:number}>}
 */
export async function sendCode(phone) {
  if (!bmobSMS) {
    const now = Date.now();
    const existing = smsStore.get(phone);
    if (existing && now - existing.lastSent < SMS_RESEND_INTERVAL_MS) {
      const waitSec = Math.ceil((SMS_RESEND_INTERVAL_MS - (now - existing.lastSent)) / 1000);
      return { ok: false, status: 429, error: `请等待 ${waitSec} 秒后重试` };
    }
    const mockCode = generateSmsCode();
    smsStore.set(phone, { code: mockCode, expiresAt: now + SMS_CODE_TTL_MS, lastSent: now });
    console.log(`📱 模拟短信验证码 [${phone}]: ${mockCode}`);
    return { ok: true, mockCode, expiresInSeconds: Math.floor(SMS_CODE_TTL_MS / 1000) };
  }
  try {
    const result = await bmobSMS.sendSmsCode(phone);
    return { ok: true, smsId: result.smsId };
  } catch (e) {
    return { ok: false, status: 400, error: e.message };
  }
}

/**
 * 校验验证码。
 * @param {boolean} [opts.consume=true] 校验成功后是否消费（开发环境）。
 *        登录流程 consume=true（防重放）；独立的预校验端点 consume=false。
 * @returns {Promise<{ok:boolean, error?:string}>}
 */
export async function verifyCode(phone, code, { consume = true } = {}) {
  if (!bmobSMS) {
    const stored = smsStore.get(phone);
    if (!stored) return { ok: false, error: "验证码不存在或已过期" };
    if (Date.now() > stored.expiresAt) {
      smsStore.delete(phone);
      return { ok: false, error: "验证码已过期" };
    }
    if (stored.code !== String(code)) return { ok: false, error: "验证码错误" };
    if (consume) smsStore.delete(phone);
    return { ok: true };
  }
  try {
    await bmobSMS.verifySmsCode(phone, code);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}
