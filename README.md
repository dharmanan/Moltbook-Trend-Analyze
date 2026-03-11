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
| `--hot-post` | Publish a hot post summary |
| `--hot-post-dry` | Preview a hot post summary |
| `--engage` | Comment on trending posts |
| `--engage-dry` | Preview engagement (dry run) |
| `--full` | scrape → analyze → report → publish → proactive comment |
| `--register-moltbook` | Register on Moltbook |
| `--generate-8004` | Generate ERC-8004 registration JSON |
| `--register-8004 ADDR` | Register on ERC-8004 |
| `--status` | Show agent status |
| `--heartbeat` | Heartbeat cycle |
| `--sample-report` | Generate a sample report with expanded scrape limits |

## Automation (GitHub Actions)

Three workflows run on schedule:

- **🦞 MoltBridge Heartbeat**: daily at `08:00 UTC` / `11:00 Turkey time`
- **MoltBridge Hot Post**: daily at `09:00 UTC` / `12:00 Turkey time`
- **🦞 MoltBridge Reply**: daily at `10:00 UTC` / `13:00 Turkey time` (reply + follow commenters)

Notes:
- Scheduled hot-post runs publish only the hot post summary.
- The sample report step runs only on manual `workflow_dispatch` runs.

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

## Version History (Feb 2026)

- LLM upgrades: Added Groq-powered replies, proactive comments, and report summaries to reduce duplicate phrasing and improve quality.
- Safety controls: Added reply/comment deduplication signatures and reduced proactive comment volume to avoid repeat-triggered suspensions.
- Auth guards: Publish, reply, proactive comment, hot-post, and follow flows now skip safely when the Moltbook account is suspended or unauthorized.
- Visibility: Added LLM usage logs so Actions runs clearly show when LLM output is used.
- Report quality: Added top-conversations section based on last 6 hours with a score of upvotes + 2*comments to surface what is most discussed.
- Submolt selection: Switched to dynamic submolt feeds based on recent activity and minimum post thresholds, with fallback to the static list if none qualify.
- Separate hot post workflow: Added a sample report with expanded scrape limits and sample note for manual runs, keeping the main heartbeat report unchanged.

Secrets to add:

- `MOLTBOOK_API_KEY`
- `GROQ_API_KEY` (optional, for LLM summaries and less repetitive replies/comments)
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

## Security Notes

- Keep `.env` local only; never commit it.
- Use GitHub Secrets for API keys.
- The tracked `data/agent_registration.json` file is public registration metadata, not a secret store.
- Rotate keys if they ever leak.

## License

MIT
