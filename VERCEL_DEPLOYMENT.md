# Vercel Deployment Guide

## Prerequisites

1. **Vercel Account**: Sign up at https://vercel.com
2. **PostgreSQL Database with pgvector**: Use Vercel Postgres, Neon, Supabase, or any PostgreSQL provider
3. **Node.js 20+** and **Python 3.12** for local development

## Environment Variables

Set these in the Vercel dashboard under Settings > Environment Variables:

### Required
- DATABASE_URL: PostgreSQL connection string (e.g., postgresql+psycopg://user:pass@host:5432/dbname)
- CORS_ORIGINS: JSON array of allowed origins (e.g., ["https://your-app.vercel.app"])
- JWT_SECRET_KEY: Strong secret for JWT tokens
- APP_ENV: Set to production

### Optional
- STORAGE_ROOT: Storage path (default: /tmp/storage on Vercel)
- EMBEDDING_PROVIDER: astembed (default)
- EMBEDDING_MODEL: BAAI/bge-small-en-v1.5 (default)
- PROCESSING_INLINE: 	rue (recommended for serverless)
- LOG_LEVEL: INFO (default)

## Database Setup

1. Create a PostgreSQL database with pgvector extension
2. Run migrations: lembic upgrade head
3. Seed demo data (optional): python scripts/seed.py

## Deployment Steps

### 1. Install Vercel CLI
`ash
npm i -g vercel
`

### 2. Login to Vercel
`ash
vercel login
`

### 3. Deploy
`ash
vercel --prod
`

### 4. Set Environment Variables
`ash
vercel env add DATABASE_URL
vercel env add CORS_ORIGINS
vercel env add JWT_SECRET_KEY
vercel env add APP_ENV
`

## Important Notes

### Serverless Limitations
- **Timeout**: Vercel serverless functions have a 60s max timeout on Pro plan
- **Document Processing**: Large documents may exceed timeout. Consider:
  - Using smaller documents
  - Implementing async processing with external workers
  - Using Vercel's background functions (if available)

### Database
- Use a managed PostgreSQL provider (Vercel Postgres, Neon, Supabase)
- Ensure pgvector extension is enabled
- Set connection pooling appropriately

### File Storage
- Vercel's filesystem is read-only except /tmp
- For persistent storage, use Vercel Blob, S3, or similar
- Set STORAGE_ROOT=/tmp/storage for temporary files

### Embeddings
- The fastembed model is downloaded on first use
- Cold starts may take 10-30 seconds for model loading
- Consider using a smaller model for faster cold starts

## Local Development

`ash
# Backend
cd backend
python -m uvicorn app.main:app --port 8000

# Frontend
cd frontend
npm run dev

# Tests
cd backend
python -m pytest tests/
`

## Troubleshooting

### Cold Start Issues
- First request may take 10-30s due to model loading
- Consider implementing a warm-up endpoint

### Database Connection Issues
- Ensure pgvector extension is installed
- Check connection string format
- Verify firewall allows Vercel IPs

### File Upload Issues
- Ensure STORAGE_ROOT is set to /tmp/storage
- Check file size limits
- Verify allowed MIME types
