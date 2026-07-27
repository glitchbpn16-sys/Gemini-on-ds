import discord
from discord.ext import commands
import google.generativeai as genai
import torch
import os
import asyncio

# --- 1. НАСТРОЙКА КЛЮЧЕЙ И МОДЕЛЕЙ ---

# Берутся из переменных окружения на Render (или из системы)
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    print("ВНИМАНИЕ: GEMINI_API_KEY не найден в переменных окружения!")

# Silero TTS (Озвучка)
device = "cuda" if torch.cuda.is_available() else "cpu"
tts_model, _ = torch.hub.load(
    repo_or_dir='snakers4/silero-models',
    model='silero_tts',
    language='ru',
    speaker='v3_1_ru'
)
tts_model.to(device)

# --- 2. НАСТРОЙКА DISCORD БОТА ---

intents = discord.Intents.default()
intents.message_content = True  # Чтение сообщений

bot = commands.Bot(command_prefix="!", intents=intents)

def text_to_speech(text, output_file="response.wav"):
    """Генерация голоса из текста"""
    tts_model.save_wav(
        text=text,
        speaker='kseniya',  # Доступные голоса: aidar, baya, kseniya, xenia, eugene
        sample_rate=48000,
        audio_path=output_file
    )
    return output_file

@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} успешно запущен и готов к работе 24/7!')

@bot.event
async def on_message(message):
    # Игнорируем свои же сообщения
    if message.author == bot.user:
        return

    # Логика сработки на слово "здорово"
    if "здорово" in message.content.lower():
        prompt = message.content.lower().replace("здорово", "").strip()
        if not prompt:
            prompt = "Привет! Чем занимаешься?"

        # Запрос к Gemini
        try:
            response = gemini_model.generate_content(prompt)
            bot_text = response.text
        except Exception as e:
            bot_text = "Ошибка при запросе к нейросети."
            print(f"Ошибка Gemini: {e}")

        # Ответ в чат
        await message.channel.send(bot_text)

        # Если пользователь в голосовом канале — бот зайдет и озвучит
        if message.author.voice:
            voice_channel = message.author.voice.channel
            try:
                vc = await voice_channel.connect()
                audio_file = text_to_speech(bot_text)

                vc.play(discord.FFmpegPCMAudio(audio_file))
                
                while vc.is_playing():
                    await asyncio.sleep(1)
                await vc.disconnect()
            except Exception as e:
                print(f"Ошибка голосового подключения: {e}")

    await bot.process_commands(message)

# Запуск бота
if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
else:
    print("ОШИБКА: DISCORD_BOT_TOKEN не задан!")