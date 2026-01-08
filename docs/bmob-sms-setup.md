# Bmob 短信服务配置指南

## 1. 注册 Bmob 账号

1. 访问 [Bmob官网](https://www.bmobapp.com/)
2. 注册账号并登录
3. 创建新应用

## 2. 获取配置信息

在 Bmob 控制台中获取：
- **Application ID**：应用的唯一标识
- **REST API Key**：REST API 密钥

## 3. 配置环境变量

在项目根目录的 `.env` 文件中添加：

```bash
# Bmob短信服务配置
BMOB_APP_ID=你的Application_ID
BMOB_REST_KEY=你的REST_API_Key
```

## 4. 短信模板配置

默认短信模板：
```
您的验证码是%%smscode%%，有效期为%%ttl%%分钟。请不要把验证码泄露给其他人。
```

可以在 `src/bmob.js` 中修改模板内容。

## 5. 测试短信功能

### 开发环境测试
如果未配置 Bmob 密钥，系统会自动使用模拟模式：
- 验证码会在控制台输出
- API 响应中包含 `mockCode` 字段

### 生产环境测试
配置正确的 Bmob 密钥后：
1. 调用 `/api/auth/sms/send` 发送验证码
2. 调用 `/api/auth/sms/verify` 验证登录

## 6. API 接口

### 发送验证码
```javascript
POST /api/auth/sms/send
Content-Type: application/json

{
  "phone": "13800138000"
}
```

### 验证登录
```javascript
POST /api/auth/sms/verify
Content-Type: application/json

{
  "phone": "13800138000",
  "code": "123456"
}
```

## 7. 错误处理

常见错误码：
- `400`: 手机号格式错误或验证码错误
- `429`: 发送频率过快，需要等待
- `500`: 网络错误或服务异常

## 8. 注意事项

1. **费用**：Bmob 短信服务按条收费，请注意控制成本
2. **频率限制**：默认同一手机号 60 秒内只能发送一次
3. **有效期**：验证码默认 5 分钟有效
4. **安全性**：生产环境请妥善保管 API 密钥