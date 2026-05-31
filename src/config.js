import dotenv from "dotenv";
import crypto from "crypto";
import { getAllSettings } from "./db.js";

dotenv.config();

// 运行期配置：先用 process.env 填充，loadConfig() 再用数据库 system_settings 覆盖。
// 这是一个常量对象引用，loadConfig() 原地写入，所有 `import { config }` 的模块共享同一份引用，
// 在 loadConfig() 之后读取即可拿到最新值（注意：必须在 await loadConfig() 完成后再读取）。
export const config = {};

// AES-256-CBC 解密（system_settings 中以 "enc:iv:ciphertext" 形式存储的敏感值）
export function decryptVal(val) {
  if (!val || typeof val !== "string" || !val.startsWith("enc:")) return val;
  const keyHex = process.env.SETTINGS_ENCRYPTION_KEY;
  if (!keyHex) return val;

  try {
    const parts = val.split(":");
    if (parts.length !== 3) return val;

    const key = Buffer.from(keyHex, "hex");
    const iv = Buffer.from(parts[1], "base64");
    const ciphertext = Buffer.from(parts[2], "base64");

    const decipher = crypto.createDecipheriv("aes-256-cbc", key, iv);
    let decrypted = decipher.update(ciphertext);
    decrypted = Buffer.concat([decrypted, decipher.final()]);
    return decrypted.toString("utf-8");
  } catch (e) {
    console.error("Decryption failed:", e.message);
    return val;
  }
}

// 从数据库加载 system_settings 并合并到 config（数据库值优先于 process.env）。
// 必须在 initDb() 之后调用。
export async function loadConfig() {
  const dbSettings = await getAllSettings();
  Object.assign(config, process.env);

  if (dbSettings && dbSettings.length > 0) {
    dbSettings.forEach((s) => {
      if (s.value && String(s.value).trim()) {
        config[s.key] = decryptVal(s.value);
      }
    });
  }
  return config;
}
