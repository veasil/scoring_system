import fetch from "node-fetch";

export class BmobSMS {
  constructor(appId, restKey) {
    this.appId = appId;
    this.restKey = restKey;
    this.baseUrl = "https://api.bmobcloud.com/1";
  }

  async sendSmsCode(phone, template) {
    const body = { mobilePhoneNumber: phone };
    if (template) body.template = template;

    const response = await fetch(`${this.baseUrl}/requestSmsCode`, {
      method: "POST",
      headers: {
        "X-Bmob-Application-Id": this.appId,
        "X-Bmob-REST-API-Key": this.restKey,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: "请求失败" }));
      throw new Error(error.error || "发送短信失败");
    }

    return await response.json();
  }

  async verifySmsCode(phone, code) {
    const response = await fetch(`${this.baseUrl}/verifySmsCode/${code}`, {
      method: "POST",
      headers: {
        "X-Bmob-Application-Id": this.appId,
        "X-Bmob-REST-API-Key": this.restKey,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ mobilePhoneNumber: phone })
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: "验证失败" }));
      throw new Error(error.error || "验证码错误");
    }

    return await response.json();
  }
}