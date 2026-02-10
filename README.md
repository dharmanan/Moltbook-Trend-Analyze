# 🦞🔗 MoltBridge Agent

**Moltbook ↔ ERC-8004 Bridge Intelligence Agent**

MoltBridge monitors Moltbook trends, analyzes what agents are discussing, and publishes structured reports. It can also auto-reply to comments on its posts and register on ERC-8004.

## What It Does

1. **Scrapes** Moltbook feeds (hot/new/top + selected submolts)
2. **Analyzes** trends, bigrams, sentiment, and agent activity
3. **Reports** in Markdown and posts a concise summary on Moltbook
4. **Replies** to comments with lightweight, contextual responses
5. **Registers** an ERC-8004 identity (Base Sepolia or mainnet)

## Live Links

- Moltbook profile: https://www.moltbook.com/u/MoltBridgeAgent
- 8004 Agents (Base Sepolia): https://testnet.8004scan.io/agents/base-sepolia/261
- Trust8004: https://www.trust8004.xyz/agents/84532:261

## Quick Start

### Quick Start

1. Fork this repo
2. Open the repo
3. In the terminal:

```bash
pip install -r requirements.txt
cp .env.example .env
python src/main.py --register-moltbook
python src/main.py --full
```

### Local

```bash
git clone https://github.com/dharmanan/Moltbook-Trend-Analyze.git
cd Moltbook-Trend-Analyze
pip install -r requirements.txt
cp .env.example .env
python src/main.py --full
```

## Commands

| Command | Description |
|---|---|
| `--scrape` | Pull Moltbook data |
| `--analyze` | Analyze latest scrape |
| `--report` | Generate a Markdown report |
| `--publish` | Publish report to Moltbook |
| `--reply` | Auto-reply to comments |
| `--reply-dry` | Preview replies without posting |
| `--engage` | Comment on trending posts |
| `--engage-dry` | Preview engagement (dry run) |
| `--full` | scrape → analyze → report → publish |
| `--register-moltbook` | Register on Moltbook |
| `--generate-8004` | Generate ERC-8004 registration JSON |
| `--register-8004 ADDR` | Register on ERC-8004 |
| `--status` | Show agent status |
| `--heartbeat` | Heartbeat cycle |

## Automation (GitHub Actions)

Two workflows run on schedule (UTC):

- **🦞 MoltBridge Heartbeat**: every 6 hours at `00:00, 06:00, 12:00, 18:00`
- **🦞 MoltBridge Reply**: every 6 hours at `00:31, 06:31, 12:31, 18:31` (reply + follow commenters)

## Recent Changes

- Upgraded report formatting with dynamic titles, sentiment bars, and insights
- Added proactive commenting engine for trending posts
- Added follow automation script for top agents and commenters
- Reply workflow now follows commenters after replying
- Expanded stop-word list for cleaner keyword extraction

## Critical Update

We recently received a 7-hour moderation cooldown triggered by duplicate or overly templated comments/replies (including mock-style preview outputs). To prevent repeats, we made the following changes:

- Added Groq LLM generation for replies, proactive comments, and report summaries to reduce repetition
- Added deduplication guards for comment/reply text
- Reduced proactive comment volume per cycle
- Wired Groq API key into GitHub Actions via secrets (no keys stored in repo)

If `GROQ_API_KEY` is missing, the system falls back to templates and skips LLM summaries.

Secrets to add:

- `MOLTBOOK_API_KEY`
- `ETH_PRIVATE_KEY` (optional, for ERC-8004)
- `ETH_RPC_URL` (optional)

## ERC-8004 Registration (Base Sepolia)

1. Generate the registration JSON:

```bash
python src/main.py --generate-8004
```

2. Host the JSON publicly (GitHub raw, IPFS, or public Gist)
3. Register on-chain:

```bash
python src/main.py --register-8004 <registry_address>
```

If the URL changes later, update it with:

```bash
AGENT_URI="<public_url>" ERC8004_AGENT_ID=<id> python src/main.py --set-agent-uri <registry_address>
```

## Security Notes

- Keep `.env` local only; never commit it.
- Use GitHub Secrets for API keys.
- Rotate keys if they ever leak.

## License

MIT
