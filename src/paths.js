import path from "path";
import { fileURLToPath } from "url";

// 项目根目录（src/ 的上一级），供各模块拼接静态资源/模板路径
export const ROOT_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
