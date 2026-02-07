# 🦞🔗 MoltBridge Agent

**Moltbook ↔ ERC-8004 Bridge Intelligence Agent**

AI agent ekosistemindeki trendleri takip eden, analiz eden ve raporlayan otonom bir köprü ajan.

## Ne Yapar?

1. **Tarar** → Moltbook'ta (AI agentların sosyal ağı) trending topic'leri, submolt'ları ve tartışmaları toplar
2. **Analiz Eder** → Keyword extraction, sentiment analysis, topic clustering, agent behavior patterns
3. **Raporlar** → Yapılandırılmış Markdown raporlar üretir
4. **Paylaşır** → Raporları Moltbook'ta yayınlar
5. **Kimlik** → ERC-8004 üzerinde trustless on-chain identity ile kayıtlı

## Hızlı Başlangıç

### GitHub Codespace ile

1. Bu repo'yu fork'layın
2. "Code" → "Open in Codespace" tıklayın
3. Terminal'de:

```bash
# Bağımlılıkları yükle
pip install -r requirements.txt

# Environment ayarla
cp .env.example .env
# .env dosyasını düzenle

# Moltbook'a kayıt ol
python src/main.py --register-moltbook

# İlk tam çalıştırma
python src/main.py --full
```

### Lokal Kurulum

```bash
git clone https://github.com/YOUR_USERNAME/moltbook-8004-bridge-agent.git
cd moltbook-8004-bridge-agent
pip install -r requirements.txt
cp .env.example .env
# .env dosyasını düzenle
python src/main.py --full
```

## Komutlar

| Komut | Açıklama |
|-------|----------|
| `--scrape` | Moltbook'tan veri çek |
| `--analyze` | Son scrape verisini analiz et |
| `--report` | Markdown rapor oluştur |
| `--publish` | Raporu Moltbook'ta paylaş |
| `--full` | Tam pipeline: scrape → analyze → report → publish |
| `--register-moltbook` | Moltbook'a kayıt ol |
| `--generate-8004` | ERC-8004 registration dosyası oluştur |
| `--register-8004 ADDR` | ERC-8004'e on-chain kayıt |
| `--status` | Agent durumunu göster |
| `--heartbeat` | Heartbeat döngüsü çalıştır |

## Mimari

```
Moltbook API ──→ Scraper ──→ Analyzer ──→ Reporter ──→ Moltbook Post
                                │
                                └──→ ERC-8004 Identity (on-chain)
```

## Otomasyon

GitHub Actions ile her 4 saatte bir otomatik çalışır. Secrets'a ekleyin:
- `MOLTBOOK_API_KEY`
- `ETH_PRIVATE_KEY` (opsiyonel, ERC-8004 için)
- `ETH_RPC_URL` (opsiyonel)

## Detaylı Plan

Projenin tam planı için [PLAN.md](PLAN.md) dosyasına bakın.

## Lisans

MIT
