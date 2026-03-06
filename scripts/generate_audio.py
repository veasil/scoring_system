import os
import sqlite3
import dashscope
import oss2
import time
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取配置
DB_PATH = os.getenv('CARDS_DB_PATH', './data/cards.db')
DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')
OSS_ACCESS_KEY_ID = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID')
OSS_ACCESS_KEY_SECRET = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
OSS_REGION = os.getenv('OSS_REGION', 'oss-cn-hongkong')
OSS_BUCKET_NAME = os.getenv('OSS_BUCKET_NAME', 'ai5000days-scoring-system-hk')
OSS_ENDPOINT = os.getenv('OSS_ENDPOINT', 'oss-cn-hongkong.aliyuncs.com')

dashscope.api_key = DASHSCOPE_API_KEY

def init_oss_bucket():
    auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)
    return bucket

def get_cards_from_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, event FROM cards")
    cards = cursor.fetchall()
    conn.close()
    return cards

def generate_and_upload_audio(bucket, card_id, text):
    file_name = f'cards_audio/{card_id}.mp3'
    
    print(f"[{card_id}] 正在生成语音: '{text[:20]}...'")
    try:
        # 调用 DashScope Sambert TTS API (使用知楚音色)
        result = dashscope.audio.tts.SpeechSynthesizer.call(
            model='sambert-zhichu-v1',
            text=text,
            sample_rate=48000,
            format='mp3'
        )
        
        if result.get_audio_data() is not None:
            # 上传到 OSS
            print(f"[{card_id}] 语音生成成功，正在上传到 OSS...")
            bucket.put_object(file_name, result.get_audio_data(), headers={'x-oss-object-acl': 'public-read'})
            print(f"[{card_id}] 上传成功: {file_name}")
            return True
        else:
            print(f"[{card_id}] 语音生成失败 (未返回音频数据: {result.get_response()})")
            return False
            
    except Exception as e:
        print(f"[{card_id}] 处理失败: {e}")
        return False

def main():
    if not all([DASHSCOPE_API_KEY, OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET]):
        print("错误: 缺少必要的环境变量 (DASHSCOPE_API_KEY, ALIBABA_CLOUD_ACCESS_KEY_ID, ALIBABA_CLOUD_ACCESS_KEY_SECRET)")
        return
        
    print("初始化 OSS Bucket...")
    bucket = init_oss_bucket()
    
    print("获取卡牌数据...")
    cards = get_cards_from_db()
    print(f"共找到 {len(cards)} 张卡牌。准备开始生成与上传。")
    
    success_count = 0
    for card_id, event_text in cards:
        if not event_text:
            print(f"[{card_id}] 跳过，事件文本为空")
            continue
            
        success = generate_and_upload_audio(bucket, card_id, event_text)
        if success:
            success_count += 1
            
        # 增加延迟以防止 API 频率限制，如果是批量可以适当调整
        time.sleep(1)
        
    print(f"\n处理完成！共成功处理 {success_count}/{len(cards)} 个音频。")

if __name__ == '__main__':
    main()
