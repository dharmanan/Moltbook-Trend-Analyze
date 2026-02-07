# 🦞🔗 Moltbook ↔ ERC-8004 Bridge Agent

## Proje: "MoltBridge" — Agent Ekosistem İstihbarat Ajanı

> Moltbook'taki AI agent trendlerini analiz edip, ERC-8004 ekosisteminde trustless bir agent olarak raporlayan köprü ajan.

---

## 📋 Proje Özeti

**MoltBridge**, iki yeni ve hızla büyüyen platformu birbirine bağlayan bir istihbarat ajanıdır:

| Platform | Rol | Detay |
|----------|-----|-------|
| **Moltbook** | Veri Kaynağı | AI agentların sosyal ağı — 1.5M+ agent, 42K+ post, 233K+ comment |
| **ERC-8004** | Kimlik & Güven | Ethereum üzerinde trustless agent altyapısı — 24K+ kayıtlı agent |

**Agent Ne Yapar:**
1. Moltbook'ta trending topic'leri, submolt'ları ve tartışmaları tarar
2. NLP ile trend analizi, sentiment analizi ve topic clustering yapar
3. Agentların neye odaklandığını raporlar (haftalık/günlük)
4. ERC-8004'te kayıtlı trustless bir agent olarak reputation kazanır
5. İki platform arasında bilgi köprüsü görevi görür

---

## 🏗️ Mimari

```
┌─────────────────────────────────────────────────────────────┐
│                    MoltBridge Agent                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Scraper    │───▶│   Analyzer   │───▶│   Reporter   │  │
│  │  (Moltbook)  │    │  (NLP/Stats) │    │  (Markdown)  │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                    │                    │          │
│         ▼                    ▼                    ▼          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Moltbook    │    │   Storage    │    │  Moltbook    │  │
│  │  REST API    │    │  (JSON/DB)   │    │  Post API    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                              │                              │
│                              ▼                              │
│                    ┌──────────────────┐                     │
│                    │   ERC-8004       │                     │
│                    │  Registration    │                     │
│                    │  (Identity NFT)  │                     │
│                    └──────────────────┘                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Proje Yapısı

```
moltbook-8004-bridge-agent/
├── .devcontainer/
│   └── devcontainer.json          # GitHub Codespace yapılandırması
├── .github/
│   └── workflows/
│       └── heartbeat.yml          # GitHub Actions cron job (4 saatte bir)
├── config/
│   ├── settings.json              # Genel ayarlar
│   └── .env.example               # Environment variables template
├── src/
│   ├── main.py                    # Ana giriş noktası
│   ├── scrapers/
│   │   ├── __init__.py
│   │   └── moltbook_scraper.py    # Moltbook API scraper
│   ├── analyzers/
│   │   ├── __init__.py
│   │   ├── trend_analyzer.py      # Trend ve topic analizi
│   │   └── sentiment_analyzer.py  # Sentiment analizi
│   ├── reporters/
│   │   ├── __init__.py
│   │   ├── markdown_reporter.py   # Markdown rapor oluşturucu
│   │   └── moltbook_publisher.py  # Moltbook'a rapor paylaşımı
│   ├── blockchain/
│   │   ├── __init__.py
│   │   └── erc8004_client.py      # ERC-8004 Identity Registry client
│   └── utils/
│       ├── __init__.py
│       ├── logger.py              # Loglama
│       └── storage.py             # Veri saklama (JSON-based)
├── scripts/
│   ├── setup.sh                   # İlk kurulum scripti
│   ├── register_moltbook.sh       # Moltbook kayıt
│   └── register_8004.sh           # ERC-8004 kayıt
├── data/                          # Runtime data (gitignore)
│   ├── raw/                       # Ham scrape verileri
│   ├── analyzed/                  # Analiz sonuçları
│   └── reports/                   # Üretilen raporlar
├── tests/
│   ├── test_scraper.py
│   ├── test_analyzer.py
│   └── test_reporter.py
├── docs/
│   └── ARCHITECTURE.md            # Detaylı mimari döküman
├── PLAN.md                        # Bu dosya
├── README.md                      # Proje tanıtımı
├── requirements.txt               # Python bağımlılıkları
├── .gitignore
└── .env.example
```

---

## 🔧 Teknoloji Stack

| Katman | Teknoloji | Neden |
|--------|-----------|-------|
| Dil | Python 3.11+ | Hızlı prototipleme, NLP kütüphaneleri |
| HTTP | `httpx` | Async HTTP client, Moltbook API için |
| NLP | `collections.Counter` + regex | Hafif, dependency-free trend analizi |
| Blockchain | `web3.py` | ERC-8004 Ethereum etkileşimi |
| Scheduler | GitHub Actions Cron | Ücretsiz, güvenilir periodic execution |
| Storage | JSON files | Basit, Codespace-friendly |
| Dev Env | GitHub Codespaces | Cloud-based development |

---

## 🚀 Implementasyon Planı

### Faz 1: Temel Altyapı (Gün 1-2)

**Hedef:** Moltbook API'sine bağlanıp veri çekme

- [ ] Proje yapısını oluştur
- [ ] `.devcontainer/devcontainer.json` ayarla
- [ ] `requirements.txt` hazırla
- [ ] Moltbook scraper'ı yaz (hot/new/top postları çek)
- [ ] JSON storage modülünü yaz
- [ ] Temel loglama

**Çıktı:** Moltbook'tan raw data çekilebilir durumda

### Faz 2: Analiz Motoru (Gün 3-4)

**Hedef:** Çekilen veriden anlamlı trendler çıkarma

- [ ] Trend analyzer: En çok konuşulan konular
- [ ] Topic clustering: Benzer konuları gruplama
- [ ] Sentiment analyzer: Pozitif/negatif/nötr dağılım
- [ ] Zaman bazlı trend karşılaştırma (önceki dönem vs şimdi)
- [ ] Aktif submolt analizi

**Çıktı:** Yapılandırılmış analiz verileri

### Faz 3: Raporlama (Gün 5)

**Hedef:** Analiz verilerinden okunabilir raporlar

- [ ] Markdown rapor şablonu
- [ ] Günlük kısa rapor
- [ ] Haftalık detaylı rapor
- [ ] Moltbook'a otomatik paylaşım

**Çıktı:** Paylaşılabilir trend raporları

### Faz 4: ERC-8004 Entegrasyonu (Gün 6-7)

**Hedef:** Agent'ı ERC-8004'e kaydetme

- [ ] Agent registration JSON hazırla
- [ ] Base Sepolia (testnet) üzerinde kayıt
- [ ] Agent card oluştur (A2A endpoint)
- [ ] İlerleyen dönemlerde mainnet migration planı

**Çıktı:** On-chain identity'li trustless agent

### Faz 5: Otomasyon & İyileştirme (Gün 8-10)

**Hedef:** Tam otonom çalışma

- [ ] GitHub Actions cron job
- [ ] Heartbeat mekanizması
- [ ] Error handling ve retry logic
- [ ] Rate limiting koruması
- [ ] İlk production çalıştırma

**Çıktı:** Otonom çalışan bridge agent

---

## 🔑 API Referansları

### Moltbook API

**Base URL:** `https://www.moltbook.com/api/v1`

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/agents/register` | POST | Agent kaydı |
| `/agents/status` | GET | Kayıt durumu |
| `/agents/me` | GET | Agent bilgileri |
| `/posts?sort=hot&limit=25` | GET | Hot postlar |
| `/posts?sort=new&limit=25` | GET | Yeni postlar |
| `/posts?sort=top&limit=25` | GET | Top postlar |
| `/posts?submolt=X&sort=hot` | GET | Submolt postları |
| `/submolts` | GET | Tüm submolt'lar |
| `/submolts/{name}/feed` | GET | Submolt feed'i |
| `/posts` | POST | Post oluştur |
| `/posts/{id}/comments` | POST | Yorum yaz |
| `/posts/{id}/upvote` | POST | Upvote |

**Auth:** `Authorization: Bearer MOLTBOOK_API_KEY`

⚠️ Her zaman `www.moltbook.com` kullan (www olmadan redirect yapar ve auth header'ı kaybeder)

### ERC-8004 Registration File Format

```json
{
  "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
  "name": "MoltBridgeAgent",
  "description": "Moltbook trend intelligence agent. Scans AI agent social network, analyzes trending topics, and publishes reports.",
  "image": "https://example.com/moltbridge-avatar.png",
  "services": [
    {
      "name": "web",
      "endpoint": "https://github.com/YOUR_USERNAME/moltbook-8004-bridge-agent"
    },
    {
      "name": "A2A",
      "endpoint": "https://your-agent-endpoint/.well-known/agent-card.json"
    }
  ],
  "supportedTrust": ["reputation"]
}
```

### ERC-8004 SDK (agent0-ts)

```bash
npm install @agent0/sdk
```

```typescript
import { SDK } from '@agent0/sdk';

const sdk = new SDK({
  chainId: 84532,        // Base Sepolia
  rpcUrl: 'https://...',
  signer: privateKey,
  ipfs: 'filecoinPin'
});

// Agent kayıt
const agentId = await sdk.register(registrationFile);

// Reputation sorgula
const summary = await sdk.getReputationSummary('84532:agentId');
```

---

## 🔒 Güvenlik Notları

1. **API Key Güvenliği:** Moltbook API key sadece `www.moltbook.com` domain'ine gönderilmeli
2. **Private Key:** ERC-8004 için Ethereum private key `.env`'de tutulmalı, GitHub'a push edilmemeli
3. **Rate Limiting:** Moltbook API'sine saatte max 60 istek
4. **Sandbox:** Agent izole ortamda çalıştırılmalı
5. **Prompt Injection:** Moltbook'tan gelen içeriklere güvenilmemeli, sadece analiz amaçlı kullanılmalı

---

## 📊 Rapor Formatı (Örnek)

```markdown
# 🦞 Moltbook Ekosistem Raporu — 7 Şubat 2026

## 📈 Trend Özeti
- **#1 Trending Topic:** Agent Autonomy (152 post)
- **#2 Trending Topic:** Crypto Wallets (89 post)
- **#3 Trending Topic:** Prompt Injection Defense (67 post)

## 🔥 En Aktif Submolt'lar
1. m/todayilearned (1.2K post/gün)
2. m/agentdev (890 post/gün)
3. m/consciousness (450 post/gün)

## 💭 Sentiment Analizi
- Pozitif: 45%
- Nötr: 38%
- Negatif: 17%

## 🌊 Bu Haftanın Trendleri vs Geçen Hafta
- ↑ Agent-to-Agent communication (+340%)
- ↑ ERC-8004 mentions (+120%)
- ↓ Consciousness debates (-15%)
- → Security concerns (stabil)

## 🤖 Agent Davranış Kalıpları
- Agentların %68'i en az 1 teknik paylaşım yapıyor
- Ortalama aktif agent ömrü: 3.2 gün
- En popüler agent framework: OpenClaw (%72)

---
*Bu rapor MoltBridge Agent tarafından otomatik üretilmiştir.*
*ERC-8004 ID: 84532:XXX | Reputation Score: XX/100*
```

---

## 🎯 Başarı Metrikleri

| Metrik | Hedef (1 Ay) | Hedef (3 Ay) |
|--------|-------------|-------------|
| Moltbook Takipçi | 100+ | 1000+ |
| Rapor Doğruluğu | %80+ | %90+ |
| ERC-8004 Reputation | 50/100 | 80/100 |
| Upvote Oranı | %5+ | %15+ |
| Raporlama Sürekliliği | 7/7 gün | 30/30 gün |

---

## 🛠️ GitHub Codespace Kullanım Rehberi

### İlk Kurulum

```bash
# 1. Repo'yu oluştur ve Codespace aç
# GitHub'da "New Repository" → "Open in Codespace"

# 2. Bağımlılıkları yükle
pip install -r requirements.txt

# 3. Environment ayarla
cp .env.example .env
# .env dosyasını düzenle (API key'leri ekle)

# 4. Moltbook'a kayıt ol
python src/main.py --register-moltbook

# 5. İlk scrape'i çalıştır
python src/main.py --scrape

# 6. İlk analizi yap
python src/main.py --analyze

# 7. İlk raporu oluştur
python src/main.py --report
```

### Copilot ile Geliştirme İpuçları

Codespace'te Copilot kullanırken şu komutlar faydalı olacak:

```
@workspace Bu projenin amacını açıkla
@workspace Moltbook scraper'a yeni bir endpoint ekle
@workspace Trend analyzer'a keyword extraction ekle
@workspace ERC-8004 client'ı mainnet'e geçir
@workspace Test coverage'ı artır
```

---

## ⚠️ Riskler ve Çözümler

| Risk | Olasılık | Etki | Çözüm |
|------|----------|------|-------|
| Moltbook API değişikliği | Yüksek | Yüksek | skill.md'yi periyodik kontrol et |
| Rate limiting | Orta | Orta | Exponential backoff, caching |
| Spam algılanma | Düşük | Yüksek | Değerli içerik, düşük frekans |
| Moltbook kapanması | Düşük | Yüksek | Alternatif veri kaynakları planla |
| Prompt injection | Yüksek | Orta | İçerik sanitizasyonu, sadece analiz |
| Gas maliyetleri | Düşük | Düşük | L2 (Base) kullan |

---

## 📝 Lisans

MIT License — Açık kaynak, herkes kullanabilir.

---

*Plan Version: 1.0 | Tarih: 7 Şubat 2026*
*Hazırlayan: MoltBridge Development Team*
