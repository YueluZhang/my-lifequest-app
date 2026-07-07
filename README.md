# LifeQuest: An RPG-Style Personal Life Management Multi-Agent System
> *Gamifying career search, scheduling, and budgeting with a secure, multi-agent AI assistant.*

*   **GitHub Repository**: [YueluZhang/my-lifequest-app](https://github.com/YueluZhang/my-lifequest-app)
*   **Live Frontend UI**: [my-lifequest-app.web.app](https://my-lifequest-app.web.app)
*   **Live Backend API**: [Cloud Run service](https://temp-lifequest-213291527780.us-east1.run.app)

## 1. Problem Statement
International students and early-career professionals face a highly complex set of stressors: managing visa and university deadlines, keeping track of tight personal budgets, and executing job application strategies. Each of these domains is critical, yet tracking them across separate spreadsheets and tools is overwhelming. When these stressors overlap—such as a major visa deadline coinciding with a low financial budget—stress compounds. There is a need for a unified, engaging, and secure assistant that can coordinate across these domains, highlight overlapping urgencies, and safeguard sensitive personal data.

## 2. Solution Overview
**LifeQuest** gamifies personal management into an RPG. The user acts as the player, whose life metrics are represented as **HP** (vitality/stress), **Gold** (financial health), **XP** (career progress), and **Quest Log** (active tasks). By wrapping real tasks (deadlines, budget transactions, job hunt activities) in RPG concepts, the system makes personal management engaging.

## 3. Project Structure
```
my-lifequest-app/
├── app/
│   ├── agent.py               # QuestMasterAgent and sub-agents (JobBoss, GoldKeeper, TimeGuardian)
│   └── tools.py               # MCP Filesystem toolset, Fernet encryption, and callback handlers
├── tests/                     # Unit, integration, and evaluation tests
├── game_ui.html               # Gamified HTML/CSS/JS frontend client
├── writeup.md                 # Kaggle project writeup
├── pyproject.toml             # Dependencies (managed via uv)
└── save.json                  # Local encrypted game state save file (Git-ignored)
```

## 4. Setup & Execution

### Prerequisites
Before you begin, ensure you have:
- **uv**: Python package manager - [Install](https://docs.astral.sh/uv/getting-started/installation/)
- **agents-cli**: Agents CLI - Install with `uv tool install google-agents-cli`

### Installation Steps

1.  **Install dependencies**:
    ```bash
    uvx google-agents-cli setup
    agents-cli install
    ```
2.  **Configure the Data Security Key**:
    This project uses at-rest Fernet symmetric encryption to secure your local `save.json` file. You must generate a key and save it to your `.env` file before running:
    ```bash
    # Generate a new Fernet key
    uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ```
    Copy the output and append it to your `.env` file:
    ```env
    SAVE_ENCRYPTION_KEY=your_generated_key_here
    GOOGLE_API_KEY=your_google_api_key_here
    ```
3.  **Run the local server**:
    ```bash
    agents-cli playground
    ```
4.  **Open the client**:
    Open the local `game_ui.html` file in your default browser to start playing!

## 5. Development Commands

| Command | Description |
|---|---|
| `agents-cli install` | Install dependencies using uv |
| `agents-cli playground` | Launch local development environment (defaults to port `8080`) |
| `agents-cli lint` | Run code quality checks |
| `agents-cli eval` | Evaluate agent behavior (generate, grade, analyze, etc.) |
| `uv run pytest tests/unit tests/integration` | Run unit and integration tests |

## 6. Deployment

The backend is deployed to Google Cloud Run and the frontend is hosted on Firebase Hosting:
* [Backend API](https://temp-lifequest-213291527780.us-east1.run.app)
* [Frontend UI (Live Demo)](https://my-lifequest-app.web.app)

To deploy updates:
```bash
gcloud config set project my-lifequest-app
agents-cli deploy
```
