# Medical Services Chatbot

A microservice-based chatbot system that answers questions about medical services for Israeli health funds (Maccabi, Meuhedet, and Clalit) based on user-specific information.

## Features

- **Stateless Microservice Architecture**: Built with FastAPI, handles multiple concurrent users
- **Two-Phase Interaction**:
  - User Information Collection: Collects personal details through natural conversation
  - Q&A Phase: Answers questions based on user's HMO and membership tier
- **Multi-language Support**: Hebrew and English
- **Hybrid Retrieval System**: Combines keyword matching with semantic search using Azure OpenAI embeddings
- **Real-time Chat Interface**: Streamlit-based frontend with RTL support for Hebrew
- **Comprehensive Knowledge Base**: Covers dental, optometry, alternative medicine, communication clinics, pregnancy services, and health workshops

## Architecture

```
medical-services-chatbot/
├── app.py                  # FastAPI backend service
├── frontend.py             # Streamlit chat interface
├── README.md               # Project documentation
├── requirements.txt        # Dependencies
├── .env.example            # Environment variables template
├── services/               # Core backend services
│   ├── azure_client.py     # Azure OpenAI client
│   ├── embedding_client.py # Azure embeddings client
│   ├── hybrid_retriever.py # Semantic + keyword retriever
│   ├── knowledge_base.py   # HTML parsing and extraction
│   ├── prompts.py          # Prompt templates
│   ├── router.py           # Main chat routing logic
│   └── validators.py       # Input validation
├── utils/                  # Shared utilities
│   ├── i18n.py             # Language detection
│   └── logging_config.py   # Logging with PII masking
├── data/                   # Generated knowledge base index
│   └── kb_index.npz
├── phase2_data/            # Raw HTML knowledge base files
│   ├── alternative_services.html
│   ├── communication_clinic_services.html
│   ├── dentel_services.html
│   ├── optometry_services.html
│   ├── pragrency_services.html
│   └── workshops_services.html
└── scripts/                # Utility scripts
    └── build_kb_index.py   # Knowledge base indexing script
```

## Prerequisites

- Python 3.10+
- Azure OpenAI account with:
  - GPT-4o deployment
  - text-embedding-ada-002 deployment

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yairayalon/medical-services-chatbot.git
   cd medical-services-chatbot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your Azure OpenAI credentials
   ```

4. **Build the knowledge base index**
   ```bash
   python -m scripts.build_kb_index
   ```
   This will create embeddings for all the medical services data and save them to `./data/kb_index.npz`.

## Environment Variables

Copy `.env.example` to `.env` and fill in your Azure OpenAI credentials:

- `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint URL
- `AZURE_OPENAI_KEY`: Your Azure OpenAI API key
- `AZURE_OPENAI_DEPLOYMENT_NAME`: Your GPT-4o deployment name
- `AZURE_OPENAI_EMBEDDINGS_ENDPOINT`: Your Azure OpenAI embeddings endpoint
- `AZURE_OPENAI_EMBEDDINGS_KEY`: Your Azure OpenAI embeddings API key
- `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT`: Your text-embedding-ada-002 deployment name

## Usage

### Start the Backend Service

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` with automatic documentation at `http://localhost:8000/docs`.

### Start the Frontend

In a separate terminal:

```bash
cd medical-services-chatbot
streamlit run frontend.py --server.port 8501
```

Access the chat interface at `http://localhost:8501`.

## User Information Collected

The system collects the following information:

- **Personal Details**: First name, last name, ID number (9 digits)
- **Demographics**: Gender, age (0-120)
- **Insurance**: HMO name (מכבי/מאוחדת/כללית), HMO card number (9 digits)
- **Membership**: Insurance tier (זהב/כסף/ארד)

All information is validated and normalized automatically.

## Knowledge Base

The system includes comprehensive data about:

- **Dental Services** (`dentel_services.html`): Checkups, fillings, root canals, crowns, orthodontics
- **Optometry** (`optometry_services.html`): Eye exams, glasses, contact lenses, laser treatments
- **Alternative Medicine** (`alternative_services.html`): Acupuncture, shiatsu, reflexology, naturopathy
- **Communication Clinics** (`communication_clinic_services.html`): Speech therapy, swallowing disorders
- **Pregnancy Services** (`pragrency_services.html`): Prenatal care, genetic screening, childbirth classes
- **Health Workshops** (`workshops_services.html`): Smoking cessation, nutrition, stress management

Each service includes specific benefits and discounts for different membership tiers across all three HMOs.

## Key Components

### Hybrid Retrieval System
- **Keyword Filtering**: Fast pre-filtering using fuzzy string matching
- **Semantic Search**: Azure OpenAI embeddings for contextual understanding
- **Category Gating**: Automatic routing to relevant service categories
- **HMO/Tier Matching**: Prioritizes user-specific information

### State Management
- **Stateless Design**: All user context passed with each request
- **Client-side Storage**: Frontend manages conversation history and user profile
- **Session Isolation**: Multiple users can interact simultaneously

### Multi-language Support
- **Automatic Detection**: Language identified from user input
- **Hebrew RTL**: Full right-to-left support in the UI
- **Contextual Responses**: Appropriate language for user's preference

## Logging and Monitoring

- **PII Masking**: Automatically masks sensitive information (ID numbers, etc.)
- **Request Tracking**: Logs all API interactions
- **Error Handling**: Comprehensive error logging with context
- **Performance Monitoring**: Request timing and success rates

## Development

### Adding New Services

1. Add HTML file to `phase2_data/`
2. Update category mapping in `services/knowledge_base.py`
3. Rebuild the knowledge base index:
   ```bash
   python -m scripts.build_kb_index
   ```

### Customizing Prompts

Edit the system prompts in `services/prompts.py` to modify the chatbot's behavior.

### Validation Rules

Modify validation logic in `services/validators.py` for different input requirements.

## Troubleshooting

### Knowledge Base Issues
- Ensure `build_kb_index.py` runs successfully
- Check that `./data/kb_index.npz` exists
- Verify HTML files are in `phase2_data/`

### Azure OpenAI Connection
- Verify endpoint URLs (no trailing `/openai`)
- Check API key permissions
- Confirm deployment names match your Azure setup

### Frontend Issues
- Check backend is running on port 8000
- Verify CORS settings allow frontend requests
- Clear browser cache if UI doesn't update