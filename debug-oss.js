import dotenv from "dotenv";
import OSS from "ali-oss";

dotenv.config();

const client = new OSS({
    region: (process.env.OSS_REGION || "oss-cn-beijing").startsWith("oss-") ? process.env.OSS_REGION : `oss-${process.env.OSS_REGION}`,
    accessKeyId: process.env.ALIBABA_CLOUD_ACCESS_KEY_ID,
    accessKeySecret: process.env.ALIBABA_CLOUD_ACCESS_KEY_SECRET,
    secure: true
});

client.listBuckets().then((result) => {
    console.log("--- BUCKET LIST START ---");
    if (result.buckets) {
        result.buckets.forEach(b => console.log(b.name, b.region));
    } else {
        console.log("No buckets found.");
    }
    console.log("--- BUCKET LIST END ---");
}).catch(e => {
    console.log("ERROR:", e.code, e.message);
});
