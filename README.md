# Cashierless API

Backend API for autonomous retail stores with AI-powered product recognition and payment processing. Built with FastAPI, Ollama (Qwen3.5), SQLite, and Forte Bank integration.

## Features

- 📷 **AI Product Recognition** - Uses Ollama with Qwen3.5 model to identify products from images (local, no API costs)
- 💳 **Payment Processing** - Integration with Forte Bank HPP (Hosted Payment Page) for secure payments
- 🔍 **Smart Search** - LIKE-based product search in SQLite database
- 🌐 **RESTful API** - Clean and documented endpoints
- 🚀 **Async/IO** - Built with aiosqlite for high performance
- 📱 **Mobile-Ready** - Designed for mobile app integration with polling and callbacks
- 💰 **Cost-Effective** - Local AI inference with Ollama, no external API costs for recognition

## Architecture

```
mobile-app-api/
├── main.py                 # FastAPI application entry point
├── database.py             # SQLite connection, schema init & product search
├── routers/
│   ├── recognize.py        # Product recognition endpoint
│   ├── checkout.py         # Checkout, payment & status endpoints
│   └── products.py          # Products list endpoint
├── services/
│   ├── ollama_service.py   # Ollama Qwen3.5 integration (local AI)
│   ├── openai_service.py   # OpenAI GPT-4o Vision integration (alternative)
│   └── forte_service.py    # Forte Bank payment integration
├── .env.example            # Environment variables template
├── .gitignore              # Git ignore rules
├── requirements.txt         # Python dependencies
└── LICENSE                 # License file
```

## Tech Stack

- **Framework**: FastAPI 0.133.1
- **AI**: Ollama with Qwen3.5:4b model (local inference)
- **Database**: SQLite with aiosqlite
- **Payment**: Forte Bank API (HPP - Hosted Payment Page)
- **HTTP Client**: httpx 0.28.1
- **Image Processing**: Pillow 12.1.1

## Getting Started

### Prerequisites

- Python 3.11+
- **Ollama** installed and running (for local AI inference)
- Forte Bank API credentials (for production)

### Installing Ollama

Before running the application, you need to install Ollama and download the Qwen3.5 model:

**macOS/Linux:**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull the Qwen3.5 model
ollama pull qwen3.5:4b

# Start Ollama service (usually starts automatically)
ollama serve
```

**Windows:**
Download and install from [ollama.com](https://ollama.com/download), then run:
```powershell
ollama pull qwen3.5:4b
```

Verify Ollama is running:
```bash
curl http://localhost:11434/api/tags
```

### Installation

#### 1. Clone the repository

```bash
git clone <repository-url>
cd mobile-app-api
```

#### 2. Create a virtual environment (recommended)

**Windows (CMD):**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- fastapi==0.133.1
- aiosqlite==0.22.1
- openai==2.24.0 (used for Ollama compatibility)
- uvicorn==0.41.0
- pydantic==2.12.5
- python-dotenv==1.2.1
- httpx==0.28.1
- python-multipart==0.0.22
- pillow==12.1.1

#### 4. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Optional: OpenAI API key (if you want to use OpenAI instead of Ollama)
OPENAI_API_KEY=sk-your-openai-key

# SQLite database path (default: shop.db)
DB_PATH=shop.db

# Forte Bank API settings
FORTE_BASE_URL=https://sandbox.forte.kz/api/v1
FORTE_API_KEY=your_forte_key
FORTE_MERCHANT_ID=your_merchant_id
NGROK_URL=https://xxxx.ngrok-free.app
```

### Running the Application

#### Start Ollama (if not running)

In a separate terminal:
```bash
ollama serve
```

#### Development Mode (with auto-reload)

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

#### Production Mode

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### Custom Host and Port

```bash
uvicorn main:app --host 127.0.0.1 --port 8080
```

### First Run

On the first run, the application will automatically:
1. Create the SQLite database file (`shop.db` by default)
2. Initialize the `products` table
3. Populate it with sample products

Sample products included:
- Coca-Cola 1L - 450 ₸
- Lay's Сметана 150г - 350 ₸
- Sprite 0.5L - 320 ₸
- Шоколад Milka 90г - 520 ₸
- Чай Lipton 25 пак - 680 ₸
- Red Bull 250мл - 750 ₸
- Snickers 50г - 280 ₸
- Orbit Spearmint - 250 ₸
- Вода Bonaqua 1L - 200 ₸
- Pringles Original - 890 ₸

## API Endpoints

### Get All Products

```
GET /products
```

Get a list of all products from the database.

**Response:**
```json
{
  "count": 10,
  "products": [
    {
      "id": 1,
      "name": "Coca-Cola 1L",
      "category": "Напитки",
      "description": "Газированный напиток Coca-Cola 1 литр",
      "price": 450.0,
      "image_url": null,
      "barcode": "4870200013834",
      "in_stock": 1,
      "created_at": "2024-01-01 12:00:00"
    },
    ...
  ]
}
```

### Get Product by ID

```
GET /products/{product_id}
```

Get a single product by its ID.

**Response:**
```json
{
  "id": 1,
  "name": "Coca-Cola 1L",
  "category": "Напитки",
  "description": "Газированный напиток Coca-Cola 1 литр",
  "price": 450.0,
  "image_url": null,
  "barcode": "4870200013834",
  "in_stock": 1,
  "created_at": "2024-01-01 12:00:00"
}
```

### Create Product

```
POST /products
```

Create a new product.

**Request Body:**
```json
{
  "name": "Fanta 1L",
  "category": "Напитки",
  "description": "Газированный напиток Fanta 1 литр",
  "price": 450.0,
  "image_url": "https://example.com/fanta.jpg",
  "barcode": "4870200013835",
  "in_stock": 1
}
```

**Response:** Returns the created product (201 Created)

### Update Product

```
PUT /products/{product_id}
```

Update an existing product. Only provided fields will be updated.

**Request Body:**
```json
{
  "name": "Fanta 1.5L",
  "price": 550.0,
  "in_stock": 0
}
```

**Response:** Returns the updated product

### Delete Product

```
DELETE /products/{product_id}
```

Delete a product by ID.

**Response:** 204 No Content

### Health Check

```
GET /health
```

Returns the API status.

**Response:**
```json
{
  "status": "ok"
}
```

### Product Recognition

```
POST /recognize
```

Recognize products from a base64-encoded image using Ollama Qwen3.5 model.

**Request Body:**
```json
{
  "image_base64": "/9j/4AAQSkZJRg..."
}
```

**Response:**
```json
{
  "recognized_items": [
    {
      "product_id": 1,
      "name": "Coca-Cola 1L",
      "price": 450.0,
      "quantity": 1,
      "confidence": 0.95
    }
  ],
  "unrecognized": [],
  "total": 450.0
}
```

### Product Recognition (File Upload)

```
POST /recognize/file
```

Recognize products from an uploaded image file. This endpoint is more convenient for Swagger UI and direct file uploads.

**Request:** Multipart form data with file upload

- **file**: Image file (JPEG, PNG)

**Response:**
```json
{
  "recognized_items": [
    {
      "product_id": 1,
      "name": "Coca-Cola 1L",
      "price": 450.0,
      "quantity": 1,
      "confidence": 0.95
    }
  ],
  "unrecognized": [],
  "total": 450.0
}
```

### Checkout - Create Order

```
POST /checkout/create
```

Create a payment order and get the HPP (Hosted Payment Page) URL.

**Request Body:**
```json
{
  "items": [
    {
      "product_id": 1,
      "name": "Coca-Cola 1L",
      "price": 450.0,
      "quantity": 1
    }
  ],
  "total": 450.0
}
```

**Response:**
```json
{
  "our_order_id": "ORD-A1B2C3D4",
  "hpp_url": "http://localhost:8082/flex?id=123&password=xyz",
  "total": 450.0
}
```

### Checkout - Payment Callback

```
GET /checkout/callback?our_order_id=ORD-xxx&ID=<forte_id>&STATUS=FullyPaid
```

Callback endpoint called by Forte after payment completion. Returns an HTML page.

**Response:** HTML page showing success or failure message.

### Checkout - Get Order Status

```
GET /checkout/status/{our_order_id}
```

Poll endpoint for mobile app to check payment status.

**Response:**
```json
{
  "our_order_id": "ORD-A1B2C3D4",
  "status": "paid",
  "forte_order_id": 123,
  "items": [...],
  "total": 450.0
}
```

Status values: `pending` | `paid` | `failed`

## How It Works

### Recognition Flow

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Mobile    │      │   FastAPI    │      │   Ollama    │
│   App       │─────▶│   Backend    │─────▶│   Qwen3.5   │
└─────────────┘      └──────────────┘      └─────────────┘
                            │                      │
                            │                      ▼
                            │              ┌──────────────┐
                            │              │   Identify   │
                            │              │   Products   │
                            │              └──────────────┘
                            │                      │
                            │                      ▼
                            │              ┌──────────────┐
                            │              │   Function   │
                            │              │   Calling    │
                            │              └──────────────┘
                            │                      │
                            ▼                      ▼
                     ┌──────────────┐      ┌──────────────┐
                     │   SQLite DB  │◀─────│   Search     │
                     │              │      │   Products   │
                     └──────────────┘      └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │   Return     │
                     │   Results    │
                     └──────────────┘
```

1. **Image Upload**: Client sends base64-encoded image to `/recognize`
2. **Vision Analysis**: Ollama Qwen3.5 analyzes the image and identifies visible products
3. **Function Calling**: Qwen3.5 calls `search_products` tool with product names
4. **Database Search**: LIKE search in SQLite database
5. **Result Compilation**: Qwen3.5 formats results with confidence scores and quantities

### Payment Flow

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Mobile    │      │   FastAPI    │      │   Forte     │
│   App       │─────▶│   Backend    │─────▶│   Bank      │
└─────────────┘      └──────────────┘      └─────────────┘
      │                     │                      │
      │  POST /checkout     │  POST /order         │
      │  /create            │                      │
      │◀────────────────────┘                      │
      │  hpp_url            │                      │
      │                     │                      │
      │  Open HPP in browser │                      │
      │                     │                      │
      │                     │◀──────────────────────┤
      │                     │  Callback (GET)       │
      │                     │  /checkout/callback   │
      │                     │                      │
      │  Poll status        │  GET /order/{id}      │
      │  /checkout/status   │                      │
      │◀────────────────────┘                      │
```

1. **Create Order**: Client sends cart items to `/checkout/create`
2. **Forte Order**: Backend creates order in Forte and gets HPP URL
3. **Open Payment Page**: User opens HPP URL in browser to complete payment
4. **Payment Callback**: Forte redirects to `/checkout/callback` after payment
5. **Status Polling**: Mobile app polls `/checkout/status/{order_id}` to get final status

## Database Schema

### Products Table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| name | TEXT | Product name |
| category | TEXT | Product category |
| description | TEXT | Product description |
| price | REAL | Price in KZT |
| image_url | TEXT | Product image URL |
| barcode | TEXT | Barcode |
| in_stock | INTEGER | Stock availability (1 = in stock) |
| created_at | TEXT | Creation timestamp |

## API Documentation

Interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| OPENAI_API_KEY | OpenAI API key (optional, for OpenAI mode) | No | - |
| DB_PATH | SQLite database file path | No | shop.db |
| FORTE_BASE_URL | Forte Bank API base URL | No | https://sandbox.forte.kz/api/v1 |
| FORTE_API_KEY | Forte API key | No | - |
| FORTE_MERCHANT_ID | Forte merchant ID | No | - |
| NGROK_URL | Ngrok URL for callbacks | No | - |

## Development

### Running Tests

```bash
pytest
```

### Code Style

This project follows PEP 8 style guidelines. Use `black` for code formatting:

```bash
pip install black
black .
```

### Switching Between Ollama and OpenAI

The project supports both Ollama (local) and OpenAI (cloud) for product recognition.

**Using Ollama (default):**
- Ensure Ollama is running: `ollama serve`
- The service is already configured in `routers/recognize.py`

**Using OpenAI:**
1. Set your `OPENAI_API_KEY` in `.env`
2. Uncomment the import in `routers/recognize.py`:
   ```python
   from services.openai_service import recognize_from_image
   ```
3. Change the function call:
   ```python
   result = await recognize_from_image(req.image_base64)
   ```

## Troubleshooting

### Database not created

The database is automatically created on first run. If you encounter issues:

1. Delete `shop.db` if it exists
2. Restart the application

### Ollama connection issues

- Ensure Ollama is running: `ollama serve`
- Verify Ollama is accessible: `curl http://localhost:11434/api/tags`
- Check that the model is downloaded: `ollama list`
- Pull the model if needed: `ollama pull qwen3.5:4b`

### OpenAI API errors

- Verify your `OPENAI_API_KEY` is correct
- Check your OpenAI account has sufficient credits
- Ensure GPT-4o Vision model is available in your account

### Forte Bank connection issues

- Verify `FORTE_BASE_URL` is correct
- Check API key and merchant ID
- Ensure Forte Bank service is running (for local development)
- Use ngrok for local development callbacks

### Port already in use

If port 8000 is already in use, use a different port:

```bash
uvicorn main:app --port 8080
```

## License

See [`LICENSE`](LICENSE:1) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
