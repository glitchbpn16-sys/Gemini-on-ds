# Glitch AI Bridge

Единое ядро мультимодельного помощника для Discord, Telegram и игровых/сообщественных модов.

## Возможности

- **OpenAI** через официальный Responses API.
- **Claude** через Anthropic Messages API.
- **Gemini** через Gemini Developer API.
- **Grok** через совместимый chat-completions API xAI.
- **OpenRouter** через единый API для выбора моделей разных поставщиков.
- **Groq**, **DeepSeek**, **Mistral** и **Cloudflare Workers AI** через совместимый Chat Completions API.
- Discord slash-команды: `/ask`, `/provider`, `/providers`, `/clear`.
- Telegram: `/ask`, `/provider`, `/providers`, `/clear` и обычные сообщения в личном чате.
- Bearer-защищённый HTTP endpoint для интеграции с модами и собственными серверами: `POST /v1/mods/message`.
- Контекст последних сообщений в оперативной памяти; по умолчанию он не записывается на диск.
- Ограничение длины запросов и частоты сообщений.
- Не требует загрузки PyTorch/Whisper при старте; голосовые функции будут отдельным необязательным модулем.

## Требования

Python 3.12+ и собственные токены платформ/API. Одновременно можно включить одну или несколько платформ.

## Запуск

1. Скопируй `.env.example` в `.env`.
2. Заполни только те переменные, которые действительно используешь.
3. Установи зависимости: `python -m pip install -r requirements.txt`.
4. Запусти: `python bot.py`.

Минимальная конфигурация требует:
- один AI API key и соответствующую модель;
- хотя бы один токен платформы: Discord, Telegram или `MODS_API_TOKEN`.

Ключи должны храниться только в локальном `.env` или в Secret/Environment Variables хостинга. Не вставляй их в исходники, README, скриншоты, сообщения или GitHub Issues. Если ключ уже попадал в публичный репозиторий, отзови его у провайдера и выпусти новый.

## Провайдеры и модели

| Провайдер | Переменные | API / endpoint | Бесплатность |
|---|---|---|---|
| OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL` | Responses API | API отдельно оплачивается |
| Claude | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Messages API | API отдельно оплачивается |
| Gemini | `GEMINI_API_KEY`, `GEMINI_MODEL` | Gemini Developer API | Бесплатный уровень для отдельных моделей, с лимитами и компромиссом по приватности |
| Grok | `XAI_API_KEY`, `XAI_MODEL` | xAI Chat Completions | Не считать бесплатным |
| OpenRouter | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | OpenAI-compatible Chat Completions | Есть бесплатные маршруты с суточными лимитами |
| Groq | `GROQ_API_KEY`, `GROQ_MODEL` | `https://api.groq.com/openai/v1` | Есть бесплатный доступ с переменными квотами; точные лимиты смотри в Console |
| DeepSeek | `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL` | `https://api.deepseek.com` | API оплачивается по токенам |
| Mistral | `MISTRAL_API_KEY`, `MISTRAL_MODEL` | `https://api.mistral.ai/v1` | Не считать постоянным бесплатным API; доступность trial зависит от аккаунта |
| Cloudflare Workers AI | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_MODEL` | Workers AI OpenAI-compatible endpoint | 10 000 Neurons/day на Workers Free; некоторые модели требуют платного плана |
| Custom / Ollama | `CUSTOM_OPENAI_BASE_URL`, `CUSTOM_OPENAI_API_KEY`, `CUSTOM_OPENAI_MODEL` | Любой совместимый endpoint | Локальная модель без платы за токены; нагрузка ложится на твоё устройство/ПК |

Стартовые model ID сверены с текущими каталогами API на 14 ноября 2026 года: `gpt-6-astra`, `claude-sonnet-5-5`, `gemini-3.8-flash`, `grok-4.7` и `openrouter/free`. Доступность всё равно зависит от аккаунта и региона; можно заменить любой ID в `.env`. Провайдеры меняют модели, тарифы и лимиты.

Для выбора провайдера:
- Discord: `/provider openrouter`
- Telegram: `/provider openrouter`

Доступные имена: `openai`, `anthropic`, `gemini`, `xai`, `openrouter`, `groq`, `deepseek`, `mistral`, `cloudflare`, `custom`. Для Cloudflare обязательно нужны и API token, и Account ID. Не настроенные ключами провайдеры не показываются. Если `AI_DEFAULT_PROVIDER` не задан, приложение выбирает OpenRouter, когда задан его ключ; иначе выбирает первый настроенный провайдер. OpenRouter по умолчанию использует `openrouter/free`, который выбирает совместимую бесплатную модель из доступных. Бесплатный доступ ограничен; лимиты, доступность и задержки меняются. Не включай платный fallback без отдельной проверки тарифа.

Резервные провайдеры включаются только явно через `AI_FALLBACK_ORDER=openrouter,openai`. Учитывай, что fallback может вызвать платный API и дополнительный расход.

## Discord

Создай Discord application и bot в Developer Portal. Добавь бота на свой сервер с минимальными разрешениями, необходимыми для slash-команд. Этот проект использует slash-команды и не включает privileged Message Content Intent. Не выдавай боту Administrator без необходимости.

После этого сохрани bot token как `DISCORD_BOT_TOKEN` в `.env` или в secrets хостинга. Команды синхронизируются при запуске.

## Telegram

Создай собственного бота через официальный BotFather и помести его token в `TELEGRAM_BOT_TOKEN`. В личном чате бот отвечает на обычный текст. В группах он отвечает на команды или сообщения с упоминанием бота.

## Интеграция модов и серверов

Endpoint активируется только при наличии `MODS_API_TOKEN`.

```http
POST /v1/mods/message
Authorization: Bearer YOUR_MODS_API_TOKEN
Content-Type: application/json
```

```json
{
  "server_id": "my-server",
  "room_id": "general",
  "user_id": "player-42",
  "message": "Объясни правила сервера",
  "provider": "openrouter"
}
```

Ответ:

```json
{
  "provider": "openrouter",
  "reply": "..."
}
```

Используй HTTPS перед публичным развёртыванием. Ограничь endpoint на уровне reverse proxy, добавь allowlist серверов и настрой rate limits. Не передавай API-токен мода в клиентский код игры.

## Контекст и приватность

- Контекст разделён по чатам и пользователям, хранится только в памяти процесса и исчезает при перезапуске.
- Команда `/clear` очищает контекст соответствующего пользователя/чата.
- По умолчанию не сохраняются тексты сообщений в файлы и не отправляются в отдельную базу данных.
- Запросы передаются выбранному AI-провайдеру; учитывай его условия обработки данных и тарифы.
- Ограничитель по умолчанию: 8 запросов за 60 секунд на conversation key.
- Ответы отправляются без автоматического разрешения массовых упоминаний Discord.

## CI и контейнер

GitHub Actions выполняет компиляцию Python и тесты при push/PR. Для self-hosting доступен Dockerfile.

```bash
docker build -t glitch-ai-bridge .
docker run --env-file .env glitch-ai-bridge
```

Не публикуй порт mod API напрямую без HTTPS и защиты токеном.

## Что пока не обещается

- Нет автоматически полученных или встроенных ключей OpenAI/Anthropic/Google/xAI/OpenRouter.
- Нет бесплатного или безлимитного доступа к коммерческим моделям.
- Нет автоматического деплоя: для него нужны твои собственные токены платформ и выбранный хостинг.
- Нет привязки к конкретной игре/мод-платформе: HTTP adapter — универсальная основа, а нативный плагин потребует спецификации конкретной игры.
- Нет голосового Discord/Telegram, генерации изображений, файлового поиска и постоянной памяти. Эти функции должны подключаться отдельными модулями и проверяться отдельно.

## Лицензия

Добавь лицензию перед публичным использованием и укажи авторство/лицензии сторонних зависимостей.


## Универсальный custom provider

Можно подключить локальный или удалённый сервис, который реализует формат OpenAI Chat Completions:

- `CUSTOM_OPENAI_BASE_URL` — базовый URL API, обычно с суффиксом `/v1`.
- `CUSTOM_OPENAI_API_KEY` — ключ, если сервер его требует.
- `CUSTOM_OPENAI_MODEL` — точное имя модели на стороне сервера.

Пример локального Ollama-подобного сервиса: `http://127.0.0.1:11434/v1`. Удалённые адреса должны использовать HTTPS. Небезопасный HTTP допускается только на loopback; не публикуй локальные endpoints в интернет. Это подключает любой **совместимый** endpoint, а не любую закрытую систему или OAuth-схему.

## MCP Connect mode

MCP — стандартный интерфейс для того, чтобы совместимые ИИ-клиенты могли обнаружить инструменты и вызывать их. В этом проекте сервер использует Streamable HTTP и по умолчанию слушает только loopback.

Для включения:
1. Сгенерируй отдельный длинный случайный токен и задай `MCP_API_TOKEN`.
2. Установи `MCP_ENABLED=true`.
3. Оставь `MCP_HOST=127.0.0.1`, если подключение идёт с того же устройства.
4. Перезапусти сервис и подключи MCP-клиент к `http://127.0.0.1:8081/mcp` с заголовком `Authorization: Bearer <твой токен>`.

Доступны только два инструмента: `list_ai_providers` и `ask_ai`. Произвольный shell, управление системой, чтение приватных файлов и команды без подтверждения здесь не открываются. Конфигурация отклоняет любой `MCP_HOST`, кроме `127.0.0.1` и `localhost`, потому что встроенный MCP endpoint не завершает TLS. Для сетевого доступа с другого устройства используй отдельный HTTPS reverse proxy и правила доступа; не выставляй MCP порт напрямую.

## Режим экономии ресурсов

Сервис рассчитан на ограниченные устройства и небольшие серверы:
- по умолчанию не запускает периодические фоновые задачи и не опрашивает устройства;
- ограничивает одновременные AI-запросы до двух;
- имеет сетевой тайм-аут и настраиваемую частоту запросов;
- ограничивает размер входного сообщения и длину ответа;
- держит короткий контекст только в оперативной памяти;
- не включает резервные платные API автоматически — fallback должен быть задан явно;
- MCP включён только по явному флагу и локально привязан к loopback по умолчанию.

Для Android-приложений Glitch Agent Connect и Jelly Bridge действует ещё более строгий профиль: без постоянного wake lock, фонового polling, автозапуска ИИ-агентов и непрерывного сканирования медиатеки; тяжёлые задачи только по действию пользователя, одна операция экспорта за раз, отмена/пауза, уменьшенный preview и термальный режим на слабых устройствах. Исходные медиа не перезаписываются автоматически.

## Free API limits and provider safety

No provider offers unlimited free hosted inference. The free routes may have low throughput, daily caps, queue delays, model availability changes, or provider-side data-use terms.

- **OpenRouter Free:** use `OPENROUTER_MODEL=openrouter/free` or an explicitly listed `:free` model. The published limit for `:free` variants is 20 requests/minute and 50/day. Failed attempts count against the daily quota. A displayed $0 model is not always a `:free` model and may still require a funded account.
- **Google AI Studio:** selected Gemini models have free input/output tokens. Google marks free-tier content as usable to improve its products. Do not submit private source code, tokens, passwords, private messages or personal data through this tier.
- **Groq:** a free access tier exists, but rate limits are model- and account-specific. The model quota shown in Groq Console is authoritative; do not assume a single global limit.
- **Cloudflare Workers AI:** the Workers Free plan includes 10,000 Neurons/day, resetting at 00:00 UTC. Consumption varies by model; some newer models require a paid plan or prepaid credits.
- **Cerebras:** the current trial advertises $5 in promotional credits, but receiving them requires adding a valid payment method; it is therefore not included in the no-card free setup.
- **Hugging Face Inference Providers:** Free accounts currently have no included monthly inference credits; use a paid credit balance or another provider.
- **DeepSeek, Mistral, OpenAI, Anthropic and xAI:** treat API calls as billable unless the provider dashboard explicitly shows a free trial or zero-cost quota for that exact account/model.
- **Local Ollama/llama.cpp/LM Studio:** no per-token API charge, but inference uses local RAM, storage, processor and battery. On a low-memory PC or phone, smaller quantized models may be necessary.

Official references:
- Gemini pricing and data-use note: https://ai.google.dev/gemini-api/docs/pricing
- OpenRouter free models and request caps: https://openrouter.ai/collections/free-models/
- Groq current rate limits: https://console.groq.com/docs/rate-limits
- Cloudflare Workers AI pricing: https://developers.cloudflare.com/workers-ai/platform/pricing/
- DeepSeek Responses API and current model/pricing details: https://api-docs.deepseek.com/guides/responses_api/ and https://api-docs.deepseek.com/quick_start/pricing/
- Mistral Chat Completions and model list: https://docs.mistral.ai/api/endpoint/chat/ and https://docs.mistral.ai/api/endpoint/models
- Cerebras trial terms: https://www.cerebras.ai/pricing
- Hugging Face inference-provider pricing: https://huggingface.co/docs/inference-providers/pricing

The bot does not add a payment method, buy credits, enable paid fallbacks, or bypass quotas. Keep fallback disabled unless every provider in the fallback order is acceptable to incur charges.
